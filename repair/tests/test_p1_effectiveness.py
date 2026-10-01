"""Paired controlled experiment, including the sync-refresh compatibility gate.

Compiles original/generated Java methods, but substitutes platform services and the
decoder. The 400ms I/O delay is injected; this is not a production freeze replay.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_p1_reload import HARNESS, ROOT


MAIN = r'''
  static volatile CountDownLatch ioStarted;
  static void slowRead() {
    ioStarted.countDown();
    try { Thread.sleep(400); } catch (InterruptedException e) { throw new AssertionError(e); }
  }
  public static void main(String[] args) throws Exception {
    Path folder = Path.of(args[0]);
    for (int iteration = 0; iteration < 3; iteration++) {
      Manager m = create(folder, "paired-" + iteration + ".txt");
      ioStarted = new CountDownLatch(1);
      AtomicBoolean readyAtReturn = new AtomicBoolean(), finalReady = new AtomicBoolean();
      AtomicReference<Throwable> error = new AtomicReference<>();
      CountDownLatch heartbeat = new CountDownLatch(1);
      AtomicLong latency = new AtomicLong();
      SwingUtilities.invokeLater(() -> {
        try {
          m.contentsChanged(new VFileContentChangeEvent(m.doc.file, m.doc.stamp));
          readyAtReturn.set(m.doc.stamp == m.doc.file.stamp && m.doc.text.equals("new text"));
        }
        catch (Throwable t) { error.set(t); }
      });
      check(ioStarted.await(20, TimeUnit.SECONDS));
      long sent = System.nanoTime();
      SwingUtilities.invokeLater(() -> { latency.set(System.nanoTime() - sent); heartbeat.countDown(); });
      check(heartbeat.await(10, TimeUnit.SECONDS));
      long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(25);
      while (!finalReady.get() && System.nanoTime() < deadline) {
        edt(() -> finalReady.set(m.doc.stamp == m.doc.file.stamp && m.doc.text.equals("new text")));
        Thread.sleep(5);
      }
      if (error.get() != null) throw new AssertionError(error.get());
      check(finalReady.get() && m.doc.replacements == 1);
      System.out.println("{\"iteration\":" + iteration + ",\"heartbeat_ms\":" + latency.get()/1000000.0 +
        ",\"ready_when_contentsChanged_returns\":" + readyAtReturn.get() + ",\"eventual_content_correct\":true}");
    }
  }
}
'''


class P1EffectivenessTest(unittest.TestCase):
  def test_paired_latency_and_existing_sync_contract(self):
    fixture = json.loads((ROOT / "repair/tests/fixtures/row4746-finder.json").read_text(encoding="utf-8"))
    evidence = ROOT / "out/edt-freeze-finder/p1-row4746-patch-20260927"
    proposal = json.loads((evidence / "proposal.json").read_text(encoding="utf-8"))
    path = proposal["source_contexts"][0]["path"]
    raw = (Path(fixture["source_root"]) / path).read_bytes()
    self.assertEqual(proposal["source_contexts"][0]["sha256"], hashlib.sha256(raw).hexdigest())
    original = raw.decode("utf-8").replace("\r\n", "\n")
    patched = proposal["replacement_source"]
    jars = [ROOT / "out/edt-freeze-finder/p1-test-deps" / (name + "-5.17.0.jar") for name in ("jna", "jna-platform")]
    self.assertTrue(all(jar.exists() for jar in jars), "Run test_p1_reload once to provision verified JNA dependencies")
    results = {}
    with tempfile.TemporaryDirectory(dir=ROOT / "out") as temp:
      folder = Path(temp)
      stub = folder / "com/intellij/openapi/vfs/LocalFileSystem.java"
      stub.parent.mkdir(parents=True)
      stub.write_text("package com.intellij.openapi.vfs; public class LocalFileSystem { "
                      "private static final LocalFileSystem INSTANCE=new LocalFileSystem(); "
                      "public static LocalFileSystem getInstance(){return INSTANCE;} }", encoding="utf-8")
      for name, full in (("original", original), ("candidate", patched)):
        generated = full[full.index("  public void contentsChanged("):full.index("  private void reloadFromDiskWithDecompiler(")]
        if name == "candidate":
          anchor = 'if (javax.swing.SwingUtilities.isEventDispatchThread()) throw new IllegalStateException("Disk read on EDT");'
          self.assertEqual(1, generated.count(anchor))
          generated = generated.replace(anchor, anchor + "\n    slowRead();")
        harness = HARNESS[:HARNESS.index("  static void noCommit(")] + MAIN
        harness = harness.replace("/*GENERATED*/", generated)
        harness = harness.replace("workers.add(work);", 'new Thread(work, "p1-probe-bgt").start();')
        harness = harness.replace("callbacks.add(callback);", "SwingUtilities.invokeLater(callback);")
        old = 'static CharSequence loadText(VirtualFile f) { syncReads++; return "sync"; }'
        self.assertIn(old, harness)
        harness = harness.replace(old, '''static CharSequence loadText(VirtualFile f) {
          syncReads++; slowRead();
          try {
            Files.size(f.path);
            return getTextByBinaryPresentation(Files.readAllBytes(f.path), f);
          } catch (java.io.IOException e) { throw new RuntimeException(e); }
        }''')
        java = folder / "ReloadProbe.java"
        java.write_text(harness, encoding="utf-8")
        cp = os.pathsep.join([str(folder)] + [str(jar) for jar in jars])
        compiled = subprocess.run(["javac", "-encoding", "UTF-8", "-cp", cp, "-d", temp, str(stub), str(java)],
                                  capture_output=True, text=True)
        self.assertEqual(0, compiled.returncode, compiled.stderr)
        run = subprocess.run(["java", "--enable-native-access=ALL-UNNAMED", "-Djava.awt.headless=true", "-cp", cp,
                              "ReloadProbe", temp], capture_output=True, text=True, timeout=50)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        results[name] = [json.loads(line) for line in run.stdout.splitlines()]
        self.assertEqual(3, len(results[name]))
    self.assertTrue(all(row["ready_when_contentsChanged_returns"] for row in results["original"]))
    self.assertTrue(all(not row["ready_when_contentsChanged_returns"] for row in results["candidate"]))
    report = {
      "row": 4746, "evidence_kind": "CONTROLLED_GENERATED_JAVA_WITH_PLATFORM_STUBS",
      "injected_io_delay_ms": 400, "runs": results,
      "correctness_gate_passed": False,
      "finding": "Candidate returns from content-change processing before document update, unlike original",
      "existing_test_reference": "FileDocumentManagerImplTest.testExternalReplaceWithTheSameText:598-608",
      "source_sha256": hashlib.sha256(raw).hexdigest(),
      "patch_sha256": hashlib.sha256((evidence / "candidate.patch").read_bytes()).hexdigest(),
      "production_source_modified": False, "target_ide_tests_executed": False,
      "target_test_blocker": "Bazel JPS model references missing repair/main/kotlin/intellij.tools.readWriteLock.repair.iml",
    }
    out = ROOT / "out/edt-freeze-finder/p1-row4746-verification-20260927"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
  unittest.main()
