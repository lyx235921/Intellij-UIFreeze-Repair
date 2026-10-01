# EDT Freeze Finder Stage 2 Java Detection Generalization Design

**Date:** 2026-08-18

**Status:** Design and implementation plan approved

**Progress source:** `tools/edt-freeze-finder/PROGRESS.md`

## Purpose

Stage 1 proved that the Finder can classify Java call sites, detect selected blocking APIs, explain its evidence, and reproduce two real before/after fixes. Stage 2 generalizes that MVP without turning it into an automatic repair tool.

The key correction is that a UI freeze is not limited to a slow call executing directly on the EDT. Background work can freeze the EDT through read/write-lock contention, bounded-pool starvation, service initialization, or synchronous waits. The Stage 2 result model must represent that causal path instead of treating `BGT` as automatically safe.

## Goals

- Preserve separate `direct`, `propagated`, and `unknown` thread evidence.
- Represent direct EDT blocking and indirect BGT-to-EDT freeze mechanisms in one result model.
- Replace ambiguous A/B/C labels with semantic repair-strategy identifiers.
- Keep the research workbook as a changing evidence pool while freezing executable Java oracles in a version-controlled TSV.
- Add capabilities through real vertical slices, beginning with CASE-011 / IJPL-248581.
- Keep every reported conclusion explainable from static evidence, a pinned external oracle, or both.

## Non-goals

- Kotlin or coroutine-source analysis; Kotlin remains Stage 5.
- A complete interprocedural call graph in the first Stage 2 slice.
- General lock-cycle or thread-pool saturation proof from source alone.
- Precision/recall thresholds or confidence weights; those belong to Stage 3.
- Automatic source modification; the product remains Finder, not Surgeon.
- Treating every `getInstance()` call as expensive service initialization.

## Sources of truth

The design combines three different evidence layers:

1. The current Finder supplies an executable static-analysis seam: `analyze_file(path)` and `recommend(result)`.
2. The teacher design supplies upstream/downstream repair factors and candidate repair strategies, pending empirical calibration.
3. JetBrains' official UI-freeze guidance supplies the platform causal model: read/write locks, thread starvation, service initialization, `runBlocking`, and cooperative cancellation.

These layers are complementary. Official platform behavior constrains the causal model, the Finder locates source candidates, and later confidence scoring decides how strong a problem or repair conclusion is.

## Initial Stage 2 decision-rule candidates

The teacher's predefined rules and JetBrains' official freeze guidance support four high-value rules that are simple enough to investigate early. They are rule compositions, not mutually exclusive result categories: for example, `HEAVY_IN_UPDATE` is a specialization of `EDT_BLOCKING`, and a long read action may also contain an EDT-blocking operation.

The rules begin as `research-seed` or `experimental`. A rule becomes `stable` only after it has a type-aware or contract-aware detector, at least one positive fixture, at least one negative fixture, a pinned real case, and an automated expectation in the golden set.

| Rule | Context and trigger | Detection evidence | False-positive guard | Consequence | Candidate repair | Initial status |
|---|---|---|---|---|---|---|
| `EDT_BLOCKING` | Effective thread is EDT and a qualified expensive operation executes there | `direct` or `propagated` EDT evidence **and** a type-aware blocking/expensive-operation registry match | `unknown` is not promoted to EDT; an enclosing recognized BGT dispatch overrides the outer EDT context; common method names are not matched without receiver/type evidence | UI freeze or visible stutter | `MOVE_TO_BGT`, `BGT_THEN_EDT`, `CACHE_OR_SNAPSHOT`, `CANCELLABLE_OPERATION`, or `MANUAL_REVIEW`, selected from dependency evidence | `experimental`; partially implemented in Stage 1 |
| `UI_FROM_NON_EDT` | Effective thread is BGT and code mutates Swing/AWT or another EDT-confined UI object | `direct` or `propagated` BGT evidence **and** a known UI-mutator or `@RequiresEdt`-style contract | Exclude documented thread-safe operations and unresolved receivers; do not count it as a freeze unless a lock/wait impact path is also proved | Primarily a race or invalid UI state; it may contribute to lock contention but is not automatically a freeze | Java: modality- and disposal-aware `invokeLater` or an equivalent platform UI executor; Kotlin handling is deferred to Stage 5 | `research-seed`; tracked separately from freeze metrics |
| `READ_ACTION_MISUSE` | EDT or BGT code holds a read action around excessive or unrelated work | A recognized read-action scope **and** at least one risk signal: qualified expensive operation, synchronous wait, broad traversal/loop with insufficient cancellation checks, or real-case evidence that non-model work unnecessarily extends the lock scope | A short read action is legal and must not be reported merely because `ReadAction` appears; cancellation and nested thread-switch behavior must be inspected | On EDT, long work blocks event processing directly; on BGT, it can delay write-lock acquisition and freeze the EDT | `SHRINK_READ_ACTION`, `CANCELLABLE_OPERATION`, NBRA where appropriate, or more frequent `ProgressManager.checkCanceled()` | `research-seed`; CASE-020 is the planned Java slice |
| `HEAVY_IN_UPDATE` | `AnAction.update()` effectively runs on EDT and performs an expensive operation | An `update(AnActionEvent)` override **and** effective EDT evidence after applying `getActionUpdateThread()` **and** a qualified expensive-operation match | If `getActionUpdateThread()` proves BGT, this rule does not fire; UI-only access may make a blanket BGT repair invalid | Repeated EDT stalls, visible stutter, or freeze | Prefer `ActionUpdateThread.BGT` when its data-access contract permits it; otherwise split background preparation from minimal EDT UI access | `experimental`; T1/update-thread classification already supplies part of the evidence |

“Simple rule” therefore means that the decision can be expressed as a small conjunction of independently explainable facts. It does not mean matching `ReadAction`, `update`, or a common method name as plain text.

### Blocking-API evidence contract

A registry entry describes which evidence is required; registration alone does not prove a receiver type. Stage 2 applies these rules:

- An exact receiver/type match is the default. `FileDocumentManager.saveAllDocuments` and `VirtualFile.contentsToByteArray` are examples.
- A missing receiver in a registry specification never means “match every receiver.” An unresolved or unrelated receiver remains unreported.
- A platform-contract match is allowed only when the analyzer emits a concrete contract identifier and the finding records that evidence. A boolean flag that merely bypasses receiver checks is not contract evidence.
- Existing qualified `FileUtil` and `VfsUtil` registrations are not supplemented with bare `loadFile` or `loadFileBytes` method-name matches.

Every blocking API admitted to the golden set therefore needs a positive typed or contract-backed specimen and an unrelated same-name negative specimen.

### Overlapping-rule reporting

Rules are predicates over the same source observation, so one finding may satisfy more than one rule. The Finder preserves that evidence without double-counting the finding:

- `matched_rules` contains every satisfied rule identifier in deterministic source-independent order. It is empty when the analyzer has found a blocking candidate but lacks enough evidence to prove any violation rule.
- `primary_rule` contains exactly one identifier used for the headline, golden-set grouping, and future aggregate rule metrics when `matched_rules` is non-empty. It is `null` for an unclassified candidate.
- A more specific rule supersedes its general parent as `primary_rule` while the parent remains in `matched_rules`. Therefore `HEAVY_IN_UPDATE` is primary over `EDT_BLOCKING` for an expensive EDT `update()` call.
- `READ_ACTION_MISUSE` is primary over `EDT_BLOCKING` only when the evidence establishes that excessive or unrelated work extends the read-lock scope. If the analyzer proves only an expensive EDT call inside a syntactic read action, `EDT_BLOCKING` remains primary and `READ_ACTION_MISUSE` must not be added speculatively.
- If `READ_ACTION_MISUSE` and `HEAVY_IN_UPDATE` are both proved, `READ_ACTION_MISUSE` is primary because the excessive lock scope is the more specific causal mechanism; `HEAVY_IN_UPDATE` remains in `matched_rules` as the entry-context specialization.
- `UI_FROM_NON_EDT` belongs to the thread-safety metric family. It can coexist with a freeze rule, but it is not promoted into freeze counts unless `freeze_mechanism` and `edt_impact_path` independently establish an EDT impact.

This reconciles the research codebook's “specific rule first” convention with the causal model: a later aggregate reporter can count one primary rule per finding, while Stage 2 explanations and case analysis retain all proven matches.

## Canonical result model

Each finding answers six separate questions:

1. Which rule is primary, and which other rules also match?
2. Where does the operation execute?
3. How strong is the thread evidence?
4. What kind of expensive operation is it?
5. How can it prevent the EDT from making progress?
6. Which repair strategy is supported by the current evidence?

### Rule identity

`primary_rule` is either `null` or one of the registered semantic rule identifiers, such as `EDT_BLOCKING` or `HEAVY_IN_UPDATE`. `matched_rules` is an ordered list containing every predicate proved for the same source observation. When it is non-empty, it must contain the non-null `primary_rule`; when it is empty, `primary_rule` must be `null`. This distinction preserves useful blocking candidates whose thread or causal evidence is still `unknown` without labeling them as proved violations. The legacy R-number mapping remains research metadata: R2 maps to `UI_FROM_NON_EDT`, R3 to `EDT_BLOCKING`, R7 to `READ_ACTION_MISUSE`, and R8 to `HEAVY_IN_UPDATE`.

### Execution thread

`execution_thread` has exactly three values:

- `EDT`
- `BGT`
- `unknown`

This field describes execution location only. It does not determine whether a finding is safe.

### Thread evidence level

`thread_evidence_level` has exactly three values:

- `direct`: a method contract, override rule, annotation, or enclosing dispatch construct directly establishes the thread.
- `propagated`: a direct fact reaches the finding through a preserved call path without an intervening conflicting switch.
- `unknown`: the source does not prove a thread, dynamic dispatch prevents proof, or the analysis boundary is reached.

`thread_evidence` stores the concrete rule or path, for example `T1(sig)`, `lambda:executeOnPooledThread`, or a future call path. An `unknown` label is a valid oracle and must never be rewritten as EDT merely because an issue reports a freeze.

Stage 2 must make `propagated` executable rather than reserving the enum for future work. Its first implementation is deliberately bounded to one Java source file and uniquely resolved calls to `private`, `static`, or `final` methods. A direct thread fact may cross that call edge only when no recognized thread switch intervenes. Ambiguous overloads, virtual dispatch, mixed EDT/BGT callers, recursion beyond the analysis budget, and unresolved targets remain `unknown`. The evidence string records the preserved path, for example `T1(sig) -> invoke -> doGenerate`.

### Blocking family

`blocking_family` describes the expensive work:

- `DISK_VFS`
- `EXTERNAL_PROCESS`
- `NETWORK`
- `PSI_RESOLVE_INDEX`
- `SERVICE_INITIALIZATION`
- `LOCK_OR_SYNC_WAIT`
- `CPU_OR_ALGORITHM`
- `OTHER`

The family is independent of the execution thread and freeze mechanism.

### Freeze mechanism

`freeze_mechanism` describes the causal mechanism:

- `DIRECT_EDT_BLOCK`
- `LOCK_CONTENTION`
- `THREAD_STARVATION`
- `SERVICE_INIT_WAIT`
- `SYNC_WAIT`
- `EXPENSIVE_EDT_COMPUTE`
- `UNKNOWN`

Static evidence may establish only the blocking family while leaving the mechanism `UNKNOWN`. A stronger label requires evidence for the causal relationship.

### EDT impact path

`edt_impact_path` records how EDT progress is prevented:

- `SAME_THREAD`
- `EDT_WAITS_FOR_LOCK`
- `SHARED_POOL_EXHAUSTED`
- `EDT_WAITS_FOR_INITIALIZATION`
- `EDT_WAITS_FOR_RESULT`
- `UNKNOWN`

For example, a BGT read action may be represented as `execution_thread=BGT`, `freeze_mechanism=LOCK_CONTENTION`, and `edt_impact_path=EDT_WAITS_FOR_LOCK`.

## Repair strategy identifiers

Stage 2 uses semantic identifiers rather than letters:

- `MOVE_TO_BGT`
- `BGT_THEN_EDT`
- `CACHE_OR_SNAPSHOT`
- `LAZY_INITIALIZATION`
- `PREFETCH`
- `CANCELLABLE_OPERATION`
- `SHRINK_READ_ACTION`
- `PRELOAD_SERVICE`
- `AVOID_COLD_INITIALIZATION`
- `AVOID_SYNC_WAIT`
- `ALGORITHM_OPTIMIZATION`

The Stage 1 names map as follows:

- 方案 A -> `MOVE_TO_BGT`
- 方案 B -> `BGT_THEN_EDT`
- 策略 C -> `CACHE_OR_SNAPSHOT`

The teacher's template letters are not reused because their A/B/C meanings conflict with the Stage 1 names.

### Recommendation status

`recommendation_status` 是 finding 级的「决策」轴，与 `repair_strategy` 正交：

- `NO_REPAIR`：执行线程为 BGT 且无已证明的间接 EDT 风险（`freeze_mechanism=UNKNOWN` 且 `edt_impact_path=UNKNOWN`），无需修复。
- `MANUAL_REVIEW`：线程证据为 `unknown`，无法下结论，需人工确认。
- `RECOMMEND`：有具体 `repair_strategy` 适用。

`repair_strategy` 始终是「would-be 修复策略」，与状态无关；`recommend(result)` 先按 `recommendation_status` 渲染，仅 `RECOMMEND` 才查策略渲染表。

## Compatibility during Stage 2

`analyze_file(path)` remains the public detection seam. New code uses canonical fields, while the existing `thread` and `evidence` keys remain temporary compatibility aliases for `execution_thread` and `thread_evidence` until all Stage 1 tests and output formatting have migrated.

`recommend(result)` remains the public recommendation seam. Internally it must select a semantic `repair_strategy` before rendering user-facing Chinese text. A BGT finding can return “no repair” only when its mechanism and impact evidence show no indirect EDT risk; thread location alone is insufficient.

Stage 2 exposes no aggregate reporting seam. `primary_rule`, `matched_rules`, `freeze_mechanism`, and `edt_impact_path` make each finding metric-ready, but production totals such as `freeze_count` and `thread_safety_count` belong to the Stage 3 evaluation design. If aggregation becomes a product capability, its public interface must be added here before tests depend on it.

## Golden-set architecture

### Research evidence pool

`EDT-Freeze-Finder-调研证据账本.xlsx` remains the human-maintained pool for community cases, issues, commits, papers, official documentation, incomplete candidates, long-form notes, Trace evidence, and exclusion reasons. It is allowed to evolve and is not read by automated tests.

### Frozen executable oracle

`tools/edt-freeze-finder/finder/golden/java-golden-set.tsv` is the version-controlled executable oracle. It contains only cases with pinned sources, reviewed expectations, fixtures, and automated tests. Tests use Python's standard TSV support and do not depend on an Excel parser.

One TSV row represents one verifiable source observation, not an entire issue. Multiple call sites in one issue therefore produce multiple rows. A repaired source with no expected finding has an explicit negative row.

The columns are:

1. `specimen_id`
2. `case_id`
3. `split`
4. `variant`
5. `language`
6. `source_file`
7. `expected_hit`
8. `primary_rule`
9. `matched_rules`
10. `callable`
11. `blocking_api`
12. `blocking_family`
13. `execution_thread`
14. `thread_evidence_level`
15. `thread_evidence`
16. `freeze_mechanism`
17. `edt_impact_path`
18. `repair_strategy`
19. `issue_id`
20. `commit_sha`
21. `oracle_kind`

`split` is either `development` or `evaluation`. Fix008 and CASE-023 are development cases because they already shaped the implementation. Evaluation cases must not be used to design the rules they evaluate.

### Admission rules

A case enters the TSV only when all of the following are true:

- An issue, commit, official source, or equivalent oracle is pinned.
- The pre-fix source is available.
- A post-fix source or explicit negative control is available.
- Expected blocking call sites are manually reviewed.
- Thread evidence is labeled without overstating certainty.
- Blocking family, freeze mechanism, EDT impact path, and repair strategy are labeled.
- An automated test reproduces the expectation.

Malformed enum values, duplicate `specimen_id` values, missing fixture paths, and contradictory expectations are hard test failures. Incomplete candidates remain in the workbook rather than being silently skipped by the golden-set runner.

## First Stage 2 vertical slice: CASE-011

### Oracle

- Case: `CASE-011`
- Issue: `IJPL-248581`
- Commit: `3bc7760a53b6423d2af570868784c406bab2885e`
- Java call site: `IdeaModifiableModelsProvider.getProjectStructureContext()`

The pre-fix Java code calls `ProjectStructureConfigurable.getInstance(project)`. The call can be reached from a background write action. Cold initialization constructs Swing UI and contends the global AWT tree lock, which can freeze the EDT.

The repair calls `getInstanceIfCreated(project)` and falls back when the Project Structure UI service has not been created. It avoids cold initialization instead of moving the call to another thread.

### Slice boundary

The first slice registers only the type-aware `ProjectStructureConfigurable.getInstance` pattern supported by this case. It does not generalize every `getInstance()` or every IntelliJ service lookup into a blocking API.

The slice uses two sequential Red-Green cycles through the same public seams.

#### Cycle 1: real before/after detection

- Before: one `ProjectStructureConfigurable.getInstance` finding.
- After: zero findings because `getInstanceIfCreated` is not cold initialization.
- Before family: `SERVICE_INITIALIZATION`.
- Before strategy: `AVOID_COLD_INITIALIZATION`.
- Single-file thread: `execution_thread=unknown`, `thread_evidence_level=unknown`.
- Single-file causal path: `freeze_mechanism=UNKNOWN`, `edt_impact_path=UNKNOWN`.

The single-file analyzer must not claim BGT propagation merely because the commit message supplies a runtime path.

#### Cycle 2: explicit BGT context

A focused Java fixture places the same cold-initialization call inside `executeOnPooledThread`. The expected finding is:

- `execution_thread=BGT`
- `thread_evidence_level=direct`
- `blocking_family=SERVICE_INITIALIZATION`
- `freeze_mechanism=LOCK_CONTENTION`
- `edt_impact_path=EDT_WAITS_FOR_LOCK`
- `repair_strategy=AVOID_COLD_INITIALIZATION`

The recommendation must not be “already on BGT, no repair.” This cycle establishes the first executable counterexample to the Stage 1 BGT-safe shortcut.

## Testing strategy

Tests observe behavior only through `analyze_file(path)` and `recommend(result)`. Private matching, AST traversal, and formatting helpers are not test seams.

The test layers are:

1. Existing Stage 1 regression tests remain green during schema migration.
2. CASE-011 real before/after fixtures establish the new service-initialization family.
3. The explicit BGT fixture establishes the indirect EDT impact and recommendation behavior.
4. Same-name negative fixtures prove that registry entries require receiver/type or explicit platform-contract evidence.
5. A pinned Java call-chain case proves `propagated`, while conflicting or unresolved call paths remain `unknown`.
6. The TSV contract test validates schema, enum values, unique IDs, fixture paths, and grouped expected results.
7. Later vertical slices add new behavior one Red-Green cycle at a time rather than adding an entire family registry in advance.

## Stage 2 sequence after CASE-011

After CASE-011, the Finder first closes the Stage 1 bare-method-name false-positive gap, establishes the golden-set runner, and implements bounded single-file thread propagation with CASE-004 / IDEA-390239. CASE-020 / IJPL-235455 then moves work out of a long read action and introduces lock-context propagation. CASE-027 / IDEA-388795 follows as a candidate for cancellable progress around expensive PSI resolve.

This order deliberately moves from type-aware local matching to bounded thread propagation, lock-context analysis, and then path-sensitive cancellation. It avoids treating a complete cross-file call graph or general lock analyzer as a prerequisite.

## Success criteria

Stage 2 is complete when:

- Findings use the canonical causal fields and semantic repair identifiers.
- Direct, propagated, and unknown evidence remain distinguishable in output and tests.
- The version-controlled Java golden set contains multiple blocking families and both positive and negative specimens.
- At least one BGT-originating finding correctly explains an indirect path to EDT freeze.
- Every frozen specimen is traceable to a pinned oracle and automated expectation.
- The Finder can explain why it reported or did not report each golden specimen.
