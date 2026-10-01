"""Eleven real-stack bindings through the Python CLI and Kotlin selection worker."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "repair/tests/fixtures/P1-preload-bindings"
EXPECTED = {
  "java.io.WinNTFileSystem.canonicalize",
  "sun.nio.fs.WindowsNativeDispatcher.GetFinalPathNameByHandle",
  "sun.nio.fs.WindowsNativeDispatcher.GetFullPathName0",
  "sun.nio.fs.WindowsNativeDispatcher.GetLogicalDrives",
  "com.intellij.util.lang.UrlClassLoader.findClass",
  "java.lang.ClassLoader.defineClass", "java.lang.ClassLoader.defineClass0",
  "java.lang.ClassLoader.defineClass2", "java.lang.ClassLoader.defineClassSourceLocation",
  "java.lang.ClassLoader.loadClass", "jdk.internal.loader.NativeLibraries.load",
}


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build Q1 first")
class P1PreloadBindingsTest(unittest.TestCase):
  def worker(self, records):
    run = subprocess.run(["java", "-cp", os.environ["Q1_CLASSPATH"],
                          "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier", "--repair-selection"],
                         input="".join(json.dumps(r)+"\n" for r in records), capture_output=True,
                         text=True, encoding="utf-8", check=True, timeout=30)
    return [json.loads(line) for line in run.stdout.splitlines()]

  def test_real_intake_contexts_selection_and_refusals(self):
    records = [json.loads(line) for line in (FIXTURE/"P1-finder.jsonl").read_text(encoding="utf-8").splitlines()]
    with tempfile.TemporaryDirectory(dir=ROOT/"out") as tmp:
      root = Path(tmp)
      with zipfile.ZipFile(FIXTURE/"P1-reviewed-sources.zip") as archive:
        archive.extractall(root)
      with zipfile.ZipFile(ROOT/"repair/tests/fixtures/q13/reviewed-sources.zip") as archive:
        archive.extractall(root)
      for record in records:
        record["source_root"] = tmp
      src, dst = root/"input.jsonl", root/"output.jsonl"
      src.write_text("".join(json.dumps(r)+"\n" for r in records), encoding="utf-8")
      command = [sys.executable, str(ROOT/"repair/main/python/repair.py"), "--input", str(src), "--output", str(dst),
                 "--q1-classpath", os.environ["Q1_CLASSPATH"], "--s1-storage", "--s1-loading", "--repair-selection"]
      run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=30)
      self.assertEqual(0, run.returncode, run.stderr)
      results = [json.loads(line) for line in dst.read_text(encoding="utf-8").splitlines()]
      self.assertEqual(9, len(results))
      covered, has_source, missing_source = set(), set(), set()
      for record in results:
        self.assertEqual("ACCEPTED", record["intake_status"])
        q1 = record["q1"]
        decisions = q1["s1_storage"]["decisions"] + q1["s1_loading"]["decisions"]
        for d in decisions:
          symbol = d["trigger"]["symbol"]
          if symbol not in EXPECTED:
            continue
          covered.add(symbol)
          self.assertEqual("BOUND", d["binding_status"])
          self.assertEqual("P1_FIRST", d["initial_priority"])
          candidate = symbol in {"java.lang.ClassLoader.defineClass0", "sun.nio.fs.WindowsNativeDispatcher.GetLogicalDrives"}
          self.assertEqual("CANDIDATE_PATCH" if candidate else "INSUFFICIENT_EVIDENCE", d["status"])
          self.assertEqual("CANDIDATE_IMPLEMENTED" if candidate else "NOT_IMPLEMENTED", d["generator_status"])
          self.assertEqual("DEFERRED", d["p3_status"])
          self.assertEqual(candidate, d["patch_generated"])
          self.assertTrue(d["method_contexts"])
          for context in d["method_contexts"]:
            if context["method_layer"] == 0:
              self.assertEqual("UNRESOLVED", context["status"])
              self.assertEqual("INCOMPLETE_STACK_PATH", context["reason"])
              self.assertNotIn("method", context)
            else:
              self.assertTrue(1 <= context["method_layer"] <= 5)
          (has_source if d["verified_context_count"] else missing_source).add(symbol)
          selected = [x for x in q1["repair_selection"]["decisions"] if x["trigger"]["symbol"] == symbol]
          self.assertTrue(selected)
          for s in selected:
            expected_status = "CANDIDATE_SELECTED" if candidate else "PENDING"
            if record["finder"]["input"]["row"] == 1031:
              expected_status = "SKIPPED_SOURCE_UNAVAILABLE"  # Saved JCEF frames explicitly lack source files.
              self.assertTrue(s["missing_source_contexts"])
              self.assertFalse(s["patch_generated"])
            self.assertEqual(expected_status, s["status"])
            if candidate:
              loading = symbol == "java.lang.ClassLoader.defineClass0"
              self.assertEqual("P1" if loading else "P2", s["selected_strategy"])
              self.assertEqual("loading_evaluation" if loading else "q13_evaluation", s["selected_proposal_pool"])
            self.assertIn(s["evaluation_pool"], {"q13_evaluation", "loading_evaluation"})
            self.assertFalse(s["p3_eligible"])
      self.assertEqual(EXPECTED, covered)
      self.assertTrue(has_source)
      self.assertIn("java.io.WinNTFileSystem.canonicalize", missing_source)
      self.assertIn("jdk.internal.loader.NativeLibraries.load", missing_source)
      waiting = copy.deepcopy(records[0])
      for thread in waiting["threads"]:
        if thread["is_ui_thread"]:
          thread["state"] = "WAITING"
      self.assertFalse(self.worker([waiting])[0]["repair_selection"]["loading_evaluation"]["decisions"])
      # Once all reviewed source files change, no previous source context may remain verified.
      for path in json.loads((FIXTURE/"P1-provenance.json").read_text())["files"]:
        file = root/path
        file.write_bytes(file.read_bytes()+b"\n// changed source\n")
      changed = self.worker(records)
      for result in changed:
        selection = result["repair_selection"]
        for pool in ["q13_evaluation", "loading_evaluation"]:
          for d in selection[pool]["decisions"]:
            if d["trigger"]["symbol"] in EXPECTED:
              self.assertEqual(0, d["verified_context_count"])
              self.assertFalse(d["patch_generated"])


if __name__ == "__main__":
  unittest.main()
