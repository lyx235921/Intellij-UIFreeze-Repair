# EDT Freeze Finder Stage 3 Confidence and Evaluation Implementation Plan

> **For agentic workers:** Execute one TDD cycle at a time and stop after each Red so the failure reason can be reviewed. Do not use subagents unless the user explicitly requests them.
>
> **Status policy:** This document is a static implementation reference. Numbered steps describe execution order but do not carry completion status. `tools/edt-freeze-finder/PROGRESS.md` remains the only progress source.

**Goal:** Turn Stage 2 findings into separately explainable problem-confidence and repair-confidence assessments, validate the teacher's six-factor repair hypothesis against frozen development/evaluation evidence, and publish reproducible precision, recall, and strategy-agreement results.

**Architecture:** Preserve `analyze_file(path)` and `recommend(result)` and add `assess_file(path)` as the public confidence seam. Keep the 21-column detection oracle unchanged; a second TSV joins by `specimen_id` and stores adjudicated problem labels, developer repair strategies, and tri-state factor evidence. Static extractors produce facts, versioned scoring profiles consume those facts, and evaluation code reports metrics without changing frozen expectations.

**Tech Stack:** Python 3, `unittest`, `tree-sitter`, `tree-sitter-java`, standard-library `csv`, `json`, and `statistics`; committed Java fixtures and TSV files; no network access in tests.

**Specs:**

- `tools/edt-freeze-finder/finder/docs/STAGE2-DESIGN.md`
- `notes/ase2027-empirical-study/repair-design.md`
- `notes/ase2027-empirical-study/codebook-r1-r9.md`
- `tools/edt-freeze-finder/PROGRESS.md`

## Global Constraints

- Stage 3 begins only after the Stage 2 exit criteria are Green.
- Java-only; Kotlin and coroutine analysis remain Stage 5.
- A missing fact is `UNKNOWN`, never `NO` and never positive evidence.
- Problem confidence answers whether the reported violation is real; repair confidence answers whether one proposed strategy is safe and suitable.
- The teacher's weights are preserved verbatim as the profile `teacher-v0`: `+25`, `-20`, `-30`, `-25`, `+15`, `+15`.
- `teacher-v0` is a hypothesis to evaluate, not an automatic-edit threshold.
- Development rows may shape extractors and scoring; evaluation rows are frozen before their first run and must not be relabeled after results are observed.
- Production scoring must not inspect Issue IDs, commit messages, or oracle labels.
- Tests do not read the Excel research workbook and do not access GitHub, YouTrack, or the network.
- `../../PROGRESS.md` is updated only at a Green checkpoint.

---

## Planned File Structure

- Create `../confidence_model.py`: tri-state facts, canonical assessment fields, invariants, and JSON-safe normalization.
- Create `dependency_analysis.py`: AST extraction of the teacher's six factors; no weights or thresholds.
- Create `confidence_scoring.py`: versioned problem and repair scoring profiles; no AST traversal.
- Create `confidence.py`: composition seam `assess_file(path)`.
- Create `confidence_evaluation.py`: split-aware metrics and deterministic JSON/Markdown reporting.
- Create `../test_confidence.py`: public-seam behavior tests.
- Create `test_confidence_golden_set.py`: confidence TSV contract and evaluation-leakage guards.
- Create `golden/java-confidence-oracle.tsv`: adjudicated labels joined to `java-golden-set.tsv` by `specimen_id`.
- Create fixtures under `fixtures/confidence/`: isolated positive, negative, and unknown evidence examples.
- Modify `../finder.py` and `../finding_model.py` only when a canonical evidence field required by scoring is missing.
- Modify `../eval_207.py`: consume public seams and stop importing private matcher functions.

## Public Interfaces

```python
def assess_file(path: str) -> list[dict[str, object]]:
    """Return each Finder result plus problem and repair assessments."""

def evaluate_oracle(
    detection_tsv: str,
    confidence_tsv: str,
    split: str,
) -> dict[str, object]:
    """Return deterministic metrics for development or evaluation rows."""
```

`assess_file()` is the only new runtime test seam. Pure model/scoring tests may call their public constructors and scoring functions; AST helpers remain private.

---

## Task 0: Freeze the Confidence Result Contract

**Files:**

- Create: `tools/edt-freeze-finder/finder/confidence_model.py`
- Create: `tools/edt-freeze-finder/finder/test_confidence.py`

**Interfaces:**

- Consumes: canonical Stage 2 finding dictionaries.
- Produces: `create_assessment(finding, factors, problem_score, repair_scores) -> dict[str, object]` and three-valued factor constants `YES`, `NO`, `UNKNOWN`.

- **Step 1: Write the result-contract Red**

  Through `create_assessment(...)`, assert the returned dictionary includes:

  ```text
  finding
  problem_score
  problem_confidence
  problem_score_profile
  factors
  repair_candidates
  recommended_strategy
  repair_confidence
  repair_score_profile
  ```

  Each of the six factors has exactly `value` and `evidence`; `value` is `YES`, `NO`, or `UNKNOWN`. A repair candidate has `strategy`, `score`, `supported_by`, `contradicted_by`, and `unknown_factors`.

- **Step 2: Verify the contract Red**

  Run:

  ```powershell
  python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_confidence.py" -v
  ```

  Expected: import failure because `../confidence_model.py` does not exist.

- **Step 3: Implement validation without scoring policy**

  Reject missing factor names, invalid tri-state values, scores outside `0..100` for problems or `-100..100` for repairs, a recommended strategy absent from `repair_candidates`, and `HIGH` repair confidence when any safety-critical factor is `UNKNOWN`.

- **Step 4: Run focused and full Finder tests**

  Expected: the contract test and all Stage 2 tests pass.

- **Step 5: Commit**

  ```powershell
  git add tools/edt-freeze-finder/finder/confidence_model.py tools/edt-freeze-finder/finder/test_confidence.py
  git commit -m "edt-freeze-finder: define confidence assessment model"
  ```

## Task 1: Establish the Confidence Oracle

**Files:**

- Create: `tools/edt-freeze-finder/finder/golden/java-confidence-oracle.tsv`
- Create: `tools/edt-freeze-finder/test_confidence_golden_set.py`

**Interfaces:**

- Consumes: `golden/java-golden-set.tsv` specimen IDs.
- Produces: a versioned adjudication row for each admitted confidence specimen.

- **Step 1: Write the TSV contract Red**

  Freeze this exact header:

  ```text
  specimen_id,split,problem_label,developer_strategy,
  prefetchable_data,prefetchable_data_evidence,
  lock_dependency,lock_dependency_evidence,
  ui_context_dependency,ui_context_dependency_evidence,
  synchronous_result_dependency,synchronous_result_dependency_evidence,
  direct_ui_consumption,direct_ui_consumption_evidence,
  cancellable_iteration,cancellable_iteration_evidence,
  issue_id,commit_sha,oracle_kind,adjudication_note
  ```

  Store it as TSV. Validate unique IDs, a matching detection-oracle row, identical `split`, `problem_label` in `TRUE_POSITIVE|FALSE_POSITIVE`, semantic developer strategies or blank, six tri-state values, nonblank evidence for every non-`UNKNOWN` factor, 40-character commit SHAs, and nonblank adjudication notes.

- **Step 2: Verify Red**

  Expected: failure only because `java-confidence-oracle.tsv` is absent.

- **Step 3: Add development rows only**

  Admit reviewed Stage 2 development specimens. Use `UNKNOWN` when the fixture cannot prove a factor; do not copy an Issue narrative into static evidence. Keep evaluation rows out until Task 7 freezes them.

- **Step 4: Prove split isolation**

  Add a test that rejects duplicate specimen IDs, confidence rows with a different split from the detection oracle, and evaluation rows passed to a development-only calibration loader.

- **Step 5: Run tests and commit**

  ```powershell
  git add tools/edt-freeze-finder/finder/golden/java-confidence-oracle.tsv tools/edt-freeze-finder/test_confidence_golden_set.py
  git commit -m "tests edt-freeze-finder: add confidence oracle contract"
  ```

## Task 2: Record Blocking-API Evidence Strength

**Files:**

- Modify: `tools/edt-freeze-finder/finder/rule_registry.py`
- Modify: `tools/edt-freeze-finder/finder/finding_model.py`
- Modify: `tools/edt-freeze-finder/finder/finder.py`
- Modify: `tools/edt-freeze-finder/finder/test_finder.py`

**Interfaces:**

- Consumes: typed receiver and platform-contract matches from Stage 2.
- Produces: canonical `api_evidence_level=typed_receiver|platform_contract|unknown` and `api_evidence` fields on findings.

- **Step 1: Write typed and contract evidence Reds**

  Assert an exact `FileDocumentManager.saveAllDocuments` match reports `typed_receiver`, a Stage 2 platform-contract case reports `platform_contract`, and unresolved same-name calls remain absent rather than becoming `unknown` findings.

- **Step 2: Verify Red for missing fields**

  Existing hit counts must stay unchanged; the Red must be caused only by absent evidence fields.

- **Step 3: Add evidence metadata to registry matches**

  Keep matching decisions in `../rule_registry.py`, pass the selected evidence kind/text into `create_finding()`, and write them without inferring from display names.

- **Step 4: Preserve the 21-column detection oracle**

  Keep API-evidence expectations in focused Stage 3 behavior tests. Do not append columns to `java-golden-set.tsv`; its Stage 2 contract remains frozen and the separate confidence oracle carries Stage 3 adjudication data.

- **Step 5: Run the full suite and commit**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "edt-freeze-finder: expose blocking API evidence strength"
  ```

## Task 3: Score Problem Evidence Separately

**Files:**

- Create: `tools/edt-freeze-finder/confidence_scoring.py`
- Create: `tools/edt-freeze-finder/confidence.py`
- Modify: `tools/edt-freeze-finder/finder/test_confidence.py`

**Interfaces:**

- Consumes: `api_evidence_level`, `thread_evidence_level`, `freeze_mechanism`, `edt_impact_path`, and `primary_rule`.
- Produces: `score_problem(finding) -> dict[str, object]` and `assess_file(path)`.

- **Step 1: Write public-seam Reds**

  Through `assess_file(path)`, assert these evidence contributions under profile `problem-v1`:

  ```text
  typed_receiver or platform_contract: 35
  direct thread evidence:               25
  propagated thread evidence:           20
  known mechanism and impact path:       25
  non-null primary_rule:                 15
  ```

  Cap the total at `100`. Unknown evidence contributes zero and appears in `missing_problem_evidence`.

- **Step 2: Keep confidence tiers unvalidated**

  Before Task 7 calibration, return `problem_confidence=UNVALIDATED` regardless of numeric score. Assert that no numeric threshold silently produces `HIGH`.

- **Step 3: Implement composition**

  `assess_file(path)` calls `analyze_file(path)` once, scores every result, and preserves the original finding unchanged under the `finding` key.

- **Step 4: Run focused and full tests, then commit**

  ```powershell
  git add tools/edt-freeze-finder/confidence.py tools/edt-freeze-finder/confidence_scoring.py tools/edt-freeze-finder/finder/test_confidence.py
  git commit -m "edt-freeze-finder: score problem evidence separately"
  ```

## Task 4: Extract the Three Upstream Factors

**Files:**

- Create: `tools/edt-freeze-finder/dependency_analysis.py`
- Create: `tools/edt-freeze-finder/finder/fixtures/confidence/PrefetchablePureData.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/confidence/ReadActionDependency.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/confidence/UiContextDependency.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/confidence/UnknownUpstreamDependency.java`
- Modify: `tools/edt-freeze-finder/confidence.py`
- Modify: `tools/edt-freeze-finder/finder/test_confidence.py`

**Interfaces:**

- Consumes: source ranges and callable context for each finding.
- Produces: `extract_dependency_factors(path, finding) -> dict[str, FactorEvidence]` for `prefetchable_data`, `lock_dependency`, and `ui_context_dependency`.

- **Step 1: Write four Red cases through `assess_file()`**

  Prove one positive for each factor and one unresolved case. Require evidence strings containing the exact AST construct, such as `enclosing:ReadAction.compute` or `receiver:JComponent`.

- **Step 2: Implement bounded AST facts**

  Treat a value as `YES` only for registered Java constructs. Absence of a registered construct is `UNKNOWN` unless the analyzer positively proves the opposite within the entire relevant callable. Never use method-name substrings such as `ui`, `lock`, or `data`.

- **Step 3: Add negative controls**

  A short PSI read action is a lock dependency but not automatically a blocking violation; a local immutable value is not automatically prefetchable when construction depends on EDT-only state.

- **Step 4: Run full tests and commit**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "edt-freeze-finder: extract upstream repair factors"
  ```

## Task 5: Extract the Three Downstream Factors

**Files:**

- Create: `tools/edt-freeze-finder/finder/fixtures/confidence/SynchronousResultDependency.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/confidence/DirectUiConsumption.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/confidence/CancellableIteration.java`
- Create: `tools/edt-freeze-finder/finder/fixtures/confidence/UnknownDownstreamDependency.java`
- Modify: `tools/edt-freeze-finder/dependency_analysis.py`
- Modify: `tools/edt-freeze-finder/finder/test_confidence.py`

**Interfaces:**

- Consumes: assignment/return/use sites after the finding and exact callable/lambda ranges.
- Produces: `synchronous_result_dependency`, `direct_ui_consumption`, and `cancellable_iteration` factor evidence.

- **Step 1: Write public-seam Reds**

  Require `YES` for a blocking result immediately returned or assigned then consumed synchronously, `YES` for a result passed to a registered EDT-confined UI mutator, and `YES` for a loop whose body contains the finding and admits `ProgressManager.checkCanceled()` between iterations.

- **Step 2: Add controls before implementation**

  Fire-and-forget `void` calls are not synchronous-result dependencies; logging is not UI consumption; a single non-looping call is not cancellable iteration. When target resolution is ambiguous, return `UNKNOWN`.

- **Step 3: Implement exact source-range data flow**

  Limit propagation to the containing callable and uniquely resolved local variables. Do not build a cross-file data-flow engine in Stage 3.

- **Step 4: Run full tests and commit**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "edt-freeze-finder: extract downstream repair factors"
  ```

## Task 6: Implement and Explain `teacher-v0`

**Files:**

- Modify: `tools/edt-freeze-finder/confidence_scoring.py`
- Modify: `tools/edt-freeze-finder/confidence.py`
- Modify: `tools/edt-freeze-finder/finder/test_confidence.py`

**Interfaces:**

- Consumes: the six tri-state factor facts and the Finder's semantic `repair_strategy`.
- Produces: `score_repair(strategy, factors, profile="teacher-v0") -> dict[str, object]`.

- **Step 1: Write exact-weight Reds**

  Assert `YES` contributes the teacher's signed weight, `NO` contributes zero, and `UNKNOWN` contributes zero plus its factor name in `unknown_factors`. Clip the sum to `-100..100`.

- **Step 2: Restrict profile applicability**

  Apply `teacher-v0` only to background/prefetch family candidates: `MOVE_TO_BGT`, `BGT_THEN_EDT`, `PREFETCH`, and `LAZY_INITIALIZATION`. Other strategies remain scored as `UNVALIDATED` until a strategy-specific profile exists.

- **Step 3: Separate score from confidence**

  Return the numeric score and explanation, but keep `repair_confidence=UNVALIDATED` until Task 7. A high arithmetic score with any `UNKNOWN` safety-critical factor must not become eligible for automatic repair.

- **Step 4: Run full tests and commit**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "edt-freeze-finder: evaluate teacher repair score hypothesis"
  ```

## Task 7: Calibrate on Development and Freeze Evaluation

**Files:**

- Create: `tools/edt-freeze-finder/confidence_evaluation.py`
- Modify: `tools/edt-freeze-finder/test_confidence_golden_set.py`
- Modify: `tools/edt-freeze-finder/finder/golden/java-confidence-oracle.tsv`
- Modify: `tools/edt-freeze-finder/finder/eval_207.py`

**Interfaces:**

- Consumes: detection/confidence TSVs and `assess_file(path)`.
- Produces: `evaluate_oracle(...)` metrics containing counts, precision, recall, F1, false-positive/false-negative IDs, factor coverage, and developer-strategy agreement.

- **Step 1: Write metric Reds with a hand-worked mini table**

  Use literal TP/FP/FN examples whose expected precision, recall, and F1 are calculated independently in the test. Reject a split other than `development` or `evaluation`.

- **Step 2: Migrate `../eval_207.py` to public seams**

  Remove imports of `_match_blocking` and `BLOCKING_IO_APIS`. Evaluation must run frozen fixtures through `analyze_file()` or `assess_file()` and report unavailable pre-fix sources as explicit exclusions.

- **Step 3: Select development thresholds deterministically**

  For observed problem scores, evaluate every distinct score as a threshold; select maximum F1, breaking ties by higher precision and then higher threshold. Map scores at or above it to `HIGH`, positive scores below it to `MEDIUM`, and zero to `LOW`.

  Repeat threshold selection for `teacher-v0` repair scores, treating a developer strategy in the supported background/prefetch family as the positive label. A score at or above the repair threshold is `HIGH` only when every safety-critical factor is known; the same score with an unknown safety factor is `MEDIUM`, a lower score is `LOW`, and a strategy outside the profile remains `UNVALIDATED`. Record both thresholds and development metrics in versioned profiles. Do not inspect evaluation labels during selection.

- **Step 4: Freeze evaluation rows before running them**

  Add untouched Stage 2 evaluation specimens with adjudicated labels and developer strategies. Commit the oracle rows before the first evaluation command.

- **Step 5: Run evaluation once and preserve failures**

  Output false-positive and false-negative specimen IDs. Any accepted behavior change starts a new TDD cycle; do not rewrite an oracle merely to improve metrics.

- **Step 6: Commit**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "tests edt-freeze-finder: calibrate confidence evaluation"
  ```

## Task 8: Integrate Explainable Recommendations

**Files:**

- Modify: `tools/edt-freeze-finder/finder/finder.py`
- Modify: `tools/edt-freeze-finder/confidence.py`
- Modify: `tools/edt-freeze-finder/finder/test_confidence.py`

**Interfaces:**

- Consumes: calibrated problem threshold, repair score, factor evidence, and existing `recommend(result)` output.
- Produces: deterministic CLI explanations; no source modifications.

- **Step 1: Write output Reds**

  Assert output contains the problem score/profile, repair score/profile, every supporting/contradicting/unknown factor, and the recommended semantic strategy. Ordering is fixed by the six-factor definition, not dictionary iteration.

- **Step 2: Preserve conservative fallbacks**

  If problem confidence is below the calibrated threshold, report a candidate rather than a proved violation. If repair confidence is unvalidated or a safety-critical factor is unknown, recommend `MANUAL_REVIEW` even when the old template renderer can print code.

- **Step 3: Run deterministic full-suite checks**

  Run the complete Finder suite twice and compare evaluation JSON byte-for-byte.

- **Step 4: Commit**

  ```powershell
  git add tools/edt-freeze-finder
  git commit -m "edt-freeze-finder: explain problem and repair confidence"
  ```

## Task 9: Stage 3 Evaluation Gate and Closeout

**Files:**

- Create: `tools/edt-freeze-finder/STAGE3-EVALUATION.md`
- Modify: `tools/edt-freeze-finder/PROGRESS.md`

**Interfaces:**

- Consumes: frozen evaluation results and false-positive/false-negative lists.
- Produces: the explicit evidence gate that Stage 4 must consume.

- **Step 1: Record reproducible evaluation facts**

  Include repository commit, commands, development/evaluation counts, thresholds, precision, recall, F1, factor coverage, strategy agreement, exclusions, and every known limitation.

- **Step 2: Make the Surgeon gate explicit**

  List which semantic strategies, score profiles, evidence combinations, and Java source shapes are eligible for Stage 4. Every unlisted combination is ineligible. Do not convert an overall average metric into permission for all strategies.

- **Step 3: Require user approval of the gate**

  Stage 4 planning may be refined, but Stage 4 implementation does not begin until the user accepts the recorded eligible subset.

- **Step 4: Update progress and commit**

  ```powershell
  git add tools/edt-freeze-finder/STAGE3-EVALUATION.md tools/edt-freeze-finder/PROGRESS.md
  git commit -m "docs edt-freeze-finder: complete Stage 3 confidence evaluation"
  ```

## Plan Self-Review Result

- Spec coverage: six factors, separate problem/repair confidence, frozen development/evaluation splits, precision/recall, strategy agreement, explainability, and the Stage 4 gate each have an implementing task.
- Leakage guard: Issue/commit/oracle fields are confined to evaluation; production scores use static finding and AST evidence only.
- Type consistency: tri-state factors and assessment/result field names are defined once in Task 0 and reused unchanged.
- Scope: no Kotlin, source rewriting, network-dependent tests, Excel parsing, or automatic-repair permission is introduced.
- Placeholder scan: every task names exact files, interfaces, Red cause, Green boundary, verification command, and commit checkpoint.
