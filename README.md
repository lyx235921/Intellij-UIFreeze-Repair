# IntelliJ UI Freeze Finder and Repair

Standalone research sources synchronized from the engineering checkout on 2026-10-01. Start with [PROGRESS.md](PROGRESS.md) for current status and the active evidence gate.

- `finder/main`: real thread-stack workbook input, source locations and call-site evidence; whole-record Huawei closed-source exclusion.
- `repair/main`: validated Finder intake, Q1/Q2 candidate classification, S1/S2 context extraction, strategy selection, source-bound candidate construction and conservative contract checks.
- `repair/docs`: construction reports, rejected candidates, controlled experiments and the bounded real-platform comparison.
- `finder/Test`, `repair/tests`: selected current tests and their fixtures. Retired-pipeline tests and backups are excluded.

Q3/Q4/Q5 remain placeholders. A classified candidate or generated patch is not a verified production repair. No patch is applied by publishing this repository. Raw workbooks, large generated outputs and IntelliJ production sources are excluded. [Publication manifest](PUBLICATION-MANIFEST.json) records source hashes and provenance.

## Run

Install Python dependencies with `python -m pip install -r finder/main/requirements.txt`. The tree-sitter pin matters.

```powershell
python finder/main/find_sources.py --help
python repair/main/python/repair.py --help
New-Item -ItemType Directory -Force out
./repair/main/scripts/build-q1.ps1 -OutputDirectory ./out/classifiers
$env:Q1_CLASSPATH = (Get-Content ./out/classifiers/classpath.txt -Raw).Trim()
```

Supply your own workbook and IntelliJ source checkout. The build script retains its historical filename and compiles Q1/Q2 plus the current S1/S2 sources. Java/JDK, PowerShell and access to Maven Central are required. `build-s1.ps1` is retained as a historical script; use `build-q1.ps1` for the current pipeline. See the lane READMEs for feature flags and original commands; dated claims and absolute paths refer to their recorded experiment environments.

## Validation and limits

Use the targeted test commands in [PUBLICATION-2026-10-01.md](PUBLICATION-2026-10-01.md). `finder/Test/test_source_locator_real.py` requires the original real workbook and IntelliJ checkout and is not part of portable validation. Do not interpret full directory discovery or historical module instructions as a new full-suite certification.

The fresh publication tests cover source-location/filtering, intake, classification, strategy selection, generated-code behavior and conservative rejection. Actual IDE validation is separately bounded: the single row4938 platform comparison improved latency but left about 3.88 seconds of delay; row4746's controlled comparison exposes a sync-refresh regression. awaitWithCheckCanceled and P3 safety-proof obligations remain unresolved. The [current progress entry](PROGRESS.md) preserves these distinctions.
