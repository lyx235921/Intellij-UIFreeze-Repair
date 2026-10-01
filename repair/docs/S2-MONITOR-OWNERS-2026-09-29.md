# Explicit monitor owner association — 2026-09-29

WaitResourceEvidence now produces monitor_owner_associations for EDT BLOCKED observations. It extracts the explicit `owned by` suffix from a recognized object description and searches all Finder threads in the same record by exact name. A unique non-self match yields REPORTED_OWNER_LINKED with owner_thread_id, owner_thread_state, waiting_thread_id and resource_id. Missing label, missing reported owner, missing owner thread, duplicate name and contradictory self-owner each have a distinct status. The raw details and candidates are preserved; no fuzzy or cross-record matching.

Resource owner_status refers to the association table (SEE_MONITOR_OWNER_ASSOCIATIONS), so multiple observations are not silently collapsed into a single owner claim. Name matching is reported-evidence association, not a new runtime object identity proof. Future producers and resource cycles remain unestablished.

Verification: build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe exit0; with Q1_CLASSPATH from TEMP/repair-q1-build/classpath.txt, `python -m unittest discover -s repair/tests -p test_wait_resource_evidence.py -v` passes3 tests and test_q2_classifier.py passes4. New scenarios cover unique/missing/duplicate owner names, absent suffix, self-owner and case mismatch. No skipped tests.

Full saved Finder replay command:

```powershell
$cp=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/full-repair-20260928/finder.jsonl --output out/edt-freeze-finder/s2-monitor-owners-20260929/repair.jsonl --q2-classpath $cp
```

Exit0;5891 accepted/0 rejected. All117 EDT monitor observations link uniquely to a reported owner. Owner states:113 RUNNABLE,1 WAITING,3 TIMED_WAITING. These counts are snapshots, not duration/cycle conclusions; RUNNABLE does not prove fast progress. Independent assertions verify record count,resource references,unique non-self targets; summary.json in the output directory records all117 associations.

Example3586: EDT/t0 waits on Sentinel@7c2b8642, explicit owner name BaseDataReader: output stream of node.exe uniquely matches t1. No claim that t1 waits for EDT.

Uncommitted;572 pre-existing tracked changes preserved. Research43be46f995a0f5c49e905c002a404efaccdd3b2a unchanged;no additional reading. No production patch or IDE runtime experiment. Next: inspect the four waiting owners' dependencies; monitor ownership alone does not prove a cycle. S1/4746 unchanged.
