# 五条记录的补丁覆盖与受控效果复核

实际已有补丁的是5条，不是6条：1238、1779、1806、1812、1813。另三条868/1774/1775未生成补丁。

逐条检查 `out/p2-eight-cases-20260927/repair-five-layers.jsonl`：五条均只有一份成功候选，before/replacement/patch/expected_sha256与已测试1238候选完全一致；当前生产源码哈希未改变；每条到达目标方法的栈路径均包含 `javax.imageio.ImageIO.read`。该调用整体位于生成代码的后台任务中。

| 行号 | 栈中操作 | 路径被迁移的静态核对 |
|---|---|---|
|1238|PNG解压清理|通过|
|1779|图像缓存文件关闭|通过|
|1806|图像缓存文件创建|通过|
|1812|图像缓存文件删除|通过|
|1813|图像缓存文件删除|通过|

对同一份补丁重新执行行为测试和3对独立JVM响应实验，未把重复补丁当成5次独立修复：

```powershell
$env:Q1_CLASSPATH = (Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw).Trim()
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_p2_relocation.py
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/tests/measure_p2_responsiveness.py --proposal out/p2-row1238-20260927/proposal.json --output out/p2-eight-cases-20260927/shared-patch-responsiveness.json
```

两命令exit0。相同500ms模拟准备停顿：原方法EDT心跳延迟503.071/501.639/501.536ms；补丁1.761/1.649/1.700ms。后台执行、EDT原生接口、隐藏过期结果、销毁、共享加载、缓存和失败重试的受控检查均通过。

结论：五条记录的相关路径均处于同一个迁移范围，共用补丁的受控效果验证通过。但未复现五个原始事件，尤其测试关闭ImageIO磁盘缓存，未实际重演1779/1806/1812/1813的缓存文件关闭/创建/删除。窗口、原生接口、ICO编码是替身；不得把静态路径覆盖及同一补丁测试写成五个真实卡顿都已修复。

生产源码未应用补丁；下一证据门仍为目标IDE编译和真实Windows徽标冷加载验证。
