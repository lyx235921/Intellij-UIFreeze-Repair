# Finder 第1～5步验证 — 2026-09-26

实现：main/find_sources.py + main/source_locator.py，复用 main/real_stack_input.py。只读源文件，未改 IntelliJ 生产代码或 Repair。
职责：输入完整性、线程、定位入口、当前源码声明、相邻调用表达式候选。类型绑定/根因/修复位置不在本次实现范围。

## 最终验证

- 16项 unittest 全部通过，0失败/错误/跳过，exit0；其中1项直接读取真实工作簿和当前源码，无mock。
- 全表CLI exit0：5891条、7958次出现，604630个帧。
- 帧结果：LOCATED 69232；CANDIDATE 100086；AMBIGUOUS 8001；UNRESOLVED 427311。
- 相邻调用：CALL_SITE_CANDIDATE 120147；UNVERIFIED 475596。
- 索引错误0，按文件名按需读取2238个源码文件。
- 独立JSONL核验exit0：记录和帧ID引用、原堆栈哈希、状态统计、selected属于候选集、调用表达式位置、声明行范围，以及1567个被引用源码文件SHA-256全部一致。
- 第2行：actionsUpdated(forceRebuild: Boolean, ...) 为候选；完整保留1225行 removeAll() 和1226行 mySecondaryActions.removeAll()，不做接收者类型绑定，不替Repair选择。
- 完整最终输出：C:/Users/Administrator/AppData/Local/Temp/finder-source-f7c3f41272c14ded9108415420548280/all-final.jsonl（735898995 bytes）。临时文件不保证跨清理保留；仓库中保留第2行完整样例 docs/row2-output.json。

## 精确验证命令（工作目录 tools/edt-freeze-finder）

本机便携Python原有tree-sitter 0.26.0在TransactionGuardImpl.java AST遍历时发生原生access violation。
在临时依赖目录解压PyPI tree-sitter 0.25.2的cp312/win_amd64 wheel，未修改共享运行时；固定依赖见main/requirements.txt。
CLI拒绝不匹配的tree-sitter版本，以避免已知崩溃。两个无输出的pip尝试已停止；最终使用urllib下载官方wheel。

```powershell
$py = 'D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe'
& $py -B -c "import sys,unittest;sys.path.insert(0,'C:/Users/Administrator/AppData/Local/Temp/finder-source-deps-wheel-20260926');s=unittest.TestLoader().discover('finder/Test',pattern='test_*.py');r=unittest.TextTestRunner(verbosity=1).run(s);sys.exit(not r.wasSuccessful())"
& $py -B -c "import sys,runpy;sys.path.insert(0,'C:/Users/Administrator/AppData/Local/Temp/finder-source-deps-wheel-20260926');sys.argv=['find_sources.py','--workbook','D:/intellij-community-master/intellij底座问题堆栈-1.xlsx','--source-root','D:/intellij-community-master','--output','C:/Users/Administrator/AppData/Local/Temp/finder-source-f7c3f41272c14ded9108415420548280/all-final.jsonl'];runpy.run_path('finder/main/find_sources.py',run_name='__main__')"
& $py -B finder/Test/verify_real_output.py 'C:/Users/Administrator/AppData/Local/Temp/finder-source-f7c3f41272c14ded9108415420548280/all-final.jsonl'
```

输出禁止覆盖，重跑需换新路径。正常安装requirements的Python环境可直接使用README命令，不需要临时sys.path覆盖。

## 输出契约与边界

docs/OUTPUT-FORMAT.md、docs/output.schema.json、docs/row2-output.json共同记录版本finder-source-locations/1。
JSON Schema已检查为合法JSON；全表独立校验覆盖关键字段与跨引用不变量，未运行第三方JSON Schema验证器。
Java AST声明唯一时LOCATED；Kotlin词法匹配、相邻调用名帮助缩小的重载均为CANDIDATE。调用名一致仅产生CALL_SITE_CANDIDATE。
不支持的生成类、协程、属性访问器、Kotlin表达式体/扩展函数及缺失源码保持UNRESOLVED；多源码/重载保留AMBIGUOUS。
源码索引排除测试、fixtures、evidence、构建输出等目录；外部JDK源码未导入。统计是对真实栈的定位覆盖，不是准确率或已证实卡顿数量。
旧行号不用于强行解除歧义；没有检查运行时版本身份。Kotlin词法分析不提供AST/类型保证。

## 修正与研究预检

全表核验发现Kotlin多行接收者起始行错误，已修正并新增回归测试、重新全扫、重新独立核验。
remote research HEAD仍83a21329f4f811fca1b5a4a555eb6504f2ff4d78，无新增阅读，历史未读保持未读。
Tree-sitter API参考Context7 /tree-sitter/py-tree-sitter；无可用IDE lint工具。只改Python/文档/JSON，不需要JVM编译。
