> Historical plan, superseded on 2026-09-27 by [the implemented candidate patch and tests](P1-RELOAD-PATCH-2026-09-27.md). The new preparation point is after VFS event application, before document commit.

# P1 文档重载方案生成器

2026-09-27：P1PreloadBeforeCriticalRegion.kt 新增 propose(finder,q1,root)，Python新增 --s1-p1。本阶段输出源码绑定的候选方案，不是可执行补丁。早先拟议直接异步化reloadFromDisk没有实施，因为同步API、事件顺序及内容解码语义尚未核验完整。

识别不绑定Excel行号。要求Q1通过且命中GetFileAttributesEx/Ex0，并在同一线程连续栈路径依次经过Files.size、readIfNotTooLarge、LoadTextUtil.loadText、setNewText、reloadFromDisk；缺口或不匹配拒绝。调用方源码按已核验完整文件SHA256验证路径/版本。模板提供prepareChange、contentsChanged、reloadFromDisk、setNewText完整上下文，标记为模板扩展定位，不冒充五层提取器结果。

输出 `q1.s1_p1`：schema repair-s1-p1-plan/1；status CANDIDATE_PLAN/NOT_APPLICABLE/UNAVAILABLE；patch_generated=false、applied=false；stack_evidence、source_contexts、steps、unresolved_conditions。readiness固定阻塞于快照和解码契约。check()的保守条件报告保持原行为；repair_selection尚不将此计划当成可选补丁。

计划选用已有MyAsyncFileListener.prepareChange作为提前准备边界，保持reloadFromDisk公开同步行为：识别事件与目标文档→读取有大小限制的新内容→不可变事件级payload→应用前验证身份/版本→原命令/写动作内提交→完成通知和清理。避免在EDT Future.get/join，也不直接把整个reloadFromDisk搬到线程池。

依据当前AsyncFileListener.java线程契约，prepareChange在后台读动作运行；但它先于VFS事件应用，普通VFS内容缓存可能仍旧。不能直接在此LoadTextUtil.loadText后假定拿到新内容。还须确定新磁盘内容与事件的对应关系、重复事件/重试、取消和内存上限；区分纯解码与当前BOM/charset副作用；定义过期/失败处理。同步回退可保留旧行为，但不能声称所有分支消除卡顿。

未生成Java替换正文或candidate.patch，未修改生产源文件，未运行IDE重载行为/卡顿测试。当前测试只验证方案生成与拒绝边界，不验证线程、版本、完成时序已正确实现。

验证：build-q1.ps1 exit0；六组24测试通过，无跳过。新增真实4746、UI等待、栈缺口、不相关调用路径、源码版本变化拒绝；CLI真实4746 exit0返回CANDIDATE_PLAN。输出out/edt-freeze-finder/p1-row4746-20260927/{repair.jsonl,plan.json}。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH = (Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw).Trim()
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input repair/tests/fixtures/row4746-finder.json --output out/edt-freeze-finder/p1-row4746-20260927/repair.jsonl --q1-classpath $env:Q1_CLASSPATH --s1-p1
@'
import sys,unittest
sys.path.insert(0,'repair/tests')
r=unittest.TextTestRunner().run(unittest.TestLoader().loadTestsFromNames(['test_p1_plan','test_repair_selection','test_repair_entry','test_extract_method','test_p2_relocation','test_q2_classifier']))
sys.exit(not r.wasSuccessful())
'@ | D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -
```

输出父目录须存在；重跑更换排他创建的输出路径。后续必须补齐快照/解码契约并实现测试后才能升级为CANDIDATE_PATCH。没有把未知自动判为安全，也没有把P1计划冒充已修复案例。
