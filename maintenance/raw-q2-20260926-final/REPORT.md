# 真实堆栈 Q2 候选全量盘点（2026-09-26）

直接读取 `D:/intellij-community-master/intellij底座问题堆栈-1.xlsx` 的“问题线程堆栈”工作表；不运行 Finder/Repair。5891 条记录各有一个 AWT-EventQueue UI 线程。跨单元格堆栈直接拼接，保留 Excel 行号、原始 UI 栈、帧编号、方法全名和整条记录哈希。计数单位为记录，不是出现次数列的加权次数。

结论：当前等待路径支持 **1363 条 Q2 候选**，其中 **17 条明确测试路径**，扣除后 **1346 条**。这是同步等待机制候选数量，不是确认根因数量，也不宣称覆盖缺失栈顶或采样时正在执行回调的潜在等待问题。Q2 分类器尚未实现。

## 建议的二级类别

| 类别 | 问题候选 | 记录数 | 匹配路径（省略包名） | Excel 示例行 |
|---|---|---:|---|---|
| Q2.1 | 同步等待 Future / Promise 结果 | 526 | FutureTask.get/awaitDone → ProgressIndicatorUtils.awaitWithCheckCanceled（516）；SafeFileOutputStream.waitForBackup（5）；数据库命令 executeBmCommandsAndCollectResults（2）；CompletableFuture.get → AsyncPromise.get/blockingGet（3） | 357、2925、2978、3253 |
| Q2.2 | 协程桥接导致调用线程同步等待 | 34 | BlockingCoroutine.joinBlocking/runBlocking；15 条直接 park 等待，19 条通过 waitBlockingAndPumpEdt 嵌套事件循环等待 | 194、393、3236 |
| Q2.3 | 进度／模态任务的同步等待与事件泵轮询 | 672 | EventStealer.waitForPing（338）；EternalEventStealer.dispatchExistingEvent（298）；EventStealer.dispatchEvents（2）；waitBlockingAndPumpEdt（19）；runWithModalProgressBlockingInternal（1）；SuvorovProgress.sleep（14） | 43、359、194、2921、3514 |
| Q2.4 | 跨线程调度的队列交接等待 | 33 | LinkedBlockingQueue.poll → AltEdtDispatcher.runOwnQueueBlockingAndSwitchBackToEDT | 3095、3096、3104 |
| Q2.5 | 等待渲染、工具包或图像任务完成 | 100 | Object.wait → MTLRenderQueue$QueueFlusher.flushNow（71）；LinkedBlockingQueue.take → AWTThreading.execute/executeWaitToolkit（27）；MediaTracker.waitForID → ImageIcon.loadImage（2） | 6、3284、3251 |
| Q2.6 | UI 线程显式休眠／延时轮询 | 31 | Thread.sleep/sleepNanos0；SuvorovProgress.sleep（14），MTLRenderQueue.testFreeze 路径（14），UIFreezeAction.actionPerformed（3） | 2921、181、2906 |

类别合计 1396，去重 1363。19 条同时属于 Q2.2/Q2.3，14 条同时属于 Q2.3/Q2.6。17 条测试记录均在 Q2.6。匹配不是仅查找任意深度的 park 或 get：先确认栈顶是等待，再结合最近的非 JDK 同步调用者和特定上下文。Q2.5 不意味着应该迁移绘制本身。

## 完整覆盖与边界

| 审核结果 | 记录数 |
|---|---:|
| Q2 当前同步等待候选 | 1363 |
| 普通 EventQueue.getNextEvent 等待，无任务等待上下文 | 387 |
| 明确 ReentrantLock / ReadWriteLock / StampedLock 获取路径 | 49 |
| BLOCKED 监视器阻塞线索 | 110 |
| BLOCKED + ProcessImpl.create，机制待定 | 7 |
| 栈顶缺失，不能判断当前操作 | 63 |
| 当前栈顶没有同步等待证据 | 3912 |
| 总计 | 5891 |

Q2 候选状态：WAITING 124、TIMED_WAITING 1235、RUNNABLE 4。RUNNABLE 仍可能有 Object.wait0/Unsafe.park 栈顶，因此不能仅按 state 分类。普通事件队列等待不能解释原事件的卡顿，但不否定原记录确实来自卡顿现场。

**Q2/Q4 可交叉**：Q2.3 中 523 条出现 acquireWriteIntentPermit 上下文。因此它们支持“当前同步等待机制”，不能据此断言最终根因不是锁竞争。事件泵等待期间可能继续分发部分事件，也不能称为完全停止处理所有 UI 事件。后续 Q4 可复用这些记录，不应强制互斥。

## 复现与验证

在 edt-freeze-finder 目录运行（输出目录必须尚不存在）：

```powershell
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe maintenance/audit_raw_q2.py --input D:/intellij-community-master/intellij底座问题堆栈-1.xlsx --output maintenance/raw-q2-20260926-final
```

本次命令 exit 0。5891 条行号、状态、全帧方法序列与此前独立原表提取逐条一致。边界断言通过：13 普通事件等待；194 双类别；3514 模态任务；5804 StampedLock；1026 RUNNABLE 但 Object.wait0；181/2906 测试标记。所有分区计数合计 5891，未归类等待 0；63 条栈顶不全仍保持未知。

- `summary.json`：工作簿 SHA256、完整方法全名 → 全部行号、类别 → 全部行号、分类规则及统计。
- `candidates.jsonl`：1363 条候选完整 UI 栈及命中字段。
- `rows.jsonl`：5891 条完整审核结果，包含未纳入记录及原因。
- `../audit_raw_q2.py`：独立盘点脚本，规则用于本批数据研究，不是生产 Q2 分类器。

研究仓库本轮检查 HEAD 仍为 `83a21329f4f811fca1b5a4a555eb6504f2ff4d78`；无新增文献阅读，历史未读保持未读。生产修复继续暂停。
