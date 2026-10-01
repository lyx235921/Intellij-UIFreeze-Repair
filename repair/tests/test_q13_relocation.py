"""Real Finder evidence, patch application, and controlled Swing scheduling; not an IDE NBRA implementation test."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "repair/tests/fixtures/q13"
TARGET = "platform/platform-impl/src/com/intellij/openapi/vfs/impl/local/LocalFileSystemImpl.java"

HARNESS = r'''
import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;
import javax.swing.SwingUtilities;
public class RefreshProbe {
  static final ExecutorService executor = Executors.newSingleThreadExecutor();
  static class AppExecutorUtil { static ExecutorService getAppExecutorService() { return executor; } }
  static class ReadAction {
    static <T> NBRA<T> nonBlocking(Callable<T> task) { return new NBRA<>(task); }
  }
  // Models scheduling/disposal only. Real read locks, cancellation/retries and write-action interleaving are NOT simulated.
  static class NBRA<T> {
    final Callable<T> task; Base owner; Consumer<T> finish;
    NBRA(Callable<T> task) { this.task=task; }
    NBRA<T> expireWith(Base owner) { this.owner=owner; return this; }
    NBRA<T> finishOnUiThread(Object modality, Consumer<T> finish) { this.finish=finish; return this; }
    void submit(ExecutorService pool) { pool.execute(() -> {
      if (owner.disposed) return;
      try { T result=task.call(); SwingUtilities.invokeLater(() -> { if (!owner.disposed) finish.accept(result); }); }
      catch (Throwable error) { owner.error=error; owner.failed.countDown(); }
    }); }
  }
  static class Watcher { boolean operational; boolean isOperational() { return operational; } }
  static class ManagingFS { NewVirtualFile[] getRoots(Base owner) { return owner.roots; } }
  static class RefreshQueue {
    static final RefreshQueue instance=new RefreshQueue(); Runnable after; int calls;
    static RefreshQueue getInstance() { return instance; }
    void refresh(boolean async, boolean recursive, Runnable finish, NewVirtualFile[] roots) {
      check(async && recursive, "first phase arguments"); after=finish; calls++;
    }
    void fire() { Runnable next=after; after=null; next.run(); }
  }
  static class NewVirtualFile {
    final Base owner; NewVirtualFile(Base owner) { this.owner=owner; }
    void markDirtyRecursively() {
      owner.markOnEdt=SwingUtilities.isEventDispatchThread(); owner.entered.countDown();
      try { owner.release.await(); } catch (InterruptedException e) { throw new RuntimeException(e); }
      if (owner.fail) throw new IllegalStateException("storage failure");
      owner.dirty++;
    }
  }
  static abstract class Base {
    final Watcher myWatcher=new Watcher(); final ManagingFS myManagingFS=new ManagingFS();
    final NewVirtualFile[] roots={new NewVirtualFile(this),new NewVirtualFile(this)};
    final CountDownLatch entered=new CountDownLatch(1), release=new CountDownLatch(1), done=new CountDownLatch(1);
    final CountDownLatch failed=new CountDownLatch(1);
    volatile boolean disposed, markOnEdt, fail; volatile Throwable error; volatile int dirty, refreshed;
    abstract void refreshWithoutFileWatcher(boolean async);
    void refresh(boolean async) {
      check(SwingUtilities.isEventDispatchThread(), "refresh consumer must be EDT in this scenario");
      check(dirty==2,"refresh before all roots dirty"); refreshed++; done.countDown();
    }
  }
  static class Original extends Base { /*BEFORE*/ }
  static class Fixed extends Base { /*AFTER*/ }
  static void check(boolean ok,String message) { if(!ok)throw new AssertionError(message); }
  static void await(CountDownLatch latch) throws Exception { check(latch.await(5,TimeUnit.SECONDS),"timeout"); }
  static void flush() throws Exception { executor.submit(() -> {}).get(5,TimeUnit.SECONDS); SwingUtilities.invokeAndWait(() -> {}); }
  static void start(Base b,boolean async,boolean watcher) throws Exception {
    RefreshQueue.instance.after=null; RefreshQueue.instance.calls=0;b.myWatcher.operational=watcher;
    SwingUtilities.invokeAndWait(() -> b.refreshWithoutFileWatcher(async));
    if(async && watcher) {
      check(b.dirty==0 && b.entered.getCount()==1,"marking must wait for first refresh completion");
      check(RefreshQueue.instance.calls==1,"first phase count");
      SwingUtilities.invokeLater(() -> RefreshQueue.instance.fire());
    }
  }
  public static void main(String[] args) throws Exception {
    try {
      for(boolean watcher:new boolean[]{false,true}) {
        Fixed fixed=new Fixed();start(fixed,true,watcher);await(fixed.entered);
        CountDownLatch heartbeat=new CountDownLatch(1);SwingUtilities.invokeLater(heartbeat::countDown);
        await(heartbeat);check(fixed.refreshed==0 && !fixed.markOnEdt,"background preparation");
        fixed.release.countDown();await(fixed.done);flush();check(fixed.refreshed==1,"one final refresh");
        for(Base sync:new Base[]{new Original(),new Fixed()}) {
          sync.release.countDown();start(sync,false,watcher);
          check(sync.refreshed==1 && sync.dirty==2 && sync.markOnEdt,"synchronous completion changed");
          check(RefreshQueue.instance.calls==0,"sync must not use first async phase");
        }
      }
      Original old=new Original();old.myWatcher.operational=false;
      SwingUtilities.invokeLater(() -> old.refreshWithoutFileWatcher(true));await(old.entered);
      CountDownLatch heartbeat=new CountDownLatch(1);SwingUtilities.invokeLater(heartbeat::countDown);
      boolean blocked=!heartbeat.await(100,TimeUnit.MILLISECONDS);
      old.release.countDown();await(old.done);await(heartbeat);check(blocked && old.markOnEdt,"original EDT blocking not reproduced");
      Fixed disposed=new Fixed();start(disposed,true,false);await(disposed.entered);
      disposed.disposed=true;disposed.release.countDown();flush();check(disposed.refreshed==0,"disposed callback");
      Fixed failure=new Fixed();failure.fail=true;failure.release.countDown();start(failure,true,false);await(failure.failed);flush();
      check(failure.error instanceof IllegalStateException && failure.refreshed==0,"failure must not start final refresh");
      System.out.println("PASS: async watcher on/off; sync completion; EDT heartbeat; first/final ordering; modeled disposal/failure");
    } finally { executor.shutdownNow(); }
  }
}
'''


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build Q1 first")
class Q13RelocationTest(unittest.TestCase):
  def run_records(self, records):
    p = subprocess.run(["java", "-cp", os.environ["Q1_CLASSPATH"],
                        "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier", "--s1-q13"],
                       input="".join(json.dumps(r)+"\n" for r in records), capture_output=True,
                       text=True, encoding="utf-8", check=True, timeout=40)
    return [json.loads(line)["s1_q13"] for line in p.stdout.splitlines()]

  def test_all_five_triggers_and_admission(self):
    records=[json.loads(l) for l in (FIXTURE/"finder.jsonl").read_text(encoding="utf-8").splitlines()]
    with tempfile.TemporaryDirectory(dir=ROOT/"out") as tmp:
      with zipfile.ZipFile(FIXTURE/"reviewed-sources.zip") as z:
        z.extractall(tmp)
      for r in records: r["source_root"]=tmp
      results=self.run_records(records)
      symbols={d["trigger"]["symbol"] for r in results for d in r["decisions"]}
      self.assertEqual(5,len(symbols))
      self.assertEqual("CANDIDATE_PATCH",results[0]["status"])
      self.assertEqual(2,len(results[0]["decisions"]))
      self.assertEqual(1,len(results[0]["proposals"]))
      selected=subprocess.run(["java","-cp",os.environ["Q1_CLASSPATH"],
                               "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier","--repair-selection"],
                              input=json.dumps(records[0])+"\n",capture_output=True,text=True,encoding="utf-8",check=True)
      selection=json.loads(selected.stdout)["repair_selection"]
      self.assertEqual("CANDIDATE_SELECTED",selection["status"])
      for decision in selection["decisions"]:
        self.assertEqual("q13_evaluation",decision["selected_proposal_pool"])
        self.assertEqual("P2",decision["selected_strategy"])
        self.assertFalse(decision["p3_eligible"])
      for result in results[1:]:
        self.assertEqual("INSUFFICIENT_EVIDENCE",result["status"])
        for d in result["decisions"]:
          self.assertEqual("DEFERRED",d["p3_status"])
          self.assertFalse(d["patch_generated"])
          self.assertNotEqual("SOURCE_CONTEXT_CHANGED",d["reason"])
      record=records[0]
      wait=copy.deepcopy(record)
      for t in wait["threads"]:
        if t["is_ui_thread"]: t["state"]="WAITING"
      gap=copy.deepcopy(record)
      for t in gap["threads"]:
        for f in t["frames"]:
          if (f.get("symbol") or "").endswith("markDirtyRecursively"):
            f["elided"]=True
      missing=copy.deepcopy(record)
      for t in missing["threads"]:
        for f in t["frames"]:
          if "refreshWithoutFileWatcher" in (f.get("symbol") or ""):
            f["symbol"]="example.Other.callback"
      for result in self.run_records([wait,gap,missing]):
        self.assertFalse(result["proposals"])
      target=Path(tmp)/TARGET;before=target.read_bytes();target.write_bytes(before+b"\n// changed\n")
      self.assertFalse(self.run_records([record])[0]["proposals"])
      target.write_bytes(before)
      forged=copy.deepcopy(record)
      for t in forged["threads"]:
        for f in t["frames"]:
          for m in f["source"]["candidates"]:
            m["path"]="../outside.java"
          if f["source"]["selected"]: f["source"]["selected"]["path"]="../outside.java"
      self.assertFalse(self.run_records([forged])[0]["proposals"])
      proposal=results[0]["proposals"][0]
      patch=Path(tmp)/"candidate.patch";patch.write_text(proposal["patch"],encoding="utf-8",newline="\n")
      for flags in [["--check"],[]]:
        p=subprocess.run(["git","apply",*flags,str(patch)],cwd=tmp,capture_output=True,text=True)
        self.assertEqual(0,p.returncode,p.stderr)
      self.assertEqual(proposal["replacement_source"],target.read_text(encoding="utf-8"))
      self.assertFalse(proposal["eligible_for_application"])
      java=HARNESS.replace("/*BEFORE*/",proposal["before"]).replace("/*AFTER*/",proposal["replacement"])
      (Path(tmp)/"RefreshProbe.java").write_text(java,encoding="utf-8")
      stubs={"com/intellij/openapi/progress/ProgressManager.java":
        "package com.intellij.openapi.progress; public class ProgressManager { public static void checkCanceled() {} }",
        "com/intellij/openapi/application/ModalityState.java":
        "package com.intellij.openapi.application; public class ModalityState { public static Object defaultModalityState() { return new Object(); } }"}
      for path,source in stubs.items():
        file=Path(tmp)/path;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(source,encoding="utf-8")
      build=subprocess.run(["javac","-encoding","UTF-8","-d",tmp,str(Path(tmp)/"RefreshProbe.java"),
                            *(str(Path(tmp)/p) for p in stubs)],capture_output=True,text=True)
      self.assertEqual(0,build.returncode,build.stderr)
      run=subprocess.run(["java","-cp",tmp,"RefreshProbe"],capture_output=True,text=True,timeout=30)
      self.assertEqual(0,run.returncode,run.stdout+run.stderr)
      print(run.stdout.strip())


if __name__=="__main__":
  unittest.main()
