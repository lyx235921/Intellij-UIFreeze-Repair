# Finder：真实堆栈输入

输入入口：`main/real_stack_input.py`；完整第1～5步入口：`main/find_sources.py`。依赖见 `main/requirements.txt`。

从 tools/edt-freeze-finder 运行：

```powershell
& 'D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe' -B finder/main/real_stack_input.py --workbook 'D:/intellij-community-master/intellij底座问题堆栈-1.xlsx' --output 'D:/intellij-community-master/out/edt-freeze-finder/real-stacks.jsonl'
```

输出父目录必须存在，目标文件必须不存在；省略 --output 则输出到标准输出，汇总写入标准错误。

按工作表“问题线程堆栈”的同名列读取，按表头定位出现次数；超过 32767 字符且延续到紧邻无表头列的内容原样拼接。每条 JSON 保留 Excel 行号、次数、raw_stack、所有线程及全部栈帧。ui_threads 标记 AWT-EventQueue-N；cause_threads 只来源于原文 cause freeze thread 标记。problem 提取 topStack、problemModuleStack，root_cause 保留 null，不做机制分类或源码定位。无法识别的行保留，并以 PARTIAL/FAILED 和 diagnostics 暴露；PARSED 仅表示格式完整，不证明因果或根因。

测试：

```powershell
& 'D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe' -B finder/Test/test_real_stack_input.py
```

2026-09-26：4 项测试通过。上述真实工作簿 CLI 写入临时 JSONL 后逐行 json.loads 验证：5891 PARSED，出现次数 7958；原文合计 61315677 字符。覆盖直接 EDT、后台致因线程、缺失/未知行、表头重排和长单元格续列。尚未进行源码定位或根因分析。

Test/fixtures、Test/golden 是旧测试数据，Test/__pycache__ 为旧缓存；evidence/snapshots 保留重写前备份。根目录剩余旧分析实现不属于本次入口。当前任务见 ../PROGRESS.md。

## 职责边界（2026-09-26 用户确认）

Finder负责第1～5步：输入完整性检查、线程确定、源码定位入口选择、栈帧到源码映射、源码调用关系核对。输出线程/堆栈证据、源码位置、调用关系与定位状态、歧义。第1～5步现已实现；源码定位区分 Java AST 声明与 Kotlin 词法候选，调用关系核对仅产生调用表达式候选，未做接收者类型/重载语义绑定。

Repair负责第6～7步：确定卡顿相关位置、选择候选修复位置，以及后续修复设计和验证。Finder不负责选定修复点。

## 第1～5步运行方式

在已安装 requirements 的 Python 环境中，从 tools/edt-freeze-finder 运行：

```powershell
python -m pip install -r finder/main/requirements.txt
python -B finder/main/find_sources.py --workbook D:/intellij-community-master/intellij底座问题堆栈-1.xlsx --source-root D:/intellij-community-master --row 2 --output D:/intellij-community-master/out/edt-freeze-finder/row2-source.jsonl
python -B -m unittest discover -s finder/Test -p 'test_*.py'
```

省略 --row 处理全表；可重复 --row 选择多行。输出父目录须存在，输出文件须不存在。仅输入读取脚本不需要 tree-sitter。
必须使用 tree-sitter 0.25.2；本机原有0.26.0在真实Java AST遍历中原生崩溃，入口会拒绝此版本。
本次未修改共享运行时，测试使用临时依赖覆盖，精确命令见 [验证报告](docs/SOURCE-LOCATION-VALIDATION-2026-09-26.md)。

输出合同：[字段说明](docs/OUTPUT-FORMAT.md)、[JSON Schema](docs/output.schema.json)、[真实第2行完整输出](docs/row2-output.json)。
Repair 必须区分 LOCATED / CANDIDATE / AMBIGUOUS / UNRESOLVED；CALL_SITE_CANDIDATE 不是类型解析后的调用边，不能直接当作修复点。