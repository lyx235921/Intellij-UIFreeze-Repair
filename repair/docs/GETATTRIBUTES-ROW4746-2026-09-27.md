# GetFileAttributesEx：第4746行上下文

2026-09-27，选取真实工作表第4746行。相对于字体初始化和缺失插件源码案例，此例能在当前项目核验文档重载业务入口。

Finder从原工作簿重新读取，Repair --extract-method接入，均exit0；1 accepted，Q1.1命中GetFileAttributesEx与GetFileAttributesEx0，是同一行而非两个问题。175帧，14 LOCATED、25 CANDIDATE、5 AMBIGUOUS、131 UNRESOLVED。

运行时栈：AWT-EventQueue-0 RUNNABLE(in native) → FileDocumentManagerImpl.reloadFromDisk → write action/externalDocumentChangeAction → setNewText → LoadTextUtil.loadText → VFS.contentsToByteArray → LocalFileSystemImpl.readContent → readIfNotTooLarge → Files.size → Files.readAttributes → WindowsNativeDispatcher.GetFileAttributesEx → GetFileAttributesEx0。

五层提取器命中：第1层TracingFileSystemProvider.readAttributes歧义/未定位；第2层LocalFileSystemBase.readIfNotTooLarge(446–469)完整定位；第3层LocalFileSystemImpl.readContent(489–498)完整定位；第4、5层lambda未定位。两个触发符号分别保留路径，完整方法去重后是两份。当前文件SHA256与方法行范围正文独立复核通过。

当前直接查询位置：platform/platform-impl/src/com/intellij/openapi/vfs/impl/local/LocalFileSystemBase.java:460 `var length = Files.size(nioFile);`。大小检查后:468 `Files.readAllBytes(nioFile)`；:447还有EEL分支，说明当前版本不是运行时源码的严格同一版本，不能保证当前所有路径经过Files.size。

人工扩展核验（不属于提取器五层自动结果）：platform/platform-impl/src/com/intellij/openapi/fileEditor/impl/FileDocumentManagerImpl.java:800–850 reloadFromDisk当前签名含Project参数，:802断言EDT，:822–831在write action中调用setNewText，:827 loader执行LoadTextUtil.loadText。setNewText:852–869先清理字符集自动检测原因、BOM和charset(:856–858)，修改只读状态，:864调用loader，:865 replaceText。

因此有明确的“EDT写动作内同步准备文件内容”候选。P1可评估把所需内容准备移出关键区、区内提交文档，但这不是已完成的安全方案：文件/文档版本一致性、BOM和解码顺序、只读状态、监听器与命令语义需要后续核验。只提前Files.size不会消除后续readAllBytes的读取风险。移出写锁也不自动意味着离开EDT。

此次只定位和读源码，没有生成或应用修复补丁，没有运行卡顿效果测试。

输出：out/edt-freeze-finder/getattributes-row4746-20260927/{finder.jsonl,repair.jsonl,context.md,source-hashes.json}；context.md包含原始堆栈、完整提取方法及手工核验业务方法，明确标记两种来源。

运行配置沿用ROW124-CONTEXT-2026-09-27.md的便携Python/tree-sitter 0.25.2路径，Finder使用 --row 4746 输出上述finder.jsonl；Repair读取该文件，--q1-classpath使用TEMP/repair-q1-build/classpath.txt，--extract-method输出repair.jsonl。两命令exit0。research HEAD83a21329未变，无新增阅读。
