> Superseded validation: [2026-09-27 correctness rejection](P1-ROW4746-VERIFICATION-2026-09-27.md). This candidate is not eligible for application. Earlier 25 passing checks did not cover synchronous refresh visibility.

# P1 文档重载候选补丁：第 4746 行

2026-09-27，未提交。当前实现取代此前只输出 `CANDIDATE_PLAN` 的阶段；旧方案文档保留为历史。生产源码没有修改。

## 实际结果

`P1PreloadBeforeCriticalRegion.propose` 现在通过 `repair.py --s1-p1` 输出 `repair-s1-p1-proposal/2`、`CANDIDATE_PATCH`、`patch_generated=true`、`applied=false`。仍按真实同线程连续堆栈和完整源码 SHA256 准入，不绑定 Excel 行号；五层提取器不变。

生成物位于 `out/edt-freeze-finder/p1-row4746-patch-20260927/`：

- `repair-validated.jsonl`：最终 Python → Kotlin 实际入口结果，1 accepted / 1 Q1 候选。
- `proposal.json`：最终候选、源码上下文及限制。
- `candidate.patch`：未应用的生产 Java 补丁。
- `FileDocumentManagerImpl.java`：候选完整源码副本。
- `repair.jsonl`：早期生成输出，已由 `repair-validated.jsonl` 取代，不作为最终验证依据。

目标源文件：`platform/platform-impl/src/com/intellij/openapi/fileEditor/impl/FileDocumentManagerImpl.java`，原始 SHA256 为 `3b2be0365dfc949f19785f569543f8b6b02538ba5e87e0c623177505aed8f9dc`。

## 执行方式

1. 在 `contentsChanged` 中、VFS 事件已经应用后捕获事件、文件、文档版本。只接收可提供新长度/时间戳的本地普通文本刷新事件，文件最多 1 MiB，排除未保存文档、二进制、目录和不支持的路径。其他分支仍走原同步实现。
2. 后台直接读取磁盘，不读取旧 VFS 内容缓存。读取前后检查普通文件属性、身份、大小和完整修改时间；与事件的长度及毫秒时间戳对应。最多三次准备；异常不转成空文本。每个文档最多一个在途读取，后续事件替换待处理请求；最多 32 个文档槽位。
3. Windows JDK 的 `WindowsFileAttributes.fileKey()` 在本机实际返回 null（`javap -c -p` 已确认）。因此默认 Windows 文件系统使用现有 JNA 5.17.0 的 `GetFileInformationByHandleEx(FileIdInfo)` 读取卷序列号和 128 位文件 ID。句柄启用 READ/WRITE/DELETE 共享，finally 关闭，不锁住外部写入。其他 provider 有 fileKey 时使用其标识，否则拒绝；不把路径或创建时间当作可靠身份。
4. EDT 回调检查最新请求、事件 stamp、VFS 长度/时间、文件与文档关联、文档 stamp、未保存状态、路径、文件类型和项目存活。新事件使旧结果失效时，转而准备最新请求；用户编辑/删除/失效时直接丢弃。读到不稳定快照时有限重试。
5. 仍在原 ThreadContext、命令、write action、externalDocumentChangeAction 中提交。重载前监听器之后再次检查版本。保留原来的 BOM/字符集重置，再调用真实 `LoadTextUtil.getTextByBinaryPresentation(bytes,file)`；解码/转换器之后再次检查，避免覆盖重入编辑。恢复文档只读状态使用 finally。
6. 仅成功替换文档才发重载完成通知、清理未保存标记。原公开同步 `reloadFromDisk` 保持同步，同时取消该文档旧的异步请求。接受的异步路径不在失败时退回 EDT 磁盘读取。

这里的 P1 是“在文档更新关键区前准备字节”，**不是在整轮 VFS 事件前准备**；没有采用旧计划的 `prepareChange` 读取点。也没有将解码、监听器或所有 VFS 工作移出 EDT。

## 验证与可复现命令

构建 exit 0：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw).Trim()
```

25 项测试通过，0 failure/error/skip，49.550 秒：

```powershell
@'
import sys,unittest
sys.path.insert(0,'repair/tests')
r=unittest.TextTestRunner(verbosity=2).run(unittest.TestLoader().loadTestsFromNames([
 'test_p1_plan','test_p1_reload','test_repair_selection','test_repair_entry',
 'test_extract_method','test_p2_relocation','test_q2_classifier']))
sys.exit(not r.wasSuccessful())
'@ | D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -
```

`test_p1_reload.py` 验证：

- 将生成的补丁在临时源码副本上 `git apply --check`、实际 apply，逐字核对 replacement_source。
- 从生成源码取出实际 `contentsChanged`、P1 辅助方法、reload、setNewText，编译运行。真实 Java/Swing EDT、临时磁盘、真实 Windows JNA 文件身份读取；IntelliJ 服务和解码器使用受控替身。
- 正常提交、事件/文档 stamp、用户编辑、新事件合并、读取失败、三次上限、删除/项目处置/失效/改路径、监听器编辑和 veto、解码期间编辑、只读状态恢复、原同步 API。
- 另外编译带显式测试钩子的版本：在读后属性检查前更改长度；用**同大小同 mtime 的新文件替换原文件**；暂停后台读取时让真实 EDT 处理心跳。前两者拒绝提交且三次结束，后者 EDT 可响应，放行后才提交。生产补丁不包含这些测试钩子。
- JNA 测试依赖与仓库 `.idea/libraries/jna.xml` 的 5.17.0 SHA256 一致；目标模块已依赖该库，无模块元数据变更。

最终实际 CLI（输出文件必须尚不存在）：

```powershell
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/getattributes-row4746-20260927/finder.jsonl --output out/edt-freeze-finder/p1-row4746-patch-20260927/repair-validated.jsonl --q1-classpath $env:Q1_CLASSPATH --s1-p1
```

## 尚不能宣称的结果

尚未编译完整目标 IDE、运行真实重载集成测试或复现第 4746 行卡顿。受控解码器只验证调用顺序和冲突处理，不能证明 IntelliJ 的真实 BOM、编码选择、text transformer、监听器、range marker 和 PSI 时序全部正确。真实堆栈不含 event.newLength/newTimestamp，不能仅凭堆栈保证原案例运行时一定进入受限异步分支。

身份/大小/mtime 是乐观检查，不能排除同一个文件内同大小同 mtime 的写入、ABA 变化、或最后一次磁盘检查后到 EDT 提交前的外部写入；没有声称原子快照。三次都失败后保留旧文档并记日志，需要后续事件或人工重载，不保证最终一致性。磁盘调用本身没有超时；同一文档工作合并及槽位上限不能取消已卡住的 OS 调用，超过容量的事件仍走原路径。

下一证据门：在目标 IDE 的实际文件刷新场景检查事件字段、异步监听器/编码/标记时序及保存冲突，再测 EDT 卡顿是否下降。`repair_selection` 的通用前置检查/选择尚未接入这一专用候选生成器，当前使用独立 `--s1-p1`。
