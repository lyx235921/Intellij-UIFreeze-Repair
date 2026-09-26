import io
from pathlib import Path
import sys
import unittest

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))
from real_stack_input import parse_stack, read_records


class RealStackInputTest(unittest.TestCase):
  def test_direct_and_indirect_threads_preserve_evidence(self):
    cause = ("cause freeze thread:[AWT-EventQueue-2] RUNNABLE\n"
             "topStack: 0 java.base/Foo.read(Native Method)\n"
             "problemModuleStack: 1 pkg.Bar.run(Bar.java:42)\n2 *")
    direct = parse_stack(cause)
    self.assertEqual("PARSED", direct["status"])
    self.assertTrue(direct["cause_threads"][0]["is_ui_thread"])
    self.assertEqual(42, direct["problem"]["problem_module_stack"][0]["line"])
    self.assertTrue(direct["threads"][0]["frames"][-1]["elided"])
    indirect = parse_stack("[AWT-EventQueue-0] WAITING on lock\n0 Foo.wait(Unknown Source)\n"
                           + cause.replace("AWT-EventQueue-2", "worker"))
    self.assertEqual("PARSED", indirect["status"])
    self.assertEqual("worker", indirect["cause_threads"][0]["name"])
    self.assertEqual(2, len(indirect["threads"]))
    self.assertIsNone(indirect["problem"]["root_cause"])

  def test_incomplete_input_is_not_silently_lost(self):
    raw = "[AWT-EventQueue-0] WAITING\nunrecognized content"
    record = parse_stack(raw)
    self.assertEqual("PARTIAL", record["status"])
    self.assertEqual(raw, record["raw_stack"])
    self.assertIn("CAUSE_THREAD_COUNT", record["diagnostics"])
    self.assertEqual(["unrecognized content"], record["threads"][0]["unparsed_lines"])
    self.assertEqual("FAILED", parse_stack("invalid")["status"])

  def test_workbook_columns_are_located_by_name(self):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "问题线程堆栈"
    sheet.append(["说明"])
    sheet.append(["无关列", "问题线程堆栈", "堆栈出现次数"])
    sheet.append(["ignore", "invalid stack", 3])
    sheet.append(["ignore", None, 9])
    stream = io.BytesIO()
    book.save(stream)
    stream.seek(0)
    records = list(read_records(stream))
    self.assertEqual(1, len(records))
    self.assertEqual(3, records[0]["row"])
    self.assertEqual(3, records[0]["occurrences"])
    self.assertEqual("invalid stack", records[0]["raw_stack"])

  def test_long_stack_continuation_is_joined_without_added_newline(self):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "问题线程堆栈"
    sheet.append(["堆栈出现次数", "问题线程堆栈", None, "备注"])
    raw = ("cause freeze thread:[AWT-EventQueue-0] RUNNABLE\n"
           "topStack: 0 Foo.run(Foo.java:1)\n"
           "problemModuleStack: 1 " + "x" * 33000 + ".run(Foo.java:2)")
    sheet.append([1, raw[:32767], raw[32767:], "not stack data"])
    stream = io.BytesIO()
    book.save(stream)
    stream.seek(0)
    record = next(read_records(stream))
    self.assertEqual(raw, record["raw_stack"])
    self.assertEqual("PARSED", record["status"])


if __name__ == "__main__":
  unittest.main()
