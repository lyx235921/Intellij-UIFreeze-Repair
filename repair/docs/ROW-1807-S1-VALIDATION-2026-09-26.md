# 第1807行 Finder → Repair → S1 实测

2026-09-26；未修改实现或生产源码。research HEAD仍为83a21329f4f811fca1b5a4a555eb6504f2ff4d78，无新增材料阅读。

真实输入：D:/intellij-community-master/intellij底座问题堆栈-1.xlsx，问题线程堆栈，第1807行。
本次输出目录：C:/Users/Administrator/AppData/Local/Temp/s1-row1807-_8tlfexs。
finder.jsonl 是本次新生成定位结果；repair.jsonl 是 repair.py 实际调用 Kotlin S1 的结果。

复现（输出文件必须不存在，父目录已存在）：

```powershell
$python = 'D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe'
& $python -B -X utf8 -c "import sys;sys.path.insert(0,'C:/Users/Administrator/AppData/Local/Temp/finder-source-deps-wheel-20260926');sys.path.insert(0,'finder/main');import find_sources;sys.exit(find_sources.main())" --workbook 'D:/intellij-community-master/intellij底座问题堆栈-1.xlsx' --source-root D:/intellij-community-master --row 1807 --output '<output-directory>/finder.jsonl'
$cp = (Get-Content "$env:TEMP/repair-s1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& $python -B repair/main/python/repair.py --input '<output-directory>/finder.jsonl' --output '<output-directory>/repair.jsonl' --s1-classpath $cp
```

实际执行调用同一 find_sources.main，Python 内插入固定0.25.2依赖目录；两个入口均exit0。
Finder：1条、118帧；12 LOCATED、17 CANDIDATE、4 AMBIGUOUS、85 UNRESOLVED；19调用候选边、98未验证边；无索引错误。
Repair：1 ACCEPTED、0 REJECTED。S1返回41个声明候选，全部HASH_MATCHED。
独立读取实际文件，核对每个候选SHA256、方法正文范围和调用表达式起始行；全部通过。原Finder对象完整保留。

| 当前源码文件 | 行号 | 实际返回的调用 |
| --- | --- | --- |
| platform/platform-impl/src/com/intellij/openapi/vfs/impl/local/LocalFileSystemBase.java | 468 | Files.readAllBytes(nioFile) |
| platform/platform-impl/src/com/intellij/openapi/vfs/impl/local/LocalFileSystemImpl.java | 493 | readIfNotTooLarge(nioPath) |
| platform/core-impl/src/com/intellij/openapi/fileEditor/impl/LoadTextUtil.java | 633 | file.contentsToByteArray() |

结论：输出包含正确的同步文件I/O源码调用点，核心为readIfNotTooLarge中的468行。该方法声明范围446–469，Finder状态LOCATED。
S1只消费并核对Finder定位，不会自动标记468行为唯一根因/修复点，也不判断安全迁移。
原堆栈的readContent行号484映射到当前调用行493；loadText原599对应当前候选调用633。
JDK原生CreateFile0未定位；上层FileDocumentManagerImpl.reloadFromDisk及其lambda、setNewText仍UNRESOLVED。
因此验证了I/O调用点的提取，未验证完整修复入口定位、根因耗时或修复效果。
