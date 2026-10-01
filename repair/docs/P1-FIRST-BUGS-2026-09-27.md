# P1 第一候选真实记录

2026-09-27，原工作簿只读扫描5891条非空记录；使用21个P1_FIRST精确方法符号和当前Q1分类器的UI RUNNABLE、非等待栈顶规则，得到588条去重Excel记录。计数不按occurrences加权；同一bug的独立身份未核验，不能将588条记录宣称为588种不同根因。

| 类别 | 去重记录 |
| --- | ---: |
| Q1.1 文件系统访问 | 310 |
| Q1.2 类／原生库加载 | 155 |
| Q1.3 索引和存储 | 119 |
| Q1.4 正则处理 | 4 |
| 合计 | 588 |

每方法去重计数合计1251，包含同一条栈上的多方法命中，不能当作记录总数。21个方法本轮均有命中。Q1.5–Q1.7在现有映射中无P1_FIRST方法，并非证明这些类别不能用P1。

完整逐记录行号/方法及每方法全部行号：`out/edt-freeze-finder/p1-first-20260927/BUGS.md`。机器可读报告report.json保留工作簿及映射SHA256；records.jsonl保留588条原始堆栈、匹配帧、UI检查结果及occurrences。

命令：`D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe out/edt-freeze-finder/p1-first-20260927/run.py`，exit0。脚本复用real_stack_input.read_records，给JVM分类器--count-only传入所需线程/帧标识；此最小分类输入不是完整finder-source-locations记录。本次不执行源码定位或Repair前置检查，不代表588条均可安全提前执行。重新运行需修改输出目录，records.jsonl排他创建。

核对：588条记录ID去重、21份方法行号列表与逐条列表双向一致、原栈记录行数一致，全部通过。未修改分类规则、修复器或原工作簿。research HEAD83a21329未变，无新增资料阅读。
