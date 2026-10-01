"""Real row 1007 and generated Java in a controlled Swing/lifecycle harness."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT/'repair/tests/fixtures/P1-git-loading'
TARGET = 'plugins/git4idea/backend/src/branch/GitBranchIncomingOutgoingManager.java'
HARNESS = r'''
import javax.swing.SwingUtilities;
import java.util.concurrent.*;
public class Probe {
  @interface NotNull {}
  enum GitIncomingRemoteCheckStrategy { TEST }
  static class GitVcsSettings { interface GitVcsSettingsListener {
    Object TOPIC = new Object();
    void incomingCommitsCheckStrategyChanged(GitIncomingRemoteCheckStrategy s);
  } }
  static class GitRepository { static final Object GIT_REPO_CHANGE = new Object(); }
  static final Object GIT_AUTHENTICATION_SUCCESS = new Object();
  static class ApplicationManager {
    static final ApplicationManager APP = new ApplicationManager();
    static final ExecutorService pool = Executors.newSingleThreadExecutor();
    static ApplicationManager getApplication() { return APP; }
    void invokeLater(Runnable r) { SwingUtilities.invokeLater(r); }
    void executeOnPooledThread(Runnable r) { pool.execute(r); }
  }
  static class Project {
    volatile boolean disposed; final Bus bus = new Bus();
    boolean isDisposed() { return disposed; }
    Bus getMessageBus() { check(SwingUtilities.isEventDispatchThread()); return bus; }
  }
  static class Bus {
    int connections; GitVcsSettings.GitVcsSettingsListener listener;
    Bus connect(Object owner) { connections++; return this; }
    void subscribe(Object topic,Object listener) {
      check(SwingUtilities.isEventDispatchThread());
      if (topic == GitVcsSettings.GitVcsSettingsListener.TOPIC) this.listener=(GitVcsSettings.GitVcsSettingsListener)listener;
    }
  }
  static class Base {
    final Project myProject = new Project(); Bus myConnection;
    volatile boolean myP1Disposed, prepareOnEdt;
    final CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1), updated = new CountDownLatch(1);
    int outgoing, incoming;
    void prepare() { prepareOnEdt=SwingUtilities.isEventDispatchThread(); entered.countDown(); await(release); }
    void updateAllBranchesWithOutgoing() { check(SwingUtilities.isEventDispatchThread()); outgoing++; }
    void updateIncomingScheduling() { check(SwingUtilities.isEventDispatchThread()); incoming++; updated.countDown(); }
    void dispose() { myP1Disposed=true; }
  }
  static class Original extends Base { /*BEFORE*/ }
  static class Fixed extends Base { /*AFTER*/ }
  static void check(boolean b) { if(!b) throw new AssertionError(); }
  static void await(CountDownLatch l) { try { check(l.await(5,TimeUnit.SECONDS)); } catch(InterruptedException e) { throw new RuntimeException(e); } }
  static void flush() throws Exception { ApplicationManager.pool.submit(() -> {}).get(5,TimeUnit.SECONDS); SwingUtilities.invokeAndWait(() -> {}); }
  public static void main(String[] args) throws Exception {
    try {
      Original old=new Original(); SwingUtilities.invokeLater(old::activate); await(old.entered);
      CountDownLatch beat=new CountDownLatch(1); SwingUtilities.invokeLater(beat::countDown);
      check(!beat.await(100,TimeUnit.MILLISECONDS)); old.release.countDown(); await(old.updated); flush(); check(old.prepareOnEdt);
      for(int mode=0;mode<3;mode++) {
        Fixed f=new Fixed(); SwingUtilities.invokeAndWait(f::activate); await(f.entered);
        CountDownLatch hb=new CountDownLatch(1);SwingUtilities.invokeLater(hb::countDown);await(hb);check(!f.prepareOnEdt);
        if(mode==1) SwingUtilities.invokeAndWait(f::dispose);
        if(mode==2) f.myProject.disposed=true;
        f.release.countDown();flush();
        if(mode!=0) { check(f.myConnection==null && f.outgoing==0);continue; }
        check(f.outgoing==1 && f.incoming==1 && f.myProject.bus.connections==1);
        SwingUtilities.invokeAndWait(f::activate);flush();check(f.myProject.bus.connections==1 && f.outgoing==2);
        SwingUtilities.invokeAndWait(() -> f.myProject.bus.listener.incomingCommitsCheckStrategyChanged(GitIncomingRemoteCheckStrategy.TEST));flush();check(f.incoming==3);
        SwingUtilities.invokeAndWait(() -> { f.myProject.bus.listener.incomingCommitsCheckStrategyChanged(GitIncomingRemoteCheckStrategy.TEST);f.dispose(); });flush();check(f.incoming==3);
      }
      System.out.println("PASS: modeled preparation/EDT heartbeat; subscription and updates on EDT; repeated activation; disposal and queued callbacks");
    } finally { ApplicationManager.pool.shutdownNow(); }
  }
}
'''

@unittest.skipUnless(os.environ.get('Q1_CLASSPATH'), 'Build Q1 first')
class P1GitLoadingTest(unittest.TestCase):
  def worker(self, r):
    p=subprocess.run(['java','-cp',os.environ['Q1_CLASSPATH'],'org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier','--repair-selection'],input=json.dumps(r)+'\n',text=True,encoding='utf-8',capture_output=True,check=True,timeout=30)
    return json.loads(p.stdout)['repair_selection']['loading_evaluation']

  def test_real_row_patch_and_behavior(self):
    r=json.loads((FIXTURE/'P1-finder.jsonl').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(dir=ROOT/'out') as tmp:
      root=Path(tmp)
      with zipfile.ZipFile(FIXTURE/'P1-source.zip') as z:z.extractall(root)
      r['source_root']=tmp
      result=self.worker(r);self.assertEqual(1,len(result['proposals']))
      p=result['proposals'][0]
      generated=[d['trigger']['symbol'] for d in result['decisions'] if d['patch_generated']]
      self.assertEqual({'java.lang.ClassLoader.loadClass','java.lang.ClassLoader.defineClass','java.lang.ClassLoader.defineClass2'},set(generated))
      self.assertFalse(p['eligible_for_application'])
      bad=copy.deepcopy(r)
      for t in bad['threads']:
        for f in t['frames']:
          if 'lambda$activate$' in (f.get('symbol') or ''):f['elided']=True
      self.assertFalse(self.worker(bad)['proposals'])
      noncontiguous=copy.deepcopy(r)
      for t in noncontiguous['threads']:
        for f in t['frames']:
          if 'lambda$activate$' in (f.get('symbol') or ''):f['index']+=2
      self.assertFalse(self.worker(noncontiguous)['proposals'])
      patch=root/'candidate.patch';patch.write_text(p['patch'],encoding='utf-8',newline='\n')
      for flags in [['--check'],[]]:
        run=subprocess.run(['git','apply',*flags,str(patch)],cwd=tmp,capture_output=True,text=True)
        self.assertEqual(0,run.returncode,run.stderr)
      self.assertEqual(p['replacement_source'],(root/TARGET).read_text(encoding='utf-8'))
      self.assertFalse(self.worker(r)['proposals'])
      before=p['before'].replace('        myConnection.subscribe(GitVcsSettings.GitVcsSettingsListener.TOPIC, new', '        prepare();\n        myConnection.subscribe(GitVcsSettings.GitVcsSettingsListener.TOPIC, new')
      after=p['replacement'].replace('      var listener = new', '      prepare();\n      var listener = new')
      (root/'Probe.java').write_text(HARNESS.replace('/*BEFORE*/',before).replace('/*AFTER*/',after),encoding='utf-8')
      run=subprocess.run(['javac','-d',tmp,str(root/'Probe.java')],capture_output=True,text=True)
      self.assertEqual(0,run.returncode,run.stderr)
      run=subprocess.run(['java','-Djava.awt.headless=true','-cp',tmp,'Probe'],capture_output=True,text=True,timeout=30)
      self.assertEqual(0,run.returncode,run.stdout+run.stderr);print(run.stdout.strip())

if __name__=='__main__':unittest.main()
