# S2 P3 precondition trial — 2026-09-28

Added four explicit UNKNOWN business checks to RepairSelectionS2: no synchronous result/completion dependency; preserve lock/transaction/modality; valid lifetime/captured data; preserve asynchronous failure handling. The sender check is FAIL for a classified UI operation. Missing semantic evidence is never PASS; eligible_for_generation remains false. No P3 generator implemented.

Verification:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_q2_classifier.py -v
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/full-repair-20260928/finder.jsonl --output out/edt-freeze-finder/s2-p3-20260928/repair.jsonl --q2-classpath $env:Q1_CLASSPATH --s2-repair-selection
```

Build exit0;4 tests pass,0 skips; full replay exit0 after creating output directory. 5891 accepted/0 rejected,1363 Q2 rows. All1363 classified operations are UI operations: P3 REJECTED_SENDER,0 eligible,0 patches. This is saved Finder data replay through current Repair, not fresh Finder extraction or IDE validation.

Additional raw-stack name scan found348 of these Q2 rows also contain a non-UI thread with invokeAndWait in a frame symbol. This includes transferred-write-action methods and lambda frames, not348 proven safe dispatch sites. Examples424,425,426 use InternalThreading.invokeAndWaitWithTransferredWriteAction. No sender-to-UI-task identity or four-contract proof is inferred. Current Q2 classifier/extractor only routes UI operations, so these background clues are not admitted by this change.

Artifacts: out/edt-freeze-finder/s2-p3-20260928/{repair.jsonl,dispatch-threads.json,summary.json}. Summary independently counts eligibility and intersects background-name hits with Q2 row IDs.

Next useful work: extract a separate background sender candidate associated with a Q2 incident, preserve the original Q2 UI classification, inspect sender continuation/locking/lifetime/error handling, then implement a patch only for a demonstrated safe pattern. Do not mark missing evidence as satisfied merely to produce a candidate.

Research HEAD549cca9404d234e192ead79ca7d9fa24c04c3d13 unchanged; no new materials read. Pre-existing572 tracked changed files preserved. Changes uncommitted; S1/4746 unchanged;100ms S2 P1 experimental budget unchanged.
