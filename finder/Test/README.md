# Finder 测试

- test_real_stack_input.py：4 项输入解析测试。
- test_source_locator.py：11 项源码定位/调用候选/CLI 测试（临时源码与工作簿，不改生产文件）。
- test_source_locator_real.py：1 项当前仓库与真实工作簿第2行集成测试，无mock。
- verify_real_output.py：独立检查完整JSONL的记录/帧引用、源码文件SHA-256、行范围与调用表达式；参数为JSONL路径。

安装 ../main/requirements.txt 后运行：`python -B -m unittest discover -s finder/Test -p 'test_*.py'`（工作目录 tools/edt-freeze-finder）。
实际工作簿及源码集成测试要求当前 checkout 和仓库根目录的 intellij底座问题堆栈-1.xlsx 可读，不静默跳过。
fixtures/、golden/、__pycache__/ 是此前保留的旧资产，不纳入新定位器测试结论。

## 全量重跑与 state 统计

`run_full_test.py` 直接调用 find_sources.main，不传 --row，覆盖全工作簿；随后执行 verify_real_output，并重新读取工作簿逐条核对记录ID、堆栈哈希和出现次数，检测漏行、重复或输入变化。

```powershell
python -B finder/Test/run_full_test.py --workbook D:/intellij-community-master/intellij底座问题堆栈-1.xlsx --source-root D:/intellij-community-master --output-dir D:/intellij-community-master/out/edt-freeze-finder/full-state-run
```

必须使用 main/requirements.txt 中的依赖；--output-dir 必须是不存在的新目录。输出 sources.jsonl、finder.log、report.json；失败也记录 FAILED 和错误，不把部分结果认定为全量成功。
`test_state_statistics.py` 新增4项测试：同状态多线程去重、UI/致因角色不重复计数、非法次数/重复记录拒绝，以及真实CLI函数运行/校验/统计/禁止覆盖。

report.json 中 statistics：

- thread_states 分 all_threads、ui_threads、cause_threads；分别统计线程 state，例如 WAITING、RUNNABLE。
- thread_entries：线程条目数；同一线程在 threads 只计一次，不累加角色引用。
- records：包含该state的记录数；同一记录内多个同state线程只计一次。
- weighted_thread_entries：每个线程条目按原表 occurrences 加权。
- weighted_records：每条包含该state的记录按 occurrences 加权一次。
- 不同state的records可重叠；不同scope也是重叠集合，不能相加当作总记录数。加权结果不是耗时，也不证明独立卡顿事件数。
- parse_statuses：按记录统计；source_statuses：按栈帧统计；call_edge_statuses：按相邻调用边统计。它们与线程state分开记录。

report.json 还保存完整命令、UTC开始时间、耗时、依赖版本、工作簿及实现/验证脚本SHA-256、完整输出位置和独立校验结果。