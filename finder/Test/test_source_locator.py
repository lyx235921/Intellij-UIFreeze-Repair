import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import openpyxl
import tree_sitter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))
from find_sources import excluded_huawei_symbols, locate_record
from real_stack_input import parse_stack
from source_locator import SourceLocator


class SourceLocatorTest(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)

  def write(self, name, content):
    path = self.root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

  def frame(self, symbol="p.Example.run", file="Example.java", line=999):
    return {"symbol": symbol, "file": file, "line": line}

  def test_java_owner_overload_and_call_site(self):
    self.write("Example.java", 'package p; class Example { void run() { target(); } void run(int n) { other(); } }')
    locator = SourceLocator(self.root)
    ambiguous = locator.locate(self.frame())
    self.assertEqual("AMBIGUOUS", ambiguous["status"])
    result = locator.locate(self.frame(), self.frame("p.Other.target"))
    self.assertEqual("CANDIDATE", result["status"])
    self.assertEqual("ADJACENT_CALLEE_NAME", result["selection_basis"])
    self.assertEqual("JAVA_AST_CALL", result["selected"]["calls"][0]["evidence"])
    self.assertEqual("UNRESOLVED", locator.locate(self.frame("other.Example.run"))["status"])

  def test_comments_strings_and_lambda_do_not_prove_java_call(self):
    self.write("Example.java", 'package p; class Example { void run() { String x = "target()"; '
               '/* target(); */ Runnable r = () -> target(); other(); } }')
    result = SourceLocator(self.root).locate(self.frame())
    self.assertEqual(["other"], [c["name"] for c in result["selected"]["calls"]])

  def test_duplicate_paths_and_test_fixtures(self):
    source = 'package p; class Example { void run() {} }'
    self.write("a/Example.java", source)
    self.write("Test/Example.java", source)
    self.assertEqual("LOCATED", SourceLocator(self.root).locate(self.frame())["status"])
    self.write("b/Example.java", source)
    self.assertEqual("AMBIGUOUS", SourceLocator(self.root).locate(self.frame())["status"])

  def test_inner_class_and_synthetic_frames(self):
    self.write("Example.java", 'package p; class Example { class Inner { void run() {} } }')
    locator = SourceLocator(self.root)
    self.assertEqual("LOCATED", locator.locate(self.frame("p.Example$Inner.run"))["status"])
    for symbol in ["p.Example$run$1.invokeSuspend", "p.Example.lambda$run$0", "p.Example$$Lambda/0x123.run"]:
      self.assertEqual("UNRESOLVED", locator.locate(self.frame(symbol))["status"])

  def test_kotlin_is_explicit_candidate_and_ignores_literals(self):
    self.write("Example.kt", 'package p\nclass Example {\n fun run() {\n val text = "target()"\n removeAll()\n }\n'
               ' fun run(x: Int) { other() }\n}\n')
    locator = SourceLocator(self.root)
    result = locator.locate(self.frame(file="Example.kt"), self.frame("java.awt.Container.removeAll"))
    self.assertEqual("CANDIDATE", result["status"])
    self.assertEqual(5, result["selected"]["calls"][0]["line"])
    self.assertEqual(["removeAll"], [c["name"] for c in result["selected"]["calls"]])

  def test_missing_and_malformed_sources(self):
    self.assertEqual("SOURCE_FILE_NOT_FOUND", SourceLocator(self.root).locate(self.frame())["reason"])
    self.write("Example.java", 'package p; class Example { void run( }')
    result = SourceLocator(self.root).locate(self.frame())
    self.assertEqual("UNRESOLVED", result["status"])
    self.assertEqual("JAVA_PARSE_ERROR", result["source_diagnostics"][0]["reason"])

  def test_receiver_candidates_and_repeated_call_sites_remain_distinct(self):
    self.write("Example.kt", 'package p\nclass Example {\n fun run() {\n removeAll()\n group.removeAll()\n }\n}\n')
    result = SourceLocator(self.root).locate(self.frame(file="Example.kt"))
    calls = result["selected"]["calls"]
    self.assertEqual([None, "group"], [c["receiver"] for c in calls])
    self.assertEqual(["removeAll()", "group.removeAll()"], [c["expression"] for c in calls])

  def test_multiline_receiver_line_starts_at_expression(self):
    self.write("Example.kt", 'package p\nclass Example {\n fun run() {\n group\n ?.removeAll()\n }\n}\n')
    result = SourceLocator(self.root).locate(self.frame(file="Example.kt"))
    call = result["selected"]["calls"][0]
    self.assertEqual(4, call["line"])
    self.assertEqual("group\n ?.removeAll()", call["expression"].replace("\r\n", "\n"))

  def test_source_hash_and_ranges_can_be_checked_by_consumer(self):
    import hashlib
    self.write("Example.java", 'package p;\nclass Example {\n void run() {}\n}\n')
    selected = SourceLocator(self.root).locate(self.frame())["selected"]
    source = (self.root / selected["path"]).read_bytes()
    self.assertEqual(hashlib.sha256(source).hexdigest(), selected["sha256"])
    self.assertEqual(3, selected["start_line"])
    self.assertEqual(3, selected["end_line"])

  def test_pipeline_ids_edges_and_no_repair_decision(self):
    self.write("Example.java", 'package p; class Example { void run() { target(); } }')
    raw = ('cause freeze thread:[AWT-EventQueue-0] RUNNABLE\n'
           'topStack: 0 external.Other.target(Native Method)\n'
           'problemModuleStack: 1 p.Example.run(Example.java:999)')
    record = {"record_id": "workbook-row-2", "sheet": "问题线程堆栈", "row": 2, "occurrences": 3, **parse_stack(raw)}
    result = locate_record(record, SourceLocator(self.root))
    self.assertEqual(["t0"], result["ui_thread_ids"])
    self.assertEqual("NOT_PERFORMED", result["repair_analysis"])
    edge = result["call_edges"][0]
    self.assertEqual("t0:f1", edge["caller_frame_id"])
    self.assertEqual("t0:f0", edge["callee_frame_id"])
    self.assertEqual("CALL_SITE_CANDIDATE", edge["status"])
    self.assertEqual("NOT_PERFORMED", edge["type_resolution"])
    self.assertEqual(raw, result["input"]["raw_stack"])

  def test_cli_jsonl_and_refusal_to_overwrite(self):
    self.write("Example.java", 'package p; class Example { void run() {} }')
    book = openpyxl.Workbook()
    book.active.title = "问题线程堆栈"
    book.active.append(["堆栈出现次数", "问题线程堆栈"])
    book.active.append([1, 'cause freeze thread:[AWT-EventQueue-0] RUNNABLE\n'
                          'topStack: 0 p.Example.run(Example.java:1)\n'
                          'problemModuleStack: 0 p.Example.run(Example.java:1)'])
    book.active.append([1, '[worker] WAITING\n0 com.huawei.snap.Task.run(Task.java:1)'])
    workbook, output = self.root / "input.xlsx", self.root / "output.jsonl"
    book.save(workbook)
    bootstrap = "import sys,runpy;sys.path.insert(0,sys.argv.pop(1));sys.argv.pop(0);runpy.run_path(sys.argv[0],run_name='__main__')"
    command = [sys.executable, "-B", "-c", bootstrap, str(Path(tree_sitter.__file__).parent.parent),
               str(Path(__file__).resolve().parents[1] / "main/find_sources.py"),
               "--workbook", str(workbook), "--source-root", str(self.root), "--output", str(output)]
    first = subprocess.run(command, capture_output=True, text=True)
    self.assertEqual(0, first.returncode, first.stderr)
    before = output.read_bytes()
    self.assertEqual("finder-source-locations/1", json.loads(before)["schema_version"])
    self.assertIn("SKIPPED_HUAWEI_CLOSED_SOURCE", first.stderr)
    summary = json.loads(first.stderr.splitlines()[-1])
    self.assertEqual(1, summary["records"])
    self.assertEqual(1, summary["skipped_huawei_records"])
    only = subprocess.run(command[:-1] + [str(self.root / "skipped.jsonl"), "--row", "3"],
                          capture_output=True, text=True)
    self.assertEqual(0, only.returncode, only.stderr)
    self.assertEqual("", (self.root / "skipped.jsonl").read_text())
    self.assertNotEqual(0, subprocess.run(command, capture_output=True).returncode)
    self.assertEqual(before, output.read_bytes())

  def test_huawei_filter_before_source_lookup(self):
    for symbol in ("com.huawei.snap.Task.run", "plugin@1/com.huawei.Foo.run",
                   "loader//com.huawei.Foo$$Lambda/0x123.run"):
      record = {"threads": [{"frames": [{"symbol": "java.lang.Object.wait"}]},
                            {"frames": [{"symbol": symbol}]}]}
      self.assertIsNone(locate_record(record, None))
    for symbol in ("com.huaweiother.Foo.run", "org.example.com.huawei.Foo.run", None):
      self.assertEqual([], excluded_huawei_symbols({"threads": [{"frames": [{"symbol": symbol}]}]}))


if __name__ == "__main__":
  unittest.main()
