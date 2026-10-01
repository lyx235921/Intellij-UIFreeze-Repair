# 缺失业务源码：记录并继续

日期：2026-09-28。用户确认范围：当前卡顿点所需业务源码缺失则跳过，继续同一行其他卡顿点及后续行；已有可用上下文仍正常检查。

实现位于 `pool/extract_method.kt`、`pool/repair_selection.kt` 和 `main/python/repair.py`。

- 提取结果附带 Finder 的 `source_status`、`source_reason`、`source_file`，保留五层限制及原有定位状态。
- 统一选择器优先保留已有可生成候选的路径。没有候选且上下文明确包含 `SOURCE_FILE_NOT_FOUND` 时，返回 `SKIPPED_SOURCE_UNAVAILABLE`，附 `missing_source_contexts` 和继续／重试说明；其他命中继续循环。
- 无任何已定位上下文时直接跳过该命中的 P1/P3 前置检查；部分上下文存在时照常尝试受支持模板，未得到候选才记录源码缺口。存储／加载池的原始评估保留在结果内。
- 全部命中被跳过时记录状态为 `SKIPPED_SOURCE_UNAVAILABLE`；跳过与成功候选共存时为 `PARTIAL`。未更改 Q1 分类和计数，也不删除 Finder 输入。
- 缺源码不是策略失败，不启用 P3。`METHOD_NOT_FOUND`、歧义、源码哈希变化和缺帧不自动等同文件缺失。

## 验证

构建：`powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe`，exit 0。

设置 `Q1_CLASSPATH` 为 `$env:TEMP/repair-q1-build/classpath.txt` 内容后，使用既有 Python unittest 模块运行回归。30 项通过，0 失败／错误／跳过，32.472 秒。模块清单与结果保存于 `out/edt-freeze-finder/source-skip-20260928/tests.json`。复现命令：

```powershell
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -c "import sys,json,unittest; from pathlib import Path; sys.path.insert(0,'repair/tests'); modules=json.loads(Path('out/edt-freeze-finder/source-skip-20260928/tests.json').read_text())['modules']; result=unittest.TextTestRunner().run(unittest.TestLoader().loadTestsFromNames(modules)); sys.exit(not result.wasSuccessful())"
```
新增 CLI 测试覆盖：缺插件源码跳过、源码存在正常检查、方法未找到不误判、同记录混合命中及后续记录继续生成候选、原 Finder 对象不变。既有 JCEF 案例 1031 的预期从 PENDING 更新为显式缺源码跳过。

重新运行 Finder 获取真实行 4492、902、4238、1238，再按此顺序进入同一 Repair 进程：

```powershell
$cp=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/source-skip-20260928/ordered.jsonl --output out/edt-freeze-finder/source-skip-20260928/repair-final.jsonl --q1-classpath $cp --repair-selection
```

| 真实行号 | 选择结果 |
|---|---|
| 4492 | SKIPPED_SOURCE_UNAVAILABLE：Huawei 业务源码缺失 |
| 902 | CANDIDATE_SELECTED：通知准备候选 |
| 4238 | SKIPPED_SOURCE_UNAVAILABLE：当前源码树无 lsp4intellij 业务源码 |
| 1238 | CANDIDATE_SELECTED：徽标图像候选 |

Finder：4 records，73 LOCATED / 72 CANDIDATE / 8 AMBIGUOUS / 367 UNRESOLVED，index_errors 为空。Repair：4 accepted / 0 rejected，4 个跳过命中帧、2 条含跳过的记录。这证明跳过和继续控制流，不是新的真实 IDE 修复效果验证。

## 范围

这是业务源码可用性处理，不是插件安装检测或完整插件依赖发现。只依据当前 Finder 与五层提取证据；五层之外、合成方法或栈缺口导致的未知仍保留未知。不会因包名推断整个插件缺失，也不自动下载源码。

新增／更换插件源码后须重跑 Finder，才能刷新可用性；源码存在后仍要通过版本、前置条件和模板检查，不保证一定有补丁。专用 `--s1-*` 仍输出原始检查，显式跳过与批量跳过统计由 `--repair-selection` 提供。

本次未修改生产源码或恢复 4746；原始事故版本和真实 IDE 验证缺口不变。研究远端 HEAD `83a21329f4f811fca1b5a4a555eb6504f2ff4d78` 未变，无新增资料阅读。
