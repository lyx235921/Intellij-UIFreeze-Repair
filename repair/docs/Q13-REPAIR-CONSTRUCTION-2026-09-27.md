# Q1.3 五个方法：修复器构造与验证

日期：2026-09-27。按 [S1 工作规范](S1-REPAIR-CONSTRUCTION-WORKFLOW.md) 执行。

**阶段结论：五个方法已接入逐项检查，两个方法的一类调用路径可生成同一份 P2 候选；另外三个方法仍没有安全补丁模板。尚未完成“五个方法都能生成有效补丁”的目标。** 没有修改生产源码或声称真实 IDE 卡顿已修复。4746 案例保持暂停。

## 真实记录、定位与结果

本轮重新读取原工作簿 `D:/intellij-community-master/intellij底座问题堆栈-1.xlsx`，工作表“问题线程堆栈”。先选择六条记录，再补充两条，均实际运行 Finder 和 Repair。

| 方法（省略共同包名） | 记录行号 | Finder / 五层提取结果 | 修复器输出 |
|---|---|---|---|
| `FSRecordsImpl.readAttribute` | 207 | 完整方法 1531–1544；同一路径继续到符号链接解析 | P2 候选，异步刷新准备路径限定 |
| `FSRecordsImpl.readSymlinkTarget` | 207、3936 | 完整方法 1109–1134 | 与上一项共用补丁 |
| `FSRecordsImpl.getName` | 699 | 完整方法 1269–1278；后续合成 lambda 部分未定位 | `INSUFFICIENT_EVIDENCE`，0 补丁 |
| `FSRecordsImpl.getNameByNameId` | 3935、4175 | 完整方法及 `findExistingChildInfo` 已定位；合成 lambda 部分未定位 | `INSUFFICIENT_EVIDENCE`，0 补丁 |
| `WorkspaceFileIndexDataImpl.getFileInfo` | 655、692、4676 | 目标方法未由 Finder 定位，五层提取找到上层完整方法；人工补读当前目标源码 175–244 | `INSUFFICIENT_EVIDENCE`，0 补丁 |

首批 Finder：6 records，180 LOCATED / 163 CANDIDATE / 10 AMBIGUOUS / 601 UNRESOLVED。补充批：2 records，24 LOCATED / 51 CANDIDATE / 228 UNRESOLVED。索引错误均为 0。Repair 两批共 8 accepted / 0 rejected，均命中 Q1.3。独立核对已提取正文的文件 SHA256 和方法范围：53 个结果、22 个不同范围全部相符。

这些行号是当前工作区源码位置；原栈存在行号漂移，未建立事故二进制与源码提交一致性。五层提取器的层数和缺口规则未更改。人工补读与模板补充上下文不计为五层提取成功。

## 两个属性／符号链接方法的共同候选

真实 EDT RUNNABLE 路径：

```text
RefreshSessionImpl.fireEventsInWriteAction
→ LocalFileSystemImpl.lambda$refreshWithoutFileWatcher$...
→ VirtualDirectoryImpl.markDirtyRecursively / markDirtyRecursivelyInternal
→ VirtualFileSystemEntry.isRecursiveOrCircularSymlink
→ getCanonicalFile → getCanonicalPath
→ PersistentFSImpl.resolveSymLink
→ FSRecordsImpl.readSymlinkTarget → readAttribute
```

当前 `LocalFileSystemImpl.refreshWithoutFileWatcher`（304–318）把 `heavyRefresh` 作为第一次异步刷新的结束回调。回调在 EDT 递归标脏，触发符号链接的持久化属性读取。

候选实际修改上层 `refreshWithoutFileWatcher`，不修改同步存储 getter：

```java
if (asynchronous) {
  ReadAction.nonBlocking(() -> {
    markRootsDirty.run();
    return (Void)null;
  }).expireWith(this)
    .finishOnUiThread(ModalityState.defaultModalityState(), unused -> refresh(true))
    .submit(AppExecutorUtil.getAppExecutorService());
}
else {
  markRootsDirty.run();
  refresh(false);
}
```

保留 watcher 工作时第一次异步刷新先完成的顺序；异步准备在后台读操作内执行，完成后在 EDT 发起下一次异步刷新。同步分支继续同步标脏和刷新。根之间增加取消检查，没有在 EDT 调用 `get/join`。

为何由 P1 初选转为 P2：当前尚未建立稳定的符号链接预加载快照，但该业务方法已经有异步调用契约，可以迁移准备阶段。P1 仍记为证据不足；P2 候选成立不要求把 P1 虚报为失败。P3 保持 DEFERRED。

前置条件集中于 `RelocationPreconditions.checkQ13`：

- 使用既有 Q1 UI 状态／栈顶规则的真实命中。
- 五层已定位上下文须重新核验文件哈希和正文范围。
- 从命中方法到异步刷新结束回调必须是同线程连续栈，不跨省略帧或编号缺口。
- 核验 LocalFileSystemImpl、VirtualDirectoryImpl、VirtualFileSystemEntry、FSRecordsImpl、PersistentFSImpl 五份已审阅源码哈希。
- 补充目标方法标记 `REVIEWED_SUPPLEMENT_OUTSIDE_FIVE_LAYER_EXTRACTOR`，不冒充 Finder 解析成功的 lambda。

两个方法和两条记录只对应一份去重补丁，不代表两个独立修复。

### 验证边界

代码构建 exit 0。候选在副本上 `git apply --check`、实际 apply 及生成全文一致性检查通过。

测试编译实际原方法和生成方法，使用真实 Swing EDT、JDK executor/latch；VFS、watcher、刷新队列和 NBRA 使用替身。受控检查通过：

- watcher 开启／关闭时的异步调度和两阶段顺序；
- 原方法被受控 latch 阻塞时 EDT 心跳不能执行，候选同样准备工作未完成时 EDT 可响应；
- 同步分支在返回前已完成全部标脏和刷新；
- 准备失败不提交，销毁后不执行完成回调（替身行为）。

这不是原始磁盘耗时测量，不是完整 IDE 的 NBRA 验证。真实 NBRA 的写操作抢占、重试、并发扫描清除 dirty 标志及取消后部分标脏仍需集成验证。当前仅在根之间检查取消，大子树或底层存储调用仍可能延迟写锁获取，不能据此保证全部 UI 卡顿消失。

候选 `eligible_for_application=false`、`applied=false`；真实目标 IDE 编译及效果未验证。本轮确认已有 JPS 阻塞仍存在：`repair/main/kotlin/intellij.tools.readWriteLock.repair.iml` 不存在；没有改模块元数据，也没有重跑已知会在此前置阶段失败的整机测试。

## 三个尚未形成安全补丁的方法

### getName / getNameByNameId

699、3935、4175 来自 VFS create 事件后的 Local History 同步记录：

```text
LocalHistoryEventDispatcher.fileCreated → createRecursively
→ FileIndexBase.iterateContentUnderDirectory
→ WorkspaceFileIndexImpl.processContentFilesUnderExcludedDirectory
→ childUrl.virtualFile → VFS.findChild
→ getName 或 findExistingChildInfo → getNameByNameId
```

已核验 `LocalHistoryEventDispatcher.kt:50–79` 的 change-set 包围范围，以及 `WorkspaceFileIndexImpl.kt:269–279` 对排除目录下嵌套内容根的查找。4175 包含 MRU 缓存未命中后的映射文件读取。

直接延迟遍历会改变同一事件的历史记录边界；只返回已缓存 child 会漏掉嵌套内容根。尚未建立可在事件提交前准备、且提交后仍完整有效的 URL/child/name 快照。修复器因此输出需要准备边界与版本化快照，不生成空补丁或直接异步改写同步 getter。这是当前已审阅路径的限制，不宣称所有调用方都不可修。

### getFileInfo

655、692 在 Local History 遍历中同步判断 `isVersioned`。当前 `WorkspaceFileIndexDataImpl.getFileInfo:175–244` 包含祖先遍历、排除／内容类型条件、忽略文件判断；`ensureIsUpToDate:246–250` 可能更新脏实体。现有 `IgnoredFileCache:59–76` 在 VFS 事件期间有意绕过缓存，不应以普通结果缓存替换它。

又选择不同业务的 4676 核验 P1：`RecentFilesVfsListener.beforeVfsChange → filterProjectFiles → isInContent → getFileInfo → updateDirtyEntities`。该真实栈明确走脏索引更新分支。把过滤直接移到 `prepareChange` 的读操作会失去原先写操作中的更新能力；`AsyncFileListener.java:78–84` 还明确允许前面的 applier 改变状态。

因此需要可证明新鲜的索引快照、失效判据及同步消费者拆分。当前不生成不带这些条件的缓存／提前读取补丁，也不把 UNKNOWN 视作 P1/P2 失败去启动 P3。

## 实现与入口

- `main/kotlin/src/pool/s1_expensive_work/P1StorageRelocation.kt`：五个精确符号的检查入口及支持路径的补丁生成。
- `RelocationPreconditions.checkQ13`：源码与路径前置检查。
- `repair_selection`：复用已有 P1_FIRST 映射，接受 Q1.3 专用结果。成功决策引用 `selected_proposal_pool=q13_evaluation`；未知仍为 PENDING。
- `repair.py --s1-q13`：输出 `q1.s1_q13`，自动五层提取。
- `repair.py --repair-selection`：也会评估 Q1.3 专用路径，不需要再加专用参数；两者可同时使用。
- 测试快照：`tests/fixtures/q13`。冻结 ZIP 内只含已审阅源码，保留版权头；它不是活动生产代码。

## 复现命令

工作目录为 `tools/edt-freeze-finder`。输出排他创建，重跑需换新输出名。

```powershell
@'
import sys,runpy
sys.path[:0]=['C:/Users/Administrator/AppData/Local/Temp/finder-source-deps-wheel-20260926','finder/main']
sys.argv=['find_sources.py','--workbook','D:/intellij-community-master/intellij\u5e95\u5ea7\u95ee\u9898\u5806\u6808-1.xlsx','--source-root','D:/intellij-community-master','--row','207','--row','655','--row','692','--row','699','--row','3935','--row','4175','--output','out/edt-freeze-finder/q13-20260927/finder.jsonl']
runpy.run_path('finder/main/find_sources.py',run_name='__main__')
'@ | D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -
# 补充批用 --row 3936 --row 4676，输出 additional-finder.jsonl。
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/q13-20260927/finder.jsonl --output out/edt-freeze-finder/q13-20260927/selection-final.jsonl --q1-classpath $env:Q1_CLASSPATH --s1-q13 --repair-selection
# 补充批对应 additional-finder.jsonl -> additional-repair.jsonl，使用 --s1-q13。
@'
import sys,unittest
sys.path.insert(0,'repair/tests')
r=unittest.TextTestRunner().run(unittest.TestLoader().loadTestsFromNames(['test_q13_relocation','test_regex_precompilation','test_repair_entry','test_repair_selection','test_extract_method','test_p2_relocation','test_q2_classifier']))
sys.exit(not r.wasSuccessful())
'@ | D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -
```

最终回归：**25 tests，12.940 s，0 failures / errors / skips，exit 0**。包括状态拒绝、缺失调用路径、栈省略、源码变更、路径越界、五方法输出与统一选择器集成；未恢复 4746 案例实验。

产物在 `out/edt-freeze-finder/q13-20260927`：两批 Finder、`selection-final.jsonl`、`additional-repair.jsonl`、`summary.json`、`candidate.patch`、`proposal.json`、`LocalFileSystemImpl.patched.java`、`tests.json`。较早的 `q13-repair.jsonl` 是迭代中间结果，最终选择器结果以 `selection-final.jsonl` 为准。

研究预检：HEAD `83a21329f4f811fca1b5a4a555eb6504f2ff4d78` 未变，无新资料阅读，历史未读范围保留。工程既有大量修改未清理；本轮改动未提交。当前工具无可用 IDE lint，使用编译、相关测试及文档/空白检查。

下一证据门：目标 IDE 异步刷新与取消验证；为名称读取建立同事件可用快照；为索引查询建立新鲜度与消费者拆分。后两项仍属于未完成的修复器构造。
