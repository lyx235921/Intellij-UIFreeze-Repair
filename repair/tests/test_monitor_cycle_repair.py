import copy
import json
import os
import subprocess
import unittest


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build classifiers first")
class MonitorCycleTest(unittest.TestCase):
  def test_admission_and_source_gate(self):
    symbols = ["java.lang.Object.wait0", "java.awt.EventQueue.invokeAndWait", "java.awt.Window.doDispose",
               "java.awt.Container.remove", "com.intellij.openapi.wm.impl.ToolWindowImpl.setAvailable",
               "example.Plugin.update"]
    r = dict(schema_version="finder-source-locations/1", record_id="not-row-bound", ui_thread_ids=["ui"], threads=[
      dict(thread_id="ui", name="edt", state="BLOCKED", details="on java.awt.Component$AWTTreeLock@123 owned by worker", frames=[]),
      dict(thread_id="bg", name="worker", state="WAITING", details=None, frames=[
        dict(frame_id=f"b{i}", index=i, symbol=s, elided=False,
             source=dict(status="UNRESOLVED", reason="SOURCE_FILE_NOT_FOUND", candidates=[], selected=None))
        for i, s in enumerate(symbols)])])
    cases = [r]
    for kind in ("no_owner", "sleep", "gap", "other_lock", "source_present"):
      value = copy.deepcopy(r)
      if kind == "no_owner": value["threads"][0]["details"] = "on java.awt.Component$AWTTreeLock@123"
      if kind == "sleep": value["threads"][1]["frames"][0]["symbol"] = "java.lang.Thread.sleep"
      if kind == "gap": value["threads"][1]["frames"][1]["index"] = 7
      if kind == "other_lock": value["threads"][0]["details"] = "on java.lang.Object@123 owned by worker"
      if kind == "source_present": value["threads"][1]["frames"][-1]["source"]["reason"] = "METHOD_NOT_FOUND"
      cases.append(value)
    run = subprocess.run(["java", "-cp", os.environ["Q1_CLASSPATH"],
                          "org.jetbrains.research.lockrepair.Q2SynchronousWaitControlClassifier"],
                         input="".join(json.dumps(v)+"\n" for v in cases), capture_output=True,
                         text=True, encoding="utf-8", check=True)
    results = [json.loads(l)["monitor_cycle_repair"] for l in run.stdout.splitlines()]
    self.assertEqual([1, 0, 0, 0, 0, 1], [len(v["candidates"]) for v in results])
    self.assertEqual("BLOCKED_SOURCE_UNAVAILABLE", results[0]["candidates"][0]["status"])
    self.assertEqual("example.Plugin.update", results[0]["candidates"][0]["repair_entry_symbol"])
    self.assertEqual("REQUIRES_CALLER_CONTRACT_ANALYSIS", results[-1]["candidates"][0]["status"])
    self.assertTrue(all(not v["patch_generated"] for v in results))
