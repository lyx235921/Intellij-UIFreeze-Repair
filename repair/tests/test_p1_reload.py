"""Generated Java + real Swing EDT/disk; platform services are controlled substitutes, not IDE tests."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import hashlib
import urllib.request

ROOT = Path(__file__).resolve().parents[2]

HARNESS = r'''
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.*;
import javax.swing.SwingUtilities;
import java.lang.annotation.*;

public class ReloadProbe {
  @Target({ElementType.TYPE_USE, ElementType.PARAMETER, ElementType.METHOD}) @interface NotNull {}
  @Target({ElementType.TYPE_USE, ElementType.PARAMETER, ElementType.METHOD}) @interface Nullable {}
  static void check(boolean condition) { if (!condition) throw new AssertionError(); }
  static void edt(Runnable task) throws Exception { SwingUtilities.invokeAndWait(task); }
  static class ThreadingAssertions {
    static void assertEventDispatchThread() { check(SwingUtilities.isEventDispatchThread()); }
  }
  static class Project { boolean disposed; boolean isDisposed() { return disposed; } }
  static class ProjectLocator {
    static final ProjectLocator INSTANCE = new ProjectLocator();
    static ProjectLocator getInstance() { return INSTANCE; }
    Project guessProjectForFile(VirtualFile file) { return file.project; }
  }
  static class FileType { boolean binary; boolean isBinary() { return binary; } }
  static class VirtualFile {
    Path path; long stamp = 2, length, time; boolean valid = true, directory;
    byte[] bom = {1}; Object charset = "old"; boolean cleared;
    final Project project = new Project(); final FileType type = new FileType();
    VirtualFile(Path p) throws Exception { path = p; update(); }
    void update() throws Exception { length = Files.size(path); time = Files.getLastModifiedTime(path).toMillis(); }
    boolean isValid() { return valid; } boolean isDirectory() { return directory; }
    Object getFileSystem() { return com.intellij.openapi.vfs.LocalFileSystem.getInstance(); }
    FileType getFileType() { return type; } Path toNioPath() { return path; }
    long getLength() { return length; } long getTimeStamp() { return time; }
    long getModificationStamp() { return stamp; }
    void setBOM(byte[] value) { bom = value; }
    void setCharset(Object value, Object ignored, boolean flag) { charset = value; }
  }
  static class Document {
    final VirtualFile file; String text = "old"; long stamp = 1; boolean writable = true, unsaved;
    Document(VirtualFile f) { file = f; }
    long getModificationStamp() { return stamp; } boolean isWritable() { return writable; }
    void setReadOnly(boolean readOnly) { writable = !readOnly; }
    void putUserData(Object key, Object value) { ThreadingAssertions.assertEventDispatchThread(); }
  }
  static class DocumentEx extends Document {
    int replacements;
    DocumentEx(VirtualFile f) { super(f); }
    void replaceText(CharSequence value, long version) {
      ThreadingAssertions.assertEventDispatchThread(); check(APP.inWrite && APP.inCommand);
      text = value.toString(); stamp = version; replacements++;
    }
  }
  static class VFileContentChangeEvent {
    final VirtualFile file; final long oldStamp, stamp, length, time; boolean refresh = true, save;
    VFileContentChangeEvent(VirtualFile f, long old) { file = f; oldStamp = old; stamp = f.stamp; length = f.length; time = f.time; }
    VirtualFile getFile() { return file; } long getModificationStamp() { return stamp; }
    long getOldModificationStamp() { return oldStamp; } long getNewLength() { return length; }
    long getNewTimestamp() { return time; } boolean isFromSave() { return save; }
    boolean isFromRefresh() { return refresh; }
  }
  static class ModalityState { static ModalityState current() { return new ModalityState(); } }
  static class App {
    final Queue<Runnable> workers = new ConcurrentLinkedQueue<>(), callbacks = new ConcurrentLinkedQueue<>();
    boolean disposed, inWrite, inCommand; int starts;
    boolean isDisposed() { return disposed; }
    void executeOnPooledThread(Runnable work) { starts++; workers.add(work); }
    void invokeLater(Runnable callback, ModalityState state) { callbacks.add(callback); }
    App getMessageBus() { return this; } Listener syncPublisher(Object topic) { return LISTENER; }
    void runWriteAction(Runnable r) { inWrite = true; try { r.run(); } finally { inWrite = false; } }
  }
  static final App APP = new App();
  static class ApplicationManager { static App getApplication() { return APP; } }
  static class Listener {
    int completed;
    void fileContentReloaded(VirtualFile f, Document d) { completed++; }
    void fileWithNoDocumentChanged(VirtualFile f) {} void afterDocumentUnbound(VirtualFile f, Document d) {}
  }
  static final Listener LISTENER = new Listener();
  static class FileDocumentManagerListenerBackgroundable { static final Object TOPIC = new Object(); }
  static class CommandProcessor {
    static CommandProcessor getInstance() { return new CommandProcessor(); }
    void executeCommand(Project p, Runnable r, String name, Object group, Object policy) {
      APP.inCommand = true; try { r.run(); } finally { APP.inCommand = false; }
    }
  }
  static class ExternalChangeActionUtil { static Runnable externalDocumentChangeAction(Runnable r) { return r; } }
  static class UIBundle { static String message(String key) { return key; } }
  static class UndoConfirmationPolicy { static final Object REQUEST_CONFIRMATION = new Object(); }
  static class ThreadContext {
    static ThreadContext currentThreadContext() { return new ThreadContext(); }
    ThreadContext minusKey(Object key) { return this; }
    static void installThreadContext(ThreadContext c, boolean b, Supplier<Object> r) { r.get(); }
  }
  static class ClientIdContextElement { static final Object Key = new Object(); }
  static class LOG {
    static int warnings; static boolean isTraceEnabled() { return false; }
    static void trace(String s) {} static void warn(String s, Exception e) { warnings++; if (e != null) e.printStackTrace(); }
  }
  static class FileUtilRt { static boolean isTooLarge(long length) { return length > 2 * 1024 * 1024; } }
  static class LoadTextUtil {
    static Runnable decoding = () -> {}; static int syncReads;
    static void clearCharsetAutoDetectionReason(VirtualFile f) { f.cleared = true; }
    static CharSequence getTextByBinaryPresentation(byte[] bytes, VirtualFile f) {
      ThreadingAssertions.assertEventDispatchThread(); check(f.cleared && f.bom == null && f.charset == null);
      decoding.run();
      // Controlled decoder, not IntelliJ's real charset/transformer pipeline.
      String text = new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
      if (text.startsWith("\uFEFF")) { f.bom = new byte[]{(byte)239,(byte)187,(byte)191}; text = text.substring(1); }
      f.charset = "UTF-8";
      return text;
    }
    static CharSequence loadText(VirtualFile f) { syncReads++; return "sync"; }
    static CharSequence loadText(VirtualFile f, int length) { return loadText(f); }
  }
  static class Base { public void reloadFromDisk(Document d, Project p) {} }
  static class Manager extends Base {
    final Set<Document> myUnsavedDocuments = new HashSet<>();
    static final Object FORCE_SAVE_DOCUMENT_KEY = new Object();
    DocumentEx doc; Runnable before = () -> {}; boolean veto, reloadable = true;
    Manager(DocumentEx d) { doc = d; }
    Document getCachedDocument(VirtualFile file) { return doc.file == file ? doc : null; }
    VirtualFile getFile(Document d) { return d.file; }
    boolean isDocumentUnsaved(Document d) { return d.unsaved; }
    static boolean isBinaryWithDecompiler(VirtualFile file) { return false; }
    static boolean isBinaryWithoutDecompiler(VirtualFile file) { return file.type.binary; }
    boolean fireBeforeFileContentReload(VirtualFile f, Document d) { before.run(); return !veto; }
    static boolean isReloadable(VirtualFile f, Document d, Project p) { return f.valid; }
    void reloadFromDisk(Document d) { reloadFromDisk(d, d.file.project); }
    void reloadFromDiskWithDecompiler(Document d, Project p, VirtualFile f) { throw new AssertionError(); }
    void unbindFileFromDocument(VirtualFile f, Document d) { throw new AssertionError(); }
    static int getPreviewCharCount(VirtualFile f) { return 100; }
    static void setDocumentTooLarge(Document d, boolean value) { check(!value); }
    /*GENERATED*/
  }
  static void runWorker() throws Exception {
    Runnable worker = APP.workers.remove();
    AtomicReference<Throwable> error = new AtomicReference<>();
    Thread t = new Thread(() -> { try { worker.run(); } catch (Throwable e) { error.set(e); } });
    t.start(); t.join(20000);
    if (t.isAlive()) throw new AssertionError("Worker timeout: " + java.util.Arrays.toString(t.getStackTrace()));
    if (error.get() != null) throw new AssertionError(error.get());
  }
  static void callbacks() throws Exception { edt(() -> { Runnable r; while ((r = APP.callbacks.poll()) != null) r.run(); }); }
  static void drain() throws Exception {
    for (int i = 0; i < 12 && (!APP.workers.isEmpty() || !APP.callbacks.isEmpty()); i++) {
      if (!APP.workers.isEmpty()) runWorker(); callbacks();
    }
    check(APP.workers.isEmpty() && APP.callbacks.isEmpty());
  }
  static Manager create(Path folder, String name) throws Exception {
    Path path = folder.resolve(name); Files.writeString(path, "\uFEFFnew text");
    return new Manager(new DocumentEx(new VirtualFile(path)));
  }
  static void schedule(Manager m) throws Exception {
    edt(() -> m.contentsChanged(new VFileContentChangeEvent(m.doc.file, m.doc.stamp)));
  }
  static void noCommit(Manager m) { check(m.doc.replacements == 0 && m.doc.text.equals("old") && m.myP1Reloads.isEmpty()); }
  static String mutation;
  static final CountDownLatch readReached = new CountDownLatch(1), releaseRead = new CountDownLatch(1);
  static void afterRead(Path p) throws Exception {
    if (mutation.equals("identity")) {
      var time = Files.getLastModifiedTime(p); byte[] bytes = Files.readAllBytes(p);
      Files.move(p, p.resolveSibling(p.getFileName() + ".old"), StandardCopyOption.REPLACE_EXISTING);
      Files.write(p, bytes); Files.setLastModifiedTime(p, time);
    }
    else if (mutation.equals("slow")) {
      readReached.countDown(); check(releaseRead.await(5, TimeUnit.SECONDS));
    }
    else Files.writeString(p, "mutated during read and length changed");
  }
  public static void main(String[] args) throws Exception {
    Path folder = Path.of(args[0]);
    if (args.length > 1) {
      mutation = args[1];
      Manager m = create(folder, "during-read.txt"); schedule(m);
      if (mutation.equals("slow")) {
        Thread worker = new Thread(APP.workers.remove()); worker.start();
        check(readReached.await(20, TimeUnit.SECONDS));
        AtomicBoolean responsive = new AtomicBoolean();
        edt(() -> responsive.set(true)); check(responsive.get() && m.doc.replacements == 0);
        releaseRead.countDown(); worker.join(5000); check(!worker.isAlive()); callbacks();
        check(m.doc.text.equals("new text"));
        System.out.println("PASS: EDT processes heartbeat while generated background reader is paused; commit follows release");
      }
      else {
        drain(); noCommit(m); check(APP.starts == 3 && LOG.warnings == 1);
        System.out.println("PASS: injected " + mutation + " change between read and post-read attributes rejected; 3 attempts");
      }
      return;
    }
    Manager stable = create(folder, "stable.txt"); schedule(stable);
    // A pending background read must not occupy EDT or require completion before other UI events.
    AtomicBoolean heartbeat = new AtomicBoolean(); edt(() -> heartbeat.set(true));
    check(heartbeat.get() && stable.doc.text.equals("old")); drain();
    if (!stable.doc.text.equals("new text") || stable.doc.stamp != 2 || stable.doc.replacements != 1)
      throw new AssertionError("stable: text=" + stable.doc.text + " stamp=" + stable.doc.stamp + " writes=" + stable.doc.replacements + " warnings=" + LOG.warnings);
    check(stable.doc.file.bom != null && stable.doc.file.charset.equals("UTF-8") && LISTENER.completed == 1);
    check(LoadTextUtil.syncReads == 0 && stable.myP1Reloads.isEmpty());

    Manager edit = create(folder, "edit.txt"); schedule(edit); runWorker();
    edt(() -> { edit.doc.text = "user edit"; edit.doc.stamp++; edit.doc.unsaved = true; }); callbacks();
    check(edit.doc.replacements == 0 && edit.doc.text.equals("user edit") && edit.myP1Reloads.isEmpty());

    Manager newer = create(folder, "newer.txt"); schedule(newer); runWorker();
    Files.writeString(newer.doc.file.path, "latest content"); newer.doc.file.update(); newer.doc.file.stamp++;
    schedule(newer); check(APP.workers.isEmpty()); callbacks(); drain();
    check(newer.doc.text.equals("latest content") && newer.doc.replacements == 1 && newer.doc.stamp == 3);

    Manager mismatch = create(folder, "mismatch.txt"); schedule(mismatch);
    Files.writeString(mismatch.doc.file.path, "unexpected length"); int attempts = APP.starts; drain();
    noCommit(mismatch); check(APP.starts - attempts == 2 && LOG.warnings == 1);

    Manager deleted = create(folder, "deleted.txt"); schedule(deleted); Files.delete(deleted.doc.file.path); drain(); noCommit(deleted);
    Manager disposed = create(folder, "disposed.txt"); schedule(disposed); disposed.doc.file.project.disposed = true; drain(); noCommit(disposed);
    Manager invalid = create(folder, "invalid.txt"); schedule(invalid); invalid.doc.file.valid = false; drain(); noCommit(invalid);
    Manager moved = create(folder, "moved.txt"); schedule(moved); runWorker(); moved.doc.file.path = folder.resolve("elsewhere"); callbacks(); noCommit(moved);
    Manager listener = create(folder, "listener.txt"); listener.before = () -> { listener.doc.stamp++; listener.doc.unsaved = true; };
    schedule(listener); drain(); noCommit(listener);
    Manager veto = create(folder, "veto.txt"); veto.veto = true; schedule(veto); drain(); noCommit(veto);
    Manager decoder = create(folder, "decoder.txt"); decoder.doc.writable = false;
    LoadTextUtil.decoding = () -> { decoder.doc.stamp++; decoder.doc.unsaved = true; };
    schedule(decoder); drain(); noCommit(decoder); check(!decoder.doc.writable); LoadTextUtil.decoding = () -> {};
    check(LISTENER.completed == 2);

    Manager unknown = create(folder, "unknown.txt"); unknown.doc.file.time = -1;
    schedule(unknown); check(APP.workers.isEmpty() && unknown.doc.text.equals("sync"));
    Manager manual = create(folder, "manual.txt"); schedule(manual); runWorker();
    edt(() -> manual.reloadFromDisk(manual.doc)); callbacks(); check(manual.doc.text.equals("sync") && manual.doc.replacements == 1);
    check(manual.myP1Reloads.isEmpty());
    // Real snapshot helper rejects EDT reads and incorrect expected metadata.
    edt(() -> { try { Manager.p1ReadSnapshot(stable.doc.file.path, 0, 0); throw new AssertionError(); }
                catch (IllegalStateException expected) {} catch (Exception e) { throw new AssertionError(e); } });
    check(Manager.p1ReadSnapshot(stable.doc.file.path, 999, stable.doc.file.time) == null);
    System.out.println("PASS: stable commit, EDT heartbeat, BOM reset ordering, user edit, newer event coalescing, bounded retry, deletion, disposal, invalidation, rename, listener edit/veto, decoder edit, read-only restoration, sync API");
  }
}
'''


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build Q1 first")
class P1ReloadTest(unittest.TestCase):
  def test_generated_patch_and_controlled_behavior(self):
    record = json.loads((ROOT / "repair/tests/fixtures/row4746-finder.json").read_text(encoding="utf-8"))
    run = subprocess.run(["java", "-cp", os.environ["Q1_CLASSPATH"],
                          "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier", "--s1-p1"],
                         input=json.dumps(record) + "\n", text=True, encoding="utf-8", capture_output=True, check=True)
    proposal = json.loads(run.stdout)["s1_p1"]
    self.assertEqual("CANDIDATE_PATCH", proposal["status"], proposal.get("reason"))
    deps = ROOT / "out/edt-freeze-finder/p1-test-deps"
    deps.mkdir(parents=True, exist_ok=True)
    jars = []
    for name, digest in [("jna", "b3a9408e7c51e08ef0e3bfcc08f443f6ec0f6191ba8cd7c18d53d2b22e5bdbc0"),
                         ("jna-platform", "b7e3d46c87bad2eb409b0e704916bcd81206168e357312dfddd0e253679cd9e0")]:
      jar = deps / (name + "-5.17.0.jar")
      if not jar.exists():
        urllib.request.urlretrieve("https://repo.maven.apache.org/maven2/net/java/dev/jna/" + name + "/5.17.0/" + jar.name, jar)
      self.assertEqual(digest, hashlib.sha256(jar.read_bytes()).hexdigest())
      jars.append(str(jar))
    source = proposal["replacement_source"]
    generated = source[source.index("  public void contentsChanged("):source.index("  private void reloadFromDiskWithDecompiler(")]
    with tempfile.TemporaryDirectory(dir=ROOT / "out") as tmp:
      folder = Path(tmp)
      target = folder / proposal["source_contexts"][0]["path"]
      target.parent.mkdir(parents=True)
      target.write_bytes((Path(record["source_root"]) / proposal["source_contexts"][0]["path"]).read_bytes())
      patch = folder / "candidate.patch"
      patch.write_text(proposal["patch"], encoding="utf-8", newline="\n")
      applied = subprocess.run(["git", "apply", "--check", str(patch)], cwd=folder, capture_output=True, text=True)
      self.assertEqual(0, applied.returncode, applied.stderr)
      applied = subprocess.run(["git", "apply", str(patch)], cwd=folder, capture_output=True, text=True)
      self.assertEqual(0, applied.returncode, applied.stderr)
      self.assertEqual(source, target.read_text(encoding="utf-8"))
      stub = folder / "com/intellij/openapi/vfs/LocalFileSystem.java"
      stub.parent.mkdir(parents=True)
      stub.write_text("package com.intellij.openapi.vfs; public class LocalFileSystem { "
                      "private static final LocalFileSystem INSTANCE=new LocalFileSystem(); "
                      "public static LocalFileSystem getInstance(){return INSTANCE;} }", encoding="utf-8")
      for inject in (False, True):
        code = generated
        if inject:
          # Explicit test-only hook; production generated Java has no hook.
          anchor = "java.nio.file.attribute.BasicFileAttributes after ="
          self.assertEqual(1, code.count(anchor))
          code = code.replace(anchor, "try { afterRead(path); } catch (Exception e) { throw new java.io.IOException(e); }\n" + anchor)
        java = folder / "ReloadProbe.java"
        java.write_text(HARNESS.replace("/*GENERATED*/", code), encoding="utf-8")
        classpath = os.pathsep.join([tmp] + jars)
        compiled = subprocess.run(["javac", "-encoding", "UTF-8", "-cp", classpath, "-d", tmp, str(stub), str(java)], capture_output=True, text=True)
        self.assertEqual(0, compiled.returncode, compiled.stderr)
        for mode in (["mutation", "identity", "slow"] if inject else [None]):
          probe = subprocess.run(["java", "-Djava.awt.headless=true", "--enable-native-access=ALL-UNNAMED", "-cp", classpath,
                                  "ReloadProbe", tmp] + ([mode] if mode else []), capture_output=True, text=True, timeout=45)
          self.assertEqual(0, probe.returncode, probe.stdout + probe.stderr)
          print(probe.stdout.strip())


if __name__ == "__main__":
  unittest.main()
