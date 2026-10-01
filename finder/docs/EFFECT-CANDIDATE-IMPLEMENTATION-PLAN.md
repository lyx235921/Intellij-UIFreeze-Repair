# Effect-Summary Candidate Lane Production Integration Plan

> **Canonical location:** This repository file is the active implementation plan. Session/visualization copies are historical artifacts only.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Productionize the validated `Source/Callable -> MethodEffectSummary -> bounded CallEdge -> LifecycleReachability` chain as an explainable, high-recall Java candidate lane without changing the existing Finder result contract or Task 0 persistence behavior.

**Architecture:** Add a source-set analyzer beside `../finder.py`. Its public seam is `discover_effect_candidates(paths)`, returning deterministic candidates with explicit evidence level, analysis mode, effect/lifecycle model provenance, complete or truncated path status, and resource-budget diagnostics. Existing `analyze_file()`, `recommend()`, confidence assessment, the 21-column golden set, CLI defaults, and `problems.xlsx` persistence remain unchanged until a separate promotion gate is approved. A sealed corpus is prepared and preflighted before analyzer freeze; evaluation never begins by searching for data after the freeze.

**Tech Stack:** Python 3.12, `unittest`, tree-sitter Java, immutable dataclasses, JSON/TSV fixtures, local historical Java blobs; no network access during tests.

**Spec:**

- `tools/edt-freeze-finder/finder/docs/STAGE2-DESIGN.md`
- `tools/edt-freeze-finder/PROGRESS.md`

**Status policy:** This file preserves the target architecture and TDD sequence; its checkboxes are not the current progress source. Tasks 0–5.5A and the Task 7R-B eligibility/runner infrastructure are implemented in the uncommitted working tree. Task 6 ran once and remains an immutable `TRANSFER_CONTRACT_FAILURE`; the bounded Task 7R-B cycle completed with 96/96 tests Green and stopped before a second canary because no new independent case matched the supported transfer target. The candidate lane remains `EXPERIMENTAL/REVISE`. `tools/edt-freeze-finder/PROGRESS.md` is the sole authoritative current-status source.

## Global Constraints

- Do not begin production edits until the existing Stage 3 Task 0 dirty worktree is reviewed and placed at a user-approved Green checkpoint.
- Do not copy `effect_spike.py` into production. Rebuild behavior through production public seams using TDD.
- Java only. Kotlin/UAST, full repository call graphs, interface dispatch, overload type resolution, and data-flow analysis remain out of scope.
- The supplied source set is the analysis boundary. Analysis uses explicit budgets for depth, nodes, edges, and elapsed time; exceeding a budget produces a lower-evidence `TRUNCATED` candidate instead of silently dropping the path.
- Evidence levels are `SYNTAX_HINT`, `SOURCE_RESOLVED`, `SEMANTIC_MODEL`, and future `COMPILER_VERIFIED`. Tree-sitter simple-name/declared-type resolution must never be labeled compiler-verified.
- Every candidate records `analysis_mode`, `effect_model_id`, `lifecycle_contract_id`, `path_status`, `truncation_reason`, and the effective analysis budget.
- Direct effect models are declarative and versioned. Name/type-suffix heuristics may produce `SYNTAX_HINT`; exact modeled signatures with provenance may produce `SEMANTIC_MODEL`.
- Real sealed packages live outside the implementation checkout under the required `EFFECT_CANDIDATE_SEALED_ROOT` path. Production/tests receive only an explicit package path; no code searches user directories for packages.
- A call edge exists only when owner, method, and parameter signature resolve uniquely through the supported rules. Ambiguity is recorded; it is never guessed away.
- Known IJPL-239329 sources are `development`, not `evaluation`, because they have already influenced the architecture.
- Production implementation and micro tests must not contain Issue IDs, commit hashes, challenge type names, source filenames, or challenge-only method names.
- Existing `analyze_file(path)`, `recommend(result)`, `create_assessment(...)`, `record_findings(...)`, and golden-set columns remain byte-for-byte compatible.
- Effect candidates are not written to `notes/problems.xlsx` and do not receive problem/repair confidence during this plan.
- `../../PROGRESS.md` is updated only after a complete Green checkpoint.
- Do not create a worktree or commit unless the user explicitly approves that operation.

---

## Planned File Structure

- Create `tools/edt-freeze-finder/finder/source_model.py`: immutable source, type, callable, invocation, and source-range records; Java source-set parsing.
- Create `tools/edt-freeze-finder/finder/effect_models.py`: versioned declarative effect models, lifecycle contracts, model provenance, and evidence-level rules.
- Create `tools/edt-freeze-finder/finder/effect_analysis.py`: `MethodEffectSummary`, budgeted `CallEdge` resolution, cached/fixpoint effect propagation, and truncation diagnostics.
- Create `tools/edt-freeze-finder/finder/candidate_discovery.py`: `LifecycleReachability`, deterministic candidate IDs, serialization, and the public composition seam.
- Create `tools/edt-freeze-finder/finder/test_candidate_discovery.py`: public-seam TDD and deterministic output checks.
- Create `tools/edt-freeze-finder/finder/test_effect_candidate_golden_set.py`: source-set manifest and oracle contract.
- Create `tools/edt-freeze-finder/finder/golden/java-effect-candidate-oracle.tsv`: a separate source-set oracle; do not alter `java-golden-set.tsv`.
- Create `tools/edt-freeze-finder/finder/sealed_corpus.py`: generic sealed-manifest, Git provenance, source-closure, package-hash, and canary validation; it contains no real evaluation case identifiers.
- Create `tools/edt-freeze-finder/finder/test_effect_candidate_corpus_contract.py`: synthetic package-readiness and failure-mode tests.
- Create `tools/edt-freeze-finder/finder/fixtures/effect_candidates/micro/`: challenge-independent before/after/negative fixtures.
- Create `tools/edt-freeze-finder/finder/fixtures/effect_candidates/effect_service_initialization_001/`: validated historical parent/after source sets and manifest.
- Modify `tools/edt-freeze-finder/finder/finder.py` only in the later opt-in CLI task, after the current Task 0 checkpoint is safe.

## Public Interfaces

```python
def discover_effect_candidates(
    paths: Sequence[str | Path],
) -> list[dict[str, object]]:
    """Return deterministic high-recall candidates for one explicit Java source set."""
```

Each candidate has this exact initial contract:

```python
{
    "candidate_id": str,
    "candidate_level": "SYNTAX_HINT | SOURCE_RESOLVED | SEMANTIC_MODEL | COMPILER_VERIFIED",
    "analysis_mode": "SOURCE_SET_BOUNDED",
    "rule_id": "SERVICE_INITIALIZATION",
    "lifecycle_callable": str,
    "lifecycle_source": str,
    "lifecycle_line": int,
    "effect_kind": "EAGER_INSTANCE_MATERIALIZATION",
    "effect_model_id": str,
    "lifecycle_contract_id": str,
    "effect_path": list[dict[str, object]],
    "path_status": "COMPLETE | TRUNCATED | UNRESOLVED",
    "truncation_reason": str | None,
    "analysis_budget": {
        "max_depth": int,
        "max_nodes": int,
        "max_edges": int,
        "timeout_ms": int,
    },
    "source_files": list[str],
    "unresolved_edges": list[dict[str, object]],
}
```

Every `effect_path` step contains `kind`, `callable_id`, `source_file`, `line`, `evidence`, `resolution`, and `model_id`. Paths and candidates are sorted deterministically by normalized repository-relative source path, source line, callable ID, and effect kind.

`COMPLETE` means the modeled effect was reached without unresolved dispatch or budget exhaustion. `TRUNCATED` means a plausible path reached a budget boundary before the effect was proved; it remains a high-recall candidate but cannot be promoted to a confirmed finding. `UNRESOLVED` means a relevant edge or model could not be resolved and the candidate records the exact reason.

> **Migration history (2026-08-25):** the earlier implementation emitted `TYPED_MATCH` and silently dropped effects beyond depth 6. Tasks 2 and 3 migrated that behavior to the evidence/model/budget contract below, including `SYNTAX_HINT/SOURCE_RESOLVED/SEMANTIC_MODEL` and `COMPLETE/TRUNCATED/UNRESOLVED`. Current evidence is recorded in `../../PROGRESS.md`; this historical note is not a pending task.

Callable identity is:

```text
package.Outer.Inner#method(parameterSimpleTypes)
```

Constructors use `<init>`. Source line/range is evidence, not part of callable identity.

---

### Task 0: Protect the Existing Stage 3 Task 0 Green Checkpoint

**Files:**

- Review only: `tools/edt-freeze-finder/finder/finder.py`
- Review only: `tools/edt-freeze-finder/PROGRESS.md`
- Review only: `tools/edt-freeze-finder/finder/confidence_model.py`
- Review only: `tools/edt-freeze-finder/finder/problems_report.py`
- Review only: `tools/edt-freeze-finder/finder/test_confidence.py`
- Review only: `tools/edt-freeze-finder/finder/test_problems_report.py`

**Interfaces:**

- Consumes: the current uncommitted Task 0 worktree.
- Produces: a user-approved Green baseline that later tasks may safely build on.

- [ ] **Step 1: Re-run the existing baseline**

  ```powershell
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_*.py" -v
  ```

  Expected: 38/38 tests Green. If the count changes, stop and inspect the new test set rather than treating 38 as a permanent constant.

- [ ] **Step 2: Review the existing dirty scope**

  ```powershell
  git status --short
  git diff -- tools/edt-freeze-finder/finder/finder.py tools/edt-freeze-finder/PROGRESS.md
  ```

  Expected: only the already-known confidence/reporting/Task0 files and `notes/problems*` artifacts. No effect-summary production files exist yet.

- [ ] **Step 3: Obtain the user's checkpoint decision**

  Do not start Task 1 until the user either accepts the current Task 0 worktree as the baseline or explicitly requests a commit. If a commit is requested, use the repository `commits` skill and commit Task 0 separately from effect-summary work.

### Task 1: Build the One-File Public Tracer Bullet

**Files:**

- Create: `tools/edt-freeze-finder/finder/source_model.py`
- Create: `tools/edt-freeze-finder/finder/effect_analysis.py`
- Create: `tools/edt-freeze-finder/finder/candidate_discovery.py`
- Create: `tools/edt-freeze-finder/finder/test_candidate_discovery.py`
- Create: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/micro/before/SettingsCandidate.java`

**Interfaces:**

- Consumes: one Java source path.
- Produces: `discover_effect_candidates(paths)` and the exact candidate schema above.

- [ ] **Step 1: Write the missing-seam Red**

  ```python
  def test_micro_before_reports_complete_effect_path(self):
      paths = [MICRO / "before" / "SettingsCandidate.java"]

      candidates = discover_effect_candidates(paths)

      self.assertEqual(1, len(candidates))
      self.assertEqual("SERVICE_INITIALIZATION", candidates[0]["rule_id"])
      self.assertEqual("SYNTAX_HINT", candidates[0]["candidate_level"])
      self.assertEqual("SOURCE_SET_BOUNDED", candidates[0]["analysis_mode"])
      self.assertEqual("COMPLETE", candidates[0]["path_status"])
      self.assertEqual(
          ["lifecycle", "call", "call", "effect"],
          [step["kind"] for step in candidates[0]["effect_path"]],
      )
      self.assertEqual(
          "EAGER_INSTANCE_MATERIALIZATION",
          candidates[0]["effect_kind"],
      )
  ```

- [ ] **Step 2: Verify Red**

  ```powershell
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_candidate_discovery.py" -v
  ```

  Expected: import failure because `../candidate_discovery.py` does not exist.

- [ ] **Step 3: Implement the smallest complete vertical slice**

  In `../source_model.py`, define immutable `SourceUnit`, `JavaType`, `JavaCallable`, `Invocation`, and `SourceSetModel`. Parse package, imports, classes, interfaces, fields, parameters, locals, methods, constructors, return types, and exact source ranges.

  In `../effect_analysis.py`, define:

  ```python
  @dataclass(frozen=True)
  class MethodEffectSummary:
      callable_id: str
      direct_effects: tuple[EffectEvidence, ...]
      reachable_effects: tuple[EffectPath, ...]

  @dataclass(frozen=True)
  class CallEdge:
      caller_id: str
      callee_id: str
      evidence: str
      resolution: str
  ```

  Support only an adapter/factory/provider instance-producing callable containing object creation. This suffix/name evidence is `SYNTAX_HINT`, not typed proof. Do not add historical API names.

  In `../candidate_discovery.py`, identify typed `Configurable` lifecycle methods (`createComponent`, `buildConfigurables`) and serialize one complete path.

- [ ] **Step 4: Verify Green and compatibility**

  Run the focused test, then the full Finder suite. Existing findings and golden-set rows must remain unchanged.

- [ ] **Step 5: Review checkpoint**

  Inspect only the three new modules, micro fixture, and test. Commit only if the user requested commits.

### Task 2: Refine the Direct Effect Seed with After and Same-Name Controls

**Files:**

- Create: `tools/edt-freeze-finder/finder/effect_models.py`
- Create: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/micro/after/SettingsCandidate.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/micro/negative/SameNamedFactory.java`
- Modify: `tools/edt-freeze-finder/finder/effect_analysis.py`
- Modify: `tools/edt-freeze-finder/finder/test_candidate_discovery.py`

**Interfaces:**

- Consumes: the Task 1 public seam.
- Produces: type-backed effect evidence that rejects ordinary UI construction and unrelated same-named methods.

- [ ] **Step 1: Write the after Red**

  The after fixture still constructs a normal Swing component but obtains only lazy keys. Assert `discover_effect_candidates(...) == []`. Run the focused test and confirm the current implementation falsely reports ordinary construction.

- [ ] **Step 2: Implement the minimal after Green**

  Require instance-producing callable semantics plus adapter/factory/provider receiver/type evidence. A plain `new JPanel()` in a lifecycle method is not `EAGER_INSTANCE_MATERIALIZATION`.

- [ ] **Step 3: Write the same-name Red**

  The negative fixture calls an unrelated `instantiate()` or `getInstance()` method on a type with no lazy/adapter/factory/provider role. Assert zero candidates and verify the name-only implementation fails.

- [ ] **Step 4: Implement the typed Green**

  Introduce declarative direct-effect specifications inside `../effect_models.py`:

  ```python
  @dataclass(frozen=True)
  class DirectEffectSpec:
      model_id: str
      receiver_fqns: tuple[str, ...]
      receiver_type_suffixes: tuple[str, ...]
      method_names: tuple[str, ...]
      effect_kind: str
      evidence_level: str
      provenance: str
  ```

  A suffix/name model for `LazyInstance`, `LazyValue`, or `LazyProvider` remains `SYNTAX_HINT`. A model with an exact receiver FQN and method signature plus provenance may emit `SEMANTIC_MODEL`. Do not match a bare method name, and do not call suffix matching typed evidence.

- [ ] **Step 5: Run focused and full tests**

  Expected: micro before=1, after=0, same-name negative=0; existing suite remains Green.

### Task 3: Add the Bounded Multi-File Call Graph

**Files:**

- Create: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/micro/source_set_before/*.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/micro/source_set_after/*.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/micro/source_set_negative/*.java`
- Modify: `tools/edt-freeze-finder/finder/source_model.py`
- Modify: `tools/edt-freeze-finder/finder/effect_analysis.py`
- Modify: `tools/edt-freeze-finder/finder/test_candidate_discovery.py`

**Interfaces:**

- Consumes: an explicit sequence of Java source paths.
- Produces: unique cross-file `CallEdge` records, cached summaries, explicit budgets, and complete/truncated/unresolved effect propagation.

- [ ] **Step 1: Write the source-set Red**

  Use anonymous micro types to require this exact shape:

  ```text
  Configurable#buildConfigurables
  -> static utility method
  -> Subclass.INSTANCE.inheritedCollectorMethod
  -> lazyInstance.getInstance
  ```

  Assert one candidate and the literal four-step effect path. Verify Task 2 returns zero because it has no cross-file/inherited edge model.

- [ ] **Step 2: Implement only these resolution rules**

  - implicit `this` receiver;
  - field/local/parameter declared type;
  - explicit static type receiver;
  - `Type.INSTANCE.method()` static singleton receiver;
  - chained receiver whose uniquely resolved inner callable supplies the return type;
  - unique inherited method through a bounded superclass chain;
  - exact method parameter signature, with arity as a fallback only when no overload shares that arity.

  Reject or record every ambiguous edge. Do not implement virtual/interface dispatch.

- [ ] **Step 3: Add explicit budgets and cached propagation**

  Define the default profile:

  ```python
  AnalysisBudget(
      max_depth=6,
      max_nodes=500,
      max_edges=2000,
      timeout_ms=2000,
  )
  ```

  Store each callable summary once per source-set/model/budget fingerprint and consume cached callee summaries from callers. Collapse strongly connected components or use a worklist/fixpoint so recursion terminates without repeatedly expanding the same subtree.

  Add an exact-six-edge positive control with `path_status=COMPLETE`. Add a seven-edge control that emits one lower-evidence candidate with `path_status=TRUNCATED`, `truncation_reason=max_depth`, and the partial path. Repeat for node, edge, and timeout budgets using small synthetic limits. No budget exhaustion may silently become zero candidates.

- [ ] **Step 4: Add ambiguity and same-signature controls**

  Two possible receiver types or overload targets must not produce a guessed edge. The candidate output must preserve deterministic `unresolved_edges` diagnostics and use `path_status=UNRESOLVED` when the ambiguous edge is relevant to the candidate path.

- [ ] **Step 5: Run focused and full tests twice**

  Compare serialized candidate JSON byte-for-byte across two runs.

### Task 4: Admit IJPL-239329 as Development Evidence

**Files:**

- Create: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/effect_service_initialization_001/manifest.json`
- Create: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/effect_service_initialization_001/before/*.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/effect_service_initialization_001/after/*.java`
- Create: `tools/edt-freeze-finder/finder/golden/java-effect-candidate-oracle.tsv`
- Create: `tools/edt-freeze-finder/finder/test_effect_candidate_golden_set.py`

**Interfaces:**

- Consumes: exact validated historical blobs and `discover_effect_candidates(paths)`.
- Produces: a versioned source-set development oracle with before=1 and after=0.

- [ ] **Step 1: Write the generic manifest/oracle Red**

  Freeze TSV columns:

  ```text
  specimen_id	split	manifest_path	variant	expected_candidate_count	candidate_level	analysis_mode	rule_id	lifecycle_callable	lifecycle_contract_id	effect_kind	effect_model_id	path_status	expected_effect_path	oracle_status	oracle_kind	adjudication_note
  ```

  Validate unique IDs, `split in {development,evaluation}`, `oracle_status in {EXPECTED_FOUND, EXPECTED_ABSENT, KNOWN_FN, KNOWN_FP}`, evidence/path enums, existing manifests, normalized relative source paths, exact blob SHA-1 values, before/after refs, and nonblank adjudication notes.

- [ ] **Step 2: Verify Red**

  Expected: failure only because the oracle and source-set fixture do not exist.

- [ ] **Step 3: Import exact historical blobs**

  Copy the four validated parent and after Java sources. Record Issue ID, full commit SHA, source path, ref, and Git blob SHA only in `manifest.json`; tests load the manifest generically and do not name the Issue or APIs.

- [ ] **Step 4: Add development expectations**

  Require the exact full path:

  ```text
  Configurable lifecycle
  -> utility wrapper
  -> inherited extension collector
  -> eager lazy-instance materialization
  ```

  Expected: parent=1 with `candidate_level=SEMANTIC_MODEL` and `path_status=COMPLETE`; after=0. The after source may retain the eager accessor elsewhere; it passes only because lifecycle reachability disappears. The exact platform receiver/method model records a stable `effect_model_id`, and the Configurable entry records a stable `lifecycle_contract_id`.

- [ ] **Step 5: Add the leakage guard**

  Scan production `.py`, micro fixtures, and test source for the manifest's Issue ID, commit SHA, source filenames, challenge types, and challenge-only methods. Exact metadata is allowed only in the historical source set, manifest, and oracle.

- [ ] **Step 6: Run focused, full, style, and determinism checks**

  ```powershell
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_candidate_discovery.py" -v
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_effect_candidate_golden_set.py" -v
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_*.py" -v
  python -m flake8 --max-line-length=140 tools/edt-freeze-finder/finder/source_model.py tools/edt-freeze-finder/finder/effect_analysis.py tools/edt-freeze-finder/finder/candidate_discovery.py tools/edt-freeze-finder/finder/test_candidate_discovery.py tools/edt-freeze-finder/finder/test_effect_candidate_golden_set.py
  git diff --check
  ```

  Stop here for user review. Tasks 1-4 are the smallest production-worthy vertical slice.

### Task 5: Add an Opt-In CLI Candidate Report

**Files:**

- Modify: `tools/edt-freeze-finder/finder/finder.py`
- Create: `tools/edt-freeze-finder/finder/test_candidate_cli.py`

**Interfaces:**

- Consumes: the file list already expanded by `finder.main()` and `discover_effect_candidates(files)`.
- Produces: an opt-in, deterministic candidate section; no workbook writes.

- [ ] **Step 1: Confirm the Task 0 checkpoint again**

  Do not modify `../finder.py` if Task 0 changes are still unreviewed or moving.

- [ ] **Step 2: Write the CLI Red**

  Add a test for `--effect-candidates` requiring one candidate with the full rendered path. A default invocation must remain byte-for-byte compatible with the existing CLI behavior.

- [ ] **Step 3: Implement the opt-in flag**

  Parse the flag in `_parse_args()`, call `discover_effect_candidates(files)` once after file expansion, and print candidates in deterministic order. Do not merge candidates into `analyze_file()` results, tallies, recommendations, confidence, or `problem_records`.

- [ ] **Step 4: Run CLI and full regression tests**

  Verify default CLI output and workbook tests are unchanged. Verify the opt-in path never creates or updates `problems.xlsx` from an effect candidate.

### Task 5.5: Prepare and Preflight a Sealed Evaluation Corpus

**Files:**

- Create: `tools/edt-freeze-finder/finder/sealed_corpus.py`
- Create: `tools/edt-freeze-finder/finder/test_effect_candidate_corpus_contract.py`
- Create outside the implementation checkout under `EFFECT_CANDIDATE_SEALED_ROOT`: curator-owned opaque package directories. The environment variable is required for real preflight/evaluation and is never given a machine-specific default in production code.

**Interfaces:**

- Consumes: sealed manifest/source packages created by an independent curator; the validator receives only a package path.
- Produces: `preflight_sealed_package(path) -> dict[str, object]` and immutable `PACKAGE_READY.json` records. It does not import or run the production analyzer.

- [ ] **Step 1: Write synthetic package-contract Reds**

  Through temporary synthetic packages, require rejection of:

  - missing commit/parent/ref/source path;
  - a source entry without a full Git blob hash;
  - a before/after ref relationship that cannot be verified;
  - incomplete source closure declared by the causal-path audit;
  - known/exposed Issue, commit, source, or derivative fixture overlap;
  - missing selector/auditor reports;
  - invalid JSON, source encoding, or evaluator syntax;
  - an evaluator that reads analyzer implementation files instead of the public seam;
  - a package whose recorded file hashes do not match its bytes.

- [ ] **Step 2: Implement generic preflight validation**

  `../sealed_corpus.py` contains no real Issue, commit, class, API, or source filename. It validates manifest schema, Git provenance, complete materialization of every declared full Java blob, selector/auditor signatures, package hashes, and evaluator AST syntax. It emits a deterministic readiness record:

  ```python
  {
      "status": "READY",
      "package_id": str,
      "package_sha256": str,
      "case_count": int,
      "before_source_count": int,
      "after_source_count": int,
      "provenance_valid": True,
      "source_closure_valid": True,
      "causal_audit_valid": True,
      "evaluator_canary_valid": True,
  }
  ```

- [ ] **Step 3: Curate packages before analyzer freeze**

  An independent Luna selector prepares at least one previously unseen Java service-initialization before/after package and compares it against every development/exposed case. The parent receives only an opaque package ID and `READY`/`BLOCKED`, never Issue/API/source details. One READY package is sufficient to run the Task 6 feasibility canary; promotion later requires a larger independent pool and must not treat one case as a recall estimate.

- [ ] **Step 4: Audit source closure and causal labels independently**

  A second Luna reads the full source package but not analyzer implementation. It verifies the shortest UI/Configurable lifecycle path, the eager materialization effect, the after mitigation, EDT/lifecycle evidence, Git blob provenance, and independence. Dynamic dispatch or missing callees are recorded as audit failures rather than inferred away.

- [ ] **Step 5: Run a neutral evaluator canary**

  Before freezing the real analyzer, materialize every sealed blob and run the packaged evaluator against an injected deterministic stub implementing the same public result shape. This proves path handling, JSON serialization, repeated-run determinism, structured success parsing, and exit-code independence without revealing whether the production analyzer will pass.

- [ ] **Step 6: Seal readiness metadata**

  Hash the package, manifest, source blobs, selector report, auditor report, and evaluator. Write `PACKAGE_READY.json`. If no package reaches READY, stop before analyzer freeze and report a data-readiness blocker.

### Task 5.5A: Eliminate Provenance Drift with Git-Native Curation

**Files:**

- Create: `tools/edt-freeze-finder/finder/sealed_curator.py`
- Create: `tools/edt-freeze-finder/finder/test_effect_candidate_curator_git.py`
- Modify: `tools/edt-freeze-finder/finder/sealed_corpus.py`
- Modify: `tools/edt-freeze-finder/finder/test_effect_candidate_corpus_contract.py`

**Interfaces:**

- Consumes: a curator-private request mapping and an empty destination path. The request contains an explicit local Git repository path, opaque package/case IDs, full before/after commit refs, explicit Java source paths for each variant, selector independence results, and tri-state lifecycle prechecks.
- Produces: `materialize_git_package(request, destination) -> dict[str, object]`, a deterministic staged schema-v1 package whose commit proof, refs, source blobs, Git SHA-1 values, fixture bytes, selector report, neutral evaluator, and package hashes come directly from the Git object database. It never writes the private request or repository path into the package, never imports the analyzer, and never creates an auditor report or `PACKAGE_READY.json`.

The curator-private request has this exact initial contract:

```python
{
    "schema_version": 1,
    "package_id": "opaque-package-001",
    "repository_path": str,
    "selector": {
        "signed_by": str,
        "independence_audit": {
            "status": "PASS",
            "exposed_issue_ids": [],
            "exposed_commit_shas": [],
            "exposed_source_paths": [],
            "derivative_fixture_overlaps": [],
        },
    },
    "cases": [{
        "case_id": "case-001",
        "before": {
            "ref": "1111111111111111111111111111111111111111",
            "sources": [{"source_path": "normalized/repository/path.java"}],
        },
        "after": {
            "ref": "2222222222222222222222222222222222222222",
            "sources": [{"source_path": "normalized/repository/path.java"}],
        },
        "selector_precheck": {
            "before_lifecycle_reachable": "YES | NO | UNKNOWN",
            "after_lifecycle_cut": "YES | NO | UNKNOWN",
        },
    }],
}
```

Only `YES/YES` may materialize. These selector prechecks move obvious causal failures before packaging but are not evaluation truth; the different-signer auditor must still independently emit `lifecycle_evidence=VERIFIED`, `causal_path=VERIFIED`, and `after_mitigation=VERIFIED`.

- [ ] **Step 1: Write the selector-precheck Red**

  Extend the synthetic sealed-package contract so every selected case has one signed `case_prechecks` entry. Reject missing, duplicate, `NO`, or `UNKNOWN` values for `before_lifecycle_reachable` or `after_lifecycle_cut`. Keep the independent auditor gates unchanged.

- [ ] **Step 2: Implement the selector-precheck Green**

  Update only generic selector-report validation. Existing synthetic packages add `YES/YES`; no real case identifier enters production or tests.

- [ ] **Step 3: Write the Git-native tracer Red**

  In a temporary local SHA-1 Git repository, create a parent and one-child fixing commit containing UTF-8 Java. Call `materialize_git_package(...)` through its public seam. Assert the staged manifest refs equal the resolved commit IDs, the raw commit proof hashes to the after commit, each fixture byte sequence equals `git cat-file blob`, the selector report contains `YES/YES`, no repository path is serialized, and a different-signer synthetic auditor can make the existing preflight return READY.

- [ ] **Step 4: Implement exact Git-object materialization**

  Resolve refs with `git rev-parse --verify <ref>^{commit}`; require SHA-1 object format and a single-parent after commit whose parent is the declared before ref. Resolve each explicit path with `git ls-tree -r -z <ref> -- <path>` and require one exact blob entry. Read commit/blob bytes only with `git cat-file`; reject absent objects, non-blobs, unsafe/non-Java paths, duplicate fixtures, non-UTF-8 bytes, ref/parent mismatch, failed independence, or non-`YES/YES` prechecks before creating the destination. Materialize through a temporary sibling directory and atomically rename it into a previously absent destination.

- [ ] **Step 5: Add provenance and determinism controls**

  Require rejection for wrong parent, missing/renamed source at either ref, invalid ref/object, merge commits, SHA-256 repositories, failed/unknown prechecks, and nonempty/existing destinations. Mutate the working-tree file after commit and prove the package still contains committed blob bytes. Materialize twice to separate destinations and compare canonical manifest/source/package hashes byte-for-byte.

- [ ] **Step 6: Run focused and full verification**

  ```powershell
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_effect_candidate_corpus_contract.py" -v
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_effect_candidate_curator_git.py" -v
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_*.py" -v
  python -m flake8 --max-line-length=140 tools/edt-freeze-finder/finder/sealed_curator.py tools/edt-freeze-finder/finder/sealed_corpus.py tools/edt-freeze-finder/finder/test_effect_candidate_curator_git.py tools/edt-freeze-finder/finder/test_effect_candidate_corpus_contract.py
  git diff --check
  ```

  Stop after a Green generic curator checkpoint. Use the blind selector/auditor workflow to acquire new evidence; never tune analyzer code or reuse the 32 rejected/insufficient records.

### Task 6: Run One Ready Sealed Transfer Evaluation

**Files:**

- Create after evaluation: `tools/edt-freeze-finder/finder/docs/EFFECT-CANDIDATE-EVALUATION.md`
- Modify after Green only: `tools/edt-freeze-finder/finder/golden/java-effect-candidate-oracle.tsv`

**Interfaces:**

- Consumes: frozen Tasks 1-5 implementation and one immutable Task 5.5 package whose readiness and package hash were already verified.
- Produces: an auditable unseen-transfer feasibility verdict. One package never constitutes a general recall claim.

- [ ] **Step 1: Select an already-READY opaque package**

  Choose one package from the curator-owned READY pool by opaque ID. Confirm its `PACKAGE_READY.json` and package SHA-256 without reading its Issue, source paths, APIs, or causal report. Do not search for or package a case after this point.

- [ ] **Step 2: Freeze implementation and run leakage audit**

  Record hashes of production analyzer files. No analyzer changes are allowed after challenge selection.

- [ ] **Step 3: Revalidate the sealed package after freeze**

  Run `preflight_sealed_package(path)` again and require the exact previously recorded package hash and `READY` status. Any difference blocks evaluation before the analyzer is loaded.

- [ ] **Step 4: Run the sealed evaluator once**

  Success requires transfer before=1, after=0, `candidate_level` at least `SEMANTIC_MODEL`, `path_status=COMPLETE`, complete effect/model/lifecycle provenance, deterministic output, unchanged analyzer hashes, unchanged development/micro results, and recorded analysis budget/elapsed time. Read the structured `success` field; do not trust process exit code alone.

- [ ] **Step 5: Preserve failure honestly**

  If the transfer case fails, record the missing capability and stop. Do not tune Tasks 1-5 against the revealed challenge while calling the result evaluation.

- [ ] **Step 6: Admit valid evaluation evidence**

  Only after the run, add the reviewed source set as `split=evaluation` and record the exact command, analyzer/package hashes, counts, path status, evidence levels, candidate/KLoC, unresolved/truncated rates, elapsed time, and limitations in `EFFECT-CANDIDATE-EVALUATION.md`. One successful package remains a feasibility canary, not a general recall estimate.

### Task 7: Decide Promotion and Resume Stage 3

**Files:**

- Modify after Green only: `tools/edt-freeze-finder/PROGRESS.md`
- Future design only: `tools/edt-freeze-finder/finder/docs/STAGE3-IMPLEMENTATION-PLAN.md`

**Interfaces:**

- Consumes: Tasks 1-6 evidence, including Task 5.5 corpus-readiness records and Task 6 budget/evidence diagnostics.
- Produces: an explicit user-approved decision to keep candidates experimental, promote them into canonical findings, or revise the architecture.

- [ ] **Step 1: Report separate evidence levels**

  Distinguish micro TDD, known-case development replay, sealed package readiness, and unseen transfer evaluation. Do not combine them into one recall percentage. Report candidate/KLoC, unresolved rate, truncated rate, complete-path rate, elapsed time, and median manual review time separately.

- [ ] **Step 2: Choose one promotion state**

  - `EXPERIMENTAL`: opt-in candidate output only.
  - `ADMIT_TO_PROBLEMS`: persist candidates in a separate `Effect候选` sheet with `UNREVIEWED/UNVALIDATED`; do not mix them into canonical findings.
  - `ADMIT_TO_CONFIDENCE`: add a separately labeled candidate assessment path only after multiple independent READY/evaluation packages; do not pretend it is a Stage 2 confirmed finding.
  - `REVISE`: keep production integration off and write the failed semantic gap.

- [ ] **Step 3: Update the authoritative progress source**

  After a user-approved Green checkpoint, record the effect-candidate lane and the promotion decision in `../../PROGRESS.md`. Then resume the confidence-oracle work from the current Stage 3 Task 1, extended only if `ADMIT_TO_CONFIDENCE` was approved.

### Task 7R: One User-Approved REVISE Development Cycle

**Decision record (2026-08-26):** The user approved `REVISE`, one bounded development cycle, local binary-patch checkpoints instead of ticketless IntelliJ commits, permanent conversion of the consumed challenge to development evidence, a versioned one-shot runner, one minimal semantic fix, and an immediate stop if the next fresh canary fails.

**Files:**

- Create: `tools/edt-freeze-finder/finder/sealed_transfer_runner.py`
- Create: `tools/edt-freeze-finder/finder/test_sealed_transfer_runner.py`
- Create: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/consumed_transfer_001/manifest.json`
- Create: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/consumed_transfer_001/before/*.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/consumed_transfer_001/after/*.java`
- Create: `tools/edt-freeze-finder/finder/test_consumed_effect_candidate.py`
- Create after diagnosis: `tools/edt-freeze-finder/finder/docs/EFFECT-CANDIDATE-REVISE.md`
- Modify after the exact root cause is approved in this plan: only the necessary analyzer module(s)
- Modify after development Green: `tools/edt-freeze-finder/finder/golden/java-effect-candidate-oracle.tsv`
- Modify after checkpoint or persistent state change: `tools/edt-freeze-finder/PROGRESS.md`

**Interfaces:**

- `run_sealed_transfer(package_path, discover, expected_package_sha256, analyzer_files, attempt_dir) -> dict[str, object]` is the versioned future-canary seam. It validates package/analyzer hashes before loading sealed sources, writes a one-shot marker, invokes the packaged evaluator exactly once through a recording wrapper, and always persists call timings, hashes, counts, nullable candidate metrics, and the correct semantic failure category.
- `discover_effect_candidates(paths)` remains the only analyzer seam. The consumed development test loads source paths generically from its manifest and requires before=1, after=0, evidence level at least `SEMANTIC_MODEL`, and `path_status=COMPLETE`.
- The original `opaque-final-c9d8e2f1` package and `EFFECT-CANDIDATE-EVALUATION.md` remain immutable failure evidence. The copied fixture records `origin_status=consumed_failed_evaluation` and can never return to an evaluation split.

- [ ] **Step 0: Preserve the pre-REVISE checkpoint**

  Use the external checkpoint at `C:\Users\38331\.codex\visualizations\2026\08\25\01a038fd-8133-7303-aecd-29552469d116\edt-freeze-finder-checkpoints\2026-08-26-pre-revise`. It contains five sequential binary patches from base commit `3a8f2c0b3eecdf4b245ffe5c88127ebc0aed8974`, final tree `cad595e0662ad13949b086dabefef1b455e0e1d4`, file inventories, and `SHA256SUMS.txt`. The real Git index remains unchanged.

- [ ] **Step 1: Write the empty-before runner Red**

  Through `run_sealed_transfer(...)`, use a synthetic READY package and a recording analyzer stub that deterministically returns empty lists for before and after. Require exactly three calls (`before`, repeated `before`, `after`) and this persisted result shape:

  ```python
  {
      "success": False,
      "failure_category": "TRANSFER_CONTRACT_FAILURE",
      "before_count": 0,
      "after_count": 0,
      "deterministic": True,
      "analyzer_hashes_unchanged": True,
      "analysis_budget": None,
      "candidate_level": None,
      "analysis_mode": None,
      "path_status": None,
      "effect_provenance_present": False,
      "lifecycle_provenance_present": False,
      "unresolved_rate": None,
      "truncated_rate": None,
      "complete_rate": None,
      "elapsed_ms": {
          "total": float,
          "analyzer_calls": [float, float, float],
      },
  }
  ```

  A second call using the same attempt directory must return/refuse with `ALREADY_ATTEMPTED` without invoking the evaluator or analyzer.

- [ ] **Step 2: Implement the minimal runner Green**

  Reuse sealed AST/package validation, but keep evaluation result derivation in `../sealed_transfer_runner.py`. Candidate metrics accept an empty before list and return nullable fields instead of raising. Write the attempt marker before analyzer import, write the result on every exit path, compare analyzer hashes again after the evaluator, and never trust process exit code over the structured `success` field.

- [ ] **Step 3: Add runner success and pre-load failure controls**

  A synthetic analyzer that returns one exact `SEMANTIC_MODEL/COMPLETE` candidate for before and zero for after must return success with complete model/lifecycle/budget metrics. Analyzer hash or package hash mismatch must block before the recording analyzer is called. Run focused runner and existing sealed tests.

- [ ] **Step 4: Materialize consumed failed evaluation as development evidence**

  Read the immutable external package only after its evaluation identity has been consumed. Copy its exact before/after Java source bytes and Git provenance into `consumed_transfer_001`; do not copy selector/auditor identities or reuse `PACKAGE_READY.json`. The development manifest records original opaque package ID/hash, `origin_status=consumed_failed_evaluation`, original `task6_verdict=TRANSFER_CONTRACT_FAILURE`, and explicit `split=development`. Add a leakage rule that prevents these newly revealed tokens from entering production analyzer or micro fixtures.

- [ ] **Step 5: Establish the tight analyzer Red**

  Add `../test_consumed_effect_candidate.py` at the public seam. It must reproduce the original failure deterministically: expected before=1/after=0 while the frozen analyzer returns before=0/after=0. Run it twice and preserve the exact failure. This test, not the sealed evaluator, becomes the development feedback loop.

- [ ] **Step 6: Diagnose and minimise before editing analyzer**

  Trace the consumed before lifecycle path and compare its after cut. Produce 3–5 ranked falsifiable hypotheses in `EFFECT-CANDIDATE-REVISE.md`, run one-variable probes, and minimise the source closure while retaining the before miss. Record the single root cause and the exact public-seam prediction. Do not edit analyzer in this step.

- [ ] **Step 7: Amend this active plan with the one allowed semantic change**

  Diagnosis is recorded in [`EFFECT-CANDIDATE-REVISE.md`](EFFECT-CANDIDATE-REVISE.md). The gate could not be replaced by one allowed analyzer change: the consumed case requires a new eager descriptor/extension/scope effect family, source-call type canonicalization and/or external receiver contracts, lifecycle/candidate multiplicity policy, and optionally nested-to-outer resolution. An in-memory effect injection produced two complete and four truncated candidates rather than the required one. On 2026-08-27 the user selected the bounded eligibility route: keep all five analyzer files frozen, classify the consumed case as outside the current lane, tighten future sealed transfer eligibility to one versioned target contract already supported by the analyzer, and seek one new in-scope unseen canary. The original Task 6 failure remains immutable.

#### Task 7R-B: Tighten Transfer Eligibility Without Analyzer Changes

**Allowed files:**

- Modify: `tools/edt-freeze-finder/finder/sealed_corpus.py`
- Modify: `tools/edt-freeze-finder/finder/sealed_curator.py`
- Modify: `tools/edt-freeze-finder/finder/sealed_transfer_runner.py`
- Modify: `tools/edt-freeze-finder/finder/test_effect_candidate_corpus_contract.py`
- Modify: `tools/edt-freeze-finder/finder/test_effect_candidate_curator_git.py`
- Modify: `tools/edt-freeze-finder/finder/test_sealed_transfer_runner.py`
- Modify: `tools/edt-freeze-finder/finder/fixtures/effect_candidates/consumed_transfer_001/manifest.json`
- Modify: `tools/edt-freeze-finder/finder/test_consumed_effect_candidate.py`
- Modify: `tools/edt-freeze-finder/finder/docs/EFFECT-CANDIDATE-REVISE.md`
- Modify: `tools/edt-freeze-finder/PROGRESS.md`

**Frozen files:** `../source_model.py`, `../effect_models.py`, `../effect_analysis.py`, `../candidate_discovery.py`, and `../finder.py` must retain the Task 6 SHA-256 values recorded in `EFFECT-CANDIDATE-EVALUATION.md`.

**New public seam:**

```python
def validate_transfer_eligibility(path: str | Path) -> dict[str, object]:
    """Require one audited sealed case to target the current supported transfer contract."""
```

The only initial eligible target is:

```python
{
    "rule_id": "SERVICE_INITIALIZATION",
    "effect_kind": "EAGER_INSTANCE_MATERIALIZATION",
    "effect_model_id": "intellij-keyed-lazy-instance-v1",
    "lifecycle_contract_id": "intellij-configurable-lifecycle-v1",
    "minimum_candidate_level": "SEMANTIC_MODEL",
    "required_path_status": "COMPLETE",
}
```

`preflight_sealed_package(path)` remains backward compatible and continues to validate the immutable consumed package. `validate_transfer_eligibility(path)` is a separate future-evaluation gate: it requires the manifest, signed selector precheck, and different-signer auditor to contain the same supported target, with auditor `transfer_target_verified=VERIFIED`. Missing/legacy/unsupported targets return a structured eligibility error and cannot reach the analyzer.

- [ ] **Step B1: Write eligibility Reds**

  Extend synthetic packages with a transfer target and auditor verification. Require `validate_transfer_eligibility(...)` to return `ELIGIBLE` only when manifest/selector/auditor targets match the supported contract. Legacy READY packages must remain preflight READY but fail transfer eligibility. Reject unsupported model IDs, mismatched reports, missing auditor verification, multiple cases, or non-READY packages.

- [ ] **Step B2: Implement eligibility Green**

  Add package-only validation in `../sealed_corpus.py`; do not import analyzer modules or inspect source behavior. The result includes opaque package ID and target contract only. No existing `PACKAGE_READY.json` schema changes.

- [ ] **Step B3: Require target contract during Git-native curation**

  Extend the curator-private request with `transfer_target`. `materialize_git_package(...)` accepts only the supported target, writes it into the manifest and signed selector `case_prechecks`, and rejects unsupported/missing values before creating a destination. Add deterministic and rejection tests.

- [ ] **Step B4: Gate the versioned runner before evaluator load**

  `run_sealed_transfer(...)` calls `validate_transfer_eligibility(...)` after package hash preflight and before loading the evaluator or invoking the recording analyzer. Persist `transfer_eligible` and the target contract. An ineligible package returns `PACKAGE_INELIGIBLE` with zero analyzer calls and still consumes the one-shot marker.

- [ ] **Step B5: Reclassify consumed development evidence**

  Keep its exact source/provenance and failed evaluation origin, but record `eligibility_status=OUTSIDE_CURRENT_LANE`, `eligibility_reason=UNSUPPORTED_EFFECT_FAMILY`, expected before=0/after=0 for the current lane, and permanent exclusion from future sealed evaluation. Convert `../test_consumed_effect_candidate.py` from an intentional positive Red to a Green regression that asserts deterministic absence plus metadata/leakage confinement. Do not add it to the positive effect-candidate oracle.

- [ ] **Step B6: Verify and seek one fresh in-scope canary**

  Eligibility 19/19, curator 9/9, runner 4/4, consumed regression 2/2, and the full suite 96/96 are Green; flake8, seven-file AST parse, `git diff --check`, and all five frozen analyzer hashes passed. The blind selector then screened the remaining new high-likelihood evidence under the exact supported target. One new record was available but did not match the supported KeyedLazy semantic contract; no fetch, curator, package, auditor, or evaluator run occurred. Per the user-approved stop rule, this REVISE cycle is complete and stopped as `EXPERIMENTAL/REVISE`. No analyzer modification or fresh canary attempt is authorized in this cycle.

- [ ] **Step 8: Execute one Red-to-Green analyzer slice**

  Implement the amended minimal behavior, run the consumed before/after test, candidate discovery tests, development oracle, full 86-plus suite, flake8, AST parse, leakage scan, deterministic JSON comparison, and `git diff --check`. Only after Green add the consumed case to `java-effect-candidate-oracle.tsv` as `split=development` with an adjudication note that it came from failed evaluation.

- [ ] **Step 9: Run one fresh sealed canary and stop**

  Acquire a new opaque package excluding all development/exposed/consumed cases. Use independent selector/auditor, Git-native curator, versioned one-shot runner, frozen analyzer hashes, and one production attempt. If it succeeds, record only feasibility and return to Task 7 promotion review. If it fails for any reason, preserve the failure and stop this REVISE cycle immediately; no second semantic adjustment is allowed.

- [ ] **Step 10: Verify and close out**

  ```powershell
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_sealed_transfer_runner.py" -v
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_consumed_effect_candidate.py" -v
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_*.py" -v
  python -m flake8 --max-line-length=140 tools/edt-freeze-finder/finder/sealed_transfer_runner.py tools/edt-freeze-finder/finder/test_sealed_transfer_runner.py tools/edt-freeze-finder/finder/test_consumed_effect_candidate.py
  git diff --check
  ```

  Update `../../PROGRESS.md` with the exact Green/failure boundary, fresh package/evaluator evidence, active plan, and at most three next actions. Do not create ticketless IntelliJ commits; update the external binary-patch checkpoint only when the user requests another checkpoint.

## Plan Self-Review Result

- Spec coverage: Source/Callable, MethodEffectSummary, budgeted CallEdge, LifecycleReachability, evidence/model provenance, complete/truncated/unresolved paths, before/after controls, leakage, real replay, preflighted sealed corpus, transfer evaluation, CLI isolation, and Stage 3 re-entry each have a task.
- Placeholder scan: clear; every implementation step is concrete and complete.
- Type consistency: public candidate/evidence/path fields, callable ID, effect kind/model, lifecycle contract, budget, oracle status, and split names are defined once and reused unchanged.
- Scope: the first review gate is Tasks 0-4. CLI and sealed corpus readiness remain separate gates; persistence, confidence, and promotion do not leak into the core vertical slice.
- Worktree safety: no task edits current Task 0 files before the user-approved checkpoint; `../finder.py` is untouched until Task 5.
