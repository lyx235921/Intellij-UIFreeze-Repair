# EDT sleep 核验（2026-09-29）

范围：保存的 full-repair-20260928/finder.jsonl，排除任一线程含 com.huawei.* 的记录；31 行 EDT sleep，分3组。按行计数，不是独立根因数。仅堆栈/源码审查，未生成补丁或测量性能。研究远端43be46f995a0f5c49e905c002a404efaccdd3b2a未变化。

## 1. 版本与源码

堆栈给出 JBR java.base@25.0.2，但不足以定位完整IDE/JBR构建及应用修改版本。下述当前源码可解释候选语义，不能冒充历史二进制的精确匹配源码。

| 组 | 行号 | 当前源码/版本证据 |
|---|---|---|
| MTLRenderQueue.flushNow（14） | 181、356、2909–2920 | com.sun.java2d.metal.MTLRenderQueue；仓库文件检索和本地Windows JBR src.zip均未找到对应文件；Windows源码包缺失不能证明其他平台不存在。栈出现flushNow:19 → flushBuffer:26 → testFreeze:31，随后有省略帧。 |
| UIFreezeAction.actionPerformed（3） | 2906–2908 | platform/platform-impl/internal/src/com/intellij/internal/UIFreezeAction.kt:19–32；sleep行30与栈一致，完整运行版本未验证。 |
| SuvorovProgress.sleep（14） | 2921–2924、4938–4947 | platform/platform-impl/src/com/intellij/openapi/progress/util/SuvorovProgress.kt:244–290；历史sleep:271，当前:289，有行号漂移。 |

## 2. 人为延迟能否删除

UIFreezeAction 当前源码：用户确认对话框后执行 Thread.sleep(seconds * 1_000L)，默认15秒，输入范围1–300秒；无休眠循环，时间到返回，未在此捕获InterruptedException。实际这3行选择的时长未知。

这是明确的内部“UI Freeze”测试动作。删除sleep会破坏制造冻结的测试用途；应标为有意测试冻结，避免当成普通业务修复样本。若用户另外授权停用测试功能，可移除该动作/触发入口，不在通用修复器里无条件删sleep。本轮未改过滤政策。

MTL组的testFreeze名称是测试路径线索，不足以证明sleep属于无用调试代码。休眠参数、循环和退出条件均UNKNOWN；需对应测试类/构建源码，才能决定删除。不能把该包误认为已经核实的标准JDK Metal实现。

## 3. 重试/节流

SuvorovProgress当前sleep为Thread.sleep(0, 100_000)，请求0.1ms，不是实测耗时或等待总上限。showPotemkinProgress每轮派发invocation事件、progress.interact、处理eternalStealer事件，然后sleep；退出条件为awaitedValue.isCompleted。finally负责进度窗口清理。注释明确避免过度触碰progress；属于等待循环中的节流，并非已证实的失败重试。

不可直接删除：可能造成忙轮询，仍然要等Deferred完成。也不能局部替换为invokeLater后直接返回：上层同步许可获取契约尚未完成。可研究事件唤醒代替定时轮询，但需保留完成通知、事件处理、生命周期及同步契约，且先确认节流确实是性能瓶颈。

## 4. 等待初始化还是其他结果

当前ApplicationImpl.java:1462–1467在postInit注册setLockAcquisitionInterceptor，调用dispatchEventsUntilComputationCompletes。栈中postInit lambda不代表正在等待初始化；真实栈继续显示RunSuspend.await → acquireWriteIntentPermit → runWriteIntentReadAction。

因此该组下一步应分析写意图许可为何迟迟不可用，而不是套用初始化修复。4938、4939、4941、4942、4945–4947共7行后台栈顶为DefaultInMemoryInvertedNameIndex.deleteDataInner；4940为CopyrightManagerDocumentListener.after；4944为Object.clone/MemberName.clone；4943顶部省略。上述后台栈是后续调查线索，不单凭同一快照认定持有者/根因。2921–2924没有后台线程栈，无法定位生产者或持有者。

## 结论与下一证据门槛

- 3行：当前源码证实内部人为冻结用途，保留测试语义，不能计为已修业务缺陷。
- 14行MTL：SOURCE_VERSION_UNRESOLVED，不能决定删sleep。
- 14行Suvorov：当前实现为许可等待中的事件泵节流，直接删sleep不是根因修复；需要许可持有者及长工作证据。
- 0个生产补丁，0次运行修复验证。未证实任何一组为重试退避或初始化等待。

复核方式：逐条读取5891条保存的Finder JSONL，先以包边界排除华为帧，再选is_ui_thread且含java.lang.Thread.sleep*的线程，以首个非Thread/TimeUnit.sleep帧分组；分组14+3+14=31。读取上述当前源码，并检索MTLRenderQueue文件；本轮不修改生产代码，不运行行为测试。
