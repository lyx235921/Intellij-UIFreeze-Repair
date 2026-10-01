# S2 background sender extraction — 2026-09-28

Implemented in extract_method_S2.kt and repair_selection_S2.kt. Existing Q2 classification remains UI-only and unchanged. In a Q2 record, additionally inspect non-UI WAITING/TIMED_WAITING threads for an exact recognized invokeAndWait method, a preceding wait/park frame and contiguous non-elided stack. Lambda-only name matches do not qualify. This identifies sender candidates, not a proven association with the frozen EDT task.

Preserve stack evidence from the top; extract up to five non-JDK method contexts starting at the dispatch method. Reuse existing path/range/hash verification, missing-source and ambiguity handling. Emit operation_role=BACKGROUND_DISPATCH_CANDIDATE and edt_task_association=NOT_ESTABLISHED. P3 analysis_context reports source availability, transferred-write-action evidence and four NOT_PERFORMED semantic analyses. Four preconditions remain UNKNOWN; eligible_for_generation=false. No generator or patch added.

Full saved Finder replay:5891 accepted/0 rejected;1363 Q2 unchanged;343 background sender candidates,all343 with at least one verified caller context beyond the recognized dispatch wrapper;1034 located method contexts (occurrences,not unique methods). Prior348 name-hit rows are a looser search;5 did not meet this stricter admission. This does not establish343 safe repairs.

Example row424/t1: verified InternalThreading.invokeAndWaitWithTransferredWriteAction, RefreshSessionImpl.invokeOnEdt, fireEventsInWriteAction and doFireEvents. Fifth lambda context unresolved. Thus source needed to start completion/ordering/lock/error analysis is present, but callback capture/lifetime and cross-method behavior may need additional source. Do not claim all four contracts are fully evidenced or passed.

Validation commands:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_q2_classifier.py -v
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/full-repair-20260928/finder.jsonl --output out/edt-freeze-finder/s2-sender-20260928/repair.jsonl --q2-classpath $env:Q1_CLASSPATH --s2-repair-selection
```

Build exit0;4 tests pass/0 skipped, including new sender source, lambda exclusion, gap exclusion and RUNNABLE exclusion assertions; full replay exit0. Artifacts repair.jsonl and summary.json under out/edt-freeze-finder/s2-sender-20260928. This is current Repair over saved Finder,not fresh Finder or runtime testing. No available IDE lint used. Research549cca9404d234e192ead79ca7d9fa24c04c3d13 unchanged;no new reading. Uncommitted. S1/4746 and S2 P1 budget unchanged.

Next: audit representative sender source and callback definition against four conditions; establish task association when required; only then consider a patch.
