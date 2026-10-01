# EDT wait-object evidence — 2026-09-28

Implemented WaitResourceEvidence.kt, invoked on every Q2 output (including non-Q2 rows). No Finder schema change. `q2.wait_resource_evidence.observations` maps thread_id to record-local resource_id; `resources` preserves reported class@hex, class name, identity hash text and waiting thread IDs. Raw thread details and input stack SHA identify evidence provenance. Existing S2 method contexts can join observations by thread_id.

Only WAITING/TIMED_WAITING/BLOCKED plus a fully recognized `on class@hex` description qualifies. Optional `owned by ...` suffix is preserved as raw evidence but ownership is not inferred. RUNNABLE remains NOT_WAITING even when the Q2 stack classifier recognizes a wait path. Missing/malformed labels remain RESOURCE_LABEL_UNAVAILABLE. Shared labels group only within one record; identity hashes are not guaranteed unique and IDs cannot be compared across records/runs. CompletableFuture$Signaller is a waiter node, not proof of the parent Future identity. No owner/producer or resource-cycle analysis implemented.

Final full saved Finder replay:5891 accepted/0 rejected;1881 UI observations with reported wait objects overall. Within1363 Q2 rows:1328 reported wait objects,31 missing labels,4 NOT_WAITING. No source modification to IDE, patches or live runtime validation.

Examples verified against saved Finder descriptions:

- row357/t0 → FutureTask@2c669a1b.
- row424/t0 → FutureTask@24f827b5.
- row424/t1 → CompletableFuture$Signaller@4f4dfc88, explicitly not the Future.

Commands:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_wait_resource_evidence.py -v
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_q2_classifier.py -v
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/full-repair-20260928/finder.jsonl --output out/edt-freeze-finder/s2-resources-20260928/repair.jsonl --q2-classpath $env:Q1_CLASSPATH
```

Build exit0;5 tests pass/0 skipped (missing/malformed descriptions,states,record-local grouping,Signaller distinction plus S2 regression). Full replay exit0. Independent summary and example assertions pass: out/edt-freeze-finder/s2-resources-20260928/summary.json. Latest replay does not request expensive S2 method extraction; the thread_id association is available alongside it when that option is used.

Research549cca9404d234e192ead79ca7d9fa24c04c3d13 unchanged/no new reading;572 pre-existing tracked changed files preserved. Uncommitted. Next: determine whether raw evidence identifies owners/producers of these particular objects. Do not infer a cycle from two waiting threads or from same class names.
