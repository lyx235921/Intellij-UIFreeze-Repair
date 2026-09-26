from pathlib import Path
from contextlib import redirect_stdout
import io
import json
import sys
import tempfile
import unittest

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_full_test import main, summarize


def record(record_id, weight, states):
  return {"record_id": record_id, "input": {"occurrences": weight}, "parse": {"status": "PARSED"},
          "threads": [{"thread_id": f"t{i}", "state": state, "frames": []} for i, state in enumerate(states)],
          "ui_thread_ids": ["t0"], "cause_thread_ids": [f"t{len(states) - 1}"], "call_edges": []}


class StateStatisticsTest(unittest.TestCase):
  def test_same_state_threads_do_not_double_count_records(self):
    result = summarize([record("a", 3, ["WAITING", "WAITING"]), record("b", 2, ["WAITING", "RUNNABLE"])])
    self.assertEqual({"thread_entries": 3, "records": 2, "weighted_thread_entries": 8, "weighted_records": 5},
                     result["thread_states"]["all_threads"]["WAITING"])
    self.assertEqual(2, result["thread_states"]["ui_threads"]["WAITING"]["thread_entries"])
    self.assertEqual(1, result["thread_states"]["cause_threads"]["RUNNABLE"]["records"])
    self.assertEqual(5, result["occurrences"])

  def test_single_thread_is_not_duplicated_by_ui_and_cause_roles(self):
    result = summarize([record("a", 7, ["RUNNABLE"])])
    self.assertEqual(1, result["thread_states"]["all_threads"]["RUNNABLE"]["thread_entries"])
    for scope in ("ui_threads", "cause_threads"):
      self.assertEqual(7, result["thread_states"][scope]["RUNNABLE"]["weighted_records"])

  def test_invalid_weight_or_duplicate_record_is_rejected(self):
    with self.assertRaises(ValueError):
      summarize([record("a", "3", ["WAITING"])])
    with self.assertRaises(ValueError):
      summarize([record("a", 1, ["WAITING"])] * 2)

  def test_runner_creates_verified_statistics_and_protects_existing_results(self):
    with tempfile.TemporaryDirectory() as directory:
      root = Path(directory)
      (root / "Example.java").write_text('package p; class Example { void run() { leaf(); } void leaf() {} }', encoding="utf-8")
      book = openpyxl.Workbook()
      book.active.title = "问题线程堆栈"
      book.active.append(["堆栈出现次数", "问题线程堆栈"])
      book.active.append([3, 'cause freeze thread:[AWT-EventQueue-0] RUNNABLE\n'
                            'topStack: 0 p.Example.leaf(Example.java:1)\n'
                            'problemModuleStack: 1 p.Example.run(Example.java:1)'])
      workbook, output = root / "input.xlsx", root / "results"
      book.save(workbook)
      args = ["--workbook", str(workbook), "--source-root", str(root), "--output-dir", str(output)]
      with redirect_stdout(io.StringIO()):
        self.assertEqual(0, main(args))
      report = json.loads((output / "report.json").read_text(encoding="utf-8"))
      self.assertEqual("PASSED", report["status"])
      self.assertEqual(1, report["verification"]["records"])
      self.assertEqual(3, report["statistics"]["thread_states"]["ui_threads"]["RUNNABLE"]["weighted_records"])
      self.assertIn(str(Path("Test") / "run_full_test.py"), report["code_sha256"])
      with self.assertRaises(FileExistsError):
        main(args)


if __name__ == "__main__":
  unittest.main()
