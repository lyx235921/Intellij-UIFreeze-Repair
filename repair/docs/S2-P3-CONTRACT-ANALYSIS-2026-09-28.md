# P3 first automatic contract analysis

2026-09-28: representative real row424, background sender t1. Reused saved Finder and verified current source contexts; no production modification.

Implemented scoped negative analysis in RepairSelectionS2.assessTransferredRefresh. Requires exact method symbol, source path and HASH_MATCHED extraction. Emits FAIL with source frame/path/hash and matching excerpt for:

1. fireBeforeRefreshStart notification preceding processEventsFromRefresh: synchronous completion ordering.
2. transferWriteActionAndBlock: existing write-action transfer requires a blocking protocol.
3. captureContextCancellationForRunnableThatDoesNotOutliveContextScope: asynchronous escape violates captured scope lifetime.
4. exceptionRef.get()?.let { throw it }: callback exception synchronously rethrown to sender.

This rejects a direct async-dispatch replacement. It does not prove every possible redesigned continuation unsafe. Regex recognizers are specific to this verified implementation, not general dataflow analysis; unmatched or unavailable evidence remains UNKNOWN. No automatic PASS rule or patch generator added.

Build-q1.ps1 with layout-python exited0. Q1_CLASSPATH set from TEMP/repair-q1-build/classpath.txt; `python -m unittest discover -s repair/tests -p test_q2_classifier.py -v`:4 pass. Replayed rows424/425/426 via repair.py --q2-classpath <classpath> --s2-repair-selection:3 accepted,exit0. Artifacts in out/edt-freeze-finder/s2-p3-contract-20260928.

Row424: four FAIL. Rows425/426: completion dependency UNKNOWN, other three FAIL. All three reject local rewrite and withdraw recommendation;0 patches. Initial over-broad assertion expecting all four FAIL in every row failed; corrected evidence-specific assertions pass, saved in verification.json. This demonstrates that missing context is not automatically rejected or passed as if proved.

Remaining work: broader positive/negative semantic analysis and dedicated rule regression fixtures; no full343 replay or live freeze experiment this turn. Current implementation is the first case-specific automatic rejection rule, not a completed general four-condition analyzer.
