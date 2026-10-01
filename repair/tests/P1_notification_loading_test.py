"""Actual generated notification methods with explicit platform doubles and a controlled preparation delay."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[2]
FIXTURE=ROOT/'repair/tests/fixtures/P1-notification-loading'
HARNESS=r'''
import javax.swing.SwingUtilities;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
public class NotificationProbe {
  @interface NotNull {} @interface RequiresEdt {}
  static class IdeMessagePanel {}
  enum NotificationType { ERROR }
  enum NotificationDisplayType { NONE, STICKY_BALLOON, BALLOON }
  static class Config { NotificationDisplayType type=NotificationDisplayType.BALLOON; NotificationDisplayType getDisplayType(String id){return type;} }
  static class NotificationsConfiguration { static final Config c=new Config(); static Config getNotificationsConfiguration(){return c;} }
  static class Project { boolean disposed; boolean isDisposed(){return disposed;} }
  static class IdeFrame { final Layout layout=new Layout(); boolean active=true; Layout getBalloonLayout(){ui();return layout;} }
  static class Layout { int count; void add(Balloon b){ui();count++;} void closeAll(){} }
  static class Balloon {}
  static class MessagePool { enum State { UnreadErrors, NoErrors } State state=State.UnreadErrors; State getState(){return state;} }
  static class Ref<T> { Ref(T v){} }
  static class Logger { static Logger getInstance(Class<?> c){return new Logger();} void error(String s){throw new AssertionError(s);} }
  static class Disposer { static void register(Balloon b,Runnable r){ui();} }
  static class AllIcons { static class Ide { static final Object FatalError=new Object(); } }
  static class DiagnosticBundle { static String message(String s){return s;} }
  static class NotificationAction { static Object createSimpleExpiring(String s,Runnable r){return r;} }
  static class JBUI { static class CurrentTheme { static class Notification { static class Error { static Object FOREGROUND=new Object(),BACKGROUND=new Object(),BORDER_COLOR=new Object(); } } } }
  static class BalloonLayoutData {
    int fadeoutTime; Object textColor,fillColor,borderColor;Runnable closeAll;boolean showSettingButton;
    static BalloonLayoutData createEmpty(){ui();return new BalloonLayoutData();}
  }
  static class NotificationsManagerImpl {
    static Balloon createBalloon(IdeFrame f,Notification n,boolean a,boolean b,Ref<BalloonLayoutData> r,Project p){ui();return new Balloon();}
  }
  static volatile Base current;
  static class Notification {
    Notification(String group,String title,NotificationType t) {
      current.prepares++;current.prepareOnEdt=SwingUtilities.isEventDispatchThread();current.entered.countDown();await(current.release);
      if(current.fail)throw new IllegalStateException("injected preparation failure");
    }
    Notification setIcon(Object o){return this;} Notification addAction(Object o){return this;}
  }
  static class App {
    final ExecutorService pool=Executors.newSingleThreadExecutor();
    void executeOnPooledThread(Runnable r){pool.submit(r);}
    void invokeLater(Runnable r){SwingUtilities.invokeLater(r);}
  }
  static class ApplicationManager { static final App app=new App();static App getApplication(){return app;} }
  static class Base {
    static final String GROUP_ID="test"; Balloon balloon; final MessagePool messagePool=new MessagePool();
    volatile boolean myP1Disposed,prepareOnEdt,fail; final AtomicBoolean myP1NotificationPending=new AtomicBoolean();
    final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);int prepares;
    boolean isActive(IdeFrame f){ui();return f.active;} void openErrorsDialog(Object unused){ui();}
  }
  static class Original extends Base { /*BEFORE*/ void start(Project p,IdeFrame f){showErrorNotification(p,f);} }
  static class Fixed extends Base { /*AFTER*/ void start(Project p,IdeFrame f){showErrorNotification(p,f);} }
  static void check(boolean b){if(!b)throw new AssertionError();} static void ui(){check(SwingUtilities.isEventDispatchThread());}
  static void await(CountDownLatch l){try{check(l.await(5,TimeUnit.SECONDS));}catch(InterruptedException e){throw new RuntimeException(e);}}
  static void flush() throws Exception {ApplicationManager.app.pool.submit(()->{}).get(5,TimeUnit.SECONDS);SwingUtilities.invokeAndWait(()->{});}
  public static void main(String[] a) throws Exception {
    try {
      Project p=new Project();IdeFrame f=new IdeFrame();Original old=new Original();current=old;
      SwingUtilities.invokeLater(()->old.start(p,f));await(old.entered);
      CountDownLatch hb=new CountDownLatch(1);SwingUtilities.invokeLater(hb::countDown);check(!hb.await(100,TimeUnit.MILLISECONDS));
      old.release.countDown();await(hb);check(old.prepareOnEdt && f.layout.count==1);
      for(int mode=0;mode<7;mode++) {
        Fixed fixed=new Fixed();Project project=new Project();IdeFrame frame=new IdeFrame();current=fixed;
        NotificationsConfiguration.c.type=NotificationDisplayType.BALLOON;
        SwingUtilities.invokeAndWait(()->{fixed.start(project,frame);fixed.start(project,frame);});await(fixed.entered);
        CountDownLatch beat=new CountDownLatch(1);SwingUtilities.invokeLater(beat::countDown);await(beat);check(!fixed.prepareOnEdt && fixed.prepares==1);
        final int choice=mode;
        SwingUtilities.invokeAndWait(()->{
          if(choice==1)fixed.myP1Disposed=true;
          if(choice==2)project.disposed=true;
          if(choice==3)fixed.messagePool.state=MessagePool.State.NoErrors;
          if(choice==4)frame.active=false;
          if(choice==5)NotificationsConfiguration.c.type=NotificationDisplayType.NONE;
          if(choice==6)fixed.fail=true;
        });
        fixed.release.countDown();flush();check(!fixed.myP1NotificationPending.get());
        check(frame.layout.count==(mode==0?1:0));
        if(mode==6){fixed.fail=false;SwingUtilities.invokeAndWait(()->fixed.start(project,frame));flush();check(frame.layout.count==1);}
      }
      System.out.println("PASS: controlled EDT heartbeat; single pending task; UI commit; stale/disposed/disabled drops; failure retry");
    } finally {ApplicationManager.app.pool.shutdownNow();}
  }
}
'''

@unittest.skipUnless(os.environ.get('Q1_CLASSPATH'),'Build Q1 first')
class P1NotificationLoadingTest(unittest.TestCase):
  def worker(self,r):
    p=subprocess.run(['java','-cp',os.environ['Q1_CLASSPATH'],'org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier','--repair-selection'],input=json.dumps(r)+'\n',capture_output=True,text=True,encoding='utf-8',check=True,timeout=30)
    return json.loads(p.stdout)['repair_selection']['loading_evaluation']

  def test_real_case_patch_behavior_and_refusals(self):
    r=json.loads((FIXTURE/'P1-finder.jsonl').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(dir=ROOT/'out') as tmp:
      root=Path(tmp)
      with zipfile.ZipFile(FIXTURE/'P1-source.zip') as z:z.extractall(root)
      r['source_root']=tmp;result=self.worker(r)
      self.assertEqual(1,len(result['proposals']));self.assertEqual(4,sum(d['patch_generated'] for d in result['decisions']))
      p=result['proposals'][0];self.assertFalse(p['eligible_for_application'])
      gap=copy.deepcopy(r)
      for thread in gap['threads']:
        for frame in thread['frames']:
          if (frame.get('symbol') or '').endswith('IdeMessagePanel.showErrorNotification'):frame['elided']=True
      self.assertFalse(self.worker(gap)['proposals'])
      target=root/p['path'];patch=root/'candidate.patch';patch.write_text(p['patch'],encoding='utf-8',newline='\n')
      for flags in [['--check'],[]]:
        run=subprocess.run(['git','apply',*flags,str(patch)],cwd=tmp,capture_output=True,text=True)
        self.assertEqual(0,run.returncode,run.stderr)
      self.assertEqual(p['replacement_source'],target.read_text(encoding='utf-8'))
      self.assertFalse(self.worker(r)['proposals'])
      java=root/'NotificationProbe.java';java.write_text(HARNESS.replace('/*BEFORE*/',p['before']).replace('/*AFTER*/',p['replacement']),encoding='utf-8')
      run=subprocess.run(['javac','-d',tmp,str(java)],capture_output=True,text=True);self.assertEqual(0,run.returncode,run.stderr)
      run=subprocess.run(['java','-Djava.awt.headless=true','-cp',tmp,'NotificationProbe'],capture_output=True,text=True,timeout=30)
      self.assertEqual(0,run.returncode,run.stdout+run.stderr);print(run.stdout.strip())

if __name__=='__main__':unittest.main()
