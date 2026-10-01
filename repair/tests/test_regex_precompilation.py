"""Actual original/generated registration and lookup methods with real JDK regexes."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = "src/main/java/org/wso2/lsp4intellij/IntellijLanguageClient.java"


def method(source, name):
  found = re.search(r"(?ms)^    (?:public|private) static [^\n]+ " + name + r"\([^\n]*\) \{.*?^    }", source)
  if not found:
    raise AssertionError(name)
  return found.group()


HARNESS = r'''
import java.util.*;
import java.util.concurrent.*;
import java.util.regex.*;
public class RegexProbe {
  record Pair<A,B>(A left, B right) {
    A getLeft() { return left; } B getRight() { return right; }
  }
  static class ImmutablePair<A,B> { }
  record VirtualFile(String name, String extension) {
    String getName() { return name; } String getExtension() { return extension; }
  }
  static class LanguageServerDefinition {
    static final String SPLIT_CHAR = ","; final String ext;
    LanguageServerDefinition(String regex) { ext = regex; }
  }
  static class LOG { static void info(String s) {} }
  static class Original {
    static final Map<Pair<String,String>,LanguageServerDefinition> extToServerDefinition = new ConcurrentHashMap<>();
    /*ORIGINAL*/
  }
  static class Fixed {
    static final Map<Pair<String,String>,LanguageServerDefinition> extToServerDefinition = new ConcurrentHashMap<>();
    /*FIXED*/
  }
  static void check(boolean b) { if (!b) throw new AssertionError(); }
  static void register(String rule) {
    Original.processDefinition(new LanguageServerDefinition(rule), "project");
    Fixed.processDefinition(new LanguageServerDefinition(rule), "project");
  }
  static void clear() {
    Original.extToServerDefinition.clear(); Fixed.extToServerDefinition.clear(); Fixed.preparedRegexes.clear();
  }
  static String result(boolean fixed, VirtualFile f) {
    try { return "result:" + (fixed ? Fixed.isExtensionSupported(f) : Original.isExtensionSupported(f)); }
    catch (PatternSyntaxException e) { return e.getClass().getName() + ":" + e.getDescription() + ":" + e.getIndex(); }
  }
  static volatile int sink;
  public static void main(String[] args) throws Exception {
    String[] names = {"Foo.java", "foo.txt", "README", "README.md", "a\nb", "", "\u6587\u4ef6.java", "UPPER.JAVA"};
    for (String rule : new String[]{"txt", ".*\\.java", "(?i)readme.*", "[", "(?s).*", ""}) {
      clear(); register(rule);
      for (String name : names) for (String ext : new String[]{null, "java", "txt", rule}) {
        VirtualFile f = new VirtualFile(name, ext); check(result(false,f).equals(result(true,f)));
      }
    }
    clear(); register("[");
    check(Fixed.preparedRegexes.isEmpty());
    check(Fixed.isExtensionSupported(new VirtualFile("any", "["))); // Invalid regex literal-extension shortcut remains legal.
    check(result(true,new VirtualFile("x",null)).startsWith(PatternSyntaxException.class.getName()));
    clear(); register(".*\\.java");
    Pattern prepared = Fixed.preparedRegexes.get(".*\\.java");
    register(".*\\.java"); check(prepared == Fixed.preparedRegexes.get(".*\\.java"));
    List<Thread> threads = new ArrayList<>();
    java.util.concurrent.atomic.AtomicReference<Throwable> failed = new java.util.concurrent.atomic.AtomicReference<>();
    for (int n=0;n<8;n++) {
      Thread thread = new Thread(() -> { try {
        for (int i=0;i<2000;i++) {
          check(Fixed.isExtensionSupported(new VirtualFile("X.java","java")));
          check(!Fixed.isExtensionSupported(new VirtualFile("X.txt","txt")));
        }
      } catch(Throwable t) { failed.set(t); } });
      threads.add(thread); thread.start();
    }
    for(Thread t:threads)t.join(); if(failed.get()!=null)throw new AssertionError(failed.get());
    Fixed.extToServerDefinition.clear(); check(!Fixed.isExtensionSupported(new VirtualFile("X.java","java")));
    check(prepared == Fixed.preparedRegexes.get(".*\\.java")); // Inactive patterns cannot make an unregistered rule active.
    clear();
    for(int i=0;i<300;i++) register("rule"+i);
    check(Fixed.preparedRegexes.size()==256);
    check(Fixed.isExtensionSupported(new VirtualFile("rule299",null))); // Capacity fallback retains exact semantics.
    check(!Fixed.isExtensionSupported(new VirtualFile("missing",null)));
    clear(); register("(?:" + "a|".repeat(200) + "z).*\\.java");
    VirtualFile input = new VirtualFile("abc.java", "java");
    for(int i=0;i<1000;i++) { Original.isExtensionSupported(input); Fixed.isExtensionSupported(input); }
    long begin=System.nanoTime();
    for(int i=0;i<3000;i++)if(Original.isExtensionSupported(input))sink++;
    long baseline=System.nanoTime()-begin;
    begin=System.nanoTime();
    for(int i=0;i<3000;i++)if(Fixed.isExtensionSupported(input))sink++;
    long fixed=System.nanoTime()-begin;
    check(sink==6000 && Fixed.preparedRegexes.size()==1);
    System.out.println("PASS semantics: literal shortcut, regex, invalid regex timing, flags, null extension, removal, capacity, concurrency");
    System.out.println("CONTROLLED JDK workload (3000 lookups, 200 alternatives): original_ms="+baseline/1e6+", prepared_ms="+fixed/1e6);
  }
}
'''


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build Q1 first")
class RegexPrecompilationTest(unittest.TestCase):
  def run_case(self, record):
    p = subprocess.run(["java", "-cp", os.environ["Q1_CLASSPATH"],
                        "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier", "--s1-regex"],
                       input=json.dumps(record)+"\n", capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(p.stdout)["s1_regex"]

  def test_patch_semantics_and_rejections(self):
    record = json.loads((ROOT/"repair/tests/fixtures/row4238-finder.json").read_text(encoding="utf-8"))
    original = (ROOT/"repair/tests/fixtures/lsp4intellij/IntellijLanguageClient.java").read_bytes()
    with tempfile.TemporaryDirectory(dir=ROOT/"out") as tmp:
      target = Path(tmp)/SOURCE_PATH
      target.parent.mkdir(parents=True)
      target.write_bytes(original)
      record["source_root"] = tmp
      proposal = self.run_case(record)
      self.assertEqual("CANDIDATE_PATCH", proposal["status"], proposal.get("reason"))
      self.assertFalse(proposal["eligible_for_application"])
      self.assertFalse(proposal["applied"])
      wait = copy.deepcopy(record)
      for thread in wait["threads"]:
        if thread["is_ui_thread"]: thread["state"]="WAITING"
      self.assertEqual("NO_SUPPORTED_METHOD",self.run_case(wait)["status"])
      missing = copy.deepcopy(record)
      for thread in missing["threads"]:
        for frame in thread["frames"]:
          if (frame.get("symbol") or "").endswith("Pattern.compile"): frame["symbol"]="example.Other.compile"
      self.assertEqual("NO_SUPPORTED_METHOD",self.run_case(missing)["status"])
      target.write_bytes(original+b"\n// changed\n")
      self.assertNotEqual("CANDIDATE_PATCH",self.run_case(record)["status"])
      target.write_bytes(original)
      patch=Path(tmp)/"candidate.patch";patch.write_text(proposal["patch"],encoding="utf-8",newline="\n")
      p=subprocess.run(["git","apply","--check",str(patch)],cwd=tmp,capture_output=True,text=True)
      self.assertEqual(0,p.returncode,p.stderr)
      p=subprocess.run(["git","apply",str(patch)],cwd=tmp,capture_output=True,text=True)
      self.assertEqual(0,p.returncode,p.stderr)
      self.assertEqual(proposal["replacement_source"],target.read_text(encoding="utf-8"))
      source=original.decode("utf-8")
      before="\n".join(method(source,name) for name in ["isExtensionSupported","processDefinition"])
      after=proposal["helper_source"]+"\n"+"\n".join(method(proposal["replacement_source"],name)
                                                      for name in ["isExtensionSupported","processDefinition"])
      # Pair substitutes the upstream Apache pair API; regexes and generated code remain unchanged.
      java=HARNESS.replace("/*ORIGINAL*/",before).replace("/*FIXED*/",after).replace("new ImmutablePair<>","new Pair<>")
      file=Path(tmp)/"RegexProbe.java";file.write_text(java,encoding="utf-8")
      c=subprocess.run(["javac","-encoding","UTF-8",str(file)],capture_output=True,text=True)
      self.assertEqual(0,c.returncode,c.stderr)
      run=subprocess.run(["java","-cp",tmp,"RegexProbe"],capture_output=True,text=True,timeout=30)
      self.assertEqual(0,run.returncode,run.stdout+run.stderr)
      print(run.stdout.strip())


if __name__=="__main__":
  unittest.main()
