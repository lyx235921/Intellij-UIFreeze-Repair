# Finder / Repair publication review — 2026-10-01

Target: lyx235921/Intellij-UIFreeze-Repair, branch main. Base: `9feb56991f2870e3b1d9732f11f3a0a3e391b610`. Engineering source checkpoint: `11cd0b6f5242369b47f262a5de247bc71b037ae2`.

The target is a standalone export with a separate Git history. This update preserves its existing files and root layout and adds the current Finder/Repair sources, selected tests/fixtures and relevant dated reports. It does not upload the engineering repository history, IntelliJ production checkout, raw workbook, large generated outputs or untracked raw datasets. All copied source hashes are recorded in PUBLICATION-MANIFEST.json; the portable intake test retains the target's existing 75-method fixture rather than an untracked rows.jsonl dependency.

## Reviewed changes

| Component | Implemented or recorded | Remaining boundary |
|---|---|---|
| Finder | Real workbook intake, source locations, call-expression evidence, whole-record Huawei exclusion | Kotlin locations are candidates; no full filtered source/Repair rerun |
| Repair intake/Q1/Q2 | Validated evidence intake, 75-method Q1/categories/UI gates, Q2 waits | Candidate classification is not root-cause or repair certification |
| S1 | Five-layer contexts, P1/P2/P3 selection, source/hash-bound candidate templates, loading/storage/regex handling, explicit source-unavailable skip | No blanket safe relocation; row4746 sync-refresh candidate is rejected |
| S2 | Method extraction/strategy assessment, waiting-object labels, EDT monitor-entry and reported-owner association, sender extraction, conservative Java/Kotlin P3 AST checks | Objects/owners are reported evidence; cycles and task identity are not generally proven; P3 has no automatic all-PASS proof |
| awaitWithCheckCanceled | Dedicated synchronous-consumer contract assessment | BLOCKED_CONTRACT, no local callback rewrite patch |
| Full historical run | Report records 5,891 accepted and 57 rows selecting five distinct candidate patches before Huawei exclusion | Not 57 successful IDE repairs; not repeated in this publication |
| row4938 | Controlled index experiments plus one real-platform paired run; event/deletion/index checks passed | Complete entry 4,821.9573→3,875.5688 ms; IMPROVED_NOT_ELIMINATED. Not an exact historical BGT incident replay |

The active investigation remains [S2-ROW4938-RESIDUAL-2026-09-30.md](repair/docs/S2-ROW4938-RESIDUAL-2026-09-30.md): matched logging control and EDT+BGT listener timing. Retain sleep throttling; S1/4746 remain paused. Reports retain original dates, commands, paths and historical “uncommitted” labels.

## Fresh verification

Engineering checkout current-source compilation:

```powershell
& tools/edt-freeze-finder/repair/main/scripts/build-q1.ps1 -OutputDirectory C:/Users/Administrator/AppData/Local/Temp/repair-q1-build -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
```

Result: exit 0. Compiles Q1/Q2 and the current S1/S2 extraction, selection, candidate and contract-check sources. Compiler emitted deprecated-Unsafe warnings. Every exported repair/main and finder/main file is byte-identical to the pinned engineering checkpoint. The compiled classpath was reused for the export checks after verifying identical sources.

From this standalone root, after installing pinned requirements:

```powershell
New-Item -ItemType Directory -Force out
$env:Q1_CLASSPATH = (Get-Content C:/Users/Administrator/AppData/Local/Temp/repair-q1-build/classpath.txt -Raw).Trim()
python -B -X utf8 run_publication_checks.py finder
python -B -X utf8 run_publication_checks.py repair
```

In this environment `python` was the existing portable interpreter `D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe`; Finder used the existing pinned dependency overlay `C:/Users/Administrator/AppData/Local/Temp/finder-source-deps-wheel-20260926`. Exact Finder invocation from the engineering root:

```powershell
& out/edt-freeze-finder/layout-python/python.exe -B -X utf8 -c "import sys,runpy;sys.path.insert(0,'C:/Users/Administrator/AppData/Local/Temp/finder-source-deps-wheel-20260926');sys.argv=['run_publication_checks.py','finder'];runpy.run_path('out/edt-freeze-finder/github-publication-20261001/run_publication_checks.py',run_name='__main__')"
```

Results: Finder 20 tests, 0 failures/errors/skips, exit 0 (0.855 s); Repair 36 tests, 0 failures/errors/skips, exit 0 (56.362 s). The same 36 Repair checks also passed in the engineering layout before export (58.944 s). These are targeted checks, not a full-suite or new real-IDE performance result. The runner explicitly requires Q1_CLASSPATH for Repair and rejects skipped integrations.

The first export attempt had two missing-data errors: intake referenced untracked raw rows; the paired row4746 experiment required an excluded historical proposal.json. The intake fixture path was restored to the target repository's existing portable baseline and the 36 checks reran successfully. `test_p1_effectiveness.py` remains available for reproducing the historical experiment with its required out/edt-freeze-finder/p1-row4746-patch-20260927 evidence; it is outside portable validation. `finder/Test/test_source_locator_real.py` requires the real workbook/IntelliJ checkout. Legacy tests importing retired Python modules remain excluded; the engineering checkout's legacy intake import blocker is not repaired here.

No new production source edit, historical incident replay or freeze-improvement measurement was performed. Research preflight confirmed unchanged main revision `1864865807395e0097f201685f699bdcd11c5b28`; previously unread literature was not used.

Whitespace validation: strict `git -c core.whitespace=cr-at-eol diff --check` for the exported change, with three preserved discussion reports checked separately allowing their Markdown two-space hard breaks, and one hash-bound lsp4intellij fixture checked separately allowing its original blank EOF. Original report/fixture bytes are retained rather than reformatted. The engineering working-tree `git diff --check` also passed.
