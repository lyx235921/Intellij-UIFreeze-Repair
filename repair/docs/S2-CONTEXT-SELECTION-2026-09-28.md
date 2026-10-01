# S2 方法提取与修复方案初选

2026-09-28：完成提取和条件性方案选择；按用户要求停在此处，未实现补丁生成器。

## 接口

- `main/kotlin/src/pool/s2_sync_wait/extract_method_S2.kt`：`ExtractMethodS2.extract(finder, classification, root)`。
- `main/kotlin/src/pool/s2_sync_wait/repair_selection_S2.kt`：`RepairSelectionS2.select(context)`。
- 包名：`org.jetbrains.research.lockrepair.pool.s2`。
- CLI：`--s2-extract-method` 仅提取；`--s2-repair-selection` 自动提取并初选。二者均要求 `--q2-classpath`；可用 `--source-root` 覆盖源码根目录。
- 输出位于 Repair 记录的 `q2.method_context_s2` 和 `q2.repair_selection_s2`，schema 分别为 `repair-s2-method-context/1`、`repair-s2-selection/1`。

## 提取规则

从 Q2 已识别线程的真实调用栈开始，按线程合并多个分类证据帧，避免把同一次等待重复当成不同卡顿点。最多提取五层非 JDK 方法；缺失层也计数，栈断裂停止。保留方法全文、行号、文件路径、Finder 候选与缺失原因、分类证据及调用点。

读取源码前核对路径范围、SHA-256 和方法行范围。当前源码一致不代表与历史运行二进制一致。缺源码且无可用上下文时跳过，继续处理后续记录；歧义、源码变化和不完整路径保留为证据不足。

## 方案语义

| 方案 | 当前初选 | 仍需确认 |
| --- | --- | --- |
| P1 BOUND_WAIT | Q2.1–Q2.5 等待类的备选 | 整体是否无界、超时 API、业务时限、失败/取消/清理策略 |
| P2 ASYNC_CONTINUATION | 等待类有可用上下文时优先建议 | 完成通知句柄、返回值和消费者可拆分、回调线程、生命周期、锁和顺序 |
| P3 ASYNC_DISPATCH | 需要明确 BGT 同步投递 EDT | 同步完成依赖、模态、事件顺序；目前 Q2 仅分类 UI 线程，不能凭 Q2.4 推出该条件 |
| G1 FAIL_FAST_ON_EDT | 独立防御性 Guard | 明确禁止 EDT 阻塞的契约、调用方处理拒绝、无部分副作用 |

当前是类型与可用源码驱动的**条件性初选**，并未自动证明语义安全或最优。`recommended_strategy` 是优先调查方案；`selected_strategy` 为空（JSON 序列化可能省略）。所有生成器为 `NOT_IMPLEMENTED`，`eligible_for_application=false`，不产生补丁。调用点名称不是类型解析结果；内层 `get(timeout)` 也不证明外层循环有界。Q2.6 单纯 sleep 没有自动映射到任务结果延续。测试注入路径跳过。

## 验证

编译（exit 0）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
```

真实样例重新经过 Finder：13、43、181、194、357、2925、2978、3095、3251、3253。Repair 命令（exit 0）：

```powershell
$cp=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/s2-context-20260928/finder.jsonl --output out/edt-freeze-finder/s2-context-20260928/repair.jsonl --q2-classpath $cp --s2-repair-selection
```

10 条接收、0 条拒绝；9 条 Q2。6 条 `CANDIDATES_RANKED`，2 条 `SKIPPED`（181 测试注入、2978 缺源码），1 条 `INSUFFICIENT_EVIDENCE`（3253），1 条 `NOT_APPLICABLE`（13）。独立核对 16 个提取方法片段的文件哈希及行范围，通过；全部无补丁。

证据目录：`out/edt-freeze-finder/s2-context-20260928/`，包含 finder.jsonl、finder.log、repair.jsonl、verification.json、tests.json。

测试命令：设置 `Q1_CLASSPATH` 为上述编译 classpath，运行 `python -m unittest discover -s repair/tests -p test_q2_classifier.py -v`，3 项通过。还通过 `unittest.TestLoader().loadTestsFromNames(modules)` 运行 `out/edt-freeze-finder/source-skip-20260928/tests.json` 中的 11 个回归模块，结果见本次 tests.json。覆盖五层限制、栈断裂、哈希变化、路径越界、缺源码续跑、歧义、非 UI、测试注入和原 Q2 分类不变。

本次未执行完整 5891 行测试，未实施生产修复或验证真实 IDE 卡顿改善。
