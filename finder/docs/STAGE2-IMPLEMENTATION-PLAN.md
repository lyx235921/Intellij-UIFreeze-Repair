# EDT Freeze Finder Stage 2 Java Detection Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `tdd` to execute this plan task-by-task. Do not use subagents unless the user explicitly requests them.
>
> **Status policy:** This document is an implementation reference, not a completion ledger. Its step markers do not carry status. `tools/edt-freeze-finder/PROGRESS.md` is the only source for completed work, the current Red/Green state, and the next action; Git commits provide historical evidence.

**Goal:** Generalize the Java Finder from a small blocking-API MVP into an explainable causal detector with typed rule identities, indirect BGT-to-EDT freeze paths, a versioned golden set, and four evidence-guarded rule families.

**Architecture:** Preserve `analyze_file(path) -> list[dict]` and `recommend(result) -> tuple[str, str]` as the public seams. Add canonical finding fields and a small typed registry behind those seams, then grow capability through real before/after vertical slices: CASE-011, CASE-020, CASE-027, IJPL-244497, and IDEA-388699. The research workbook remains a human evidence pool; executable tests consume only committed Java fixtures and TSV rows.

**Tech Stack:** Python 3, `unittest`, `tree-sitter`, `tree-sitter-java`, the existing Java parser/thread classifier from `tools/anaction-scanner-v2`, TSV via Python's standard `csv` module, IntelliJ Java source fixtures.

**Spec:** `tools/edt-freeze-finder/finder/docs/STAGE2-DESIGN.md`

## Global Constraints

- Java-only in Stage 2; Kotlin and coroutine source analysis remain Stage 5.
- Finder detects and recommends; it does not edit IntelliJ production source.
- Preserve `analyze_file(path)` and `recommend(result)` as the only public test seams.
- Preserve compatibility aliases `thread` and `evidence` until every Stage 1 consumer has migrated.
- Never convert `unknown` thread or causal evidence into EDT/BGT based only on an Issue or commit description.
- BGT is not automatically safe; recommendations must also inspect `freeze_mechanism` and `edt_impact_path`.
- Blocking and UI APIs require receiver/type or platform-contract evidence; common method names alone are insufficient.
- A missing receiver specification never acts as a wildcard. Platform-contract matching requires a concrete contract identifier emitted by the analyzer.
- Stage 2 thread propagation is limited to uniquely resolved calls within one Java file; ambiguous or conflicting call paths remain `unknown`.
- `READ_ACTION_MISUSE` requires evidence of excessive or unrelated work inside the lock; a short legitimate read action is a negative case.
- A candidate with no proved violation has `primary_rule=None` and `matched_rules=[]`.
- A classified finding has one `primary_rule`, and `matched_rules` contains every proved rule in canonical R-number order: `UI_FROM_NON_EDT`, `EDT_BLOCKING`, `READ_ACTION_MISUSE`, `HEAVY_IN_UPDATE`.
- Primary selection precedence is causal and specific: proved `READ_ACTION_MISUSE` > `HEAVY_IN_UPDATE` > `EDT_BLOCKING`; `UI_FROM_NON_EDT` is primary only when no proved freeze rule supplies a more specific causal headline.
- Automated tests never read `EDT-Freeze-Finder-调研证据账本.xlsx` and never require network access.
- Stage 2 does not add aggregate reporting seams or assert production `freeze_count` / `thread_safety_count` values; aggregate evaluation belongs to Stage 3.
- Use Red-Green-Refactor for each behavior. Stop after a Red and confirm the failure reason before implementing Green.
- Run the full Finder suite after every Green:

  ```powershell
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_*.py" -v
  ```

---

## Planned File Structure

- Create `tools/edt-freeze-finder/finder/finding_model.py`: canonical enums/constants, finding normalization, rule ordering, and invariant validation.
- Create `tools/edt-freeze-finder/finder/rule_registry.py`: typed blocking/UI API specifications; no AST traversal.
- Modify `tools/edt-freeze-finder/finder/finder.py`: AST evidence extraction, rule composition, causal classification, and recommendation rendering.
- Modify `tools/edt-freeze-finder/finder/test_finder.py`: public-seam behavior tests for every vertical slice.
- Create `tools/edt-freeze-finder/finder/test_golden_set.py`: TSV schema, enum, fixture-path, uniqueness, and grouped-oracle execution tests.
- Create `tools/edt-freeze-finder/finder/golden/java-golden-set.tsv`: frozen executable oracle.
- Create fixture directories under `tools/edt-freeze-finder/finder/fixtures/` for each pinned case.
- Modify `tools/edt-freeze-finder/PROGRESS.md`: only after a Green checkpoint; do not mark a stage item complete on Red alone.

## Task 0: Freeze the Approved Design Checkpoint

**Files:**

- Modify: `tools/edt-freeze-finder/finder/docs/STAGE2-DESIGN.md`
- Create: `tools/edt-freeze-finder/finder/docs/STAGE2-IMPLEMENTATION-PLAN.md`
- Modify: `tools/edt-freeze-finder/PROGRESS.md`

**Interfaces:**

- Consumes: the approved Stage 2 design and R2/R3/R7/R8 research codebook.
- Produces: a reviewable design/plan checkpoint; no runtime behavior change.

- **Step 1: Review terminology consistency**

  Confirm that every Stage 2 document uses `READ_ACTION_MISUSE`, not `READ_ACTION`, and describes `primary_rule=None` with an empty `matched_rules` list for unclassified candidates.

- **Step 2: Review scope consistency**

  Confirm that the plan contains no Kotlin implementation, automatic patch generation, confidence weights, or tests that read Excel.

- **Step 3: Inspect the documentation diff**

  Run:

  ```powershell
  git diff --check
  git diff -- tools/edt-freeze-finder/finder/docs/STAGE2-DESIGN.md tools/edt-freeze-finder/finder/docs/STAGE2-IMPLEMENTATION-PLAN.md tools/edt-freeze-finder/PROGRESS.md
  ```

  Expected: no whitespace errors; only Stage 2 documentation changes.

- **Step 4: Commit only after user approval**

  ```powershell
  git add tools/edt-freeze-finder/finder/docs/STAGE2-DESIGN.md tools/edt-freeze-finder/finder/docs/STAGE2-IMPLEMENTATION-PLAN.md tools/edt-freeze-finder/PROGRESS.md
  git commit -m "docs edt-freeze-finder: plan Stage 2 implementation"
  ```

## Task 1: CASE-011 Cycle 1 — Detect Cold UI-Service Initialization

**Files:**

- Create: `tools/edt-freeze-finder/finder/fixtures/case011/before/IdeaModifiableModelsProvider.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/case011/after/IdeaModifiableModelsProvider.java`
- Create: `tools/edt-freeze-finder/finder/finding_model.py`
- Create: `tools/edt-freeze-finder/finder/rule_registry.py`
- Modify: `tools/edt-freeze-finder/finder/finder.py`
- Modify: `tools/edt-freeze-finder/finder/test_finder.py`

**Interfaces:**

- Consumes: `analyze_file(path)` and the pinned oracle CASE-011 / IJPL-248581 / commit `3bc7760a53b6423d2af570868784c406bab2885e`.
- Produces: canonical finding dictionaries and a type-aware `ProjectStructureConfigurable.getInstance` detector.

- **Step 1: Freeze the real before/after source**

  Copy the smallest compilable Java context containing `IdeaModifiableModelsProvider.getProjectStructureContext()` from the pinned commit. Preserve the real receiver type and call spelling:

  ```java
  ProjectStructureConfigurable configurable =
    ProjectStructureConfigurable.getInstance(myProject);
  ```

  The after fixture must contain `ProjectStructureConfigurable.getInstanceIfCreated(myProject)` and the real null/fallback branch. Add a fixture header comment containing the Issue ID, full commit SHA, variant, and original source path.

- **Step 2: Write the failing public-seam test**

  Add a test equivalent to:

  ```python
  def test_case_011_real_sources_detect_cold_initialization_before_only(self):
      case = FIXTURES / "case011"
      before = analyze_file(str(case / "before" / "IdeaModifiableModelsProvider.java"))
      after = analyze_file(str(case / "after" / "IdeaModifiableModelsProvider.java"))

      self.assertEqual(1, len(before))
      self.assertEqual([], after)
      finding = before[0]
      self.assertEqual("ProjectStructureConfigurable.getInstance", finding["api"])
      self.assertEqual("SERVICE_INITIALIZATION", finding["blocking_family"])
      self.assertEqual("unknown", finding["execution_thread"])
      self.assertEqual("unknown", finding["thread_evidence_level"])
      self.assertEqual("UNKNOWN", finding["freeze_mechanism"])
      self.assertEqual("UNKNOWN", finding["edt_impact_path"])
      self.assertIsNone(finding["primary_rule"])
      self.assertEqual([], finding["matched_rules"])
      self.assertEqual("AVOID_COLD_INITIALIZATION", finding["repair_strategy"])
  ```

- **Step 3: Run the focused test and verify Red**

  ```powershell
  Push-Location tools/edt-freeze-finder
  python -m unittest test_finder.AnalyzeFileTest.test_case_011_real_sources_detect_cold_initialization_before_only -v
  Pop-Location
  ```

  Expected: FAIL because `ProjectStructureConfigurable.getInstance` is not registered/detected; do not accept a failure caused by a missing fixture, import error, or dependency error.

- **Step 4: Add the canonical model without changing public seams**

  In `../finding_model.py`, define the allowed values and a constructor/normalizer that returns a dictionary containing:

  ```python
  primary_rule: str | None
  matched_rules: list[str]
  execution_thread: str
  thread_evidence_level: str
  thread_evidence: str
  blocking_family: str
  freeze_mechanism: str
  edt_impact_path: str
  repair_strategy: str
  ```

  It must also populate `thread` and `evidence` compatibility aliases. Validate the invariant `(primary_rule is None) == (matched_rules == [])` and require a non-null primary rule to appear in `matched_rules`.

- **Step 5: Add one type-aware registry entry**

  In `../rule_registry.py`, represent receiver, method, description, blocking family, default repair strategy, and optional cache/replacement template in one immutable specification. Register only `ProjectStructureConfigurable.getInstance` for the new service-initialization family; do not generalize all `getInstance()` calls.

- **Step 6: Implement minimal Green**

  Make `../finder.py` use the registry and canonical constructor. For this single-file CASE-011 observation, preserve unknown thread and causal fields, leave rule identity unclassified, and select `AVOID_COLD_INITIALIZATION` from the API specification.

- **Step 7: Run focused and full tests**

  Expected: CASE-011 before=1/after=0; all existing Stage 1 assertions remain Green.

- **Step 8: Commit the vertical slice**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "IJPL-248581 detect cold UI service initialization"
  ```

## Task 2: CASE-011 Cycle 2 — Explain Indirect BGT-to-EDT Lock Contention

**Files:**

- Create: `tools/edt-freeze-finder/finder/fixtures/case011/ProjectStructureInitializationOnBgt.java`
- Modify: `tools/edt-freeze-finder/finder/finder.py`
- Modify: `tools/edt-freeze-finder/finder/finding_model.py`
- Modify: `tools/edt-freeze-finder/finder/test_finder.py`

**Interfaces:**

- Consumes: the CASE-011 service-initialization registry entry and existing lambda dispatch classification.
- Produces: a BGT finding that explains lock contention and recommends avoiding cold initialization.

- **Step 1: Add an explicit BGT fixture**

  Put the exact blocking call inside `ApplicationManager.getApplication().executeOnPooledThread(() -> { ... })`. Keep the receiver typed as `ProjectStructureConfigurable`.

- **Step 2: Write the failing behavior test**

  Assert:

  ```python
  self.assertEqual("BGT", finding["execution_thread"])
  self.assertEqual("direct", finding["thread_evidence_level"])
  self.assertEqual("SERVICE_INITIALIZATION", finding["blocking_family"])
  self.assertEqual("LOCK_CONTENTION", finding["freeze_mechanism"])
  self.assertEqual("EDT_WAITS_FOR_LOCK", finding["edt_impact_path"])
  self.assertEqual("AVOID_COLD_INITIALIZATION", finding["repair_strategy"])
  self.assertNotIn("无需修复", recommend(finding)[0])
  ```

  Rule identity remains unclassified unless the implementation adds a separately justified indirect-freeze rule; do not force this observation into `EDT_BLOCKING`.

- **Step 3: Run the focused test and verify Red**

  Expected: FAIL because the current recommendation returns “already on BGT” and causal fields are missing or unknown.

- **Step 4: Implement mechanism-aware recommendation**

  Derive the CASE-011 BGT causal pair only when both the recognized cold UI-service initializer and explicit BGT dispatch evidence are present. Change `recommend()` so BGT returns “无需修复” only when no indirect EDT impact is established.

- **Step 5: Add the negative BGT control**

  A normal qualified disk API inside `executeOnPooledThread` with `freeze_mechanism=UNKNOWN` must retain the Stage 1 “already on BGT” behavior. This prevents every BGT blocking operation from becoming a false freeze.

- **Step 6: Run the full suite and commit**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "IJPL-248581 model background UI lock contention"
  ```

## Task 3: Require Receiver Evidence for Blocking APIs

**Files:**

- Create: `tools/edt-freeze-finder/finder/fixtures/registry/UnrelatedCommonMethodNames.java`
- Modify: `tools/edt-freeze-finder/finder/rule_registry.py`
- Modify: `tools/edt-freeze-finder/finder/test_finder.py`

**Interfaces:**

- Consumes: `analyze_file(path)` and the existing typed receiver extraction used by Stage 1 and CASE-023.
- Produces: exact receiver matching for blocking APIs; unresolved or unrelated same-name calls produce no finding.

- **Step 1: Write the same-name negative Red**

  Add unrelated declared receiver types whose methods are named `saveAllDocuments`, `contentsToByteArray`, `loadFileBytes`, and `loadFile`. Through `analyze_file(path)`, assert the fixture produces zero findings. Do not call the registry directly.

- **Step 2: Run the focused test and verify Red**

  Expected: FAIL because the current `receiver=None` rows act as wildcards and report all four unrelated calls. Existing qualified Stage 1 and CASE-023 positives must remain unchanged.

- **Step 3: Remove wildcard receiver semantics**

  Register `FileDocumentManager.saveAllDocuments` and `VirtualFile.contentsToByteArray` with exact receivers. Delete the bare `loadFileBytes` and `loadFile` rows because exact `FileUtil` and `VfsUtil` registrations already cover supported contracts. Make `match_blocking_api()` reject unresolved receivers unless a future entry supplies a concrete platform-contract identifier and the analyzer proves it.

- **Step 4: Run focused and full tests**

  Expected: the unrelated fixture is clean; all existing `FileDocumentManager`, `VirtualFile`, `FileUtil`, `VfsUtil`, `SvnVcs`, and CASE-011 expectations remain Green.

- **Step 5: Commit the false-positive guard**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "edt-freeze-finder: require receiver evidence for blocking APIs"
  ```

## Task 4: Establish the Versioned Java Golden Set

**Files:**

- Create: `tools/edt-freeze-finder/finder/golden/java-golden-set.tsv`
- Create: `tools/edt-freeze-finder/finder/test_golden_set.py`
- Modify: `tools/edt-freeze-finder/PROGRESS.md`

**Interfaces:**

- Consumes: committed fixtures and `analyze_file(path)`.
- Produces: a network-free executable oracle with one row per source observation.

- **Step 1: Write the failing schema-contract test**

  Define the exact 21-column header from `STAGE2-DESIGN.md`. Validate unique `specimen_id`, allowed enums, `development|evaluation`, `before|after|negative`, existing relative fixture paths, and the primary/matched invariant. Store multiple matched rules as comma-separated semantic IDs in canonical order; store an unclassified candidate as blank `primary_rule` and blank `matched_rules`.

- **Step 2: Run the schema test and verify Red**

  Expected: FAIL because the TSV does not exist.

- **Step 3: Add initial development rows**

  Add explicit rows for Fix008, CASE-023 before/after observations, and CASE-011 before/after/BGT observations. Use full Issue IDs and commit SHAs. Do not label Fix008 or CASE-023 as evaluation data because they shaped Stage 1.

- **Step 4: Add grouped execution assertions**

  Group rows by `source_file`; run `analyze_file()` once per file; compare expected hit count and every nonblank expected field. Negative after rows must assert zero findings rather than being silently skipped.

- **Step 5: Run both test modules**

  Expected: contract and grouped oracle tests pass, along with all Stage 1/CASE-011 tests.

- **Step 6: Update progress and commit**

  Record CASE-011 as Green and link its two commits. Do not mark all Stage 2 blocking families complete.

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "tests edt-freeze-finder: add Java golden set"
  ```

## Task 5: CASE-004 — Prove Bounded Java Thread Propagation

**Files:**

- Create: `tools/edt-freeze-finder/finder/fixtures/case004/before/GenerateMembersHandlerBase.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/case004/ConflictingCallers.java`
- Modify: `tools/edt-freeze-finder/finder/edt_classify.py`
- Modify: `tools/edt-freeze-finder/finder/rule_registry.py`
- Modify: `tools/edt-freeze-finder/finder/finder.py`
- Modify: `tools/edt-freeze-finder/finder/finding_model.py`
- Modify: `tools/edt-freeze-finder/finder/test_finder.py`
- Modify: `tools/edt-freeze-finder/finder/golden/java-golden-set.tsv`

**Interfaces:**

- Consumes: CASE-004 / IDEA-390239 / commit `efae1394a7aad48aabbefbbff585b912f956eaea`, the `CodeInsightActionHandler.invoke(...)` EDT contract, and `analyze_file(path)`.
- Produces: bounded same-file thread propagation with evidence paths such as `CodeInsightActionHandler.invoke -> doGenerate`; it does not expose a general call-graph API.

- **Step 1: Freeze the real call path**

  Preserve the pre-fix Java path `GenerateMembersHandlerBase.invoke(...) -> doGenerate(...) -> generateMemberPrototypes(...)` from the pinned commit. Keep `invoke` final, `doGenerate` private, the real receiver/class declarations, and a header with Issue ID, full commit SHA, variant, and source path.

- **Step 2: Write the blocking-contract Red**

  Through `analyze_file(path)`, first assert the prototype-generation observation in `doGenerate` is detected as `GenerateMembersHandlerBase.generateMemberPrototypes`, with `blocking_family=PSI_RESOLVE_INDEX`, `repair_strategy=CANCELLABLE_OPERATION`, and thread/evidence level both `unknown`. This cycle establishes the blocking API and implicit-`this` receiver precondition without claiming propagation.

- **Step 3: Verify the blocking-contract Red**

  Expected: zero findings because the exact CASE-004 contract is not registered and implicit-`this` calls do not yet emit their containing class as receiver evidence. Confirm the fixture parses and exposes the expected callables; do not accept a failure caused by malformed Java.

- **Step 4: Implement the blocking-contract Green**

  Infer the containing Java class as the compile-time receiver for supported implicit-`this` calls and register only `GenerateMembersHandlerBase.generateMemberPrototypes` as `PSI_RESOLVE_INDEX` with `CANCELLABLE_OPERATION`. Keep the helper thread `unknown`; do not implement call-path propagation in this cycle.

- **Step 5: Run the blocking-contract tests and commit**

  Run the focused test and full Finder suite. Expected: the real observation is detected exactly once with unknown thread evidence; all same-name receiver guards remain Green.

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "IDEA-390239 detect prototype generation risk"
  ```

- **Step 6: Write the propagated-evidence Red**

  Through `analyze_file(path)`, change the real observation expectation to `execution_thread=EDT`, `thread_evidence_level=propagated`, and a `thread_evidence` path containing the direct `CodeInsightActionHandler.invoke` contract and the `doGenerate` edge. The prior Green guarantees this Red cannot be caused by an unresolved blocking API.

- **Step 7: Add conflict and thread-switch controls before propagation**

  In `ConflictingCallers.java`, call one private helper from both a direct EDT entry and an explicit BGT dispatch; its helper finding must remain `unknown`. Add a nested BGT dispatch on an otherwise EDT path and assert the blocking operation inside that lambda is direct BGT, not propagated EDT.

- **Step 8: Verify Red for the missing propagation capability**

  Expected: the registered private-helper observation remains `unknown`; the direct entry contract and blocking API are both recognized. The failure must be caused only by absent same-file thread propagation.

- **Step 9: Implement the bounded call path**

  Recognize the exact `CodeInsightActionHandler.invoke(Project, Editor, PsiFile)` platform contract. Build same-file edges only when the target is unique and `private`, `static`, or `final`. Propagate a direct thread fact until a recognized switch. Mixed callers, ambiguous overloads, unsupported virtual dispatch, and cycles beyond the budget produce `unknown`.

  Extend `create_finding(...)` with an explicit optional `thread_evidence_level` input. Existing direct/unknown callers may omit it and retain the current derivation, while the call-path analyzer passes `propagated`. Validate the three allowed values and write the supplied level to the canonical finding dictionary; do not infer propagation by parsing the human-readable `thread_evidence` string.

- **Step 10: Add the golden observation and focused controls**

  Add the CASE-004 development row. The real finding records the full commit SHA and `thread_evidence_level=propagated`. Keep the nested-BGT and conflicting-caller controls as focused fixtures/tests rather than golden rows because they guard propagation mechanics, not independently sourced Issue oracles.

- **Step 11: Run the full suite and commit**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "IDEA-390239 propagate EDT evidence through Java helpers"
  ```

## Task 6: CASE-020 — Detect Proven `READ_ACTION_MISUSE`

**Files:**

- Create: `tools/edt-freeze-finder/finder/fixtures/case020/before/HighlightInfoUpdaterImpl.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/case020/after/HighlightInfoUpdaterImpl.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/case020/ReadActionMisuseOnBgt.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/case020/ShortPsiReadAction.java`
- Modify: `tools/edt-freeze-finder/finder/finder.py`
- Modify: `tools/edt-freeze-finder/finder/test_finder.py`
- Modify: `tools/edt-freeze-finder/finder/golden/java-golden-set.tsv`

**Interfaces:**

- Consumes: CASE-020 / IJPL-235455 / commit `1f29744736ba62bccec3df1f3c525a6617dec63d`.
- Produces: read-action scope recognition, lock-context evidence, and `SHRINK_READ_ACTION` recommendations.

- **Step 1: Freeze real before/after fixtures**

  Preserve the real structural difference: `processQueues()` executes inside the read action before the fix and outside it after the fix.

- **Step 2: Write the real-case Red**

  Assert before=1, after=0, `primary_rule=READ_ACTION_MISUSE`, `matched_rules` includes `READ_ACTION_MISUSE`, and `repair_strategy=SHRINK_READ_ACTION`. Preserve `execution_thread=unknown`, `freeze_mechanism=UNKNOWN`, and `edt_impact_path=UNKNOWN` if the frozen single-file source does not prove the runtime path described by the Issue.

- **Step 3: Add the required negative fixture**

  `ShortPsiReadAction.java` must contain a small `ReadAction.compute(() -> psiElement.getContainingFile())`-style model read and produce zero findings. This test must be written before the detector.

- **Step 4: Verify Red for the right reason**

  Expected: the real before case is not classified; the negative already remains clean. Do not accept a Red caused by matching every `ReadAction`.

- **Step 5: Implement scoped AST evidence**

  Recognize supported read-action lambda scopes and locate qualified risky operations within their exact AST ranges. Add `READ_ACTION_MISUSE` only when a registered risk signal or pinned contract identifies unrelated/excessive work. Do not reuse the old Scanner's broad “loop means computation” regex.

- **Step 6: Test rule overlap explicitly**

  Add an EDT fixture where a registered expensive operation is also proven to extend a read action. Assert `matched_rules=[EDT_BLOCKING, READ_ACTION_MISUSE]` in canonical order and `primary_rule=READ_ACTION_MISUSE`.

- **Step 7: Prove the indirect path with an explicit BGT fixture**

  In `ReadActionMisuseOnBgt.java`, place the same misuse inside a recognized BGT dispatch. Assert `execution_thread=BGT`, `freeze_mechanism=LOCK_CONTENTION`, and `edt_impact_path=EDT_WAITS_FOR_LOCK`. This fixture, not the Issue prose, supplies the static causal evidence.

- **Step 8: Add golden rows, run full suite, and commit**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "IJPL-235455 detect excessive Java read actions"
  ```

## Task 7: CASE-027 — Recognize Expensive EDT Resolve and Cancellable Repair

**Files:**

- Create: `tools/edt-freeze-finder/finder/fixtures/case027/before/JavaResolveSnapshot.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/case027/after/JavaResolveSnapshot.java`
- Modify: `tools/edt-freeze-finder/finder/rule_registry.py`
- Modify: `tools/edt-freeze-finder/finder/finder.py`
- Modify: `tools/edt-freeze-finder/finder/test_finder.py`
- Modify: `tools/edt-freeze-finder/finder/golden/java-golden-set.tsv`

**Interfaces:**

- Consumes: CASE-027 / IDEA-388795 / commit `457a97acac108fd8346a05d0dac381deb10056cb`.
- Produces: the `PSI_RESOLVE_INDEX` family and evidence-based `CANCELLABLE_OPERATION` recommendation.

- **Step 1: Freeze the real resolve call and repair wrapper**

  Preserve the before call path that performs snapshot-wide resolve synchronously and the after split between `runWriteActionWithCancellableProgressInDispatchThread` and `runProcessWithProgressSynchronously`.

- **Step 2: Write before=hit/after=no-unprotected-hit Red**

  Assert the before observation is `EDT_BLOCKING`, `blocking_family=PSI_RESOLVE_INDEX`, `execution_thread=EDT`, `freeze_mechanism=EXPENSIVE_EDT_COMPUTE`, `edt_impact_path=SAME_THREAD`, and `repair_strategy=CANCELLABLE_OPERATION`.

- **Step 3: Define after semantics precisely**

  If the blocking API remains in the after source, the detector must suppress the violation only when it proves the supported cancellable-progress wrapper. Do not assert literal zero merely because the method name changed.

- **Step 4: Implement one typed resolve signature and one wrapper guard**

  Register only the receiver/method pair supported by CASE-027. Add AST ancestry recognition for the two platform progress wrappers used by the commit. Do not treat arbitrary methods containing `Progress` as cancellable.

- **Step 5: Add an evaluation specimen without tuning the rule**

  Add CASE-026 / IDEA-388816 / commit `b9f8a94ab4e8a1b42e638cff5150a44562bdce32` as an `evaluation` specimen after the detector behavior is frozen. Record its observed result; if it exposes a gap, document the gap before starting a new Red rather than silently changing the original oracle.

- **Step 6: Run full suite and commit**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "IDEA-388795 detect uncancellable EDT resolve"
  ```

## Task 8: IJPL-244497 — Implement `HEAVY_IN_UPDATE` and Overlap Reporting

**Files:**

- Create: `tools/edt-freeze-finder/finder/fixtures/heavy_update/before/ProposedPlanAction.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/heavy_update/after/ProposedPlanAction.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/heavy_update/UpdateOnBgt.java`
- Modify: `tools/edt-freeze-finder/finder/finder.py`
- Modify: `tools/edt-freeze-finder/finder/test_finder.py`
- Modify: `tools/edt-freeze-finder/finder/golden/java-golden-set.tsv`

**Interfaces:**

- Consumes: IJPL-244497 / commit `4385e8888735609a63b53943e957b7e338d8cfb6` and existing T1 update-thread classification.
- Produces: specific-over-general primary rule selection.

- **Step 1: Write the real before/after Red**

  Assert the pre-fix expensive `update(AnActionEvent)` observation has canonical ordered matches `[EDT_BLOCKING, HEAVY_IN_UPDATE]` and `primary_rule=HEAVY_IN_UPDATE`. Assert the repaired BGT update is not reported as an EDT freeze.

- **Step 2: Add explicit `ActionUpdateThread.BGT` negative control**

  A class whose `getActionUpdateThread()` returns BGT and whose `update()` reads allowed BGT data must not match `HEAVY_IN_UPDATE` merely because it overrides `update()`.

- **Step 3: Verify Red**

  Expected: current Finder can classify some update methods but cannot emit `HEAVY_IN_UPDATE` or overlap fields correctly.

- **Step 4: Compose rules after thread classification**

  Apply `HEAVY_IN_UPDATE` only when the callable is an `update(AnActionEvent)` override, effective thread remains EDT after T1/BGT override handling, and the same observation already has a qualified expensive-operation match. Select it as primary over `EDT_BLOCKING`.

- **Step 5: Add golden rows, run full suite, and commit**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "IJPL-244497 detect heavy AnAction updates"
  ```

## Task 9: IDEA-388699 — Classify `UI_FROM_NON_EDT` Without Freeze Aggregation

**Files:**

- Create: `tools/edt-freeze-finder/finder/fixtures/ui_from_bgt/before/JigsawModuleDependency.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/ui_from_bgt/after/JigsawModuleDependency.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/ui_from_bgt/ThreadSafeUiOperation.java`
- Modify: `tools/edt-freeze-finder/finder/rule_registry.py`
- Modify: `tools/edt-freeze-finder/finder/finder.py`
- Modify: `tools/edt-freeze-finder/finder/test_finder.py`
- Modify: `tools/edt-freeze-finder/finder/golden/java-golden-set.tsv`

**Interfaces:**

- Consumes: IDEA-388699 / commit `7456061896cfc9d6aa7b04b9925328127f9bae0d`.
- Produces: a contract-aware UI mutation finding whose per-finding causal fields do not claim a freeze without an EDT impact path.

- **Step 1: Freeze real callback fixtures**

  Preserve the promise callback that mutates UI directly before the fix and the platform `invokeLater` hop after the fix.

- **Step 2: Write before=1/after=0 Red**

  Assert the before finding has `primary_rule=UI_FROM_NON_EDT`, `matched_rules=[UI_FROM_NON_EDT]`, `execution_thread=BGT`, `freeze_mechanism=UNKNOWN`, `edt_impact_path=UNKNOWN`, and a UI-thread-hop recommendation. These per-finding fields express that no freeze has been proved; do not invent an aggregate count seam in this test.

- **Step 3: Add a documented thread-safe negative**

  Register one explicit thread-safe UI operation or fixture contract and assert it is not reported. Unresolved receivers must also remain unreported.

- **Step 4: Implement the smallest contract-aware UI registry**

  Match only the receiver/mutator contract needed by IDEA-388699 plus the negative contract. Recognize enclosing platform UI dispatch so the repaired fixture is clean. Do not import the old Scanner's broad Swing method-name regex list.

- **Step 5: Add golden rows and verify causal classification**

  The golden runner validates the rule identity and the `UNKNOWN` mechanism/impact fields. Aggregate `freeze_count` and `thread_safety_count` behavior is deferred until Stage 3 defines a production reporting interface.

- **Step 6: Run full suite and commit**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "IDEA-388699 detect UI updates from background threads"
  ```

## Task 10: Stage 2 Evaluation and Closeout

**Files:**

- Modify: `tools/edt-freeze-finder/finder/finder.py`
- Modify: `tools/edt-freeze-finder/finder/test_finder.py`
- Modify: `tools/edt-freeze-finder/finder/test_golden_set.py`
- Modify: `tools/edt-freeze-finder/finder/golden/java-golden-set.tsv`
- Modify: `tools/edt-freeze-finder/PROGRESS.md`

**Interfaces:**

- Consumes: all Stage 2 rule slices and golden specimens.
- Produces: deterministic CLI output, explainable per-finding decisions, and an evidence-backed Stage 2 completion decision.

- **Step 1: Add untouched evaluation cases**

  Add CASE-015 / PY-89735 / commit `984a0a06d0708d1bdf5d5a791f334a6773a8c8bb` as a read-action evaluation case and CASE-021 / IJPL-246986 / commit `7717e420a4d4efe574838c30166d3558afb98b24` as a cold-initialization evaluation case. Do not alter their expectations after observing results; record false positives/negatives as explicit oracle outcomes and open a new TDD cycle for any accepted rule change.

- **Step 2: Add deterministic reporting tests**

  Assert stable ordering by file, source line, API, and canonical matched-rule order. CLI output must show primary rule, secondary matches, execution thread/evidence level, blocking family, causal path, and semantic repair strategy without removing Stage 1-readable fields during this stage.

- **Step 3: Run the full Finder suite twice**

  Run the same command twice and confirm identical results. Expected: all tests Green and no network access.

- **Step 4: Run a bounded real-source smoke scan**

  Scan only the Java files represented by golden fixtures or a small explicitly listed platform directory. Save counts in the commit message or progress note; do not claim repository-wide precision/recall, which belongs to Stage 3.

- **Step 5: Check Stage 2 exit criteria**

  Mark Stage 2 complete only if canonical fields are used, direct/propagated/unknown remain distinct, at least one indirect BGT freeze path is explained, multiple blocking families have positive and negative golden specimens, and every frozen specimen maps to a pinned oracle.

- **Step 6: Update progress and commit**

  Record each Green commit and the next action as Stage 3 confidence/evaluation design. Do not start Stage 3 in this commit.

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "docs edt-freeze-finder: complete Stage 2 Java detection"
  ```

## Plan Self-Review Result

- Spec coverage: canonical causal fields, unknown preservation, BGT indirect impact, receiver/type false-positive guards, bounded `propagated` evidence, semantic strategies, four initial rules, overlap reporting, golden-set architecture, and real vertical slices are all assigned to tasks.
- Scope: no Kotlin implementation, automatic repair, confidence weights, or repository-wide precision/recall threshold is included.
- Type consistency: `primary_rule` is `str | None`; `matched_rules` is `list[str]`; compatibility aliases remain until after Stage 2.
- Oracle hygiene: all named real cases have pinned Issue IDs and full commit SHAs; tests use committed fixtures and TSV only.
- Placeholder scan: no implementation step depends on an unspecified case, API, file path, or “implement later” item.
- Status audit: Task completion is intentionally absent from this document. Read `../../PROGRESS.md` and Git history before choosing an execution step; the approved plan may evolve when a reviewed Red/Green cycle exposes a design gap.
