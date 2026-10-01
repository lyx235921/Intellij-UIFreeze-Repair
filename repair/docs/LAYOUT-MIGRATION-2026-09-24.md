# Repair 目录统一：2026-09-24

当前进度只由[项目 PROGRESS](../../PROGRESS.md)维护；本报告记录目录变更、守恒核查与验证，不建立另一份任务队列。

## 布局与入口

所有活动源码、演示、归档工具和脚本归入 main；Python、PowerShell、Kotlin 测试及 fixtures 统一归入 tests。
Kotlin 包名与生产/测试模块名称保持不变。V1 与 V2 的不同修复行为保留，分别由 main/kotlin 与 main/indexed-bucket-v2 下的构建入口调用。
原根目录 Python 文件不保留第二份副本或兼容转发。跨目录资源、配方、调用者、模块登记和测试数据路径随迁移更新。

原 IMPLEMENTATION 中的当前状态、阻断点与下一步已同步到 PROGRESS；完整阶段记录保留于[历史归档](history/IMPLEMENTATION-2026-09-24.md)。报告中的历史命令保留执行时语境；重跑使用[当前入口说明](../README.md)及[旧路径映射](layout-migration-2026-09-24.json)。

## 文件守恒

迁移前共542文件。逐文件 SHA-256 与新路径记录在迁移清单；其中168个历史快照文件收进5个 ZIP，压缩后逐项读取并核对原SHA才移除展开副本。已有ZIP、配方、契约、冻结fixtures及证据内容不改写。
历史快照不是可编辑源码入口。测试实际需要的历史输入放入 tests/fixtures，保留其归档来源和哈希。
原工作树状态与迁移前清单保存在 `out/edt-freeze-finder/repair-layout-2026-09-24/before-status.txt`、`before-files.json`。

## 验证记录

日志均在 `out/edt-freeze-finder/repair-layout-2026-09-24/`。

- `node --test build/jps-module.test.mjs`：17/17通过。新增 --replace-missing 只替换已缺失的同名旧模块登记，拒绝仍存在的同名模块；check模式不写文件。
- `build/jps-module.cmd register tools/edt-freeze-finder/repair/main/kotlin/intellij.tools.readWriteLock.repair.iml tools/edt-freeze-finder/repair/tests/kotlin/intellij.tools.readWriteLock.repair.tests.iml --fix-iml-eof --replace-missing`：exit0。
- 同两模块 `build/jps-module.cmd check ... --fix-iml-eof`：canonical，exit0。
- `build/jpsModelToBazel.cmd`：exit0，生成分离生产/测试模块的BUILD；删除旧模块BUILD。见 jps-to-bazel.log。
- `out/edt-freeze-finder/layout-python/python.exe out/edt-freeze-finder/repair-layout-2026-09-24/verify_layout.py`：初检542/542可追溯，168归档成员哈希一致，无main/tests外散落代码，两个模块登记唯一。
- `tools/edt-freeze-finder/maintenance/bazel-format-check.cmd`：exit0，执行项目 Windows 入口的 `bazel run ... //:format.check`，见 format-check.log。
- 两组 PowerShell 测试通过：`powershell.exe -NoProfile -File tools/edt-freeze-finder/repair/tests/test_stable_identity_contract.ps1`（21案例、45合成检查）与同目录 `test_action_toolbar_runtime_attribution.ps1`。四个Python直接入口 --help 均exit0：repair_s1_from_stack、repair_ast_m1、repair_ast_v2、prepare_string_lexer_case，日志在 python/。
- `tests.cmd --module intellij.tools.readWriteLock.repair.tests --test 'org.jetbrains.research.lockrepair.*'`：243项，235通过、6失败、2跳过；其中4项因测试仍读取旧STACK目录而失败，已将7个运行时所需原样输入从ZIP提取到tests/fixtures并修正引用。
- `cmd.exe /d /c 'tests.cmd --module intellij.tools.readWriteLock.repair.tests --test "org.jetbrains.research.lockrepair.RealLexerRepairTest;org.jetbrains.research.lockrepair.FindXmlJsonProductionTest"'`：6/6通过，0失败/跳过；含全部4项路径失败的复验，和首轮XML等待写请求未观测到的复验。见 kotlin-path-regression-quoted.log。之前未保留CMD内层引号的多测试名调用在启动时失败，未执行测试，保留于 kotlin-path-regression.log。
- 仍有1项运行时实验断言失败：LockBoundaryRuntimeTest 的 `S1 hand fix freeze-time comparison on the EDT`。模拟load固定sleep 300ms，但断言要求5轮中至少3轮>=500ms；本次实测300–302ms。该文件迁移前后SHA均为 `e7d40cd39975af0d5bf4f2e17e8668408c1ed1315048eaf60688582b3924d1aa`。本轮未改其行为或断言，不能声称全量Kotlin Green。2项Replay测试按现有配置跳过。
- Finder调用方默认基线已指向 evidence/read-write-lock；导入后验证文件存在且JSON可解析通过。`git diff --check` exit0。
- V2真实进程CLI集成4/4通过，见 python/v2-cli-integration.log；首次沙箱调用无法写标准Bazel缓存，按CR-004提升同一调用后通过。`bazel.cmd run //tools/edt-freeze-finder/repair/main/kotlin:read-write-lock-repair -- methods` exit0，验证V1新标签可运行，见 python/v1-methods.log；CLI集成使用隔离测试副本，未修改IntelliJ生产源码。
- Python非JVM全量加载363项，但首类Task6的 `acceptance(runs=2)` 在5,891条工作簿源码定位阶段异常退出（Windows `-1073741819 / 0xC0000005`），没有unittest汇总。faulthandler堆栈位于 `shared/java_callable_locator.py` → `repair_admission._source_check`；shared实现本轮未改，尚不能确定崩溃根因，不能把它归因于迁移前状态。保留 python/unittest-non-jvm.log。
- 排除Task6的首轮加载350项、运行342项，11 failures / 10 errors / 2 skipped；详见 python/unittest-without-task6.log 和 python/python-failures.txt。已修复配方fixtures前缀重复、隔离Python缺失同目录导入、共享P0基线错误定位。后续只复验受这些修正影响的测试，不改历史期望值。
- 最终窄复验：MVP 19/19、聚类CLI负向1/1、S1/P1七组93/93通过；22个可执行Python入口逐一直接 --help 均exit0；P0共享基线5,891条及原SHA验证通过。分别见 python/mvp-focused-rerun.log、root-cli-negative.log、s1-p1-focused.log、python-cli-help-matrix.log。S1/P1七组是 test_p1_source_evidence、test_s1_source_binding、test_s1_source_context、test_s1_semantic_context、test_s1_dynamic_dispatch、test_s1_input_provenance、test_s1_critical_boundary_propagation；用README的bootstrap和 `unittest.defaultTestLoader.loadTestsFromNames([...])` 复现。MVP与聚类负向同样用该bootstrap加载 `test_repair_excel_mvp` 和 `test_root_cause_clusterer.ClusterSourceIdentityTest.test_cli_negative_exit_codes`。
- 未闭合的Python回归：AST V2 record结构、ContractFinder corpus非空判据、DryRun冻结计数、Cluster source_identity/源计数仍与旧期望不同。没有迁移前对照，不能断言与迁移无关。Finder SourceIndex遍历时过去会看见部分展开快照，归档后来源枚举改变是待核查解释；没有恢复旧源码副本、放宽门禁或改写冻结数字。首次语料运行的2项链接测试受当前Windows环境限制跳过。

## 最终状态

目录与运行入口切换已完成；全量研究验收仍有上述缺口，不能标记全量Green。Repair相关文档链接全部可解析，活动代码仅在main/tests；旧路径字符串仅保留于明确的冻结证据重定位表和历史资料。共享Finder基线及平台模块仍由其原有目录管理，不复制成第二份活动实现。

本轮只整理源码、测试和文档入口，不增加P1支持规则，也不证明真实UI卡顿修复效果。所有修改未提交，保留此前未提交工作。
