# 当前重写测试（2026-09-26）

S1 集成测试也在 test_repair_entry.py；先构建 S1 并设置 Q1_CLASSPATH，命令见 ../README.md。
2026-09-26：全部10项通过；未设置 classpath 时3项 Kotlin 集成测试显式跳过。

活动入口测试：`test_repair_entry.py`，使用真实 Finder 第2行JSON样例，并测试拒收和CLI行为。
从 tools/edt-freeze-finder 运行：`python -B repair/tests/test_repair_entry.py`。
本次不运行旧的test_*.py全目录发现：旧测试依赖已清空的历史实现。以下保留为历史说明，不代表当前测试命令。

---
# Repair tests

This directory is the single root for active script-level Repair tests:

- `test_*.py`: Python contract, routing, admission, and adapter tests.
- `test_*.ps1`: PowerShell tests for the ActionToolbar research utilities.
- `p0_test_baseline.py` and `_repair_test_bootstrap.py`: shared test-only baseline and import setup.
Fixtures remain beside the production component that owns them. Historical evidence bundles,
frozen source snapshots, recorded logs, and archived test commands are not active test sources
and are intentionally left in their original evidence directories.

Kotlin/JPS tests remain under `../read-write-lock/module/testSrc` because IntelliJ's generated
Bazel target requires the test source root to stay inside that registered module.

Run the Python suite from the repository root with:

```powershell
& out/edt-freeze-finder/layout-python/python.exe -B -X utf8 -m unittest discover -s tools/edt-freeze-finder/repair/tests -p "test_*.py" -v
```

Run the Kotlin suite with:

```powershell
./tests.cmd --module intellij.tools.readWriteLock.repair.tests --test org.jetbrains.research.lockrepair.*Test
```
