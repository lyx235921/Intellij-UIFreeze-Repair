# 第1345行字体路径：BGT受控可行性实验

2026-09-26。状态：受控线程迁移实验通过；原IDE卡顿未复现、未修复验证。
没有修改IntelliJ生产源码，没有实现或宣称通用S1.1修复。

## 已读源码及迁移边界

- platform/usageView-impl/src/com/intellij/usages/impl/UsagePreviewPanel.kt：resetEditor先readAction获取文档，再withContext(Dispatchers.EDT)创建编辑器并调用highlight；后者涉及UI布局，不能整体移到后台。
- platform/platform-impl/src/com/intellij/openapi/editor/impl/ComplementaryFontsRegistry.java：回退字体查找位于synchronized(lock)内，遍历字体并调用FontInfo.canDisplay。
- 同目录FontFallbackIterator.java：按字符片段选择回退字体；实际选择还受FontPreferences、style、FontRenderContext影响。
- 第1345行原栈：Font.canDisplay → TrueTypeFont.open → RandomAccessFile → Files.readAttributes → GetFileAttributesEx。

## 实验

源码：[FontBgtProbe.kt](../tests/FontBgtProbe.kt)。调用真实JDK Font.canDisplay，无mock、无人为慢I/O、无sleep注入。
对本机303个物理字体和11个固定测试码点执行3333次查询；不是原1345行文本或IntelliJ回退算法的复现。
两个模式分别在EDT执行和单线程BGT执行；BGT完成后invokeLater回EDT重复查询，逐项核对布尔结果。
10ms Swing Timer观察EDT响应；BGT模式不在EDT调用get/join/await。main线程的等待仅用于测试进程收尾。
Java 25.0.4.1，原栈25.0.2；每次新JVM，操作系统字体/文件缓存未清空。正式六次交错运行，全部exit0。

| 指标 | EDT三次 | BGT三次 |
| --- | --- | --- |
| 字体工作耗时 | 118.35–123.31ms | 122.31–134.61ms |
| 最大EDT事件间隔 | 123.91–128.86ms | 12.01–12.04ms |
| 工作期间EDT定时回调 | 每次0 | 每次11–12 |
| 回EDT重复查询耗时 | 0.61–0.70ms | 0.61–0.76ms |
| 逐项查询结果一致 | 是 | 是 |

原始测量：[JSON](FONT-BGT-EXPERIMENT-2026-09-26.json)。早期单次冷启动约1秒，不纳入正式六次比较，不能将OS缓存收益算作线程迁移提速。
结论：对这个受控字体工作负载，后台执行使EDT保持响应，而非让工作本身更快。

## 复现

在tools/edt-freeze-finder下运行；依赖为build-q1.ps1已准备的固定版本Kotlin编译器、stdlib、Gson等：

```powershell
$deps = (Get-ChildItem "$env:TEMP/repair-q1-build" -Filter '*.jar' | Where-Object Name -ne 'q1.jar' | ForEach-Object FullName) -join ';'
& java -cp $deps org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -no-stdlib -no-reflect -classpath $deps -d "$env:TEMP/font-bgt-probe.jar" repair/tests/FontBgtProbe.kt
& java -cp "$env:TEMP/font-bgt-probe.jar;$deps" org.jetbrains.research.lockrepair.FontBgtProbe edt
& java -cp "$env:TEMP/font-bgt-probe.jar;$deps" org.jetbrains.research.lockrepair.FontBgtProbe bgt
```

## 尚缺证据

未测量GetFileAttributesEx次数或耗时；重复查询更快不证明此API调用消失。
未运行UsagePreviewPanel、IntelliJ字体缓存/共享锁、动态高亮字体配置；未检查其他编辑器竞争预热锁。
缺少原始预览文本/字体配置/复现步骤（已向用户询问），因此不能认证第1345行解决。
下一步在原预览场景中准备字体后再触发布局，测EDT堆栈/延迟、共享锁等待和显示一致性；此前不把实验当生产补丁。
