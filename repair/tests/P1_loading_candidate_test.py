"""Source-generated Kotlin/coroutine/Swing probe; not a complete IntelliJ plugin integration test."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "repair/tests/fixtures/P1-preload-bindings"
TARGET = "plugins/terminal/frontend/src/com/intellij/terminal/frontend/fus/TerminalFocusFusService.kt"

HARNESS = r'''
import kotlinx.coroutines.*
import java.awt.Component
import java.awt.KeyboardFocusManager
import java.awt.Toolkit
import java.awt.AWTEvent.FOCUS_EVENT_MASK
import java.awt.AWTEvent.WINDOW_FOCUS_EVENT_MASK
import java.awt.event.AWTEventListener
import java.awt.event.FocusEvent
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import javax.swing.SwingUtilities
import kotlin.coroutines.CoroutineContext

val Dispatchers.UI: CoroutineDispatcher get() = object : CoroutineDispatcher() {
  override fun dispatch(context: CoroutineContext, block: Runnable) { SwingUtilities.invokeLater(block) }
}
data class Inputs(val hasFocusedWindow: Boolean, val focusedComponent: Component?)
fun reduceFocusEvent(id: Int, source: Component?, window: Boolean, owner: Component?): Inputs? =
  if (id == FocusEvent.FOCUS_GAINED) Inputs(window, source) else null

class Probe(val coroutineScope: CoroutineScope, val fail: Boolean = false) {
  private val initialized = AtomicBoolean(false)
  val entered = CountDownLatch(1)
  val release = CountDownLatch(1)
  val installed = CountDownLatch(1)
  var prepareOnEdt = false
  var updates = 0
  var initializationOnEdt = false
  private fun prepareProbe() {
    prepareOnEdt = SwingUtilities.isEventDispatchThread()
    entered.countDown()
    check(release.await(5, TimeUnit.SECONDS))
    if (fail) error("preparation failure")
  }
  private fun updateState(window: Boolean, component: Component?) {
    check(SwingUtilities.isEventDispatchThread())
    initializationOnEdt = true
    updates++
  }
  private suspend fun collectState() { awaitCancellation() }
  fun start() { ensureInitialized() }
  // Exact generated method block, apart from explicit probe hooks around preparation/registration.
  /*METHODS*/
}
fun await(latch: CountDownLatch) { check(latch.await(5, TimeUnit.SECONDS)) }
fun main(args: Array<String>) = runBlocking {
  val fixed = args[0] == "fixed"
  val mask = FOCUS_EVENT_MASK or WINDOW_FOCUS_EVENT_MASK
  val toolkit = Toolkit.getDefaultToolkit()
  val initialListeners = toolkit.getAWTEventListeners(mask).size
  val errors = mutableListOf<Throwable>()
  val handler = CoroutineExceptionHandler { _, e -> synchronized(errors) { errors.add(e) } }
  suspend fun runCase(cancel: Boolean, fail: Boolean) {
    val job = SupervisorJob()
    val probe = Probe(CoroutineScope(job + Dispatchers.Default + handler), fail)
    SwingUtilities.invokeAndWait { probe.start(); probe.start() }
    await(probe.entered)
    val heartbeat = CountDownLatch(1)
    SwingUtilities.invokeLater { heartbeat.countDown() }
    if (fixed) { await(heartbeat); check(!probe.prepareOnEdt) }
    else { check(!heartbeat.await(100, TimeUnit.MILLISECONDS)); check(probe.prepareOnEdt) }
    if (cancel) job.cancel()
    probe.release.countDown()
    if (!cancel && !fail) {
      await(probe.installed)
      SwingUtilities.invokeAndWait {
        check(probe.initializationOnEdt)
        val listeners = toolkit.getAWTEventListeners(mask)
        check(listeners.size == initialListeners + 1)
        val before = probe.updates
        val event = FocusEvent(javax.swing.JPanel(), FocusEvent.FOCUS_GAINED)
        listeners.forEach { it.eventDispatched(event) }
        check(probe.updates == before + 1)
      }
    }
    if (fail) {
      // Join initialization through its children; the collector remains suspended until cancellation.
      repeat(100) { if (synchronized(errors) { errors.isEmpty() }) delay(10) }
      check(synchronized(errors) { errors.any { it.message == "preparation failure" } })
    }
    job.cancelAndJoin()
    SwingUtilities.invokeAndWait {}
    check(toolkit.getAWTEventListeners(mask).size == initialListeners)
    if (fixed && (cancel || fail)) check(probe.updates == 0)
  }
  runCase(false, false)
  if (fixed) { runCase(true, false); runCase(false, true) }
  println("${args[0]}: heartbeat, UI callback, single registration and cleanup passed")
}
'''


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build Q1 first")
class P1LoadingCandidateTest(unittest.TestCase):
  def worker(self, record):
    run = subprocess.run(["java", "-cp", os.environ["Q1_CLASSPATH"],
                          "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier", "--s1-loading"],
                         input=json.dumps(record)+"\n", capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)
    return json.loads(run.stdout)["s1_loading"]

  def test_patch_refusals_and_generated_coroutine_behavior(self):
    records = [json.loads(s) for s in (FIXTURE/"P1-finder.jsonl").read_text(encoding="utf-8").splitlines()]
    record = next(r for r in records if r["record_id"] == "workbook-row-890")
    with tempfile.TemporaryDirectory(dir=ROOT/"out") as tmp:
      root = Path(tmp)
      with zipfile.ZipFile(FIXTURE/"P1-reviewed-sources.zip") as archive:
        archive.extractall(root)
      record["source_root"] = tmp
      result = self.worker(record)
      proposal = result["proposals"][0]
      self.assertFalse(proposal["eligible_for_application"])
      original = (root/TARGET).read_text(encoding="utf-8")
      gap = copy.deepcopy(record)
      for t in gap["threads"]:
        for f in t["frames"]:
          if (f.get("symbol") or "").endswith("java.lang.invoke.LambdaMetafactory.metafactory"):
            f["elided"] = True
      self.assertFalse(self.worker(gap)["proposals"])
      patch = root/"candidate.patch"
      patch.write_text(proposal["patch"], encoding="utf-8", newline="\n")
      for flags in [["--check"], []]:
        run = subprocess.run(["git", "apply", *flags, str(patch)], cwd=tmp, capture_output=True, text=True)
        self.assertEqual(0, run.returncode, run.stderr)
      self.assertEqual(proposal["replacement_source"], (root/TARGET).read_text(encoding="utf-8"))
      self.assertFalse(self.worker(record)["proposals"], "Do not reapply to modified source")
      deps_root = Path(os.environ["Q1_CLASSPATH"].split(os.pathsep)[0]).parent
      deps = os.pathsep.join(str(p) for p in deps_root.glob("*.jar") if p.name != "q1.jar")
      for name, source in [("original", original), ("fixed", proposal["replacement_source"])]:
        methods = source[source.index("  private fun ensureInitialized()"):source.index("  internal fun updateFocusStateForTest")]
        marker = "    return AWTEventListener" if name == "fixed" else "    val listener = AWTEventListener"
        methods = methods.replace(marker, "    prepareProbe()\n"+marker)
        registration = "    Toolkit.getDefaultToolkit().addAWTEventListener(listener, FOCUS_EVENT_MASK or WINDOW_FOCUS_EVENT_MASK)"
        methods = methods.replace(registration, registration+"\n    installed.countDown()")
        code = root/"Probe.kt"
        code.write_text(HARNESS.replace("/*METHODS*/", methods), encoding="utf-8")
        jar = root/(name+".jar")
        build = subprocess.run(["java", "-cp", deps, "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect",
                                "-classpath", deps, "-d", str(jar), str(code)], capture_output=True, text=True, timeout=60)
        self.assertEqual(0, build.returncode, build.stderr)
        run = subprocess.run(["java", "-Djava.awt.headless=true", "-cp", str(jar)+os.pathsep+deps, "ProbeKt", name],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(0, run.returncode, run.stdout+run.stderr)
        print(run.stdout.strip())


if __name__ == "__main__":
  unittest.main()
