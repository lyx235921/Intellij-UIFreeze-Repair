"""Boundary tests against the compiled Kotlin classifier (Q1_CLASSPATH)."""
import copy
import json
import os
import subprocess
import unittest


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build classifiers and set Q1_CLASSPATH")
class Q2ClassifierTest(unittest.TestCase):
  def test_wait_context_and_evidence_boundaries(self):
    def record(symbols, state="WAITING", ui=True):
      return {"schema_version": "finder-source-locations/1", "record_id": "test",
              "ui_thread_ids": ["t"] if ui else [], "threads": [{"thread_id": "t", "state": state,
                "frames": [{"index": i, "symbol": s, "elided": False, "frame_id": f"f{i}"}
                           for i, s in enumerate(symbols)]}]}

    park = "java.base@25/jdk.internal.misc.Unsafe.park"
    wait = "com.intellij.openapi.progress.util.ProgressIndicatorUtils.awaitWithCheckCanceled"
    idle = [park, "java.awt.EventQueue.getNextEvent", "com.intellij.ide.IdeEventQueue.getNextEvent"]
    cases = [
      (record([park, "java.util.concurrent.FutureTask.get", wait]), ["Q2.1"]),
      (record([park, wait], "RUNNABLE"), ["Q2.1"]),
      (record([park, wait], ui=False), []),
      (record(["example.Work.run", wait], "RUNNABLE"), []),
      (record([park, wait], "BLOCKED"), []),
      (record(idle), []),
      (record(idle + ["com.intellij.openapi.fileEditor.impl.FileEditorManagerImplKt.waitBlockingAndPumpEdt"]),
       ["Q2.2", "Q2.3"]),
      (record([park, "java.util.concurrent.locks.StampedLock.writeLock", wait]), []),
      (record(["java.lang.Thread.sleepNanos0", "com.intellij.openapi.progress.util.SuvorovProgress.sleep"]),
       ["Q2.3", "Q2.6"]),
      (record(["java.lang.Object.wait0", "sun.java2d.metal.MTLRenderQueue$QueueFlusher.flushNow"]), ["Q2.5"]),
    ]
    for field, value in (("index", 1), ("elided", True), ("symbol", None)):
      partial = copy.deepcopy(cases[0][0])
      partial["threads"][0]["frames"][0][field] = value
      cases.append((partial, []))
    process = subprocess.run(
      ["java", "-cp", os.environ["Q1_CLASSPATH"], "org.jetbrains.research.lockrepair.Q2SynchronousWaitControlClassifier"],
      input="".join(json.dumps(r) + "\n" for r, _ in cases), capture_output=True, text=True, encoding="utf-8", check=True)
    results = [json.loads(line)["classification"] for line in process.stdout.splitlines()]
    self.assertEqual(len(cases), len(results))
    for (r, expected), result in zip(cases, results):
      with self.subTest(record=r):
        self.assertEqual(expected, [c["category"] for c in result["categories"]])
        self.assertEqual(int(bool(expected)), result["q2_count"])
        frame_ids = {f["frame_id"] for t in r["threads"] for f in t["frames"]}
        self.assertTrue(all(f["frame_id"] in frame_ids for f in result["matched_frames"]))


if __name__ == "__main__":
  unittest.main()
