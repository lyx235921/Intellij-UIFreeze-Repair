"""Boundary tests against the compiled Kotlin classifier (Q1_CLASSPATH)."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build classifiers and set Q1_CLASSPATH")
class Q2ClassifierTest(unittest.TestCase):
  def test_s2_await_disk_query_requires_consumer_contract(self):
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(dir=root / "out") as tmp:
      text = "class LocalFileSystemImpl { Object fetchCaseSensitivity() { return caseSensitivityGetter.accessDiskWithCheckCanceled(arg); } }\n"
      Path(tmp, "LocalFileSystemImpl.java").write_text(text, encoding="utf-8", newline="\n")
      method = dict(path="LocalFileSystemImpl.java", sha256=hashlib.sha256(text.encode()).hexdigest(),
                    start_line=1, end_line=1, source_text=text,
                    owner="com.intellij.openapi.vfs.impl.local.LocalFileSystemImpl", method="fetchCaseSensitivity")
      symbols = ["jdk.internal.misc.Unsafe.park", "java.util.concurrent.FutureTask.get",
                 "com.intellij.openapi.progress.util.ProgressIndicatorUtils.awaitWithCheckCanceled",
                 "com.intellij.openapi.vfs.DiskQueryRelay.accessDiskWithCheckCanceled",
                 "com.intellij.openapi.vfs.impl.local.LocalFileSystemImpl.fetchCaseSensitivity"]
      frames = [dict(frame_id=f"f{i}", index=i, symbol=s, elided=False, file="LocalFileSystemImpl.java",
                     source=dict(status="UNRESOLVED", reason="METHOD_NOT_FOUND", candidates=[], selected=None))
                for i, s in enumerate(symbols)]
      frames[-1]["source"].update(status="LOCATED", reason=None, candidates=[method], selected=method)
      record = dict(schema_version="finder-source-locations/1", record_id="not-bound-to-row-357", source_root=tmp,
                    ui_thread_ids=["t"], threads=[dict(thread_id="t", state="WAITING", frames=frames)], call_edges=[])
      unrelated = copy.deepcopy(record)
      unrelated["threads"][0]["frames"][3]["symbol"] = "example.Other.waitForResult"
      command = ["java", "-cp", os.environ["Q1_CLASSPATH"],
                 "org.jetbrains.research.lockrepair.Q2SynchronousWaitControlClassifier", "--s2-repair-selection"]
      run = subprocess.run(command, input="".join(json.dumps(r)+"\n" for r in [record, unrelated]),
                           capture_output=True, text=True, encoding="utf-8", check=True)
      blocked, other = [json.loads(line)["repair_selection_s2"] for line in run.stdout.splitlines()]
      self.assertEqual("BLOCKED_CONTRACT", blocked["status"])
      decision = blocked["decisions"][0]
      self.assertIsNone(decision.get("recommended_strategy"))
      self.assertFalse(decision["await_repair"]["patch_generated"])
      self.assertEqual(["f4"], decision["await_repair"]["source_method_frame_ids"])
      self.assertEqual("CANDIDATES_RANKED", other["status"])

  def test_s2_context_selection_and_source_boundaries(self):
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(dir=root / "out") as tmp:
      text = "class ProgressIndicatorUtils { void awaitWithCheckCanceled() { while (true) future.get(10, unit); } }\n"
      (Path(tmp) / "ProgressIndicatorUtils.java").write_text(text, encoding="utf-8", newline="\n")
      method = dict(path="ProgressIndicatorUtils.java", sha256=hashlib.sha256(text.encode()).hexdigest(),
                    start_line=1, end_line=1, owner="com.intellij.openapi.progress.util.ProgressIndicatorUtils",
                    method="awaitWithCheckCanceled", declaration="void awaitWithCheckCanceled()",
                    language="java", basis="JAVA_AST")
      empty = dict(status="UNRESOLVED", reason="SOURCE_FILE_NOT_FOUND", candidates=[], selected=None)
      frames = [dict(frame_id=f"f{i}", index=i, symbol=s, elided=False, file="ProgressIndicatorUtils.java", source=copy.deepcopy(empty))
                for i, s in enumerate(["jdk.internal.misc.Unsafe.park", "java.util.concurrent.FutureTask.get",
                                       "com.intellij.openapi.progress.util.ProgressIndicatorUtils.awaitWithCheckCanceled"])]
      frames[2]["source"].update(status="LOCATED", reason=None, candidates=[method], selected=method)
      original = dict(schema_version="finder-source-locations/1", record_id="s2-test", source_root=tmp,
                      ui_thread_ids=["t"], threads=[dict(thread_id="t", state="WAITING", frames=frames)], call_edges=[])
      missing, stale, ambiguous, gap, traversal, many = [copy.deepcopy(original) for _ in range(6)]
      missing["threads"][0]["frames"][2]["source"] = copy.deepcopy(empty)
      stale["threads"][0]["frames"][2]["source"]["selected"]["sha256"] = "0" * 64
      ambiguous["threads"][0]["frames"][2]["source"].update(status="AMBIGUOUS", selected=None, reason="METHOD_NOT_FOUND")
      gap["threads"][0]["frames"][1]["index"] = 8
      traversal["threads"][0]["frames"][2]["source"]["selected"]["path"] = "../ProgressIndicatorUtils.java"
      for i in range(3, 10):
        f = copy.deepcopy(frames[2])
        f.update(frame_id=f"f{i}", index=i)
        many["threads"][0]["frames"].append(f)
      cases = [original, missing, stale, ambiguous, gap, traversal, many, original]
      command = ["java", "-cp", os.environ["Q1_CLASSPATH"], "org.jetbrains.research.lockrepair.Q2SynchronousWaitControlClassifier"]
      run = subprocess.run(command + ["--s2-repair-selection"], input="".join(json.dumps(r)+"\n" for r in cases),
                           capture_output=True, text=True, encoding="utf-8", check=True)
      results = [json.loads(line) for line in run.stdout.splitlines()]
      self.assertEqual(len(cases), len(results))
      op = results[0]["method_context_s2"]["operations"][0]
      self.assertEqual(1, len(results[0]["method_context_s2"]["operations"]))
      self.assertGreater(len(op["evidence_frames"]), 1)
      self.assertEqual(text.rstrip(), op["method_contexts"][0]["method"]["source_text"])
      d = results[0]["repair_selection_s2"]["decisions"][0]
      self.assertEqual("CANDIDATES_RANKED", d["status"])
      self.assertEqual("P2_ASYNC_CONTINUATION", d["recommended_strategy"])
      self.assertNotIn("selected_strategy", d)  # Gson omits a null; no safe final strategy asserted.
      strategies = {s["strategy"]: s for s in d["candidates"]}
      self.assertEqual("NOT_APPLICABLE", strategies["P3_ASYNC_DISPATCH"]["status"])
      p3 = strategies["P3_ASYNC_DISPATCH"]
      self.assertFalse(p3["eligible_for_generation"])
      self.assertEqual("REJECTED_SENDER", p3["preconditions_status"])
      self.assertEqual("FAIL", p3["checks"][1]["status"])
      self.assertEqual({
        "NO_SYNCHRONOUS_RESULT_OR_COMPLETION_DEPENDENCY",
        "LOCK_TRANSACTION_AND_MODALITY_PRESERVED", "LIFETIME_AND_CAPTURED_DATA_VALID",
        "ASYNC_FAILURE_HANDLING_PRESERVED",
      }, {c["id"] for c in p3["checks"][2:]})
      self.assertTrue(all(c["status"] == "UNKNOWN" for c in p3["checks"][2:]))
      self.assertEqual("UNKNOWN", strategies["G1_FAIL_FAST_ON_EDT"]["checks"][1]["status"])
      self.assertEqual("UNKNOWN", strategies["P1_BOUND_WAIT"]["checks"][1]["status"])
      self.assertFalse(d["patch_generated"])
      self.assertEqual("SKIPPED_SOURCE_UNAVAILABLE", results[1]["repair_selection_s2"]["decisions"][0]["status"])
      for index in [2, 3, 4, 5]:
        self.assertEqual("INSUFFICIENT_EVIDENCE", results[index]["repair_selection_s2"]["decisions"][0]["status"])
      self.assertEqual("INCOMPLETE_STACK_PATH", results[4]["method_context_s2"]["operations"][0]["stop_reason"])
      self.assertEqual(5, len(results[6]["method_context_s2"]["operations"][0]["method_contexts"]))
      self.assertEqual("CANDIDATES_RANKED", results[7]["repair_selection_s2"]["status"])
      baseline = subprocess.run(command, input=json.dumps(original)+"\n", capture_output=True,
                                text=True, encoding="utf-8", check=True)
      self.assertEqual(json.loads(baseline.stdout)["classification"], results[0]["classification"])
      # Current Q2 does not classify a BGT invokeAndWait as a UI wait.
      background = copy.deepcopy(original)
      background["ui_thread_ids"] = []
      run = subprocess.run(command+["--s2-repair-selection"], input=json.dumps(background)+"\n",
                           capture_output=True, text=True, encoding="utf-8", check=True)
      self.assertEqual("NOT_APPLICABLE", json.loads(run.stdout)["repair_selection_s2"]["status"])
      sender = copy.deepcopy(original)
      bg = copy.deepcopy(original["threads"][0])
      bg["thread_id"] = "bg"
      for i, frame in enumerate(bg["frames"]):
        frame["frame_id"] = f"bg{i}"
      bg["frames"][1]["symbol"] = "javax.swing.SwingUtilities.invokeAndWait"
      sender["threads"].append(bg)
      variants = [sender]
      for mode in ("lambda", "gap", "running"):
        bad = copy.deepcopy(sender)
        if mode == "lambda":
          bad["threads"][1]["frames"][1]["symbol"] += "$lambda$0"
        elif mode == "gap":
          bad["threads"][1]["frames"][0]["index"] = 9
        else:
          bad["threads"][1]["state"] = "RUNNABLE"
        variants.append(bad)
      run = subprocess.run(command+["--s2-repair-selection"],
                           input="".join(json.dumps(r)+"\n" for r in variants),
                           capture_output=True, text=True, encoding="utf-8", check=True)
      parsed = [json.loads(line) for line in run.stdout.splitlines()]
      self.assertEqual([2, 1, 1, 1], [len(r["method_context_s2"]["operations"]) for r in parsed])
      operation = parsed[0]["method_context_s2"]["operations"][1]
      self.assertEqual("BACKGROUND_DISPATCH_CANDIDATE", operation["operation_role"])
      self.assertEqual(text.rstrip(), operation["method_contexts"][0]["method"]["source_text"])
      p3 = next(c for c in parsed[0]["repair_selection_s2"]["decisions"][1]["candidates"]
                if c["strategy"] == "P3_ASYNC_DISPATCH")
      self.assertFalse(p3["eligible_for_generation"])
      self.assertTrue(p3["analysis_context"]["sender_source_available"])
      self.assertEqual("NOT_ESTABLISHED", p3["analysis_context"]["edt_task_association"])
      # Test injection is retained as evidence, never promoted to a repair recommendation.
      injected = copy.deepcopy(original)
      injected["threads"][0]["frames"][0]["symbol"] = "java.lang.Thread.sleep"
      injected["threads"][0]["frames"][1]["symbol"] = "com.intellij.internal.UIFreezeAction.actionPerformed"
      run = subprocess.run(command+["--s2-repair-selection"], input=json.dumps(injected)+"\n",
                           capture_output=True, text=True, encoding="utf-8", check=True)
      self.assertEqual("SKIPPED_TEST_PATH", json.loads(run.stdout)["repair_selection_s2"]["decisions"][0]["status"])

  def test_s2_cli_requires_q2_classpath(self):
    root = Path(__file__).resolve().parents[2]
    run = subprocess.run([sys.executable, str(root / "repair/main/python/repair.py"), "--input", "unused",
                          "--output", "unused", "--s2-repair-selection"], capture_output=True, text=True, encoding="utf-8")
    self.assertEqual(2, run.returncode)
    self.assertIn("requires --q2-classpath", run.stderr)

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
