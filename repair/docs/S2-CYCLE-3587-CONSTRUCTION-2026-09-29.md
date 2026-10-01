# Row3587 cycle repair construction — partial

Implemented MonitorCycleRepair.kt and automatic `q2.monitor_cycle_repair` output. Although BLOCKED rows are not Q2 matches, the auxiliary assessment runs independently of that classification. This is a repair admission/entry selector, NOT a completed patch generator.

Recognized shape: reported EDT monitor owner, AWTTreeLock, unique non-UI owner, contiguous owner stack with Object.wait → EventQueue.invokeAndWait → Window.doDispose → Container.remove → ToolWindowImpl.setAvailable. Select the immediate business caller of setAvailable as the investigation/repair entry; no row-number binding. Queue identity remains unverified. Missing/ambiguous source cannot authorize a patch.

Row3587 selected entry: com.huawei.deveco.internal.betaclub.BetaClubProjectActivity.blockIssusReport. Finder reports SOURCE_FILE_NOT_FOUND for this method and execute. Result BLOCKED_SOURCE_UNAVAILABLE; generator NOT_IMPLEMENTED_PENDING_CALLER_CONTRACT;0 patches. Known absence of this plugin source was previously reported by the user; no repeated source request or guessed replacement.

Source audit: current platform/platform-impl/src/com/intellij/openapi/wm/impl/ToolWindowImpl.kt setAvailable checks toolWindowManager.assertIsEdt() before mutating availability. Therefore the candidate repair direction is moving the complete dependent UI operation to EDT BEFORE acquiring the tree monitor. Do not remove blockingWait in JDK Window disposal, do not globally weaken setAvailable, and do not enqueue halfway through the held-monitor region. Choice of asynchronous posting versus a suspending continuation depends on plugin caller result/ordering/exception/lifetime semantics, which cannot be determined without its source. No runnable patch skeleton masquerades as a repair.

Validation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_monitor_cycle_repair.py -v
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_wait_resource_evidence.py -v
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_q2_classifier.py -v
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/s2-cycle-3587-20260929/finder.jsonl --output out/edt-freeze-finder/s2-cycle-3587-20260929/repair.jsonl --q2-classpath $env:Q1_CLASSPATH
```

Build exit0;8 tests pass/0 skipped, including6 admission scenarios; four saved real rows accepted. Independent assertions confirm3587 source-blocked and3623/3643/3656 do not match this cycle pattern. No live reproduction or repair-effect validation. Worktree uncommitted;S1/4746 unchanged;remote research43be46f9 unchanged. Next prerequisite: actual plugin caller source, then choose valid threading boundary and generate/validate a patch. This remains incomplete construction rather than a successful repair.
