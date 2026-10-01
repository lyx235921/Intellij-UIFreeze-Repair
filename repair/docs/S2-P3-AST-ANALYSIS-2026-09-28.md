# S2 P3 AST analysis and full replay

2026-09-28. Implemented Java/Kotlin intraprocedural analysis, replacing the row424-specific regex checker. This is a conservative analyzer, not a complete interprocedural safety prover. Automatic all-PASS admission remains unimplemented; no patches generated.

## Implementation

`P3PreconditionAnalyzer.kt` consumes HASH_MATCHED extracted method contexts. Kotlin compiler PSI and JDK javac parse method fragments without resolving types or invoking annotation processors. No arbitrary project code executes. Reports source frame/path/hash/line and excerpts, parse diagnostics and remaining obligations.

- Completion: identifies dispatch/wrapper candidate expressions, following block statements, consumed expression results, and Kotlin callback assignment/following-reference overlaps. These require adaptation/review; name overlaps alone are not alias proofs.
- Locks/context: identifies enclosing monitor/action scopes and Java synchronized methods. Verified InternalThreading write-transfer method with an actual transferWriteActionAndBlock call rejects direct asynchronous posting.
- Lifetime: identifies inline callback references/source and explicit scope-limited capture APIs. Arbitrary captured values and callee lifetimes remain unresolved, not safe by default.
- Failure: identifies enclosing try/catch/finally/resource scopes and throw expressions; marks failure routing as needing adaptation. Arbitrary throws/calls are not proved harmless.

Checks emit FAIL, NEEDS_ADAPTATION or UNKNOWN. The implementation deliberately has no all-PASS rule: absence of syntax hazards cannot prove cross-method effects, task identity, ownership/disposal, or exception policy. Callback reference names are candidate facts, not resolved free-variable sets. Known API recognition is not general type resolution. Thus the user's requested complete automatic pass/fail analyzer is only partially fulfilled; the AST analysis and full experiment are complete, but positive semantic proof remains open.

`repair_selection_S2` integrates results, withdraws automatic P3 recommendation for unresolved/rejected cases, retains eligible_for_generation=false. Prior case-specific regex function removed. build-q1.ps1 adds the analyzer and uses already downloaded compiler dependencies at runtime. Q2 classification unchanged.

## Final full-data results

Final artifact: `out/edt-freeze-finder/s2-p3-analysis-20260928/repair-java-kotlin.jsonl`; independent per-row tally: `summary-java-kotlin.json`. Earlier repair.jsonl/repair-final.jsonl are intermediate Kotlin-only runs, not final results.

5891 records accepted,0 rejected;1363 Q2 rows;343 extracted background sender candidates;1034 method-context occurrences parsed,0 parser diagnostics. All343 encounter the blocking write-transfer contract, so direct P3 replacement is rejected.

| Check | FAIL | NEEDS_ADAPTATION | UNKNOWN |
| --- | ---: | ---: | ---: |
| Completion dependence | 0 | 5 | 338 |
| Locks/context | 343 | 0 | 0 |
| Lifetime | 0 | 343 | 0 |
| Failure routing | 0 | 343 | 0 |

The historical516 awaitWithCheckCanceled rows are not516 P3-safe bugs.341 of them contain extracted P3 senders;175 do not. The other2 senders belong to other Q2 rows. Zero all-PASS,zero generated patches. Rejection concerns direct dispatch replacement, not every possible larger redesign.

## Validation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_p3_analysis.py -v
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_q2_classifier.py -v
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/full-repair-20260928/finder.jsonl --output out/edt-freeze-finder/s2-p3-analysis-20260928/repair-java-kotlin.jsonl --q2-classpath $env:Q1_CLASSPATH --s2-repair-selection
```

Build exit0.5 test methods pass/0 skipped,including12 new source scenarios covering Kotlin/Java hazards, harmless syntax retaining UNKNOWN, comments/strings, parse failure and write-transfer rejection. Initial test fixture outside workspace was unreadable to the child JVM; moved fixture into workspace out,then passed. Full Repair exit0;independent assertions on5891 records/343 senders/516 await rows and evidence-bearing non-UNKNOWN checks pass. Tests use the project's existing standalone runner because the retired Repair module is not registered. No live IDE performance test or production patch; no available IDE lint tool used.

Research549cca9404d234e192ead79ca7d9fa24c04c3d13 unchanged, no new reading. Pre-existing worktree preserved; uncommitted. S1/4746 unchanged. Next: resolved callback/call-effect and lifecycle models plus validated positive cases before enabling any PASS-based generation.
