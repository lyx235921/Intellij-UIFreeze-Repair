import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build classifiers and set Q1_CLASSPATH")
class ExtractMethodTest(unittest.TestCase):
  def test_real_method_and_incomplete_or_changed_evidence(self):
    original = json.loads((ROOT / "repair/tests/fixtures/row1238-finder.json").read_text(encoding="utf-8"))
    if not Path(original["source_root"]).exists():
      self.skipTest("Real checkout required for row1238 source verification")
    cases = [original]
    changed = copy.deepcopy(original)
    source = changed["threads"][0]["frames"][7]["source"]
    for c in source["candidates"]:
      c["sha256"] = "0" * 64
    source["selected"]["sha256"] = "0" * 64
    cases.append(changed)
    missing = copy.deepcopy(original)
    missing["threads"][0]["frames"][4]["elided"] = True
    cases.append(missing)
    unresolved = copy.deepcopy(original)
    unresolved["threads"][0]["frames"][7]["source"].update(selected=None, candidates=[], status="UNRESOLVED")
    cases.append(unresolved)
    other = copy.deepcopy(original)
    other["threads"][0]["frames"][2]["symbol"] = "java.util.zip.Other.work"
    cases.append(other)
    result = subprocess.run(
      ["java", "-cp", os.environ["Q1_CLASSPATH"], "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier",
       "--s1-q16-method"], input="".join(json.dumps(r) + "\n" for r in cases),
      capture_output=True, text=True, encoding="utf-8", check=True)
    results = [json.loads(line)["s1_q16"] for line in result.stdout.splitlines()]
    self.assertEqual(["METHOD_LOCATED", "UNRESOLVED", "UNRESOLVED", "UNRESOLVED"],
                     [r["results"][0]["status"] for r in results[:4]])
    self.assertEqual("NOT_APPLICABLE", results[4]["status"])
    self.assertEqual(5, results[0]["max_method_layers"])
    self.assertEqual([1, 2, 3, 4, 5], [r["method_layer"] for r in results[0]["results"]])
    self.assertEqual(5, len(results[3]["results"]))
    self.assertEqual(1, len(results[2]["results"]))
    method = results[0]["results"][0]["method"]
    self.assertEqual("com.intellij.ui.AppIcon$Win7AppIcon", method["owner"])
    self.assertEqual("_setOkBadge", method["method"])
    self.assertEqual((641, 674), (method["start_line"], method["end_line"]))
    lines = Path(method["absolute_path"]).read_text(encoding="utf-8").splitlines()
    self.assertEqual("\n".join(lines[640:674]), method["source_text"])
    self.assertIn("ImageIO.read", method["source_text"])
    self.assertEqual("t0:f7", results[0]["results"][0]["method_frame_id"])
    self.assertEqual("INCOMPLETE_STACK_PATH", results[2]["results"][0]["reason"])
    with tempfile.TemporaryDirectory() as tmp:
      source, output = Path(tmp) / "input.jsonl", Path(tmp) / "output.jsonl"
      source.write_text(json.dumps(original) + "\n", encoding="utf-8")
      subprocess.run([sys.executable, str(ROOT / "repair/main/python/repair.py"), "--input", str(source),
                      "--output", str(output), "--q1-classpath", os.environ["Q1_CLASSPATH"], "--s1-q16-method"], check=True)
      intake = json.loads(output.read_text(encoding="utf-8"))
      self.assertIn(intake["q1"]["s1_q16"]["status"], ("METHOD_LOCATED", "PARTIAL"))
      self.assertEqual(original, intake["finder"])


if __name__ == "__main__":
  unittest.main()
