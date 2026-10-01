# 第 4746 行 P1 候选验证：正确性未通过

2026-09-27。结论：当前候选在受控慢读实验中改善 EDT 响应，但同步刷新兼容性失败，不能作为有效修复应用。生产源码未修改；未宣称复现原始卡顿或通过真实 IDE 测试。

## 验证结果

`repair/tests/test_p1_effectiveness.py` 分别提取原始源码和生成补丁中的 `contentsChanged`、重载方法、辅助方法，编译后进行对照。使用真实 Swing EDT、磁盘文件、Windows JNA 身份查询；平台服务、VFS 对象和解码器为受控替身。两条路径均显式注入 400 ms 读盘延迟，后台调度及 EDT 回调使用真实线程。

| 指标 | 原路径，3 次 | 候选补丁，3 次 |
|---|---|---|
| EDT 心跳延迟（ms） | 403.4433 / 402.2806 / 401.6028 | 1.56 / 0.0211 / 0.0235 |
| contentsChanged 返回时文档已更新 | 3/3 | 0/3 |
| 最终内容、版本及一次替换检查 | 3/3 | 3/3 |

这些时间只说明在指定的受控延迟下，磁盘等待离开 EDT；不代表真实第 4746 行的性能提升比例。

反例对应当前源码中的既有约束：

- `platform/core-api/src/com/intellij/openapi/vfs/VirtualFile.java:621-633`：同步刷新返回前处理完变更事件，postRunnable 在操作完成后执行。
- `platform/platform-tests/testSrc/com/intellij/openapi/fileEditor/impl/FileDocumentManagerImplTest.java:598-608`：真实本地文件外部改写后执行 `file.refresh(false,false)`，随即断言文档 stamp 等于文件 stamp。`createFile` 在 362-369 行创建本地物理文件，并非 MockVirtualFile。
- `platform/platform-impl/src/com/intellij/openapi/vfs/newvfs/RefreshWorker.java:912-914`：刷新生成事件携带新长度、时间；`VFileContentChangeEvent` 构造器将 -1 的新 modification stamp 转为 `LocalTimeCounter`，因此不是因 stamp=-1 必然退出异步分支。

候选在 `contentsChanged` 中启动后台工作即返回，EDT invokeLater 提交只能发生在当前事件处理返回之后。于是同一 EDT 调用方可在文档仍旧时继续执行。原方法保持公开 reloadFromDisk 同步，并不足以保住 contentsChanged/refresh 的原完成语义。受控实验复现的是这个时序反例；**上述真实 IDE 测试没有实际执行成功，不能写成其测试失败报告**。

## 真实 IDE 测试尝试

命令（工作目录 `D:/intellij-community-master`）：

```powershell
./tests.cmd --module intellij.platform.tests --test com.intellij.openapi.fileEditor.impl.FileDocumentManagerImplTest
```

首次因 Bazel 缓存 `C:/ProgramData/_bazel/j66whxgf` 权限失败。随后相同命令通过自动审批运行，Bazel 启动成功，但在加载 JPS 模型时 exit 1：

```text
Invocation ID: 0b6f83af-cad7-47e6-9f0c-8c6ad91ee36a
FileNotFoundException:
D:\intellij-community-master\tools\edt-freeze-finder\repair\main\kotlin\intellij.tools.readWriteLock.repair.iml
Build did NOT complete successfully
Build failed. Not running target
```

这发生在未应用补丁的基线阶段。没有为绕过它补造旧模块、改动注册文件或修改生产代码。目标 IDE 编译、编码/监听器/PSI 集成验证依然未完成。

## 新增验证及输出

```powershell
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/tests/test_p1_effectiveness.py
```

exit 0，1 项实验测试完成，14.685 秒。测试成功是指成功完成对照并捕获预期反例；`correctness_gate_passed=false`，不是修复通过。

详细数据：`out/edt-freeze-finder/p1-row4746-verification-20260927/report.json`。原文件 SHA256 `3b2be0365dfc949f19785f569543f8b6b02538ba5e87e0c623177505aed8f9dc`，实验候选 patch SHA256 `cfd74483edd1fb0684af07c5b4ca7d320030ae38c68165f1d7b4a02aedb1419a`。

P1 输出已增加 `validation_status=CONTROLLED_CORRECTNESS_FAILURE`、`eligible_for_application=false`，readiness 改为 `BLOCKED_BY_SYNC_REFRESH_CONTRACT`；保留 CANDIDATE_PATCH 表示补丁存在，不表示可应用。该变更后构建 exit 0，`test_p1_plan.py` 的 1 项准入/拒绝/状态检查通过（0.571 秒）。未改变候选 Java 字节内容，不重复运行无关套件。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/tests/test_p1_plan.py
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/getattributes-row4746-20260927/finder.jsonl --output out/edt-freeze-finder/p1-row4746-verification-20260927/repair.jsonl --q1-classpath $env:Q1_CLASSPATH --s1-p1
```

下一证据门：将准备边界调整到事件提交前，或在具有明确异步完成契约的上层入口拆分流程，不能在底层内容事件里无条件延后文档更新；同时修复现有 JPS 模型缺失后，运行真实刷新/编码/监听器和性能验证。当前没有通过这些门槛的第 4746 行修复。
