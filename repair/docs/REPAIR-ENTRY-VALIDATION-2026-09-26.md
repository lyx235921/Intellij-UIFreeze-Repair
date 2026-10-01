# Repair 新总入口验证 — 2026-09-26

活动入口 repair/main/python/repair.py。仅用Python标准库接收finder-source-locations/1 JSONL，输出repair-intake/1，完整保留Finder对象。

## 验证

- 新入口测试：7 tests OK，exit0。覆盖真实第2行输入、候选保持、版本/类型/哈希错误、引用与路径异常、重复记录、损坏JSON继续读取、部分证据、CLI退出码/禁止覆盖/空输入。
- 实际Finder全量输入：5891条ACCEPTED，0 REJECTED，CLI exit0。
- 独立逐条对比：5891条输出的finder对象与输入对象相等，repair_status全部NOT_STARTED，source_verification全部NOT_PERFORMED。
- 没有重新运行Finder，没有读取/修改生产源码，没有选定修复点或生成补丁。旧Repair测试依赖已删除实现，本次未运行旧全套测试。

## 精确命令

工作目录 tools/edt-freeze-finder；便携解释器不需要tree-sitter覆盖或任何新依赖。

```powershell
& 'D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe' -B repair/tests/test_repair_entry.py
& 'D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe' -B repair/main/python/repair.py --input 'C:/Users/Administrator/AppData/Local/Temp/finder-full-state-20260926-run2/sources.jsonl' --output 'C:/Users/Administrator/AppData/Local/Temp/repair-intake-20260926-run1.jsonl'
& 'D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe' -B -c "import json,itertools; a=open('C:/Users/Administrator/AppData/Local/Temp/finder-full-state-20260926-run2/sources.jsonl',encoding='utf-8');b=open('C:/Users/Administrator/AppData/Local/Temp/repair-intake-20260926-run1.jsonl',encoding='utf-8');n=sum(1 for i,o in itertools.zip_longest(a,b) if (r:=json.loads(o))['finder']==json.loads(i) and r['intake_status']=='ACCEPTED' and r['repair_status']=='NOT_STARTED' and r['source_verification']=='NOT_PERFORMED');assert n==5891,n;print('Preserved Finder records:',n)"
```

输出文件必须不存在，重跑请换新路径。临时输出路径不保证跨系统清理保留。

## 接收边界

ACCEPTED只说明入口合同校验通过；不是根因/源码身份/修复准入判定。PARTIAL/FAILED原解析状态、歧义及候选均保持原样。
入口校验所需结构和跨引用，不自建通用JSON Schema验证器；不认证输入工作簿来源，也不核验源码当前哈希。
进程I/O错误可能留下部分输出，必须检查退出码。单条错误有REJECTED及errors，继续处理后续行；存在拒收或空输入返回2。
后续第6～7步待用户指定，不恢复历史策略实现。

research HEAD复核仍83a21329f4f811fca1b5a4a555eb6504f2ff4d78；无新增资料阅读。未提交Git。