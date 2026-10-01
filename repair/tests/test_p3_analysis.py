"""Exercise source analysis through the real extraction and selection pipeline."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build classifiers first")
class P3AnalysisTest(unittest.TestCase):
  def test_ast_contracts_and_unknowns(self):
    sources = [
      'fun send() { var result = 0; invokeAndWait { result = 1 }; consume(result) }',
      'fun send() { synchronized(lock) { invokeAndWait { work() } } }',
      'fun send() { val r = captureContextCancellationForRunnableThatDoesNotOutliveContextScope { work() }; invokeAndWait(r) }',
      'fun send() { try { invokeAndWait { work() } } catch (e: Exception) { report(e) } }',
      'fun send() { invokeAndWait { } }',
      'fun send() { /* synchronized(lock) throw error */ val text = "transferWriteActionAndBlock"; invokeAndWait { } }',
      'fun send() { invokeAndWait { ',
      'fun invokeAndWaitWithTransferredWriteAction(r: Runnable) { lock.transferWriteActionAndBlock({}, r) }',
      'void send() { invokeAndWait(() -> work()); consume(); }',
      'synchronized void send() { invokeAndWait(() -> work()); }',
      'void send() { try { invokeAndWait(() -> work()); } catch (Exception e) { report(e); } }',
      'void send() { /* throw error; synchronized(lock) */ invokeAndWait(() -> {}); }',
    ]
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / "out") as tmp:
      records = []
      for i, source in enumerate(sources):
        path = f"Case{i}.java" if i >= 8 else f"Case{i}.kt"
        Path(tmp, path).write_text(source, encoding="utf-8")
        method = dict(path=path, sha256=hashlib.sha256(source.encode()).hexdigest(), start_line=1, end_line=1)
        def frame(index, symbol, prefix, located=False):
          return dict(index=index, symbol=symbol, frame_id=f"{prefix}{index}", elided=False, file=path,
                      source=dict(status="LOCATED" if located else "UNRESOLVED", reason=None,
                                  candidates=[method] if located else [], selected=method if located else None))
        ui = [frame(0, "jdk.internal.misc.Unsafe.park", "u"),
              frame(1, "com.intellij.openapi.progress.util.ProgressIndicatorUtils.awaitWithCheckCanceled", "u")]
        bg = [frame(0, "jdk.internal.misc.Unsafe.park", "b"),
              frame(1, "javax.swing.SwingUtilities.invokeAndWait", "b"), frame(2, "example.Case.send", "b", True)]
        if i == 7:
          bg[2]["symbol"] = "com.intellij.openapi.application.impl.InternalThreading.invokeAndWaitWithTransferredWriteAction"
        records.append(dict(schema_version="finder-source-locations/1", record_id=str(i), source_root=tmp,
                            ui_thread_ids=["ui"], call_edges=[], threads=[
                              dict(thread_id="ui", state="WAITING", frames=ui),
                              dict(thread_id="bg", state="WAITING", frames=bg)]))
      run = subprocess.run(["java", "-cp", os.environ["Q1_CLASSPATH"],
                            "org.jetbrains.research.lockrepair.Q2SynchronousWaitControlClassifier", "--s2-repair-selection"],
                           input="".join(json.dumps(r)+"\n" for r in records), text=True, encoding="utf-8",
                           capture_output=True, check=True)
      analyses = []
      for line in run.stdout.splitlines():
        decision = json.loads(line)["repair_selection_s2"]["decisions"][1]
        p3 = next(c for c in decision["candidates"] if c["strategy"] == "P3_ASYNC_DISPATCH")
        self.assertFalse(p3["eligible_for_generation"])
        self.assertFalse(p3["recommended"])
        analyses.append(p3["semantic_analysis"])
      for i in range(4):
        self.assertEqual("NEEDS_ADAPTATION", analyses[i]["checks"][i]["status"], analyses[i])
        self.assertTrue(analyses[i]["checks"][i]["evidence"])
      for i in (4, 5, 6):
        self.assertTrue(all(c["status"] == "UNKNOWN" for c in analyses[i]["checks"]))
      self.assertIn("PARSE_ERROR:b2", analyses[6]["diagnostics"])
      self.assertIn("result", analyses[0]["dispatch_sites"][0]["callback_written_names"])
      self.assertEqual("FAIL", analyses[7]["checks"][1]["status"])
      self.assertEqual("REJECTED_CONTRACT", analyses[7]["status"])
      self.assertEqual("NEEDS_ADAPTATION", analyses[8]["checks"][0]["status"])
      self.assertEqual("NEEDS_ADAPTATION", analyses[9]["checks"][1]["status"])
      self.assertEqual("NEEDS_ADAPTATION", analyses[10]["checks"][3]["status"])
      self.assertTrue(all(c["status"] == "UNKNOWN" for c in analyses[11]["checks"]))


if __name__ == "__main__":
  unittest.main()
