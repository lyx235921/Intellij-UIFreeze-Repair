# Q1.1 的 P2 覆盖统计

2026-09-27：对缓存 Finder 全量5891条逐条运行当前 Q1 `--count-only`，对其中全部678条 Q1.1 再运行 `--repair-selection`，重新核验当前源码并生成候选。未重新解析Excel，不宣称独立重现事故。

| P2_FIRST 方法 | 去重记录数 | Excel 示例行 |
| --- | ---: | --- |
| sun.nio.fs.WindowsNativeDispatcher.FindFirstFile0 | 250 | 124、125、127 |
| sun.nio.ch.FileDispatcherImpl.read0 | 7 | 1247、1248、1249 |
| sun.nio.fs.WindowsNativeDispatcher.FindNextFile0 | 2 | 1344、4384 |
| 去重合计 | 259 | 本次三个方法的记录集合无交叉 |

259条是P2优先分析候选，不是已证明可修复数量。其中258条在最多五层项目帧中找到至少一个哈希匹配的完整源码方法，1249未定位到；不保证其他258条每层都能定位。

这259条当前能被选择器选中现有P2补丁的数量为0。全部678条Q1.1中有3条（1806、1812、1813）选中已有AppIcon候选补丁，其命中为CreateFile0/DeleteFile0，属于CONTEXT_FIRST而不在本次三个优先方法中。候选补丁不是原始事故修复效果证明。

建议下一步从第124行 FindFirstFile0 的调用上下文确定可后台化的完整目录读取任务；不能由底层方法相同推断250条都可用同一补丁修复。本次没有扩展修复模板或修改生产源码。

执行：`D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe out/edt-freeze-finder/q11-p2-assessment-20260927/run.py`，exit0。脚本读取TEMP下repair-q1-build/classpath.txt，使用当前编译的分类器。逐行结果排他创建，重跑需更换输出目录或文件。证据：同目录 `report.json`（全部行号、方法数量、源码位置）、`cases.jsonl`（选择结果及候选补丁）。

输入：`C:/Users/Administrator/AppData/Local/Temp/finder-full-state-20260926-run2/sources.jsonl`。计数单位为Excel记录，不按occurrences加权，不按栈帧次数重复计数。
