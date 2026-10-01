# Row4938 删除机制受控对照

2026-09-30：运行完成exit0。未修改生产代码；不是历史4938复现，也没有测量完整IntelliJ write action。

## 方法与身份

测试源码：repair/tests/kotlin/Row4938DeletionExperiment.kt。before为保存的row694 before.java.raw（SHA256校验5b8f9c8e423ffcb149be4f746c1bdeb725457578b07e94b110a7d024d1665355）；after为当前工作树DefaultInMemoryInvertedNameIndex.java，不宣称为历史4938二进制。两份源码本次重新javac编译，独立classloader加载，复用已保存平台依赖。源码副本及SHA在输出before/after和identity.txt。

输出：out/edt-freeze-finder/row4938-comparison-20260930/{identity.txt,correctness.txt,samples.csv,summary.json}。

正确性：两种实现，桶大小1/2/3/128/129/1000；固定随机种子4938逐个删除，每一步核对完整存活ID及顺序；不存在ID删除不改变内容；全部通过。性能每轮另校验最终空桶。未覆盖完整VFS提交、并发可见性或监听器契约。

性能：预填一个同名桶（不计时），后台持ReentrantLock执行全部updateFileName(id,1,0)。真实Swing EDT排入一个等待相同锁的任务，并在它之后排队响应探针。latch确保EDT已开始等待才计时删除；锁持有的协调准备部分不计入critical_ms。每规模1轮预热+5轮测量，交替前后顺序。reflection开销同在两种实现；工作量人为指定，真实4938桶大小未知。

## 中位数（ms）

| 桶大小 | 删除临界区 前→后 | EDT锁等待 前→后 | EDT排队响应 前→后 |
|---:|---:|---:|---:|
|128|0.049→0.071|0.080→0.101|0.077→0.099|
|16000|29.919→2.266|30.023→2.332|30.051→2.334|
|128000|3759.433→15.199|3759.531→15.350|3759.543→15.365|

小桶未见收益，微小差异不能解释成确定回归；大桶在本实验中改善明显。5次样本不足以给出稳健尾延迟结论。EDT响应为受控探针，不是输入到绘制延迟；ReentrantLock替代许可，只说明临界区耗时对响应的作用，未复现Suvorov事件泵。

## 可复现命令

工作目录tools/edt-freeze-finder，Java为D:/intellij-community-master/build/download/jbr-25.0.3b531.20-windows-x64/jbr/bin/java.exe。

```powershell
$deps=(Get-ChildItem "$env:TEMP/repair-q1-build" -Filter '*.jar' | ForEach-Object FullName) -join ';'
& $java -cp $deps org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -no-stdlib -no-reflect -classpath $deps -d out/row4938-experiment.jar repair/tests/kotlin/Row4938DeletionExperiment.kt
& $java -cp "out/row4938-experiment.jar;$env:TEMP/repair-q1-build/kotlin-stdlib-2.1.20.jar" Row4938DeletionExperimentKt D:/intellij-community-master D:/intellij-community-master/tools/edt-freeze-finder/out/edt-freeze-finder/row4938-comparison-20260930
```

输出目录必须不存在；重跑用新路径。编译和运行均exit0。使用独立实验入口，因为原Repair测试模块注册已被用户删除，不重建iml。

## 尚未完成的目标

完整写动作时间和真实IDE响应仍待验证：本轮没有启动IDE或运行完整递归删除/事件监听链；也未定位历史4938具体文件集合。后续需在可控IDE项目中构造同名文件子树删除，测量VFS整段write action及Suvorov等待与UI探针，比较行为和响应。不删除sleep，本实验不支持删除节流，也不能把7行计为已修复。
