# S2 等待耗时实验

2026-09-28。本次取得**本机原生查询耗时**和**JDK有界等待实测耗时**；尚未取得完整 `ProgressIndicatorUtils.awaitWithCheckCanceled` 在目标IDE中的正常/事故耗时。

## 正常查询实测

当前 `LocalFileSystemBase.fetchCaseSensitivity` 在非EEL路径调用 `FileSystemUtil.readParentCaseSensitivity`。Windows原生分支打开目录句柄、执行 `NtQueryInformationFile(FileCaseSensitiveInformation=71)` 并关闭句柄。
实验用Python ctypes调用同一组Windows API，逐次核验成功状态与大小写标志；不是模拟磁盘返回值。Python FFI替代JNA，因此不代表Java/IDE端到端时间。没有强制启用事故机器的实际分支。

| 本机D盘目录场景 | 样本数 | P50 ms | P95 ms | P99 ms | 最大 ms |
|---|---:|---:|---:|---:|---:|
| 同目录重复查询，3批 | 9000 | 0.0110 | 0.0124 | 0.0169 | 0.4778 |
| 新建目录首次查询，3批 | 300 | 0.0334 | 0.0733 | 0.1841 | 0.4421 |

9300个样本无一次超过20/50/100/200ms。新建目录元数据可能已经缓存，**不是冷缓存实验**。无网络盘、磁盘故障、Java线程池排队、锁等待、EDT或真实编辑操作样本。样本创建只在本次out目录；保留目录便于核对。

## 超时机制实测（人工阻塞）

使用真实JDK `Future.get(timeout)`。worker先启动，然后阻塞在实验闩锁；测量超时抛出时间后释放闩锁，确认原任务仍能返回7。每个预算20次，全部发生TimeoutException，无任务残留。不是IDE修复补丁，不使用人工阻塞数据推断真实事故发生率。

| 设定上限 ms | 实测P50 ms | 实测P95 ms | 最大 ms |
|---:|---:|---:|---:|
| 20 | 20.5996 | 21.8660 | 22.1627 |
| 50 | 50.6971 | 51.8179 | 51.8553 |
| 100 | 100.7691 | 101.9544 | 102.0820 |
| 200 | 200.4840 | 201.9062 | 201.9912 |

额外执行6次20ms内层轮询，累计123.9432ms后仍需释放任务才能结束。这说明单次get超时不等于整个等待方法有总超时；这是受控机制实验，不是执行IntelliJ工具的结果。

## 平台测试阻塞

执行 `D:/intellij-community-master/tests.cmd --module intellij.platform.tests --test com.intellij.openapi.util.io.DiskQueryRelayTest`。
首次缓存权限失败；通过任务级提权使用原缓存后，Bazel在加载项目模型时失败：

```text
FileNotFoundException: D:\intellij-community-master\tools\edt-freeze-finder\repair\main\kotlin\intellij.tools.readWriteLock.repair.iml
Build did NOT complete successfully
Build failed. Not running target
```

未运行任何该平台测试，没有修复或伪造模块文件。即使该既有测试通过，它的人工慢任务也不能替代真实磁盘/IDE计时。

## 复现及证据

脚本：`repair/main/scripts/measure_s2_native_query.py`。
JVM实验：`repair/main/kotlin/src/pool/s2_sync_wait/S2WaitTimingExperiment.kt`。
原始数据：`out/edt-freeze-finder/s2-timing-20260928/native.json`（包括操作系统、Python版本、源码SHA及每次观测）、`waits.json`（Java版本与每次观测）、`wait-summary.json`。

```powershell
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/scripts/measure_s2_native_query.py out/edt-freeze-finder/s2-timing-20260928
$timingDeps=(Get-ChildItem -LiteralPath "$env:TEMP/repair-q1-build" -Filter '*.jar' | Where-Object { $_.Name -ne 'q1.jar' } | ForEach-Object { $_.FullName }) -join ';'
java -cp $timingDeps org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -no-stdlib -no-reflect -classpath $timingDeps -d out/edt-freeze-finder/s2-timing-20260928/timing.jar repair/main/kotlin/src/pool/s2_sync_wait/S2WaitTimingExperiment.kt
java -cp "out/edt-freeze-finder/s2-timing-20260928/timing.jar;$timingDeps" org.jetbrains.research.lockrepair.pool.s2.S2WaitTimingExperiment out/edt-freeze-finder/s2-timing-20260928/waits.json
```

三步均exit0，原生调用结果检查及JVM超时/完成/清理断言通过。重跑应选择新输出目录，程序拒绝覆盖已有结果。

## 结论边界

这批本机查询均小于0.5ms；20ms以上明显超出本批样本，但不能据此设定业务失败阈值。实际超时退出会因调度比预算稍晚，且不会自动取消后台任务。
**真实事故超时样本：未获得；完整方法正常耗时：未获得；生产超时阈值：未确定。**
下一证据门是恢复可运行的目标IDE测试入口，对整个relay调用分别记录排队、执行、等待和取消时间，并验证超时后的业务行为。
