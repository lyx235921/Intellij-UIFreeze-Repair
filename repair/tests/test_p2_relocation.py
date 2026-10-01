"""Compile and exercise generated Java with real Swing EDT and controlled native/window seams."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

HARNESS = r'''
import java.awt.image.BufferedImage;
import java.util.Objects;
import javax.imageio.ImageIO;
import javax.swing.SwingUtilities;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public class AppIcon {
  @interface Nullable {}
  static class JFrame {
    volatile boolean valid = true;
    volatile int checks;
    volatile WinDef.HICON overlay;
    boolean isDisplayable() { return valid; }
  }
  static class WinDef { static class HICON {} }
  static class EDT {
    static void assertIsEdt() { if (!SwingUtilities.isEventDispatchThread()) throw new AssertionError("not EDT"); }
  }
  static class LOG {
    static final AtomicInteger errors = new AtomicInteger();
    static void error(Throwable e) { EDT.assertIsEdt(); e.printStackTrace(); errors.incrementAndGet(); }
  }
  static class Win7TaskBar {
    static WinDef.HICON createIcon(byte[] bytes) {
      EDT.assertIsEdt();
      if (bytes.length != 1 || bytes[0] != 7) throw new AssertionError("wrong result");
      return new WinDef.HICON();
    }
    static void setOverlayIcon(JFrame f, WinDef.HICON icon, boolean ignored) { EDT.assertIsEdt(); f.overlay = icon; }
  }
  static class Base { public void _setOkBadge(JFrame frame, boolean visible) {} }
  static volatile CountDownLatch gate = new CountDownLatch(1);
  static volatile CountDownLatch started = new CountDownLatch(1);
  static volatile boolean fail;
  static final AtomicInteger preparations = new AtomicInteger();
  static byte[] writeTransparentIco(BufferedImage image) throws java.io.IOException {
    if (SwingUtilities.isEventDispatchThread()) throw new AssertionError("preparation on EDT");
    preparations.incrementAndGet(); started.countDown();
    try { if (!gate.await(5, TimeUnit.SECONDS)) throw new AssertionError("gate timeout"); }
    catch (InterruptedException e) { throw new AssertionError(e); }
    if (fail) throw new java.io.IOException("controlled failure");
    if (image.getWidth() != 2) throw new AssertionError("PNG decode changed");
    return new byte[] {7};
  }
  static class Win7AppIcon extends Base {
    private WinDef.HICON myOkIcon;
    boolean isValid(JFrame f) { EDT.assertIsEdt(); if (f != null) f.checks++; return f != null && f.valid; }
    /*REPLACEMENT*/
  }
  static void edt(Runnable r) throws Exception { SwingUtilities.invokeAndWait(r); }
  static void until(java.util.function.BooleanSupplier condition) throws Exception {
    long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
    while (!condition.getAsBoolean()) {
      if (System.nanoTime() > end) throw new AssertionError("condition timeout");
      edt(() -> {}); Thread.sleep(5);
    }
  }
  static void check(boolean ok) { if (!ok) throw new AssertionError(); }
  public static void main(String[] args) throws Exception {
    // Avoid sandbox entropy/temp-file initialization; production ImageIO policy is unchanged.
    ImageIO.setUseCache(false);
    java.nio.file.Path png = java.nio.file.Path.of(args[0], "mac", "appIconOk512.png");
    java.nio.file.Files.createDirectories(png.getParent());
    ImageIO.write(new BufferedImage(2, 2, BufferedImage.TYPE_INT_ARGB), "png", png.toFile());
    Win7AppIcon app = new Win7AppIcon(); JFrame hidden = new JFrame(); JFrame shown = new JFrame();
    JFrame closed = new JFrame();
    edt(() -> { app._setOkBadge(hidden, true); app._setOkBadge(hidden, true);
                app._setOkBadge(shown, true); app._setOkBadge(closed, true); });
    if (!started.await(5, TimeUnit.SECONDS)) {
      Thread.getAllStackTraces().forEach((thread, trace) -> {
        System.err.println(thread);
        for (StackTraceElement e : trace) System.err.println(e);
      });
      throw new AssertionError("preparation never started");
    }
    AtomicBoolean heartbeat = new AtomicBoolean();
    edt(() -> { heartbeat.set(true); app._setOkBadge(hidden, false); closed.valid = false; });
    check(heartbeat.get() && preparations.get() == 1);
    int hiddenChecks = hidden.checks, closedChecks = closed.checks;
    gate.countDown();
    until(() -> shown.overlay != null && hidden.checks >= hiddenChecks + 2 && closed.checks > closedChecks);
    check(hidden.overlay == null && closed.overlay == null);
    edt(() -> app._setOkBadge(hidden, true)); check(hidden.overlay != null && preparations.get() == 1);
    Win7AppIcon retry = new Win7AppIcon(); JFrame retried = new JFrame();
    fail = true; gate = new CountDownLatch(0); started = new CountDownLatch(1);
    edt(() -> retry._setOkBadge(retried, true)); until(() -> LOG.errors.get() == 1);
    fail = false;
    edt(() -> retry._setOkBadge(retried, true)); until(() -> retried.overlay != null);
    check(preparations.get() == 3);
    System.out.println("PASS: background preparation, EDT heartbeat/native calls, shared load, hide, disposal, cache, retry");
  }
}
'''


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build and set Q1_CLASSPATH")
class P2RelocationTest(unittest.TestCase):
  def test_generated_patch_and_behavior(self):
    record = json.loads((ROOT / "repair/tests/fixtures/row1238-finder.json").read_text(encoding="utf-8"))
    changed = copy.deepcopy(record)
    source = changed["threads"][0]["frames"][7]["source"]
    source["selected"]["sha256"] = "0" * 64
    for c in source["candidates"]:
      c["sha256"] = "0" * 64
    unsupported = copy.deepcopy(record)
    unsupported["threads"][0]["frames"][7]["source"]["selected"]["owner"] = "example.Other"
    for c in unsupported["threads"][0]["frames"][7]["source"]["candidates"]:
      c["owner"] = "example.Other"
    p = subprocess.run(["java", "-cp", os.environ["Q1_CLASSPATH"],
                        "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier", "--s1-p2"],
                       input="".join(json.dumps(r) + "\n" for r in (record, changed, unsupported)),
                       text=True, encoding="utf-8", capture_output=True, check=True)
    outputs = [json.loads(l) for l in p.stdout.splitlines()]
    self.assertEqual("repair-method-context/1", outputs[0]["method_context"]["schema_version"])
    self.assertEqual(["CANDIDATE_PATCH", "NO_SUPPORTED_METHOD", "NO_SUPPORTED_METHOD"],
                     [o["s1_p2"]["status"] for o in outputs])
    proposal = outputs[0]["s1_p2"]["proposals"][0]
    self.assertFalse(outputs[0]["s1_p2"]["applied"])
    with tempfile.TemporaryDirectory() as tmp:
      input_path, output_path = Path(tmp) / "finder.jsonl", Path(tmp) / "repair.jsonl"
      input_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
      subprocess.run([sys.executable, str(ROOT / "repair/main/python/repair.py"), "--input", str(input_path),
                      "--output", str(output_path), "--q1-classpath", os.environ["Q1_CLASSPATH"], "--s1-p2"],
                     capture_output=True, check=True)
      intake = json.loads(output_path.read_text(encoding="utf-8"))
      self.assertEqual(record, intake["finder"])
      self.assertEqual("CANDIDATE_PATCH", intake["q1"]["s1_p2"]["status"])
      source = Path(tmp) / "AppIcon.java"
      source.write_text(HARNESS.replace("/*REPLACEMENT*/", proposal["replacement"]), encoding="utf-8")
      subprocess.run(["javac", "-encoding", "UTF-8", str(source)], check=True, capture_output=True)
      run = subprocess.run(["java", "-Djava.awt.headless=true", "-cp", tmp, "AppIcon", tmp],
                           capture_output=True, text=True, timeout=20)
      self.assertEqual(0, run.returncode, run.stdout + run.stderr)
      self.assertIn("PASS:", run.stdout)
      print(run.stdout.strip())
      # Apply-check the emitted patch against a pristine copy, not production source.
      target = Path(tmp) / proposal["path"]
      target.parent.mkdir(parents=True, exist_ok=True)
      target.write_bytes((Path(record["source_root"]) / proposal["path"]).read_bytes())
      patch = Path(tmp) / "candidate.patch"
      patch.write_text(proposal["patch"], encoding="utf-8", newline="\n")
      checked = subprocess.run(["git", "apply", "--check", str(patch)], cwd=tmp, capture_output=True, text=True)
      self.assertEqual(0, checked.returncode, checked.stderr)


if __name__ == "__main__":
  unittest.main()
