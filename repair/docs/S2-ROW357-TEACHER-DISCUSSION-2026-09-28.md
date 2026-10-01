# 与老师讨论：同步等待修复应当迁移到哪一层？

日期：2026-09-28  
案例：真实堆栈表第 357 行，EditorConfig / VFS 文件创建相关路径  
目标方法：`ProgressIndicatorUtils.awaitWithCheckCanceled`

## 1. 当前结论

真实堆栈证实 EDT 在等待 Future。当前源码核验表明，不能只把这个等待改成回调，也不能只把文件创建监听器中的编码计算放到后台：后续代码同步需要编码、BOM 和创建完成的文件。

在更上层采用“后台提前准备，准备完成后继续创建和消费结果”有设计上的可能性，但尚未确定该事故的原始创建调用方。因此当前状态是 **BLOCKED_CONTRACT（同步调用契约尚未解决）**，不是“P2 原理不可行”，也不是“已修复”。

本案例没有生成修复补丁，没有完成行为正确性或真实卡顿改善验证。

## 2. 问题背景与真实路径

这里的 P1/P2 指 Pool S2 的策略：

- S2 P1：BOUND_WAIT，有界等待，给同步等待设置时间上限。
- S2 P2：ASYNC_CONTINUATION，异步延续，等待结果的当前线程返回，结果完成后继续后续业务。
- 下文提到的“提前准备”属于 S1 P1 的思路，不是 S2 P1 超时等待。

第 357 行记录的线程为 `AWT-EventQueue-0`，状态为 `TIMED_WAITING`，关键调用链是：

```text
EditorConfigEncodingCache.VfsListener.fileCreated
  → computeAndCacheEncoding
  → EditorConfigPropertiesService.getProperties / relevantEditorConfigsFor
  → VirtualDirectoryImpl.findChild
  → 更新或确定目录大小写敏感性
  → LocalFileSystemImpl.fetchCaseSensitivity
  → DiskQueryRelay.accessDiskWithCheckCanceled
  → ProgressIndicatorUtils.awaitWithCheckCanceled
  → FutureTask.get → Unsafe.park
```

堆栈能证明当时 EDT 在此等待，不能单独给出等待持续时间、正常耗时分布和业务允许的超时时间。`TIMED_WAITING` 也不等于整个业务已经具有可接受的最大等待时长。

记录中还包含“转移写操作到 EDT”的事件分发。保存的数据只有该 EDT 线程，没有原始后台发送方的线程栈，不能据此确定是谁创建文件、创建完成后要做什么。

## 3. 核验到的三个关键约束

| 问题 | 当前源码证据 | 对修复的影响 |
| --- | --- | --- |
| 谁消费编码？ | `ConfigEncodingManager.getEncoding` 读取编码缓存，缺失时返回 null，平台继续查找其他编码设置；BOM 提供器通过 `getUseUtf8Bom` 查询，缓存未命中会同步计算 | 仅延迟填缓存，可能改变编码选择，也可能把阻塞转移到 BOM 查询 |
| 能否延后消费者？ | `PersistentFSImpl.createChildFile` 在创建事件完成后检查 charset/BOM，然后返回文件；`VirtualFile.createChildData` 要求写锁；`PsiDirectoryImpl.createFile` 随即取得并返回 PSI | 当前接口没有 pending 状态，不能先返回“创建完成”再补编码/BOM |
| 后台结果过期怎么办？ | 已有配置缓存清理和修改计数，但编码计算、缓存写入和设置文件 charset 没有异步任务代次校验 | 需要额外保证配置更新、用户修改、文件变化和项目关闭后旧结果不会提交 |

注意：上述是当前源码中的具体消费者，不等于已经证明它们就是该次历史事故的全部后续消费者。

## 4. 为什么两个简单改法不成立

### 改法 A：只把 await 改成回调

```text
原来：result = 同步查询(); 使用 result
改后：启动查询(回调); 立即返回 ???
```

上层需要实际的大小写敏感性结果才能继续查找文件。没有等价返回值时，回调不能直接替换同步表达式；随意返回默认值会改变查找语义。

### 改法 B：只异步执行 fileCreated 中的编码计算

```text
创建事件 → 启动后台编码计算 → 监听器返回
                                 ↓
创建流程继续 → 读取编码/BOM（后台可能尚未完成）
```

这会造成编码数据未就绪，或者让 BOM 提供器再次同步查询。如果 EDT 再通过 get/join 等待后台任务，原来的卡顿仍然存在。

此外，`computeAndCacheEncoding` 当前使用 `withCache=false`。只在前面预热编码缓存，监听器仍然会重新计算，不能据此认定阻塞被消除。

## 5. 可讨论的候选方案：提前准备 + 整体异步延续

```text
接收创建请求，保存目标父目录、文件名和业务参数
  → 在创建写操作之前，后台计算目标路径所需的编码配置
  → 准备完成后调度后续操作
  → 校验请求仍有效、配置及目标路径未过期
  → 在需要的写操作中创建文件，让监听器消费准备结果
  → 按原语义处理编码/BOM
  → 调用原来的结果消费者，继续打开/展示等操作
```

此方案必须满足：

1. 后台准备和等待期间不持有写锁，EDT 不等待后台任务。
2. 创建前的目标路径计算与创建后对实际文件的配置计算语义一致；路径变化时重新准备。
3. 监听器与编码/BOM 消费者使用同一份有效准备结果，不能再同步查询补漏。
4. 校验与提交之间保持必要的一致性；过期则退出本次提交，在写操作之外有限重试。
5. 项目关闭后取消；文件删除、重命名、配置变化、用户手动编码或 ignored 设置变化时不覆盖新状态。若涉及文档写入，还需检查文档版本。
6. 失败与“合法地没有配置”分开处理，保留取消和错误语义，不能失败后冒充成功。
7. 保留创建、命令/撤销以及后续消费的顺序与错误处理。这些仍需针对真实调用方核验。

当前发现 `CreateFileAction` 有 `elementsConsumer` 结果回调，可作为一个外层改造位置的例子；但其 `create` 仍同步执行写操作并返回 PSI 数组。**没有证据表明第 357 行由这个 Action 触发，不能把修改它当成该事故已被修复。**

这个候选方案涉及 S1 P1 的提前准备与 S2 P2 的异步延续组合，尚不是可直接应用的通用修复模板。

## 6. 与老师讨论的核心问题

1. 修复器的边界应止于等待方法，还是允许向上扩展到能够异步返回的完整业务操作？扩展到何处算足够？
2. “提前准备配置 + 完成后创建并消费”的组合，应记录为 P1/P2 组合策略，还是由主要消除的同步等待归为 P2？
3. 缺少原始创建方时，应继续收集完整线程证据，还是选择一个调用方明确的真实案例先验证模板？
4. 自动生成补丁之前，需要哪些最小证据证明编码/BOM、创建完成时机和失败行为保持正确？
5. 修复器如何表达“当前局部模板不适用，但上层改造可能可行”，避免把未确定误记为不可修？

## 7. 下一步验证与实验边界

建议先复现目标操作，捕获完整多线程栈，以及创建事件 requestor 和原始创建调用方。明确后再构造候选补丁。

候选补丁至少验证：编码与 BOM 一致性、配置变化导致结果过期、用户编辑/编码修改、项目关闭、失败/取消、重复请求，以及 EDT 响应性。分别记录补丁生成、行为测试和真实卡顿改善。

之前 JFR 只捕获到一次后台 Maven 启动路径上的 `DiskQueryRelay` 调用，耗时 148.6281 ms；它不是本例 EDT 路径，也不是超时事件，不能用来确定本例生产超时阈值。当前没有该案例可靠的正常耗时分布或生产超时阈值。

## 8. 本地证据索引

源码根目录：`D:\intellij-community-master`。以下行号针对本次核验的当前源码，不保证与事故运行版本一致；事故中 DiskQueryRelay 显示 Java，当前源码为 Kotlin。

| 文件（相对源码根目录） | 位置/内容 |
| --- | --- |
| `plugins/editorconfig/backend/src/configmanagement/EditorConfigEncodingCache.kt` | 70–104：缓存缺失计算、强制重新计算和设置 charset |
| `plugins/editorconfig/backend/src/configmanagement/ConfigEncodingManager.kt` | 11–17：读取缓存编码 |
| `plugins/editorconfig/backend/src/configmanagement/EditorConfigUtf8BomOptionProvider.kt` | 9–13：BOM 查询 |
| `platform/platform-impl/src/com/intellij/openapi/vfs/newvfs/persistent/PersistentFSImpl.java` | 978–1014：创建后检查 charset/BOM；1801–1810：事件通知 |
| `platform/core-api/src/com/intellij/openapi/vfs/VirtualFile.java` | 400–418：同步创建、写锁契约 |
| `platform/core-impl/src/com/intellij/psi/impl/file/PsiDirectoryImpl.java` | 395–405：同步取得 PSI |
| `platform/lang-impl/src/com/intellij/ide/actions/CreateFileAction.java` | 67–80：结果消费者；107–111：同步创建 |

工作目录：`D:\intellij-community-master\tools\edt-freeze-finder`。

- 原始 Finder 记录：`out/edt-freeze-finder/s2-await-20260928/finder.jsonl`，`input.row=357`。
- 核验报告：`repair/docs/S2-ROW357-P2-AUDIT-2026-09-28.md`。
- 实验记录：`repair/docs/S2-LIVE-TIMING-2026-09-28.md`。

本文件是问题讨论材料，不是修复成功报告。
