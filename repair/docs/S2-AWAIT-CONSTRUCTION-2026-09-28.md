# awaitWithCheckCanceled 修复器构造尝试

2026-09-28；结果：**PARTIAL / BLOCKED_CONTRACT**。已实现专项前置审查，未实现补丁生成器；不能计为已修好。

## 真实案例与定位

工作簿 `D:/intellij-community-master/intellij底座问题堆栈-1.xlsx`，问题线程堆栈，第357行。
真实UI线程为 TIMED_WAITING，等待链：

```text
EditorConfigEncodingCache.VfsListener.fileCreated
→ computeAndCacheEncoding → EditorConfigPropertiesService
→ VirtualDirectoryImpl.findChild
→ PersistentFSImpl.determineCaseSensitivity
→ LocalFileSystemImpl.fetchCaseSensitivity
→ DiskQueryRelay.accessDiskWithCheckCanceled
→ ProgressIndicatorUtils.awaitWithCheckCanceled → FutureTask.get → Unsafe.park
```

本次重新执行 Finder `--row 357`，然后执行 Repair `--s2-repair-selection`：1条接收、Q2.1。
五层提取规则未扩大：两个 await 重载帧歧义、DiskQueryRelay方法未定位；实际定位到
`LocalFileSystemImpl.java:412–415` 和 `PersistentFSImpl.java:2540–2552`，全文、SHA和行范围独立核对通过。
未把后续人工补读伪装为提取器自动获得的上下文。

## 必要源码补读与方案判断

- `platform/ide-core-impl/src/com/intellij/openapi/progress/util/ProgressIndicatorUtils.java:372`：当前Future重载委托到核心工具，与历史栈存在实现演进，不能宣称事故二进制一致。
- `platform/core-api/src/com/intellij/openapi/vfs/DiskQueryRelay.kt`：当前实现返回 `future.awaitWithCheckCanceled()`；不可取消上下文则直接 `function.apply(arg)`。只改Future等待还可能保留同步I/O分支。
- `LocalFileSystemImpl.fetchCaseSensitivity`：直接返回relay结果。
- `PersistentFSImpl.determineCaseSensitivity`：立即消费并返回实际大小写规则。
- `VirtualDirectoryImpl.findChild`：先更新大小写规则，再以该规则查找文件。`UNKNOWN`虽然是合法查询结果，但这并不证明把“慢查询”改成UNKNOWN不会影响查找行为。
- `EditorConfigEncodingCache.computeAndCacheEncoding`：写编码缓存并设置 `virtualFile.charset`；把整个事件简单延后有编码应用时序风险。

补读文件及哈希保存在 `supplemental-sources.json`。真实栈证明等待发生，不证明可任意改变上述返回值/完成顺序。

| 方案 | 此路径结论 |
|---|---|
| P1 BOUND_WAIT | 缺总等待预算和超时结果/异常处理策略；不擅自填50ms或默认值 |
| P2 ASYNC_CONTINUATION | 拒绝仅把局部等待改回调；必须先确定上层消费者的异步边界 |
| P3 ASYNC_DISPATCH | 这里是磁盘查询结果等待，不是BGT同步投递EDT |
| G1 FAIL_FAST_ON_EDT | 未建立禁止EDT调用的契约及调用方拒绝处理，不能直接抛异常 |

## 已实现部分

`pool/s2_sync_wait/AwaitWithCheckCanceledRepair.kt` 提供 `assess(operation)`，按真实路径及已核验的源码上下文识别同步返回依赖，不绑定Excel行号。
`repair_selection_S2` 自动调用审查；匹配时撤回P2推荐，标记 `BLOCKED_CONTRACT`，P2候选标记 `REJECTED_LOCAL_REWRITE`，输出下一证据门。
这只是局部改写的拒绝条件，不宣称上层P2重构不可能，也不宣称已实现通用修复器。

## 验证与复现

产物目录：`out/edt-freeze-finder/s2-await-20260928/`。

Finder通过既有Python依赖运行 `finder/main/find_sources.py --workbook <上述工作簿> --source-root D:/intellij-community-master --output out/edt-freeze-finder/s2-await-20260928/finder.jsonl --row 357`，exit0。依赖路径同全量报告；标准错误保留于finder.log。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_q2_classifier.py -v
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/s2-await-20260928/finder-await.jsonl --output out/edt-freeze-finder/s2-await-20260928/repair-await.jsonl --q2-classpath $env:Q1_CLASSPATH --s2-repair-selection
```

编译exit0，Q2/S2四项测试通过；既有11模块回归共33项通过、0跳过（tests.json）。使用本地编译脚本与Python回归，未完成目标IDE模块编译；既有repair iml缺口仍存在。

批量复用已有全量Finder证据，筛出方法名出现的517行：516条Q2均为BLOCKED_CONTRACT，1054行非Q2。四条同步业务路径：fetchCaseSensitivity271、getAttributes217、listWithAttributes26、contentsToByteArray2。每条均无补丁。原全量报告中的1324条P2建议属于修改前快照，本次仅重跑该方法子集。

没有候选补丁，因此没有补丁apply/生产行为/卡顿改善验证；现有S1测试打印的受控性能结果不能用于证明本例有效。
构造流程停在源码与前置条件阶段，尚需确定具体消费者的异步改写或明确的有界等待失败契约后才能实现生成器。
