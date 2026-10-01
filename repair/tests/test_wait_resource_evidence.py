"""Thread-to-reported-object association; never infer resource ownership."""
import json
import os
import subprocess
import unittest


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build classifiers first")
class WaitResourceTest(unittest.TestCase):
  def test_explicit_monitor_owners(self):
    cases = [("worker", ["worker"]), ("worker", []), ("worker", ["worker", "worker"]),
             (None, ["worker"]), ("edt", []), ("worker", ["Worker"])]
    records = []
    for owner, names in cases:
      threads = [dict(thread_id="ui", name="edt", state="BLOCKED", frames=[],
                      details="on java.lang.Object@123" + (" owned by " + owner if owner else ""))]
      threads += [dict(thread_id=f"b{i}", name=name, state="WAITING", details=None, frames=[])
                  for i, name in enumerate(names)]
      records.append(dict(schema_version="finder-source-locations/1", record_id=str(len(records)),
                          ui_thread_ids=["ui"], threads=threads))
    run = subprocess.run(["java", "-cp", os.environ["Q1_CLASSPATH"],
                          "org.jetbrains.research.lockrepair.Q2SynchronousWaitControlClassifier"],
                         input="".join(json.dumps(r)+"\n" for r in records), capture_output=True,
                         text=True, encoding="utf-8", check=True)
    results = [json.loads(line)["wait_resource_evidence"] for line in run.stdout.splitlines()]
    associations = [r["monitor_owner_associations"][0] for r in results]
    self.assertEqual(["REPORTED_OWNER_LINKED", "OWNER_THREAD_MISSING", "OWNER_NAME_AMBIGUOUS",
                      "OWNER_NOT_REPORTED", "INCONSISTENT_SELF_OWNER", "OWNER_THREAD_MISSING"],
                     [a["status"] for a in associations])
    self.assertEqual("b0", associations[0]["owner_thread_id"])
    self.assertEqual("r0", associations[0]["resource_id"])
    self.assertTrue(all("owner_thread_id" not in a for a in associations[1:]))
    self.assertTrue(all(r["resource_cycle_status"] == "NOT_ANALYZED" for r in results))

  def test_edt_monitor_blocking_with_and_without_label(self):
    records = []
    for state, details, ui in [("BLOCKED", "on java.lang.Object@123", True),
                               ("BLOCKED", None, True), ("BLOCKED", "unrecognized", True),
                               ("WAITING", "on java.lang.Object@123", True),
                               ("BLOCKED", "on java.lang.Object@123", False)]:
      records.append(dict(schema_version="finder-source-locations/1", record_id=str(len(records)),
                          ui_thread_ids=["t"] if ui else [],
                          threads=[dict(thread_id="t", state=state, details=details, frames=[])]))
    run = subprocess.run(["java", "-cp", os.environ["Q1_CLASSPATH"],
                          "org.jetbrains.research.lockrepair.Q2SynchronousWaitControlClassifier"],
                         input="".join(json.dumps(r)+"\n" for r in records), capture_output=True,
                         text=True, encoding="utf-8", check=True)
    outputs = [json.loads(line) for line in run.stdout.splitlines()]
    observations = [r["wait_resource_evidence"]["observations"][0] for r in outputs]
    for o in observations[:3]:
      self.assertEqual("MONITOR_ENTRY_BLOCKED", o["wait_kind"])
    self.assertEqual("REPORTED_LABEL_LINKED", observations[0]["monitor_object_status"])
    self.assertEqual("r0", observations[0]["resource_id"])
    for o in observations[1:3]:
      self.assertEqual("LABEL_MISSING_OR_UNRECOGNIZED", o["monitor_object_status"])
      self.assertNotIn("resource_id", o)
    for o in observations[3:]:
      self.assertEqual("UNCLASSIFIED_WAIT", o["wait_kind"])
      self.assertNotIn("monitor_object_status", o)
    self.assertTrue(all(r["classification"]["q2_count"] == 0 for r in outputs))

  def test_objects_states_and_record_scope(self):
    def record(record_id):
      return dict(schema_version="finder-source-locations/1", record_id=record_id, ui_thread_ids=["t0"],
                  threads=[dict(thread_id=f"t{i}", state=state, details=details, frames=[])
                           for i, (state, details) in enumerate([
                             ("TIMED_WAITING", "on java.util.concurrent.FutureTask@ABC123"),
                             ("WAITING", "on java.util.concurrent.FutureTask@abc123"),
                             ("WAITING", "on java.util.concurrent.CompletableFuture$Signaller@123"),
                             ("RUNNABLE", "on java.lang.Object@555"),
                             ("WAITING", None),
                             ("BLOCKED", "on java.lang.Object@555 owned by worker"),
                             ("WAITING", "on invalid@nothex"),
                           ])])
    run = subprocess.run(["java", "-cp", os.environ["Q1_CLASSPATH"],
                          "org.jetbrains.research.lockrepair.Q2SynchronousWaitControlClassifier"],
                         input="".join(json.dumps(record(i))+"\n" for i in ("one", "two")),
                         capture_output=True, text=True, encoding="utf-8", check=True)
    outputs = [json.loads(line)["wait_resource_evidence"] for line in run.stdout.splitlines()]
    self.assertEqual(["one", "two"], [o["record_id"] for o in outputs])
    for out in outputs:
      self.assertEqual(3, len(out["resources"]))
      self.assertEqual(["t0", "t1"], out["resources"][0]["waiting_thread_ids"])
      self.assertEqual("WAITER_NODE_NOT_THE_FUTURE", out["resources"][1]["semantic_resource_status"])
      self.assertEqual("NOT_WAITING", out["observations"][3]["status"])
      for i in (4, 6):
        self.assertEqual("RESOURCE_LABEL_UNAVAILABLE", out["observations"][i]["status"])
        self.assertNotIn("resource_id", out["observations"][i])
      self.assertTrue(all(r["owner_status"] == "NOT_ESTABLISHED" for r in out["resources"]))
      self.assertEqual("NOT_ANALYZED", out["resource_cycle_status"])


if __name__ == "__main__":
  unittest.main()
