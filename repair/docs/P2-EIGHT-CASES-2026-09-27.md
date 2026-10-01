# 八条 _setOkBadge 堆栈进入 Repair/P2 的测试

2026-09-27：从已保存的全量 Finder JSONL 提取868、1238、1774、1775、1779、1806、1812、1813行，用当前真实 Python→Kotlin 入口运行；未改变分类/提取/补丁规则，未重新扫描源码索引。定位阶段重新读取并校验当前源码。

```powershell
$cp = (Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw).Trim()
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/p2-eight-cases-20260927/finder.jsonl --output out/p2-eight-cases-20260927/repair.jsonl --q1-classpath $cp --s1-p2
```

输出必须为新文件。CLI exit0；8 accepted，0 rejected；5条命中Q1；4条生成候选补丁，去重后1份补丁。逐条核对Finder对象保留一致，四份补丁SHA256相同。

| Excel行 | Q1类别 | 提取的方法 | P2结果 |
|---|---|---|---|
|868|无|不适用|无补丁|
|1238|Q1.6|Win7AppIcon._setOkBadge|候选补丁|
|1774|无|不适用|无补丁|
|1775|无|不适用|无补丁|
|1779|Q1.7|Win7AppIcon._setOkBadge|候选补丁|
|1806|Q1.1|TracingFileSystemProvider.newByteChannel|不支持的方法形态|
|1812|Q1.1、Q1.7|TracingFileSystemProvider.delete；Win7AppIcon._setOkBadge|后者生成候选补丁|
|1813|Q1.1、Q1.7|TracingFileSystemProvider.delete；Win7AppIcon._setOkBadge|后者生成候选补丁|

1806暴露的是提取策略边界：从命中帧出发停在首个非JDK项目帧，没有继续枚举上层业务方法。这不同于“现有徽标补丁在语义上迁移了整个ImageIO.read链路”。1812/1813可以通过第二个Q1.7命中帧到达徽标方法。

868/1774/1775采样于原生setOverlayIcon链路，不在当前Q1方法名单内，且P2补丁也未迁移该原生调用。

未应用补丁或验证这些原始事件的性能改善。完整结果见同名JSON；输入、原始Repair输出及逐行补丁在 `out/p2-eight-cases-20260927`。下一定位改进候选是沿栈枚举上层业务方法供P2匹配，而非一律选择首个项目帧；本轮尚未实施。
