# 与老师讨论：P3 被拒绝的真实案例——第 424 行

日期：2026-09-28。本文采用最新 Java/Kotlin AST 分析结果，替代此前“四项全部 FAIL”的旧说法。

## 讨论结论

第 424 行进入 Repair 后，后台发送方候选 t1 的 P3 结果为 `REJECTED_CONTRACT`。

**被拒绝的是“直接把同步调度替换为异步投递”这一候选变换，不是证明该 bug 不可能修复。** 当前没有生成补丁，也没有验证真实卡顿改善。

## 案例中的调用关系

Finder 已有后台线程栈，Repair 提取了以下发送方及调用方上下文：

```text
RefreshSessionImpl.doFireEvents
  → fireEventsInWriteAction
  → invokeOnEdt
  → InternalThreading.invokeAndWaitWithTransferredWriteAction
  → 写操作转移与同步等待
```

提取结果包含当前源码及哈希校验。发送方与具体冻结 EDT 任务的对象级对应关系尚未建立；当前源码与历史运行版本的身份也未完全确认。

## 四项条件的实际输出

| 条件 | 最新结果 | 解释 |
| --- | --- | --- |
| 不依赖同步完成 | NEEDS_ADAPTATION | 调度后还有事件处理语句，需要确认并保持完成顺序 |
| 保持锁与执行上下文 | FAIL | 使用阻塞式写操作转移协议，不能直接替换为普通异步投递 |
| 生命周期与数据有效 | NEEDS_ADAPTATION | 使用明确限制存活作用域的上下文捕获；回调对象和数据仍需进一步分析 |
| 保持异常处理 | NEEDS_ADAPTATION | 存在同步异常重抛及 try/finally，需要重新安排异步失败和清理路径 |

`NEEDS_ADAPTATION` 表示发现需处理的结构或依赖，不代表已经找到可行改法。`FAIL` 针对当前直接替换方案。未分析清楚的事实不能因没有发现冲突而当成 PASS。

## 关键源码示例

以下片段来自 Repair 保存的当前源码上下文，省略无关代码，不是可直接应用的补丁。

### 1. 通知后还有事件处理

`RefreshSessionImpl.kt`，约 254 行：

```kotlin
invokeOnEdt {
  manager.fireBeforeRefreshStart(this.isAsynchronous)
}
try {
  AsyncEventSupport.processEventsFromRefresh(events, appliers, excludeAsyncListeners)
}
// catch 分支省略
finally {
  invokeOnEdt {
    try {
      manager.fireAfterRefreshFinish(this.isAsynchronous)
    }
    finally {
      myFinishRunnable?.run()
    }
  }
}
```

同步通知改为延后投递后，事件处理可能先于开始通知执行，结束通知和完成回调的时机也会变化。分析器自动提取了后续语句，但尚未完整证明所有回调副作用和业务顺序。

### 2. 它不是普通的无锁 UI 通知

`appImpl.kt`，约 216 行：

```kotlin
lock.transferWriteActionAndBlock({ toRun: RunnableWithTransferredWriteAction ->
  val event = TransferredWriteActionEvent(toRun)
  try {
    IdeEventQueue.getInstance().doPostEvent(event, true)
    event.blockingWait()
  }
  catch (e: InterruptedException) {
    exceptionRef.set(e)
  }
}, capturedRunnable)
```

此处依赖写操作转移和等待协议。直接删除等待或改用普通 invokeLater，不能证明执行时仍有正确的写操作上下文，因此当前变换被拒绝。这是基于已知平台协议的检查，不是通用锁语义证明。

### 3. 捕获上下文具有作用域限制

同一方法约 204 行：

```kotlin
val capturedRunnable =
  AppScheduledExecutorService.captureContextCancellationForRunnableThatDoesNotOutliveContextScope {
    // 执行原任务并收集异常
  }
```

若发送方提前返回，任务可能超出原作用域。是否改用独立任务生命周期、怎样关联取消，都需要进一步设计。

### 4. 异常原来会回到同步发送方

同一方法约 226 行：

```kotlin
exceptionRef.get()?.let { throw it }
```

异步任务尚未完成时，发送方无法在此取得后来才发生的异常。需要确定失败反馈、取消和清理机制，不能仅保持这一行不变。

## 当前分析器能做什么、不能做什么

- 已实现：解析 Java/Kotlin 方法片段，提取调用、回调、后续语句、部分变量写入/引用、锁作用域和异常结构；输出源码位置、哈希及判定证据。
- 已实现：识别该写操作转移协议不适合直接异步替换。
- 尚未完成：通用跨方法副作用、别名、捕获对象生命周期和任务对应关系证明，以及自动判定四项全部 PASS。
- “保守”意味着证据不足保持 UNKNOWN；没有检测到危险不等于已经证明安全。
- 当前没有自动构造配套改造，也没有生成本例修复补丁。

## 建议与老师讨论的问题

1. P3 的研究范围是“直接替换同步投递”，还是允许同时重构刷新事务、事件顺序和锁管理？
2. 对写锁转移案例，应作为当前 P3 模板的排除条件，还是单独建立更复杂的修复模板？
3. NEEDS_ADAPTATION 应作为人工审查出口，还是继续驱动配套代码变换？需要什么证据才能放行？
4. 是否先选择不涉及写锁转移、任务和消费者明确的真实案例，建立成功的 P3 正例？

## 实验与证据位置

最新全量回放：5891 行接收成功，1363 行 Q2，343 个后台发送方候选。343 个候选均发现写操作转移冲突，直接替换通过 0 个；不表示所有更大范围的异步重构都不可行。

工作目录：`D:\intellij-community-master\tools\edt-freeze-finder`。

- 最新逐行输出：`out/edt-freeze-finder/s2-p3-analysis-20260928/repair-java-kotlin.jsonl`。
- 查找 `q2.record_id = workbook-row-424`，后台 `thread_id = t1`，策略 `P3_ASYNC_DISPATCH`。
- 汇总：同目录 `summary-java-kotlin.json`。
- 构造与测试报告：`repair/docs/S2-P3-AST-ANALYSIS-2026-09-28.md`。
- 源码根目录：`D:\intellij-community-master`。
- 发送方源码：`platform/platform-impl/src/com/intellij/openapi/application/impl/appImpl.kt`。
- 刷新源码：`platform/platform-impl/src/com/intellij/openapi/vfs/newvfs/RefreshSessionImpl.kt`。

本文只整理已有结果，未新增实验或修改生产源码。
