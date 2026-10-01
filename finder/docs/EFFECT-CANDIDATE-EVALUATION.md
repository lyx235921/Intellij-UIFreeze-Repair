# Effect Candidate Sealed Transfer Evaluation

**Date:** 2026-08-26

**Verdict:** `TRANSFER_CONTRACT_FAILURE`

The frozen analyzer produced no candidate for the sealed before source set (`before=0`, `after=0`). This is an honest unseen-transfer feasibility failure, not a general recall estimate. The analyzer and package were not modified or rerun after the production attempt.

## Scope

- Opaque package: `opaque-final-c9d8e2f1`
- Package status before execution: `READY`
- Package SHA-256: `0b9a6165095a563782512b39e51441b05576ad55acda90728f9b876a044b34b1`
- Package cases: 1
- Before sources: 1
- After sources: 1
- Before size: 1,756 lines / 1.756 KLoC
- Purpose: one feasibility canary only; no precision, recall, or promotion claim

## Frozen Analyzer

| File | SHA-256 |
|---|---|
| `../source_model.py` | `d55046aaa6f12a16192dcd2b15c507f5ed1cdbacb58e5f4073debf9b3d5971c3` |
| `../effect_models.py` | `da33850190acdf038af6043cb2f28af957707d730126abee3f9989b0e83a1b1d` |
| `../effect_analysis.py` | `eb3d1552ccefc8e50be1e09d214fff89b132a4e30846b929876106585449b3da` |
| `../candidate_discovery.py` | `1f07bd180a177e6abfa6dbfb5071d7811aa6252d42b61f6204f61316f7ffcd88` |
| `../finder.py` | `112f6b19a43c3d1bf4d9c56e7f181e3f52749c452fc6d22eb98d0d9d59e89dfd` |

The same hashes were independently recorded by the leakage auditor and recomputed after the production attempt.

## Pre-Execution Gates

- Independent leakage audit: `PASS`
- Challenge-specific overlap with production analyzer: Issue IDs 0, commit hashes 0, source paths 0, distinctive symbols 0, derivative fragments 0
- Generic contract overlaps: 6, recorded separately and not treated as challenge leakage
- Development/micro baseline before execution: candidate discovery 18/18 Green; development oracle 3/3 Green
- Frozen-package revalidation: exact `READY` status and package SHA-256 matched before analyzer import

## One-Shot Result

| Metric | Result |
|---|---|
| Task 6 structured success | `false` |
| Packaged evaluator `success` | `true` |
| Evaluator call protocol | exactly `before`, repeated `before`, `after` |
| Before candidate count | 0 |
| After candidate count | 0 |
| Deterministic | `true` |
| Candidate/KLoC | 0.0 |
| Analyzer hashes unchanged | `true` |
| Total recorded elapsed time | 250.0 ms |

The packaged evaluator canary checks deterministic execution and an empty after result, so its own `success=true` is necessary but not sufficient for Task 6. The Task 6 contract additionally requires `before=1`; that gate failed.

Because the before result was empty, candidate-level metrics do not exist: `candidate_level`, `analysis_mode`, `path_status`, effect/lifecycle model provenance, analysis budget, and unresolved/truncated/complete rates are unavailable rather than zero. Per-analyzer-call timing is also unavailable because the one-shot runner raised while deriving metrics for the empty before result.

## Runner Evidence

- Exact command: `python C:\Users\38331\.codex\visualizations\2026\08\25\01a038fd-8133-7303-aecd-29552469d116\task6-execution\run_once.py`
- Runner SHA-256: `e6914a9dc8fdae83329ffd3fb5639dca673b849032a51053c0724a44fcfc223b`
- Attempt marker: present; the runner refuses a second production attempt
- Production rerun during postmortem: `false`

The runner initially labeled the exception `EXECUTION_FAILURE`. Read-only postmortem established that the evaluator had already completed the required three-call protocol with `before=0`, repeated deterministic `before=0`, and `after=0`; the exception occurred afterward when candidate metrics required a nonempty before result. The corrected semantic category is therefore `TRANSFER_CONTRACT_FAILURE`. The instrumentation defect lost per-call timing and post-call metric fields but does not change the before miss.

## Post-Execution Verification

```powershell
python -m unittest discover -s tools/edt-freeze-finder/finder -p "test_*.py" -v
```

Result: 86/86 Green after the production attempt. `git diff --check` and all five analyzer hashes remained unchanged.

## Consequence

- Do not add this package to `java-effect-candidate-oracle.tsv` as successful evaluation evidence.
- Do not tune Tasks 1–5 against the revealed challenge while calling it evaluation.
- Keep the candidate lane experimental and record the missing transfer capability before deciding whether a separately labeled development cycle is warranted.
