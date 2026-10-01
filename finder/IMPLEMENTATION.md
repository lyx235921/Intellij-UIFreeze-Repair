# Finder 实现与证据

2026-09-29 Huawei exclusion (user-authorized, uncommitted): `find_sources.locate_record` returns None before source lookup when any parsed thread frame has package com.huawei.; main omits the whole record and logs SKIPPED_HUAWEI_CLOSED_SOURCE to stderr. Full-test coverage expectation excludes these rows. Explicit excluded --row is present, not missing. Raw intake and old artifacts unchanged.
Verification: portable layout-python, dependency overlay `C:/Users/Administrator/AppData/Local/Temp/finder-source-deps-wheel-20260926`, unittest discover `finder/Test` patterns `test_source_locator.py` (12 pass) and `test_real_stack_input.py` (4 pass). Bootstrap: `python -B -c "import sys,unittest;sys.path.insert(0,'C:/Users/Administrator/AppData/Local/Temp/finder-source-deps-wheel-20260926');s=unittest.TestLoader().discover('finder/Test',pattern='test_source_locator.py');r=unittest.TextTestRunner().run(s);sys.exit(not r.wasSuccessful())"`. Initial unoverlaid run failed known tree-sitter version gate; overlay run passes. Streaming saved `out/edt-freeze-finder/full-repair-20260928/finder.jsonl` through exclusion function:5891 checked,1009 excluded (each verified locate_record(record,None) returns None),4882 retained. No full source re-location or Repair rerun. Research43be46f9 unchanged. Next: regenerate Finder output for future Repair batches; closed-source paths including3587 are excluded by policy.

2026-09-19 当前授权切片：[检测链路接通实施与验收](DETECTION-INTEGRATION-2026-09-19.md)。状态“检测链路接通并通过约定验证”，工作树未提交；共享快照核心及v4全链已实现，定向123/123，最终补充44 tests含1平台跳过，20项新增接线均通过。旧全量310 tests曾12失败，其中2迁移夹具问题经37 tests修正，10既有失败原代码已复现；以下旧检查点不认证本轮工作树，最终状态以PROGRESS为准。

当前路由核对：2026-09-18。唯一入口：[PROGRESS](../PROGRESS.md)，活动计划为[C2C完整计划](../repair/docs/reports/C2C-NEXT-STEPS-2026-09-17.md)。P0已`GREEN_UNCOMMITTED`：定向Finder57/57、admission11/11，完整Finder48/48、admission32/32，5891×3记录比较与9个篡改控制通过；命令和边界见[实施记录](../repair/docs/reports/C2C-IMPLEMENTATION-2026-09-17.md)。P1-A仅局部角色识别开发中，未运行其新测试；P2独立案例0。9.2B和Stage3保持暂停；下方历史能力不另立活动路线。

历史检查点（2026-09-15）：Task 9.2A 经[独立验收](../repair/docs/reports/TASK9-2A-INDEPENDENT-REVIEW-2026-09-15.md)通过为 TASK9_2A_ACCEPTED_UNCOMMITTED / CONTROLLED_WAIT_MECHANISM；当时模块全类18项（14通过/4 Unix skip）、exit0。原Task9与9.2B描述不认证当前工作树。
**读取条件：** 修改/调用 Finder、复核检测能力或执行其回归时读取；自动修复工作不依赖检测器时跳过。
Finder 的 Effect Candidate 仍保持 `EXPERIMENTAL/REVISE`，Stage 3 不恢复。下方为原进度记录迁入的能力基线；其中 T1-T9 Task 0-6 的推进要求属于历史记录，不是当前任务。本次独立定向/反例与制品核验见第四次报告；Finder 全套未重跑。

## 实现入口

主检测链与真实堆栈处理链的 14 个真实实现统一位于 [`main/`](main/)；Finder 根目录不再保留同名兼容实现或 Python 测试代码。

| 能力 | 文件或符号 |
|---|---|
| Java 检测与建议 | [main/finder.py](main/finder.py)：`analyze_file(path)`、`recommend(result)` |
| 线程分类与规则 | [main/edt_classify.py](main/edt_classify.py)、[main/rule_registry.py](main/rule_registry.py) |
| 有界 effect 候选 | [candidate_discovery.py](candidate_discovery.py)：`discover_effect_candidates(paths, analysis_budget=...)`；CLI `--effect-candidates` |
| 置信度与报告 | [main/confidence_model.py](main/confidence_model.py)、[main/problems_report.py](main/problems_report.py) |
| 语料来源与评估 | [sealed_curator.py](sealed_curator.py)、[sealed_corpus.py](sealed_corpus.py)、[sealed_transfer_runner.py](sealed_transfer_runner.py) |
| 运行与回归命令 | [使用说明](README.md) |
| 旧七类工作簿路由 | [main/workbook_router.py](main/workbook_router.py) |
| Finder-Repair 共享证据 | [通用闭环计划](../FINDER-REPAIR-INTEGRATION-PLAN.md)；Finder识别错误并提供线程、阻塞、锁路径及堆栈来源，不决定 repair 准入 |
| 已完成的真实堆栈基线 | [T1-T9 真实堆栈实施计划](FINDER-T1-T9-REAL-STACK-IMPLEMENTATION-PLAN.md)：Task 0-6，真实 Excel、当前源码、无编译；当前任务见 PROGRESS |

## 复用边界

- 最近记录的完整 Finder 回归为 96/96；这是历史工程回归，不是修复准确率或召回率，本次未复验。
- [2026-09-09 能力复核](../repair/docs/read-write-lock/FINDER-CAPABILITY-CHECK-2026-09-09.md)：CASE-020 历史 before=1 / after=0，当前生产目标=0；作用域识别有效，历史切片的线程/EDT 影响仍 UNKNOWN。
- 检测与建议不等于安全补丁；候选证据、预算和 `COMPLETE/TRUNCATED/UNRESOLVED` 必须保留，六因子 UNKNOWN 不转成 NO，问题置信度与修复置信度分开。
- 旧七类工作簿分类属于 Finder；S1-S5 修复器族及其独立路由不属于 Finder。
- T1-T9 是线程证据，不与 S1-S5 一一映射；`unknown` 必须原样交给路由层并导致缺证或拒绝。
- Finder 输出 `identified_problem`；融合层再选择通用 Pattern，最后由 repair 路由到 S1-S5 和 method。三层字段不得合并为一个 family 标签。
- 2026-09-11通用闭环已对真实Excel 5,891条完成确定性源码测试5/5；FQN解析与路由无案例类名/行号白名单。[验证记录](../repair/docs/reports/FINDER-REPAIR-INTEGRATION-VALIDATION-2026-09-11.md)
- 已消费 sealed package 永久作为 development；不得重跑并声称 unseen evaluation。原实现计划保持不变，历史任务和恢复前提见下面的能力记录与链接。

## 已有能力基线（迁入记录）

以下“当前”和 Green 均指原记录时点；具体命令和证据以链接报告为准。这里只归纳实现，没有修改链接中的计划。

### 阶段 1：Java Finder MVP ✅ 7/7

- [x] 用 tree-sitter 解析 Java，并通过 `analyze_file()` 输出结构化结果。
- [x] 复用 T1–T9，将方法分为 EDT、BGT、unknown。
- [x] 识别派发 lambda 的有效线程上下文。
- [x] 检测 `saveAllDocuments()`，按下游依赖推荐方案 A/B。
- [x] 补齐 Fix008 的 VFS 刷新依赖打分。
- [x] 用 CASE-023 增加类型化 `SvnVcs.getInfo()` 检测和策略 C（缓存/快照替代）。
- [x] 在 CASE-023 真实修复片段上达到 before=3、after=0；构造器命中保留为 `unknown`。

**阶段出口**：至少两条真实纵向切片完整贯通“真实案例 → 检测 → 线程证据 → 建议 → before/after 测试”，且全部测试有 Green 提交。

### 阶段 2：Java 检测泛化 ✅

- [x] 扩展 Java EDT 入口和调用链传播，但保留 direct / propagated / unknown 的证据区别；CASE-004 已实现受限同文件传播（private/static/final 唯一解析）。
- [x] 从社区案例扩展阻塞家族：磁盘/VFS、外部进程、网络、锁与其他主要类别；CASE-020（`READ_ACTION_MISUSE`）、CASE-027（PSI_RESOLVE_INDEX + 可取消）、IJPL-244497（`HEAVY_IN_UPDATE`）、IDEA-388699（`UI_FROM_NON_EDT`）已落地。
- [x] 将阻塞 API、线程证据和修复策略从硬编码清单整理为可维护模型；推荐决策（recommendation_status）与修复策略（repair_strategy）已拆为两轴，recommend() 改为渲染表单一派发。
- [x] 用证据账本建立 Java 黄金集，记录真阳性、误报和漏报原因；20 条 development 观测 + 2 条 evaluation 观测已进入版本控制。

**设计基线**：[`STAGE2-DESIGN.md`](../finder/docs/STAGE2-DESIGN.md)。执行线程与 EDT 影响路径分开建模；BGT 不自动等于安全；阻塞 API 要求 receiver/type 或可追溯的平台契约证据；阶段 2 必须通过受限的真实 Java 调用链案例实际产出 `propagated`；阶段 3 之前不引入未定义的聚合指标 seam。首批候选规则为 `EDT_BLOCKING`、`UI_FROM_NON_EDT`、`READ_ACTION_MISUSE` 和 `HEAVY_IN_UPDATE`，重叠命中同时记录 `primary_rule` 与 `matched_rules`。

**阶段出口**：Finder 不再只对少数教学 fixture 有效，能在黄金集上稳定复现多个阻塞家族，并能解释每次命中的线程依据。

### 阶段 3：置信度与评估 ⬜

**实施计划**：[`STAGE3-IMPLEMENTATION-PLAN.md`](../finder/docs/STAGE3-IMPLEMENTATION-PLAN.md)。

**Task 0 工作树状态**：`finder/confidence_model.py` 已冻结六因子 tri-state、问题/修复分数载荷、候选解释和安全关键因子约束；Finder CLI 已能把需处理的命中安全 upsert 到 `notes/problems.xlsx`；报表测试改用 `fixtures/reporting/problems-template.xlsx`，不再复制可变真实清单。当前 38/38 tests Green，尚未形成 Git 检查点，因此不勾选阶段条目。

**高召回前置轨道**：暂停计划为 [`EFFECT-CANDIDATE-IMPLEMENTATION-PLAN.md`](../finder/docs/EFFECT-CANDIDATE-IMPLEMENTATION-PLAN.md)。Tasks 0–5 已实现 Source/Callable、MethodEffectSummary、有界 CallEdge、LifecycleReachability、development oracle 和 `--effect-candidates` opt-in CLI；证据/model/预算/截断契约已迁移为 `SYNTAX_HINT/SOURCE_RESOLVED/SEMANTIC_MODEL` 与 `COMPLETE/TRUNCATED/UNRESOLVED`，source-set 共享 depth/node/edge/timeout 预算，development before 为 `SEMANTIC_MODEL/COMPLETE`。Task 5.5 已实现不导入 analyzer 的通用 `preflight_sealed_package(path)`、强制 selector `YES/YES` precheck，以及 Git-native `materialize_git_package(request, destination)`；curator 只从 Git commit/tree/blob 对象生成 provenance、fixture 和 hash，不读取 working tree 或 analyzer。synthetic contract 16/16、Git curator 8/8、全量 86/86 tests Green，仍未形成 Git 检查点。

**Task 5.5 真实 readiness**：早期 32 个 blind 候选没有 READY；首个 staged 包被独立 auditor 以 provenance mismatch 与 after lifecycle reachability remains 拒绝。引入 Git-native curator 后又 blind 筛选 88 个新记录，并从剩余高可能性集合获得 `opaque-final-c9d8e2f1`。不同 signer auditor 的 parent/provenance/lifecycle/eager-before/after-mitigation/independence/dispatch/source-closure 八项 gate 全部通过；neutral evaluator canary 与 `preflight_sealed_package(path)` 返回 READY。包已复制到 checkout 外 `E:\coze\edt-freeze-finder-sealed\opaque-final-c9d8e2f1` 并二次复验，`package_sha256=0b9a6165095a563782512b39e51441b05576ad55acda90728f9b876a044b34b1`。一个 READY 包只允许 Task 6 feasibility canary，不构成 recall 估计。Stage 3 confidence oracle 在有效 Task 6 canary 前继续暂停。

**Task 6 sealed transfer**：production analyzer 五文件 hashes 冻结后，blind leakage audit PASS，challenge-specific overlap 全部为 0；development/micro 基线 18/18 + 3/3 Green，package 在 analyzer import 前再次以相同 SHA-256 READY。one-shot runner 只调用 packaged evaluator 一次，协议为 before、重复 before、after；结果 deterministic，`before=0`、`after=0`，candidate/KLoC=0.0，五文件 hashes 不变。packaged evaluator 的弱 canary 因 deterministic + after empty 返回 true，但 Task 6 必需的 `before=1` 失败，最终为 `TRANSFER_CONTRACT_FAILURE`。runner 在 empty-before 指标派生时把异常误标为 `EXECUTION_FAILURE` 并丢失 per-call timing；只读 postmortem 在不重跑 production 的前提下纠正语义分类。完整证据见 [`EFFECT-CANDIDATE-EVALUATION.md`](../finder/docs/EFFECT-CANDIDATE-EVALUATION.md)。该 package 已被消费，不能再作为 unseen evaluation 重跑。

**Task 7R bounded REVISE**：用户批准 one-cycle、pre-REVISE 五组 binary patch checkpoint、consumed package 永久转 development、版本化 runner、一个最小缺口和 fresh-canary stop gate。诊断发现 consumed case 属于不同 effect family，并同时暴露 call typing、external receiver、candidate multiplicity/lifecycle precision 等独立缺口；用户选择不扩展 analyzer，而是收紧 sealed transfer eligibility。`validate_transfer_eligibility(path)` 只接受当前已支持的 KeyedLazy semantic target；legacy READY 仍可 preflight 但不可 evaluation。Git curator 与 runner 都在 analyzer/evaluator 前强制该 target。consumed case 永久标记 `OUTSIDE_CURRENT_LANE / UNSUPPORTED_EFFECT_FAMILY`，当前 lane deterministic 0/0。eligibility 19/19、curator 9/9、runner 4/4、consumed 2/2、全量 96/96 Green；五个 analyzer hashes 未变。最终 blind selector 仅发现 1 条新记录且 target 不匹配，未 fetch/封包/audit/evaluate；按 stop gate 结束为 `EXPERIMENTAL/REVISE`。详见 [`EFFECT-CANDIDATE-REVISE.md`](../finder/docs/EFFECT-CANDIDATE-REVISE.md)。

- [ ] 接入导师提出的六因子：上游依赖 3 项、下游影响 3 项。
- [ ] 区分“问题置信度”和“修复置信度”，避免把发现阻塞等同于可以自动修。
- [ ] 冻结黄金集和 precision/recall 评估方法，再确定可接受阈值。
- [ ] 将推荐结果与真实开发者 commit 的修复策略进行一致性比较。

**阶段出口**：每条建议都有可追溯证据和分数；阈值来自黄金集评估，而不是主观设定。

## 已完成与正在进行的纵向切片

| 切片 | 真实案例 | 新增能力 | 状态 | 证据 |
|---|---|---|---|---|
| 第一切片 | `saveAllDocuments()`，含 Fix008 | EDT/BGT 分类、方案 A/B、VFS 下游依赖 | ✅ Green | `0f4196baf6`；Finder 测试通过 |
| 第二切片 | CASE-023 / IJPL-245647 | 类型化 `SvnVcs.getInfo()`、策略 C、缓存替代、构造器扫描 | ✅ Green | `aa740f620b`；真实 before=3、after=0 |
| 第三切片 Cycle 1 | CASE-011 / IJPL-248581 | 类型化 UI 服务冷初始化、规范结果字段、unknown 候选不升级 | ✅ Green | `267b0b3596`；真实 before=1、after=0 |
| 第三切片 Cycle 2 | CASE-011 / IJPL-248581 | BGT 冷初始化到 EDT 的间接锁竞争 | ✅ Green | `2cda75d8d8`；冷初始化与普通 BGT IO 正反例通过 |
| 阶段 2 基础设施 | Fix008、CASE-023、CASE-011 | 21 列 Java 黄金集契约和分组执行 Oracle | ✅ Green | 10 条 development 观测；Finder 11/11 通过 |
| 第四切片 | CASE-004 / IDEA-390239 | 受限同文件线程证据传播：`propagated`（private/static/final 唯一解析，冲突/切换保持 unknown） | ✅ Green | `f2c10dd0a1`；真实 before=1，冲突/切换控制通过 |
| 阶段 2 重构 | 全案例 | 推荐决策与修复策略拆为两轴（`recommendation_status` + `repair_strategy`），`recommend()` 单一派发 | ✅ Green | `2fa6da060b`；14/14 通过 |
| 第五切片 | CASE-020 / IJPL-235455 | 读锁作用域识别 + `READ_ACTION_MISUSE`（`processQueues` 移出读锁；延迟派发打断读锁作用域） | ✅ Green | `7f87a30c55`；真实 before=1、after=0，短读锁负例、EDT 重叠、BGT 间接路径通过 |
| 第六切片 | CASE-027 / IDEA-388795 | PSI_RESOLVE_INDEX + 可取消进度包装抑制（`createSnapshot` 包裹后可取消，否则报 `EXPENSIVE_EDT_COMPUTE`） | ✅ Green | `bee03a2142`；真实 before=1、after=0 |
| 第七切片 | IJPL-244497 | `HEAVY_IN_UPDATE` 规则 + 重叠报告（update() EDT + 昂贵操作 → [EDT_BLOCKING, HEAVY_IN_UPDATE]）；修复 scanner T1 误把 BGT-update 判为 EDT | ✅ Green | `47cc030aac`；真实 before=1（HEAVY_IN_UPDATE）、after 未分类、BGT 负例通过 |
| 第八切片 | IDEA-388699 | `UI_FROM_NON_EDT`（BGT 上改 UI → 线程安全违规，与 freeze 计数分离；`onSuccess` 回调归 BGT） | ✅ Green | `c9bbaa0fb7`；真实 before=1（UI_FROM_NON_EDT）、after=0、线程安全负例通过 |
| 阶段 2 收尾 | CASE-021 / IJPL-246986（evaluation） | 确定性输出 + 评估样例冻结；FN 记录：`ConfigurableWrapper.cast` 冷初始化未泛化（留待 Stage 3） | ✅ Green | 原记录为“本提交”，具体哈希待工位核对；24/24 通过；smoke 38 文件 25 命中（EDT=10/BGT=7/unknown=10） |
