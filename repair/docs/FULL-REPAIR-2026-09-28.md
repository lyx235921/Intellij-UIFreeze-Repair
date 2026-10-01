# 真实堆栈全量 Finder → Repair 结果

日期：2026-09-28，当前工作区，未提交。**5,891 行全部完成处理，其中 57 行生成并选中候选补丁；5 份不同补丁全部通过 `git apply --check`。** 没有应用生产补丁，也没有逐行复现真实 IDE 卡顿。

## 统计口径与结果

每条 Excel 记录计一行；同一行多个命中／重复调用帧不重复计数，不按表中 occurrences 加权。

| 结果 | 去重行数 |
|---|---:|
| 输入／接收成功 | 5,891 |
| 不进入 Q1 候选 | 4,835 |
| Q1 候选 | 1,056 |
| 生成并选中候选补丁 | **57** |
| 全部命中因源码缺失而跳过 | 308 |
| 其余 PENDING，未生成候选 | 691 |
| Repair 拒绝输入 | 0 |

57 + 308 + 691 = 1,056。候选生成覆盖率为 Q1 的 **5.40%**，全部输入的 **0.97%**。
共有 316 行包含至少一个源码缺失跳过，其中 308 行全部跳过，另 8 行仍有其他待处理命中，归入 PENDING；两者不能相加重复计数。
实际有 83 个命中帧选中候选、604 个命中帧跳过，这些不是 bug 行数。

## 实际生成的五份补丁

| 方案 | 修改目标 | 覆盖行数 | 行号 |
|---|---|---:|---|
| P2 | `LocalFileSystemImpl.refreshWithoutFileWatcher` 异步刷新准备 | **49** | 207、1347–1349、3912–3920、3936、3995–3996、4080–4081、4088、4121–4124、4136、4170、4172–4174、4176、4235、4499–4517 |
| P2 | `AppIcon.Win7AppIcon._setOkBadge` 图像准备 | **5** | 1238、1779、1806、1812、1813 |
| P1 | Terminal AWT 监听器准备 | **1** | 890 |
| P1 | 错误通知对象准备 | **1** | 902 |
| P1 | Git 监听器准备 | **1** | 1007 |
| **合计** | **P1：3 行；P2：54 行** | **57** | 各组本次无行号重叠 |

相同补丁文本按 SHA256 去重：5 份。对每份在当前 `D:/intellij-community-master` 执行 `git apply --check`，5 次 exit 0；这仅证明补丁当前可应用，不等于目标 IDE 编译、行为或卡顿验证通过。

此次生成候选涉及 **12 个触发方法**。历史第 13 个 `Pattern.compile` 的参考候选没有纳入：本次使用当前工程源码树，未额外导入 lsp4intellij 参考源码，独立 `--s1-regex` 全量输出 `NO_SUPPORTED_METHOD`。
第 4746 行原重载生成器仍按用户要求暂停，未执行独立 `--s1-p1`，不计为正常补丁；该行仍经过普通分类／选择。P3 尚无生成器。

## 执行与核验

输入：`D:/intellij-community-master/intellij底座问题堆栈-1.xlsx` 的“问题线程堆栈”，Excel 第 2–5892 行。当前源码根目录：`D:/intellij-community-master`。没有加 `--row` 过滤。

产物目录：`out/edt-freeze-finder/full-repair-20260928/`：

- `finder.jsonl`、`repair.jsonl`：全量证据和结果，保留在本地。
- `summary.json`、`row-status.json`：完整计数、57 行清单、每行结果与补丁检查。
- `candidate-method-rows.json`：每个实际选中触发方法对应的行号。
- `patches/*.patch`：5 份不同补丁。
- `source-hashes.json`、`repair-run.json`、`repair.stderr`、`finder.log`：实现快照及执行记录。

Finder 使用既有固定 tree-sitter 依赖：

```python
import runpy, sys
sys.path[:0] = ['C:/Users/Administrator/AppData/Local/Temp/finder-source-deps-wheel-20260926', 'finder/main']
sys.argv = ['find_sources.py', '--workbook', 'D:/intellij-community-master/intellij底座问题堆栈-1.xlsx',
            '--source-root', 'D:/intellij-community-master',
            '--output', 'out/edt-freeze-finder/full-repair-20260928/finder.jsonl']
runpy.run_path('finder/main/find_sources.py', run_name='__main__')
```

由 `D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe` 执行。Finder 最终摘要：5,891 records，427,311 UNRESOLVED / 100,086 CANDIDATE / 69,232 LOCATED / 8,001 AMBIGUOUS，读 2,238 个源码文件，index_errors 为空。
PowerShell 的 stderr 重定向将正常 JSON 摘要包装为 NativeCommandError、外层返回 1，保留在 finder.log；因此不声称该 shell 命令 exit 0。已独立逐行解析整个输出，确认 5,891 条有效 JSON、行号恰为 2–5892 且无重复，并由 Repair 全部成功接收，未使用半截输出。

重新构建：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
```

构建 exit 0。随后通过 Python subprocess 将 stdout/stderr 直接保存到文件运行，Repair **exit 0，98.063 秒**，实际参数记录于 repair-run.json：

```powershell
$cp=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/full-repair-20260928/finder.jsonl --output out/edt-freeze-finder/full-repair-20260928/repair.jsonl --q1-classpath $cp --repair-selection --s1-regex
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe out/edt-freeze-finder/full-repair-20260928/summarize.py
```

输出使用排他创建，复跑须更换结果文件名。汇总断言：5,891 accepted；行号完全覆盖且唯一；有选中候选的行必有实际非空补丁；原始生成行集合与选中候选行集合均为相同的 57 行。没有仅凭方法名计为修复成功。

本次不改变生成器／分类器，也不重复上轮已通过的 30 项回归或宣称这些 57 行各自完成行为测试。下一证据门仍是具体候选在目标 IDE 中的编译、语义及卡顿改善验证。研究远端 HEAD83a21329 未变，无新增资料阅读。
