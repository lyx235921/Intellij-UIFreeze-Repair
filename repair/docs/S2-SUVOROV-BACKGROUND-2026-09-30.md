# Suvorov 后台工作核验

2026-09-30，源码/保存堆栈审查，未改生产代码、未运行性能实验、未生成补丁。输入为full-repair-20260928/finder.jsonl，按当前华为整条排除政策筛选。历史构建身份和实际工作量仍未知。

## 结果

14行中4行（2921–2924）仅有EDT栈，不能定位后台任务。另10行（4938–4947）具有后台栈。

| 行 | 后台工作 | 缩短方向与限制 |
|---|---|---|
| 4938、4939、4941、4942、4945–4947 | 名称索引deleteDataInner，递归VFS删除 | 最强算法优化候选：数组桶线性查找/搬移，连续删除同名桶可能累计O(n²)。实际桶大小和耗时未测。当前源码已有大桶哈希集合优化，不重复实现。 |
| 4940 | CopyrightManagerDocumentListener.after | 当前源码对refresh事件直接continue；不能从栈顶推断是昂贵版权计算。先测事件数量/回调耗时，不直接异步化。 |
| 4943 | VfsData.invalidateFile / invalidateSubtree | 栈顶两帧省略；当前源码更新失效状态并将id加入清理队列。不能确认热点；提前/延后失效会影响删除可见性。 |
| 4944 | StringConcatFactory / MethodHandles / Object.clone，调用自RefreshSessionImpl.doFireEvents | 当前doFireEvents在写动作中构造慢刷新日志；有将日志格式化移出临界区的候选，但需保存稳定快照并核对历史行号。栈不能量化链接开销，更不能证明这是此前整个长刷新原因。 |

## 许可关联证据

EDT路径：SuvorovProgress → RunSuspend.await → acquireWriteIntentPermit → runWriteIntentReadAction。
4938后台路径：deleteDataInner → updateFileName → markAsDeletedRecursively → applyDeletions → processEventsFromRefresh → doFireEvents → fireEventsInBackgroundWriteAction → PlatformReadWriteActionSupport → proceedWithSuspendWriteLockAcquisitionFromWriteIntent。

当前NestedLocksThreadingSupport.kt:1144起说明write action先获取write-intent再升级write，以保持原子性；RefreshSessionImpl.doFireEvents标注RequiresWriteLock；索引updateFileName另持有rwLock.writeLock。故后台确实有在写动作内处理VFS删除的路径证据，不再仅凭线程名判断。注意索引内部rwLock不是EDT栈直接等待的许可；快照没有同一许可对象ID，历史锁层级和精确运行身份未建立运行时证明。

## 当前代码与推荐

DefaultInMemoryInvertedNameIndex.java:109起updateFileName在内部写锁中执行删除。小桶deleteDataInner扫描数组并搬移；updateDataInner在桶元素超过128后转IntLinkedOpenHashSet，deleteDataInner优先indexed.remove并在剩2个元素时降级。这是本轮前已存在的工作树修改，不能将其存在算成本轮完成修复或实际性能验证。

FSRecordsImpl.java:561起先收集子树，再自底向上逐文件标记删除并更新索引。索引和VFS提交必须保持一致，不建议把这些可变状态写入简单移出锁；优先对同名大桶删除机制做定向行为/性能验证。分批释放外层写许可会暴露部分提交，需额外设计事件顺序/原子性契约。

CopyrightManager.kt:300–313跳过refresh事件，仅对非refresh create/move收集路径并注册文档监听。VfsData.java:425起失效和清理入队；RefreshSessionImpl.kt:314起在fireEventsInWriteAction完成后统计耗时、构造慢日志。以上均是当前源码，历史精确实现未认证。

## 为什么仍不删除EDT sleep

SuvorovProgress.showPotemkinProgress的sleep请求0.1ms，用于事件泵节流；Deferred完成即退出循环。缩短后台写动作会减少等待循环持续时间，可能避免达到进度显示门槛，但不能保证所有负载都不进入等待。无条件删除会在仍需等待时增加轮询。正确目标是降低许可等待时间，保留节流；取消整个同步等待需更大范围异步契约改造。

下一步：优先4938组验证现有大桶实现相对旧数组实现的删除行为、写动作持续时间和EDT响应；尚未运行，不能报告加速倍数或已修复行数。本轮只读诊断不恢复S1/历史实验计划。
