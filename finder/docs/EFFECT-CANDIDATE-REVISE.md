# Effect Candidate REVISE Diagnosis

**Date:** 2026-08-26

**Status:** diagnosis complete; analyzer modification blocked by the user-approved one-gap scope

## Immutable Starting Point

- Task 6 remains `TRANSFER_CONTRACT_FAILURE`, `before=0`, `after=0`.
- The consumed package is copied to `fixtures/effect_candidates/consumed_transfer_001` as `split=development` with `origin_status=consumed_failed_evaluation`.
- The external package and `EFFECT-CANDIDATE-EVALUATION.md` remain unchanged.
- The pre-REVISE working state is recoverable from the five verified binary patches under the external checkpoint recorded in `../../PROGRESS.md`.
- A versioned `run_sealed_transfer(...)` now handles empty-before without losing timings, hash state, or nullable metrics; focused runner tests are 3/3 Green.

## Tight Feedback Loop

```powershell
python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_consumed_effect_candidate.py" -v
```

The command was run twice. Both runs produced the same result in approximately 0.2 seconds:

- provenance/leakage control: Green;
- expected consumed before count: 1;
- actual consumed before count: 0;
- consumed after count: 0.

The public seam is `discover_effect_candidates(paths)`. No analyzer file was changed during diagnosis.

## Real Before/After Causal Difference

The before lifecycle path is:

```text
Configurable.buildConfigurables
→ ColorAndFontOptions.buildConfigurables
→ initAll
→ initScheme
→ eager descriptor/extension/scope initialization
```

The after revision removes both `initScheme` calls from `initAll` and initializes descriptors lazily from `MyColorScheme.getDescriptors()` instead. The Git parent/child relationship, exact source bytes, source closure, lifecycle relevance, eager-before effect, after mitigation, independence, and absence of dynamic dispatch were independently audited before Task 6.

## Ranked Hypotheses and Probes

### H1 — Effect taxonomy/model coverage gap

**Prediction:** If the existing lifecycle/call propagation is functional, injecting a semantic direct effect at `initScheme` in memory will make the before result nonempty without changing source parsing or edges.

**Observed:** direct effect count and reachable effect count are initially zero. A diagnostic in-memory `SEMANTIC_MODEL` effect at `initScheme` produced candidates, proving the lifecycle and the two `initAll → initScheme` edges are functional. This confirms a real effect-model gap.

It did not satisfy the transfer contract: the result contained two `COMPLETE` buildConfigurables paths and four `TRUNCATED` createComponent paths instead of one candidate.

### H2 — Source-resolved call edge canonicalization gap

**Prediction:** If invocation argument types and callable parameter types use the same canonical form, `initScheme → initPluggedDescriptions` and `initScheme → initScopesDescriptors` will resolve.

**Observed:** callable parameters are stored as simple `List`, while invocation arguments are stored as imported `java.util.List`. Exact compatibility rejects both edges. Injecting an effect into `initPluggedDescriptions` therefore produced zero candidates. This is independent of H1.

### H3 — External static receiver typing gap

**Prediction:** Giving external registry/service calls a resolved receiver type will allow a declarative direct-effect model to evaluate them.

**Observed:** the supplied source set contains only the main source file. External receivers such as the page registry and project/scope services have `receiver_type=None`; current exact receiver models cannot match. A probe that assigns a known modeled type makes `_direct_effects` respond, but the real receiver has no applicable current model. This is independent of the call-edge canonicalization gap.

### H4 — Lifecycle precision and candidate multiplicity gap

**Prediction:** A direct effect at the eager helper will expose whether the result contract already collapses equivalent callsites and suppresses dominated truncated paths.

**Observed:** two eager callsites in `initAll` produce two separate `COMPLETE` candidates. Long over-approximated createComponent/reset paths produce four additional `TRUNCATED` candidates. The current `createComponent` lifecycle check is name-based and also accepts the boolean overload. No existing rule selects one representative causal mechanism, makes complete paths dominate related truncated paths, or enforces the Task 6 count of one.

### H5 — Nested-to-outer call edge gap after the cut

**Prediction:** The lazy after call will resolve only if an unqualified call from nested `MyColorScheme` can target the enclosing class helper.

**Observed:** the current resolver searches the nested owner and cannot bind the outer helper. Qualifying the call in a diagnostic probe exposes the expected edge. This does not explain the before miss, but it affects any future analysis of the after lazy path.

## Minimal Load-Bearing Slice

The smallest real semantic slice retains:

1. the `Configurable` class declaration and `buildConfigurables` lifecycle;
2. `buildConfigurables → initAll`;
3. both before `initAll → initScheme` callsites;
4. the `initScheme` body and its descriptor/extension/scope helpers;
5. the after removal of eager calls and lazy `getDescriptors → initScheme` replacement.

Removing the lifecycle or eager helper makes the expected candidate invalid. Removing external effect evidence prevents semantic classification. Removing duplicate callsites/control paths hides the candidate-count mismatch rather than fixing it.

## Root-Cause Conclusion

The sealed case is a valid UI lifecycle eager-initialization fix, but it belongs to an effect family the current lane cannot represent. Supporting it under the existing Task 6 contract requires at least these independent behavior changes:

1. a semantic model for eager descriptor/extension/scope materialization;
2. canonical source-call type compatibility and/or external receiver contracts;
3. lifecycle signature precision plus a defined policy for equivalent complete paths and dominated truncated paths;
4. optionally, nested-to-outer resolution to explain the lazy after path.

This is not one localized semantic gap. Implementing all of it would violate the user-approved single-gap REVISE scope. Hardcoding the consumed class, helper names, APIs, or source path would also violate the leakage contract.

## Decision Required Before Analyzer Work

No analyzer modification is authorized by the current active plan. A new user decision must choose one honest route:

- broaden REVISE into a multi-slice new effect-family design, accepting that it exceeds the original one-cycle scope;
- classify the consumed package as outside the current `SERVICE_INITIALIZATION / EAGER_INSTANCE_MATERIALIZATION` lane, fix sealed-case eligibility, and seek a new in-scope canary;
- pause the candidate lane as `EXPERIMENTAL` and resume Stage 3 confidence work without candidate promotion.

The original Task 6 failure remains unchanged under every route.

## User Decision: Tighten Current-Lane Eligibility

On 2026-08-27 the user selected the bounded eligibility route. The consumed case remains valid evidence of a UI lifecycle eager-initialization family and valid evidence that Task 6 failed, but it is explicitly `OUTSIDE_CURRENT_LANE / UNSUPPORTED_EFFECT_FAMILY`. Its current-lane regression is deterministic absence (`before=0`, `after=0`), not a positive oracle. It is permanently excluded from future sealed evaluation.

No analyzer file is modified under this route. Future Task 6 packages must declare and independently audit the one currently supported transfer target:

```text
SERVICE_INITIALIZATION
EAGER_INSTANCE_MATERIALIZATION
intellij-keyed-lazy-instance-v1
intellij-configurable-lifecycle-v1
minimum SEMANTIC_MODEL
required COMPLETE path
```

Legacy READY packages remain historically preflight-valid but are transfer-ineligible. The Git curator writes the target into manifest and signed selector prechecks; the different-signer auditor must repeat it with `transfer_target_verified=VERIFIED`; the versioned runner blocks ineligible packages before evaluator/analyzer calls.

## Route B Result

- Package eligibility contract: 19/19 Green.
- Git-native curator target enforcement: 9/9 Green.
- Versioned runner eligibility gate: 4/4 Green.
- Consumed out-of-lane regression: 2/2 Green.
- Full Finder suite: 96/96 Green.
- Flake8, AST parse, `git diff --check`, and the five frozen analyzer SHA-256 values: PASS.

The final blind selector searched only new independent evidence for the exact supported KeyedLazy semantic transfer target. One new high-likelihood record was screened and rejected because it did not match that target. No Git fetch, package materialization, auditor, preflight, or production evaluator run occurred. The user-approved stop gate therefore ends this bounded cycle with the lane remaining `EXPERIMENTAL/REVISE`. The absence of a fresh in-scope package is evidence scarcity, not a successful transfer and not an analyzer regression.
