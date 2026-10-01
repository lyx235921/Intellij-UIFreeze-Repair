# 第124行刷新入口源码核验

2026-09-27，仅核验当前源码和已重新读取的真实堆栈；未改生产代码，未生成补丁，未执行运行时性能测试。

## 已核验的调用和线程边界

| 源码位置（相对 IntelliJ 根目录） | 当前实现事实 |
| --- | --- |
| platform/core-impl/src/com/intellij/openapi/vfs/impl/VirtualFileManagerImpl.java:161–174 | refreshWithoutFileWatcher(asynchronous) 将参数传给各文件系统；同步时要求 write-intent lock。 |
| platform/platform-impl/src/com/intellij/openapi/vfs/impl/local/LocalFileSystemImpl.java:304–317 | heavyRefresh 遍历根节点 markDirtyRecursively，随后 refresh(asynchronous)。异步且 watcher 可用时，先排一个异步刷新，以 heavyRefresh 作为完成回调；否则在调用线程直接 heavyRefresh.run()。 |
| platform/platform-impl/src/com/intellij/openapi/vfs/impl/local/LocalFileSystemBase.java:689–690 | 传递 asynchronous，发起递归刷新。 |
| platform/analysis-api/src/com/intellij/openapi/vfs/newvfs/RefreshQueue.kt:25–34 | 创建对应 async 标志的 session，添加文件后 launch。 |
| platform/platform-impl/src/com/intellij/openapi/vfs/newvfs/RefreshSessionImpl.kt:108–110 | launch 调用 RefreshQueueImpl.execute。 |
| platform/platform-impl/src/com/intellij/openapi/vfs/newvfs/RefreshQueueImpl.kt:81–96 | async=true 排队；同步且在 EDT 或持有写权限时，直接 runRefreshSession + fireEvents；同步后台调用可能 queue 后 waitFor；读锁下同步刷新被拒绝。 |
| 同文件:59、131–150、184–198 | 两条异步扫描路径都通过 Dispatchers.Default 的 eventScanningScope 排队运行扫描。 |
| 同文件:331–334；RefreshSessionImpl.kt:179–181 | runRefreshSession → session.scan → RefreshWorker.scan。 |
| platform/platform-impl/src/com/intellij/openapi/vfs/newvfs/RefreshWorker.java:405–419、519–522 | 扫描同步取得目录属性 Map，随即参与子节点比较；调用 listWithAttributes 位于不可取消区。不能仅将生产 Map 的底层函数异步化而不调整消费者。 |
| platform/platform-impl/src/com/intellij/openapi/vfs/impl/local/LocalFileSystemImpl.java:460–482 | 目录属性入口 → disk relay；listWithAttributesImpl 调 visitDirectory 收集结果并同步返回。 |
| RefreshQueueImpl.kt:280–313 | 旧异步事件处理路径通过 finishOnUiThread，或 AppUIExecutor.onWriteThread，进入事件应用。 |
| RefreshQueueImpl.kt:201–218、259–275 | 协程路径通过平台后台写动作应用事件。 |
| RefreshSessionImpl.kt:226–274、282–300 | 旧 fireEvents 要求 EDT/写锁；后台分支要求 BGT/写锁。before/after 通知和完成回调经 invokeOnEdt；后台调用通过带写动作转移的 invokeAndWait。不能替换成任意线程池直接修改VFS。 |

## 与真实堆栈的关系

原始第124行线程是 AWT-EventQueue-0 RUNNABLE，栈顶 FindFirstFile0，调用链经 RefreshWorker、RefreshSessionImpl、RefreshQueueImpl.execute、refreshWithoutFileWatcher，回到 `com.huawei.tools.idea.codescanner.toolwindow.ScanPanel$2$1.lambda$onComplete$1(ScanPanel.java:238)`。

这是 EDT 正在执行目录扫描的运行时证据。当前平台源码中的同步分支与该调用链吻合；但是堆栈不包含 boolean 实参，且源码版本不同，不能声称已直接读取到插件传入 false。不能将当前源码行号当成事故版本行号。

本次超出提取器五层限制进行人工定向核验，未改变 ExtractMethod 的五层配置。

## 修复方向和边界

P2 候选应优先放在插件发起刷新处：使用平台异步刷新能力，保留事件应用的线程/锁管理，将依赖刷新结果的后续操作放在正确完成边界。底层 FindFirstFile0、目录流和同步 Map 返回方法不应直接变成异步接口。

不能把 `refreshWithoutFileWatcher(false)` → `true` 宣称为已核验安全补丁：业务实参尚未读取；此API没有完成回调参数；异步模式下仍有标脏准备工作，watcher可用时还会出现两次刷新的衔接。随意追加一次刷新或用 invokeLater 并不能代表等待原刷新完成。当前 VirtualFileManager.java:85–87 还将此全VFS接口标为 Obsolete，建议有范围的 markDirtyAndRefresh；需要知道插件实际修改了哪些文件才能评估替换是否等价。

异步扫描能避开已观察到的 EDT 目录枚举路径，但不证明整个刷新没有其他 EDT 开销，尤其是标脏、VFS事件监听器和UI完成回调。

## 缺失证据

在当前源码工作树（排除 .git、.idea、out、node_modules、build、target）按文件名查找 ScanPanel.java/ScanPanel.kt，未找到。Finder 对 t0:f34 和 t0:f35 也返回 UNRESOLVED / MISSING_OR_SYNTHETIC_SYMBOL。未搜索用户其他目录、未反编译插件包。

因此尚未核验插件 onComplete 的完整方法、刷新实参、后续VFS读取、项目/窗口生命周期、锁及模态上下文。需要该插件对应版本的 ScanPanel.java，至少包括238行所在回调及其前后操作，才能确定具体P2改写位置和完成时序。

结论：平台机制核验完成，真实业务补丁的语义核验仍缺插件源码。下一步补齐业务上下文，不修改通用底层文件系统实现。

来源：当前工作树源码，`out/edt-freeze-finder/row124-source-20260927/finder.jsonl`；文件快照哈希见同目录 `refresh-source-hashes.json`。rg.exe 启动失败，未安装/修复工具；使用已知文件定向读取和限于工作树的文件名扫描。research HEAD仍83a21329，无新增资料阅读。
