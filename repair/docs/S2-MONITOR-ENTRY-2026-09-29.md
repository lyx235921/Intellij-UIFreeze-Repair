# EDT monitor entry marker — 2026-09-29

WaitResourceEvidence now emits `wait_kind=MONITOR_ENTRY_BLOCKED` only when thread_id is in Finder ui_thread_ids and reported Java state is BLOCKED. This includes monitor reacquisition after wait; it does not mean Object.wait in WAITING is monitor-entry blocking. Basis is explicitly REPORTED_JAVA_THREAD_STATE_BLOCKED.

`monitor_object_status=REPORTED_LABEL_LINKED` uses the existing record-local resource_id. Missing/null/unrecognized descriptions retain the monitor marker but emit LABEL_MISSING_OR_UNRECOGNIZED and no resource_id. Other waits stay UNCLASSIFIED_WAIT. No inferred owner/producer, cycle or new Q2 classification; BLOCKED records are still outside Q2 but resource evidence is emitted for them.

Validation: build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe exit0. With Q1_CLASSPATH from TEMP/repair-q1-build/classpath.txt, `python -m unittest discover -s repair/tests -p test_wait_resource_evidence.py -v` passes2 tests and corresponding test_q2_classifier.py passes4. Tests cover valid/missing/malformed monitor labels, WAITING versus BLOCKED, and non-UI exclusion.

Full saved Finder replay:

```powershell
$cp=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/full-repair-20260928/finder.jsonl --output out/edt-freeze-finder/s2-monitors-20260929/repair.jsonl --q2-classpath $cp
```

Exit0,5891 accepted/0 rejected.117 EDT BLOCKED observations;117 linked labels,0 missing in this dataset. Missing branch covered by tests. Independent assertions verify marker iff EDT+BLOCKED, resource references and record count; summary.json in the output directory records every matching row. Row3586 reports Sentinel@7c2b8642; owner text is preserved only, not linked to a thread yet.

No IDE runtime test or repair patch. Working tree uncommitted;572 pre-existing tracked changes preserved. Research remote advanced one commit to43be46f995a0f5c49e905c002a404efaccdd3b2a; read both changed files PROJECT.md and workflow/coordination/2026-09-29-01-status-review.md fully at that revision. Status synchronization only, no changed task requirement. Next: validate explicit owner evidence separately; monitor marker alone does not prove a resource cycle. S1/4746 unchanged.
