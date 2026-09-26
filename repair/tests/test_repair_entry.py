import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "repair/main/python"))
import repair


class RepairEntryTest(unittest.TestCase):
  def setUp(self):
    self.record = json.loads((ROOT / "finder/docs/row2-output.json").read_text(encoding="utf-8"))

  def intake(self, *records):
    return list(repair.receive(io.StringIO("".join(json.dumps(r) + "\n" for r in records))))

  def test_accepts_real_finder_record_without_upgrading_candidates(self):
    result = self.intake(self.record)[0]
    self.assertEqual("ACCEPTED", result["intake_status"])
    self.assertEqual("NOT_STARTED", result["repair_status"])
    self.assertEqual("NOT_PERFORMED", result["source_verification"])
    self.assertEqual(self.record, result["finder"])

  def test_rejects_version_missing_fields_and_bad_hash(self):
    for field, value in [("schema_version", "finder-source-locations/99"), ("threads", None)]:
      record = copy.deepcopy(self.record)
      record[field] = value
      self.assertEqual("REJECTED", self.intake(record)[0]["intake_status"])
    self.record["input"]["raw_stack"] += "changed"
    self.assertIn("STACK_HASH_MISMATCH", self.intake(self.record)[0]["errors"])

  def test_rejects_bad_references_and_unsafe_source_paths(self):
    record = copy.deepcopy(self.record)
    record["call_edges"][0]["callee_frame_id"] = "missing"
    self.assertEqual("REJECTED", self.intake(record)[0]["intake_status"])
    frame = next(f for t in self.record["threads"] for f in t["frames"] if f["source"]["candidates"])
    frame["source"]["candidates"][0]["path"] = "../outside.java"
    self.assertEqual("REJECTED", self.intake(self.record)[0]["intake_status"])

  def test_duplicates_are_scoped_to_workbook(self):
    other = copy.deepcopy(self.record)
    other["workbook_sha256"] = "a" * 64
    self.assertEqual(["ACCEPTED", "REJECTED", "ACCEPTED"],
                     [r["intake_status"] for r in self.intake(self.record, self.record, other)])

  def test_malformed_json_does_not_drop_later_records(self):
    lines = 'invalid\n{"x":1,"x":2}\nNaN\n' + json.dumps(self.record) + '\n'
    result = list(repair.receive(io.StringIO(lines)))
    self.assertEqual(["REJECTED"] * 3 + ["ACCEPTED"], [r["intake_status"] for r in result])
    self.assertEqual([1, 2, 3, 4], [r["input_line"] for r in result])

  def test_partial_evidence_is_accepted_but_not_repaired(self):
    self.record["parse"]["status"] = "PARTIAL"
    self.record["parse"]["diagnostics"] = ["UI_THREAD_NOT_PRESENT"]
    result = self.intake(self.record)[0]
    self.assertEqual("ACCEPTED", result["intake_status"])
    self.assertEqual("PARTIAL", result["finder"]["parse"]["status"])

  def test_cli_outputs_and_exit_codes(self):
    with tempfile.TemporaryDirectory() as directory:
      source, output = Path(directory) / "finder.jsonl", Path(directory) / "repair.jsonl"
      source.write_text(json.dumps(self.record) + "\ninvalid\n", encoding="utf-8")
      command = [sys.executable, "-B", str(ROOT / "repair/main/python/repair.py"),
                 "--input", str(source), "--output", str(output)]
      run = subprocess.run(command, capture_output=True, text=True)
      self.assertEqual(2, run.returncode, run.stderr)
      self.assertEqual(1, json.loads(run.stderr)["accepted"])
      before = output.read_bytes()
      self.assertNotEqual(0, subprocess.run(command, capture_output=True).returncode)
      self.assertEqual(before, output.read_bytes())
      empty = Path(directory) / "empty.jsonl"
      empty.write_text("", encoding="utf-8")
      self.assertEqual(2, repair.main(["--input", str(empty), "--output", str(Path(directory) / "empty-result.jsonl")]))

  def q1(self, record):
    classpath = os.environ.get("Q1_CLASSPATH")
    if not classpath:
      self.skipTest("Build Q1 and set Q1_CLASSPATH for Kotlin integration tests")
    run = subprocess.run(["java", "-cp", classpath, "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier"],
                         input=json.dumps(record), capture_output=True, encoding="utf-8", check=True)
    return json.loads(run.stdout)

  def test_q1_real_source_and_both_call_candidates(self):
    result = self.q1(self.record)
    frame = next(f for f in result["frames"] if f["method_name"] == "actionsUpdated")
    self.assertEqual(1159, frame["stack_line"])
    calls = [s for c in frame["locations"] for s in c["call_sites"]]
    self.assertEqual({1225, 1226}, {s["line"] for s in calls})
    self.assertTrue(all(c["verification"] == "HASH_MATCHED" for c in frame["locations"]))
    self.assertEqual([], result["frames"][0]["locations"])
    self.assertEqual("sun.awt.windows.WGlobalCursorManager", result["frames"][0]["class_name"])
    self.assertEqual("NO_RULE_MATCH", result["problem_assessment"])

  def test_q1_source_changes_and_path_escape(self):
    frame = next(f for t in self.record["threads"] for f in t["frames"] if f["source"]["candidates"])
    frame["source"]["candidates"][0]["sha256"] = "0" * 64
    result = self.q1(self.record)
    candidate = next(f for f in result["frames"] if f["frame_id"] == frame["frame_id"])["locations"][0]
    self.assertEqual("SOURCE_CHANGED", candidate["verification_error"])
    self.assertNotIn("source_text", candidate)
    frame["source"]["candidates"][0]["path"] = "../escape.java"
    result = self.q1(self.record)
    candidate = next(f for f in result["frames"] if f["frame_id"] == frame["frame_id"])["locations"][0]
    self.assertEqual("PATH_OUTSIDE_ROOT", candidate["verification_error"])

  def test_q1_python_entry(self):
    classpath = os.environ.get("Q1_CLASSPATH")
    if not classpath:
      self.skipTest("Q1_CLASSPATH not set")
    with tempfile.TemporaryDirectory() as directory:
      source, output = Path(directory) / "input.jsonl", Path(directory) / "output.jsonl"
      source.write_text(json.dumps(self.record) + "\ninvalid\n", encoding="utf-8")
      self.assertEqual(2, repair.main(["--input", str(source), "--output", str(output), "--q1-classpath", classpath]))
      accepted, rejected = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
      self.assertEqual("repair-q1-locations/1", accepted["q1"]["schema_version"])
      self.assertNotIn("s1", accepted)
      self.assertEqual(self.record["input"], accepted["q1"]["input"])
      self.assertEqual(self.record["record_id"], accepted["q1"]["record_id"])
      self.assertEqual("Q1", accepted["q1"]["problem_family"])
      self.assertEqual(self.record, accepted["finder"])
      self.assertNotIn("q1", rejected)

  def test_q1_exact_method_counts_record_once_and_only_ui(self):
    target = "sun.nio.fs.WindowsNativeDispatcher.GetFileAttributesEx0"
    frames = self.record["threads"][0]["frames"]
    frames[0]["symbol"] = "java.base@25.0.2/" + target
    frames[1]["symbol"] = target
    result = self.q1(self.record)["classification"]
    self.assertEqual(1, result["q1_count"])
    self.assertEqual(2, len(result["matched_frames"]))
    frames[0]["symbol"] = target + "Extra"
    frames[1]["symbol"] = "other.WindowsNativeDispatcher.GetFileAttributesEx0"
    self.assertEqual(0, self.q1(self.record)["classification"]["q1_count"])
    frames[0]["symbol"] = target
    self.record["ui_thread_ids"] = []
    self.assertEqual(0, self.q1(self.record)["classification"]["q1_count"])

  def test_q1_seven_methods_share_one_record_count(self):
    methods = [
      "sun.nio.fs.WindowsNativeDispatcher.GetFileAttributesEx0",
      "sun.nio.fs.WindowsNativeDispatcher.FindFirstFile0",
      "java.lang.ClassLoader.defineClass2",
      "sun.nio.fs.WindowsNativeDispatcher.FindClose",
      "com.intellij.workspaceModel.core.fileIndex.impl.WorkspaceFileIndexDataImpl.getFileInfo",
      "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.getName",
      "sun.nio.fs.WindowsNativeDispatcher.CreateFile0",
    ]
    for frame, symbol in zip(self.record["threads"][0]["frames"], methods):
      frame["symbol"] = symbol
    result = self.q1(self.record)["classification"]
    self.assertEqual(1, result["q1_count"])
    self.assertEqual(set(methods), set(result["matched_methods"]))

  def test_q1_all_75_baseline_methods_including_nested_classes(self):
    evidence = ROOT / "repair/tests/fixtures/q1-method-baseline.json"
    rows = json.loads(evidence.read_text(encoding="utf-8"))
    methods = {row["evidence"] for row in rows if row["group"] == "WORK_CANDIDATE"}
    self.assertEqual(75, len(methods))
    template = self.record["threads"][0]["frames"][0]
    frames = []
    for index, method in enumerate(sorted(methods)):
      frame = copy.deepcopy(template)
      frame.update(symbol="java.base@25/" + method, frame_id=f"t0:f{index}", index=index)
      frames.append(frame)
    self.record["threads"][0]["frames"] = frames
    result = self.q1(self.record)["classification"]
    self.assertEqual(methods, set(result["rules"]))
    self.assertEqual(methods, set(result["matched_methods"]))
    self.assertEqual(1, result["q1_count"])
    families = {"FILESYSTEM_IO": "Q1.1", "CLASS_LOADING": "Q1.2", "INDEX_STORAGE_WORK": "Q1.3",
                "REGEX": "Q1.4", "PARSING_LEXING": "Q1.5", "COMPRESSION": "Q1.6",
                "IMAGE_LOADING_PROCESSING": "Q1.7"}
    expected = {r["evidence"]: families[r["family"]] for r in rows if r["group"] == "WORK_CANDIDATE"}
    self.assertEqual(7, len(result["categories"]))
    for category in result["categories"]:
      self.assertEqual(1, category["count"])
      self.assertEqual({m for m, c in expected.items() if c == category["category"]}, set(category["matched_methods"]))
    self.assertEqual(expected, {f["symbol"]: f["category"] for f in result["matched_frames"]})

  def test_q1_ui_state_and_top_gate(self):
    thread = self.record["threads"][0]
    thread["frames"][1]["symbol"] = "sun.nio.fs.WindowsNativeDispatcher.CreateFile0"
    for state, top, expected in [
        ("WAITING", "java.lang.Object.wait0", "STATE_NOT_RUNNABLE"),
        ("BLOCKED", "anything.run", "STATE_NOT_RUNNABLE"),
        ("TIMED_WAITING", "java.lang.Thread.sleep", "STATE_NOT_RUNNABLE"),
        ("UNKNOWN", "anything.run", "STATE_NOT_RUNNABLE"),
        ("RUNNABLE", "java.base@25/jdk.internal.misc.Unsafe.park", "TOP_WAIT_METHOD"),
        ("RUNNABLE", None, "TOP_FRAME_UNAVAILABLE"),
        ("RUNNABLE", "sun.nio.fs.WindowsNativeDispatcher.CreateFile0", "PASSED"),
        ("RUNNABLE", "jdk.internal.misc.Unsafe.unpark", "PASSED"),
    ]:
      thread["state"] = state
      thread["frames"][0]["symbol"] = top
      result = self.q1(self.record)["classification"]
      self.assertEqual(expected, result["ui_checks"][0]["result"])
      self.assertEqual(int(expected == "PASSED"), result["q1_count"])
    thread["frames"][0]["index"] = 1
    self.assertEqual(0, self.q1(self.record)["classification"]["q1_count"])


if __name__ == "__main__":
  unittest.main()
