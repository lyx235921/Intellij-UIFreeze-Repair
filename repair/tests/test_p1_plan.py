import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build Q1 first")
class P1PlanTest(unittest.TestCase):
  def run_cases(self, cases, root=None):
    command = ["java", "-cp", os.environ["Q1_CLASSPATH"],
               "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier", "--s1-p1"]
    if root is not None:
      command.append(str(root))
    result = subprocess.run(command, input="".join(json.dumps(r) + "\n" for r in cases),
                            text=True, encoding="utf-8", capture_output=True, check=True)
    return [json.loads(line)["s1_p1"] for line in result.stdout.splitlines()]

  def test_real_path_rejections_and_source_version(self):
    record = json.loads((ROOT / "repair/tests/fixtures/row4746-finder.json").read_text(encoding="utf-8"))
    gap = copy.deepcopy(record)
    gap["threads"][0]["frames"][15]["elided"] = True
    wait = copy.deepcopy(record)
    wait["threads"][0]["state"] = "WAITING"
    other = copy.deepcopy(record)
    for frame in other["threads"][0]["frames"]:
      if (frame.get("symbol") or "").endswith("FileDocumentManagerImpl.reloadFromDisk"):
        frame["symbol"] = "example.Unrelated.reloadFromDisk"
    good, *rejected = self.run_cases([record, gap, wait, other])
    self.assertEqual("CANDIDATE_PATCH", good["status"], good.get("reason"))
    self.assertTrue(good["patch_generated"])
    self.assertFalse(good["applied"])
    self.assertIn("p1ReadSnapshot", good["replacement_source"])
    self.assertEqual(4, len(good["source_contexts"]))
    self.assertEqual(7, len(good["steps"]))
    self.assertEqual("BLOCKED_BY_SYNC_REFRESH_CONTRACT", good["readiness"])
    self.assertEqual("CONTROLLED_CORRECTNESS_FAILURE", good["validation_status"])
    self.assertFalse(good["eligible_for_application"])
    self.assertTrue(all(r["status"] == "NOT_APPLICABLE" for r in rejected))
    with tempfile.TemporaryDirectory(dir=ROOT / "out") as tmp:
      path = Path(tmp) / good["source_contexts"][0]["path"]
      path.parent.mkdir(parents=True)
      original = Path(record["source_root"]) / good["source_contexts"][0]["path"]
      path.write_bytes(original.read_bytes() + b"\n// changed source\n")
      changed = self.run_cases([record], tmp)[0]
      self.assertEqual("UNAVAILABLE", changed["status"])
      self.assertEqual("UNREVIEWED_RELOAD_SOURCE_VERSION", changed["reason"])


if __name__ == "__main__":
  unittest.main()
