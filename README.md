# IntelliJ UI Freeze Finder and Repair

Current standalone snapshot of the rewritten Finder and Repair pipeline.

- `finder/main`: real thread-stack workbook input, source location and call-site evidence.
- `repair/main`: Finder intake and Kotlin Q1/Q2 multi-label candidate classifiers.
- Q3/Q4/Q5 are placeholders. Classification is not an automatic repair.
- Historical backups, old pipelines, raw workbook and large generated outputs are excluded.

## Run

Install Python dependencies with `python -m pip install -r finder/main/requirements.txt`.
Run `python finder/main/find_sources.py --help` and `python repair/main/python/repair.py --help`.
Supply your own workbook and IntelliJ source checkout; source mapping does not bundle IntelliJ.
Build both classifiers using `repair/main/scripts/build-q1.ps1` (Java and PowerShell required).
The script retains its historical filename and emits a jar containing Q1 and Q2.
`build-s1.ps1` is a historical script; S1 is not an active repair implementation in this snapshot.

## Tests

```powershell
python -m unittest discover -s finder/Test -p test_*.py
python -m unittest discover -s repair/tests -p test_*.py
```

Set `Q1_CLASSPATH` to the generated `classpath.txt` contents to enable Kotlin integration tests.
The validation reports describe the original 2026-09-26 checkout and dataset, not a new production performance result.
Some lane documentation preserves original machine paths and historical report links.

## Export validation (2026-09-26)

Repair: 15 tests passed with the compiled Q1/Q2 classpath. Finder: the available interpreter has an incompatible tree-sitter version; its 19-test run had 1 failure and 11 errors. Installing the pinned requirements is required before rerunning Finder tests. This export does not claim a new passing Finder run.
