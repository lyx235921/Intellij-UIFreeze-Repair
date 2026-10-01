import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SelectionMappingTest(unittest.TestCase):
  def test_all_75_priorities_match_reviewed_mapping(self):
    source = (ROOT / "repair/main/kotlin/src/pool/s1_expensive_work/repair_selection.kt").read_text(encoding="utf-8")
    pairs = re.findall(r'"([^"\n]+)" to "(P1_FIRST|P2_FIRST|CONTEXT_FIRST)"', source)
    expected = json.loads((ROOT / "repair/docs/Q1-P1-P3-MAPPING-2026-09-27.json").read_text())
    self.assertEqual(75, len(pairs))
    self.assertEqual({x["symbol"]: x["priority"] for x in expected["methods"]},
                     {k.replace("\\$", "$"): v for k, v in pairs})


@unittest.skipUnless(os.environ.get("Q1_CLASSPATH"), "Build classifiers and set Q1_CLASSPATH")
class RepairSelectionTest(unittest.TestCase):
  def test_missing_plugin_source_skips_hit_but_continues_batch(self):
    original = json.loads((ROOT / "repair/tests/fixtures/row1238-finder.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(dir=ROOT / "out") as tmp:
      root = Path(tmp)
      text = "package example.plugin; class Plugin { void run() {} }\n"
      (root / "Plugin.java").write_text(text, encoding="utf-8")
      candidate = {"path": "Plugin.java", "sha256": hashlib.sha256(text.encode()).hexdigest(),
                   "owner": "example.plugin.Plugin", "method": "run", "declaration": "void run()",
                   "language": "java", "basis": "JAVA_AST", "start_line": 1, "end_line": 1}
      missing = copy.deepcopy(original)
      thread = missing["threads"][0]
      trigger = copy.deepcopy(next(f for f in thread["frames"] if (f.get("symbol") or "").endswith("Inflater.end")))
      trigger.update(frame_id="t0:f0", index=0)
      plugin = copy.deepcopy(trigger)
      plugin.update(frame_id="t0:f1", index=1, symbol="example.plugin.Plugin.run", file="Plugin.java", line=1)
      plugin["source"] = {"status": "UNRESOLVED", "reason": "SOURCE_FILE_NOT_FOUND", "candidates": [],
                          "selected": None, "selection_basis": None, "source_diagnostics": [],
                          "historical_identity": "NOT_CHECKED"}
      thread["frames"] = [trigger, plugin]
      present = copy.deepcopy(missing)
      present["source_root"] = str(root)
      present["threads"][0]["frames"][1]["source"].update(
        status="LOCATED", reason=None, candidates=[candidate], selected=candidate, selection_basis="UNIQUE_OWNER_METHOD")
      ambiguous = copy.deepcopy(missing)
      ambiguous["threads"][0]["frames"][1]["source"]["reason"] = "METHOD_NOT_FOUND"
      mixed = copy.deepcopy(missing)
      good_thread = copy.deepcopy(original["threads"][0])
      good_thread["thread_id"] = "t1"
      for f in good_thread["frames"]:
        f["frame_id"] = f["frame_id"].replace("t0:", "t1:")
      mixed["threads"].append(good_thread)
      cases = [missing, present, ambiguous, mixed, copy.deepcopy(original)]
      for index, record in enumerate(cases):
        record["record_id"] += f"-source-gate-{index}"
        record["ui_thread_ids"] = [t["thread_id"] for t in record["threads"] if t["is_ui_thread"]]
        record["cause_thread_ids"] = [t["thread_id"] for t in record["threads"] if t["role"] == "cause"]
        record["call_edges"] = []
        record["entry_frames"] = []
        counts = {}
        for t in record["threads"]:
          for f in t["frames"]:
            state = f["source"]["status"]
            counts[state] = counts.get(state, 0) + 1
        record["location_summary"] = counts
      source, output = root / "input.jsonl", root / "output.jsonl"
      source.write_text("".join(json.dumps(r) + "\n" for r in cases), encoding="utf-8")
      run = subprocess.run([sys.executable, str(ROOT / "repair/main/python/repair.py"), "--input", str(source),
                            "--output", str(output), "--q1-classpath", os.environ["Q1_CLASSPATH"], "--repair-selection"],
                           capture_output=True, text=True, encoding="utf-8")
      self.assertEqual(0, run.returncode, run.stderr)
      records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
      self.assertEqual(5, json.loads(run.stderr)["accepted"])
      self.assertEqual(2, json.loads(run.stderr)["source_skipped_points"])
      self.assertEqual(2, json.loads(run.stderr)["source_skipped_records"])
      skipped, available, unresolved, combined, later = [r["q1"]["repair_selection"] for r in records]
      self.assertEqual("SKIPPED_SOURCE_UNAVAILABLE", skipped["status"])
      decision = skipped["decisions"][0]
      self.assertFalse(decision["patch_generated"])
      self.assertFalse(decision["p3_eligible"])
      self.assertEqual("CONTINUE_NEXT_FREEZE_POINT", decision["next_action"])
      self.assertEqual("example.plugin.Plugin.run", decision["missing_source_contexts"][0]["method_symbol"])
      # Source exists: normal template evaluation, even though this synthetic method has no supported template.
      self.assertEqual("PENDING", available["status"])
      self.assertEqual("PENDING", unresolved["status"])
      self.assertEqual("PARTIAL", combined["status"])
      self.assertEqual({"SKIPPED_SOURCE_UNAVAILABLE", "CANDIDATE_SELECTED"},
                       {d["status"] for d in combined["decisions"]})
      self.assertEqual("CANDIDATE_SELECTED", later["status"])
      self.assertTrue(any(p["status"] == "CANDIDATE_PATCH" for p in later["p2_evaluation"]["proposals"]))
      self.assertEqual(cases, [r["finder"] for r in records])

  def test_p2_all_31_bindings_preserve_context_and_unresolved_layers(self):
    # Synthetic binding coverage, not 31 independently reproduced real incidents.
    mapping = json.loads((ROOT / "repair/docs/Q1-P1-P3-MAPPING-2026-09-27.json").read_text())
    original = json.loads((ROOT / "repair/tests/fixtures/row1238-finder.json").read_text(encoding="utf-8"))
    run = subprocess.run(["java", "-cp", os.environ["Q1_CLASSPATH"],
                          "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier", "--extract-method"],
                         input=json.dumps(original) + "\n", text=True, encoding="utf-8", capture_output=True, check=True)
    base = json.loads(run.stdout)["method_context"]["results"][0]
    layers = []
    for i, entry in enumerate(mapping["methods"]):
      layer = copy.deepcopy(base)
      layer.update(trigger_frame_id=f"t0:f{i}", trigger_symbol=entry["symbol"], problem_category=entry["category"])
      layers.append(layer)
      missing = copy.deepcopy(layer)
      missing.update(status="UNRESOLVED", reason="PROJECT_METHOD_UNAVAILABLE_OR_AMBIGUOUS", method_layer=2)
      missing.pop("method")
      layers.append(missing)
    context = {"schema_version": "repair-method-context/1", "results": layers}
    java = '''
import com.google.gson.*;
import java.nio.file.*;
import org.jetbrains.research.lockrepair.pool.s1.P2ExpensiveWorkRelocation;
class RecognizeCheck {
  public static void main(String[] args) throws Exception {
    var context = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
    System.out.println(P2ExpensiveWorkRelocation.INSTANCE.recognize(context));
  }
}
'''
    with tempfile.TemporaryDirectory() as tmp:
      source, data = Path(tmp) / "RecognizeCheck.java", Path(tmp) / "context.json"
      source.write_text(java, encoding="utf-8")
      data.write_text(json.dumps(context), encoding="utf-8")
      run = subprocess.run(["java", "--class-path", os.environ["Q1_CLASSPATH"], str(source), str(data)],
                           text=True, encoding="utf-8", capture_output=True, check=True)
    recognized = json.loads(run.stdout)
    expected = {x["symbol"] for x in mapping["methods"] if x["priority"] == "P2_FIRST"}
    self.assertEqual(31, len(recognized))
    self.assertEqual(expected, {x["trigger_symbol"] for x in recognized})
    for operation in recognized:
      self.assertEqual("PARTIAL", operation["context_status"])
      self.assertEqual(1, operation["located_method_count"])
      expected_layers = [x for x in layers if x["trigger_symbol"] == operation["trigger_symbol"]]
      self.assertEqual(expected_layers, operation["method_contexts"])

  def run_cases(self, cases):
    result = subprocess.run(
      ["java", "-cp", os.environ["Q1_CLASSPATH"],
       "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier", "--repair-selection"],
      input="".join(json.dumps(r) + "\n" for r in cases),
      capture_output=True, text=True, encoding="utf-8", check=True)
    return [json.loads(line)["repair_selection"] for line in result.stdout.splitlines()]

  def test_real_case_and_missing_changed_unrelated_context(self):
    original = json.loads((ROOT / "repair/tests/fixtures/row1238-finder.json").read_text(encoding="utf-8"))
    changed = copy.deepcopy(original)
    for thread in changed["threads"]:
      for frame in thread["frames"]:
        source = frame.get("source", {})
        for candidate in source.get("candidates", []):
          candidate["sha256"] = "0" * 64
        if source.get("selected"):
          source["selected"]["sha256"] = "0" * 64
    unrelated = copy.deepcopy(original)
    for thread in unrelated["threads"]:
      for frame in thread["frames"]:
        if (frame.get("symbol") or "").endswith("javax.imageio.ImageIO.read"):
          frame["symbol"] = "javax.imageio.ImageIO.other"
    no_hit = copy.deepcopy(original)
    for thread in no_hit["threads"]:
      for frame in thread["frames"]:
        frame["symbol"] = "java.lang.Other.work"
    good, stale, wrong_path, empty = self.run_cases([original, changed, unrelated, no_hit])
    self.assertEqual("CANDIDATE_SELECTED", good["status"])
    decision = good["decisions"][0]
    self.assertEqual("CONTEXT_FIRST", decision["initial_priority"])
    self.assertTrue(decision["initial_tie"])
    self.assertEqual("P2", decision["selected_strategy"])
    self.assertEqual("INSUFFICIENT_EVIDENCE", decision["p1_status"])
    self.assertEqual("NOT_IMPLEMENTED", decision["p1_generator_status"])
    evidence = decision["source_preconditions"][0]
    p1 = {c["id"]: c for c in evidence["p1"]["checks"]}
    self.assertEqual("PASS", p1["SOURCE"]["status"])
    self.assertEqual("PASS", p1["INPUTS_AVAILABLE_EARLY"]["status"])
    self.assertEqual("UNKNOWN", p1["PRELOAD_INSERTION_POINT"]["status"])
    scopes = evidence["p3"]["scopes"]
    self.assertEqual("NOT_APPLICABLE", scopes[0]["status"])
    self.assertEqual("INSUFFICIENT_EVIDENCE", scopes[1]["status"])
    self.assertFalse(decision["p3_eligible"])
    proposal = good["p2_evaluation"]["proposals"][decision["selected_proposal_index"]]
    self.assertEqual("CANDIDATE_PATCH", proposal["status"])
    self.assertIn("supplyAsync", proposal["patch"])
    for selection in (stale, wrong_path):
      self.assertEqual("PENDING", selection["status"])
      self.assertTrue(all(not d["p3_eligible"] and "selected_strategy" not in d for d in selection["decisions"]))
      for d in selection["decisions"]:
        for e in d["source_preconditions"]:
          self.assertEqual("INSUFFICIENT_EVIDENCE", e["p1"]["status"])
          self.assertEqual("INSUFFICIENT_EVIDENCE", e["p3"]["scopes"][0]["status"])
    self.assertEqual("NOT_APPLICABLE", empty["status"])

  def test_python_entry_and_combined_legacy_flag(self):
    original = (ROOT / "repair/tests/fixtures/row1238-finder.json").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
      source, output = Path(tmp) / "input.jsonl", Path(tmp) / "output.jsonl"
      source.write_text(json.dumps(json.loads(original)) + "\n", encoding="utf-8")
      subprocess.run([sys.executable, str(ROOT / "repair/main/python/repair.py"), "--input", str(source),
                      "--output", str(output), "--q1-classpath", os.environ["Q1_CLASSPATH"],
                      "--repair-selection", "--s1-p2"], check=True, capture_output=True)
      intake = json.loads(output.read_text(encoding="utf-8"))
      self.assertEqual(json.loads(original), intake["finder"])
      self.assertEqual("CANDIDATE_SELECTED", intake["q1"]["repair_selection"]["status"])
      self.assertEqual(intake["q1"]["s1_p2"], intake["q1"]["repair_selection"]["p2_evaluation"])

  def test_p3_fallback_truth_table(self):
    java = '''
import org.jetbrains.research.lockrepair.pool.s1.RepairSelection;
class FallbackCheck {
  public static void main(String[] args) {
    for (var a : RepairSelection.Outcome.values()) {
      for (var b : RepairSelection.Outcome.values()) {
        boolean expected = (a.name().equals("FAILED") || a.name().equals("NOT_APPLICABLE"))
            && (b.name().equals("FAILED") || b.name().equals("NOT_APPLICABLE"));
        if (RepairSelection.INSTANCE.canTryP3(a, b) != expected) throw new AssertionError(a + "/" + b);
      }
    }
  }
}
'''
    with tempfile.TemporaryDirectory() as tmp:
      source = Path(tmp) / "FallbackCheck.java"
      source.write_text(java, encoding="utf-8")
      subprocess.run(["java", "--class-path", os.environ["Q1_CLASSPATH"], str(source)],
                     check=True, capture_output=True)

  def test_preconditions_recheck_saved_source_and_three_way_verdict(self):
    original = json.loads((ROOT / "repair/tests/fixtures/row1238-finder.json").read_text(encoding="utf-8"))
    result = subprocess.run(
      ["java", "-cp", os.environ["Q1_CLASSPATH"],
       "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier", "--extract-method"],
      input=json.dumps(original) + "\n", capture_output=True, text=True, encoding="utf-8", check=True)
    context = json.loads(result.stdout)["method_context"]["results"][0]
    java = '''
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import org.jetbrains.research.lockrepair.pool.s1.*;
class PreconditionsCheck {
  static void assertStatus(JsonObject report, String id, String status) {
    for (var element : report.getAsJsonArray("checks")) {
      var c = element.getAsJsonObject();
      if (c.get("id").getAsString().equals(id)) {
        if (!c.get("status").getAsString().equals(status)) throw new AssertionError(c);
        return;
      }
    }
    throw new AssertionError("Missing " + id);
  }
  public static void main(String[] args) throws Exception {
    var c = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
    var root = Path.of(args[1]);
    assertStatus(P1PreloadBeforeCriticalRegion.INSTANCE.check(c, root), "SOURCE", "PASS");
    var checked = RelocationPreconditions.INSTANCE.checkP2(c.getAsJsonObject("method"), root);
    if (!checked.getStatus().equals("PRECONDITIONS_MET") || checked.getSourceText() == null) throw new AssertionError(checked);
    for (String fault : List.of("hash", "range", "escape", "text", "shape", "missing")) {
      var altered = c.deepCopy();
      var m = altered.getAsJsonObject("method");
      switch (fault) {
        case "hash": m.addProperty("sha256", "0".repeat(64)); break;
        case "range": m.addProperty("start_line", 0); break;
        case "escape": m.addProperty("path", "../outside.java"); break;
        case "text": m.addProperty("source_text", "changed"); break;
        case "shape": m.addProperty("owner", "Other"); break;
        case "missing": altered.addProperty("status", "UNRESOLVED"); break;
      }
      var p1 = P1PreloadBeforeCriticalRegion.INSTANCE.check(altered, root);
      assertStatus(p1, "SOURCE", fault.equals("shape") ? "PASS" : "UNKNOWN");
      assertStatus(p1, "INPUTS_AVAILABLE_EARLY", "UNKNOWN");
      var p3 = P3DeferExpensiveOperation.INSTANCE.check(altered, root);
      if (!p3.get("status").getAsString().equals("INSUFFICIENT_EVIDENCE")) throw new AssertionError(p3);
      if (!fault.equals("missing")) {
        var p2 = RelocationPreconditions.INSTANCE.checkP2(m, root);
        String expected = fault.equals("shape") || fault.equals("text") ? "UNSUPPORTED" : "UNAVAILABLE";
        if (!p2.getStatus().equals(expected) || p2.getSourceText() != null) throw new AssertionError(p2);
      }
    }
    var collision = c.getAsJsonObject("method").deepCopy();
    var temporaryRoot = Path.of(args[0]).getParent();
    String text = checked.getSourceText() + "\\n// myP2OkIconBytes\\n";
    Files.writeString(temporaryRoot.resolve("collision.java"), text);
    collision.addProperty("path", "collision.java");
    collision.addProperty("sha256", HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256")
        .digest(text.getBytes(java.nio.charset.StandardCharsets.UTF_8))));
    var rejected = RelocationPreconditions.INSTANCE.checkP2(collision, temporaryRoot);
    if (!"GENERATED_NAME_COLLISION".equals(rejected.getReason()) || rejected.getSourceText() != null) throw new AssertionError(rejected);
    var checks = new ArrayList<RelocationPreconditions.Check>();
    var rules = RelocationPreconditions.INSTANCE;
    if (!rules.status(checks).equals("INSUFFICIENT_EVIDENCE")) throw new AssertionError();
    checks.add(new RelocationPreconditions.Check("a", RelocationPreconditions.Verdict.PASS, "observed"));
    if (!rules.status(checks).equals("PRECONDITIONS_MET")) throw new AssertionError();
    checks.add(new RelocationPreconditions.Check("b", RelocationPreconditions.Verdict.UNKNOWN, "missing"));
    if (!rules.status(checks).equals("INSUFFICIENT_EVIDENCE")) throw new AssertionError();
    checks.add(new RelocationPreconditions.Check("c", RelocationPreconditions.Verdict.FAIL, "contradiction"));
    if (!rules.status(checks).equals("NOT_APPLICABLE")) throw new AssertionError();
  }
}
'''
    with tempfile.TemporaryDirectory(dir=ROOT / "out") as tmp:
      source, data = Path(tmp) / "PreconditionsCheck.java", Path(tmp) / "context.json"
      source.write_text(java, encoding="utf-8")
      data.write_text(json.dumps(context), encoding="utf-8")
      run = subprocess.run(["java", "--class-path", os.environ["Q1_CLASSPATH"], str(source), str(data),
                            original["source_root"]], capture_output=True, text=True)
      self.assertEqual(0, run.returncode, run.stderr)


if __name__ == "__main__":
  unittest.main()
