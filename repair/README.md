当前调用链：Finder → repair.py → Q1ExpensiveWorkRelocationClassifier.kt。Q1 → S1 留待Q1设计完成后接入。S1.kt本次保持不变，不由repair调用。参数改为 --q1-classpath。

2026-09-26：Q1编译exit0、10项测试全部通过、0跳过；1807行实际调用仍返回468行Files.readAllBytes。
输出：C:/Users/Administrator/AppData/Local/Temp/s1-row1807-_8tlfexs/repair-q1.jsonl。
S1.kt前后SHA256一致：289f196d6334d15eed38ebd442046f6dd04c8b250fb94baf30c185298b9b1fda。
Q1尚不分类；输出额外含record_id、workbook_sha256、input、parse、source_root，每帧含thread_name、thread_state、thread_role、is_ui_thread。stdout固定UTF-8。

# Repair

S1 专用方法提取与修复选择位于 `main/kotlin/src/pool/s1_expensive_work/extract_method.kt` 和 `repair_selection.kt`，包名均为 `org.jetbrains.research.lockrepair.pool.s1`。CLI 参数保持不变。

## 缺失业务／插件源码时继续处理（2026-09-28）

`--repair-selection` 对每个命中分别处理：已有受验证模板候选正常返回；没有候选且五层上下文中
Finder 明确报告 `SOURCE_FILE_NOT_FOUND` 时返回 `SKIPPED_SOURCE_UNAVAILABLE`，继续同一行其他命中及后续行。
保留 `missing_source_contexts`（方法、文件和定位原因），不按插件包名屏蔽，不把缺源码视为 P1/P2 失败而启动 P3。
源码存在但方法未找到、定位歧义、哈希不符或栈缺帧仍保留原诊断，不自动认定插件缺失。
补入源码后重新运行 Finder 再进入 Repair；旧 Finder 输出的缺失结论不会自动刷新。
stderr 的 `source_skipped_points` 是跳过的命中帧数，`source_skipped_records` 是含跳过命中的记录数。
原始分类、Q1 计数及专用修复器评估保留。此跳过策略属于统一选择入口，专用 `--s1-*` 输出仍保留原前置检查结果。
验证及范围见 [源码缺失跳过报告](docs/SOURCE-SKIP-2026-09-28.md)。

## P1 路径／加载方法接入（2026-09-27）

`--s1-storage` 评估原五个存储方法及新增四个文件系统路径方法；`--s1-loading` 评估七个类／原生库加载方法。
二者需要 `--q1-classpath`，自动提取上下文；`--repair-selection` 自动路由这两组评估。
新增 11 个方法均已绑定，但目前只输出真实上下文及未满足的前置条件，不生成新补丁，UNKNOWN 不启动 P3。
存储旧参数 `--s1-q13` 保留兼容。详见 [P1 接入报告](docs/P1-BINDINGS-2026-09-27.md)。

## Q1.3 存储方法修复构造（2026-09-27）

`--s1-q13 --q1-classpath <classpath>` 自动提取上下文，逐项评估五个 P1_FIRST 存储方法。
`--repair-selection` 也已接入同一评估；选择器中的 `selected_proposal_pool=q13_evaluation` 引用专用候选。
目前 `readAttribute/readSymlinkTarget` 的异步刷新准备路径可共用一份 P2 候选；
`getName/getNameByNameId/getFileInfo` 尚无安全模板，返回证据不足，不自动转 P3。
输出不应用生产补丁。25 项相关测试通过，真实 IDE 验证未完成。
详见 [构造与验证报告](docs/Q13-REPAIR-CONSTRUCTION-2026-09-27.md)，后续构造遵循 [S1 工作规范](docs/S1-REPAIR-CONSTRUCTION-WORKFLOW.md)。

## Q1二级类别映射（2026-09-26，当前）

现有75个方法在同一Kotlin文件中配置methodCategories：Q1.1文件系统、Q1.2类/原生库加载、Q1.3索引存储、
Q1.4正则、Q1.5词法语法/语法树、Q1.6压缩解压、Q1.7图像加载处理。沿用原独立筛查的类别归属。
UI门及方法名单不变。每条记录允许多个类别；Q1总计至多1，各类别count也至多1。
classification.categories包含category、count、matched_methods、frame_ids；matched_frames新增category。
frame_ids关联原Finder帧及常规模式下Q1.frames的源码位置；count-only不读取源码。
stderr新增q1_categories，按类别统计命中的记录数，类别数量之和可能大于Q1总数。
编译exit0，14项测试通过，包括75方法逐项类别核对和同记录七类别命中。
全量验证沿用下文命令，将输出改为 `$env:TEMP/q1-categories-full.jsonl`。
结果：5891条全部接收，Q1仍1056条且行号集合完全不变，305条命中多个类别。
Q1.1–Q1.7计数依次678、155、464、12、23、11、18；所有类别方法/帧引用核对通过。
详见[统计结果](docs/Q1-CATEGORIES-2026-09-26.json)。

## 当前Q1的UI检查（2026-09-26）

先对每个UI线程检查state=RUNNABLE、栈顶存在且index=0/非省略帧/符号非空、栈顶不属于明确等待方法。
通过后才对该线程完整栈进行75方法匹配。没有其他池分类，也不增加耗时风险判断。
classification.ui_checks记录thread_id、state、top_symbol、result：PASSED / STATE_NOT_RUNNABLE /
TOP_FRAME_UNAVAILABLE / TOP_WAIT_METHOD。没有任何UI线程通过时decision=UI_CHECK_NOT_PASSED。
栈顶等待方法覆盖Unsafe.park、Object.wait/wait0、Thread.sleep系列/join、LockSupport.park系列、FutureTask.get/awaitDone。
这是有限的精确匹配检查；通过不证明CPU忙。Unsafe.unpark是唤醒其他线程，不作为等待拦截；原生文件I/O保持可通过。
混合线程只统计通过检查的UI线程命中；Q1总数仍每记录至多1。
编译exit0；设置Q1_CLASSPATH后运行repair/tests/test_repair_entry.py：14项通过、0跳过。
全量命令沿用下文，将输出改为 `$env:TEMP/q1-ui-check-full.jsonl`。
实际5891条全部接收、exit0，1056个Q1候选。相较原1333条：243非RUNNABLE、1栈顶等待、33缺失完整栈顶。
明细：[UI检查结果](docs/Q1-UI-CHECK-2026-09-26.json)。不通过UI检查不等于原问题不存在。

## Q1全部75个代表方法（2026-09-26，当前）

从独立原表筛查1024条的evidence字段提取75个不同方法，保留原7个并补齐68个。
保持完整UI栈精确匹配、无state过滤、每记录计一次，分类器仍在单个Kotlin文件。
构建和测试命令沿用下文；全量命令输出改为 `$env:TEMP/q1-75-methods-full.jsonl`。
5891条全部接收，命中1333条；原1024条全部覆盖，缺失0、新增309。
新增中248条原属等待/争用组、61条原未判定；方法出现在等待栈下层并不证明采样时正在执行该重操作。
本次按用户要求扩展方法匹配，不改变判定条件；计数是方法命中候选，不是确认的Q1根因。
全部5891行与独立原表UI帧逐条集合核对一致。编译exit0、13 tests OK、0 skipped，含全部75方法及内部类美元符号。
完整方法、分项计数和行号见[验证结果](docs/Q1-75-METHODS-COUNT-2026-09-26.json)。

## Q1七方法规则（2026-09-26，当前）

已扩展为用户指定的七个全限定方法。完整UI栈精确匹配，每记录Q1计一次、每方法每记录也计一次；
输出classification.rules、matched_methods、matched_frames，替代旧单数rule字段。stderr新增q1_methods分方法计数。
使用下方计数命令，将输出改为 `$env:TEMP/q1-seven-methods-full.jsonl`。
5891条全部接收，Q1命中843条：GetFileAttributesEx0=270、FindFirstFile0=250、defineClass2=125、FindClose=74、
getFileInfo=60、getName=33、CreateFile0=31。完整UI栈逐行与独立原表提取比对全部一致。
旧表122/39/32来自前8帧且每条选一个代表方法，当前为完整栈任意命中，不能要求三个数字不变。
编译exit0；设置Q1_CLASSPATH后运行repair/tests/test_repair_entry.py：12项通过、0跳过。
证据及行号：[七方法统计](docs/Q1-SEVEN-METHODS-COUNT-2026-09-26.json)。仅候选命中，不证明耗时或修复安全。

## Q1首条规则计数（2026-09-26）

精确匹配 `sun.nio.fs.WindowsNativeDispatcher.GetFileAttributesEx0`，去掉模块/加载器前缀后匹配整个符号。
检查完整UI线程栈，不限制前8帧，不按state过滤；后台线程不计，同一记录重复命中仍q1_count=1。
`q1.classification` 返回rule、scope、decision（CANDIDATE/NO_RULE_MATCH）、q1_count、matched_frames。
NO_RULE_MATCH只表示这条规则未命中，不代表排除Q1。此规则不证明耗时或可迁移。
入口复用一个JVM处理整批，stderr汇总新增q1_candidates。

```powershell
$cp = (Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -B repair/main/python/repair.py --input "$env:TEMP/finder-full-state-20260926-run2/sources.jsonl" --output "$env:TEMP/q1-file-attributes-full.jsonl" --q1-classpath $cp --q1-count-only
```

--q1-count-only仅执行堆栈规则，跳过源码读取，输出repair-q1-classification/1；原Finder对象仍完整保留。
实际exit0：5891 accepted、0 rejected、270 Q1候选；与独立原表筛查的270条逐行集合一致。
详细行号见 [计数证据](docs/Q1-FILE-ATTRIBUTES-COUNT-2026-09-26.json)。11项入口/集成测试通过、0跳过，
含精确方法正例、同记录重复帧、相似名反例和非UI排除。未改S1及Q2–Q5。

分类文件位于 `main/kotlin/src/org/jetbrains/research/lockrepair/classification/`。
Q1沿用既有逻辑，类名为 `Q1ExpensiveWorkRelocationClassifier`，包名仍为 `org.jetbrains.research.lockrepair`。
Q2SynchronousWaitControlClassifier.kt、Q3CooperativeCancellationClassifier.kt、Q4LockContentionReductionClassifier.kt、
Q5RedundantWorkEliminationClassifier.kt 仅为空文件（0字节），暂未实现。2026-09-26目录调整后编译及10项测试通过。

当前入口：[main/python/repair.py](main/python/repair.py)。仅接收 Finder 输出；卡顿位置判断、策略选择和补丁生成尚未实现。
唯一活动任务及进度：[PROGRESS.md](../PROGRESS.md)。重写前的入口文档已保存到 [历史说明](docs/README-before-new-entry-20260926.md)，其中旧命令不适用于已清空的实现。

## 运行

Python 3.12，仅使用标准库，不依赖 Finder 的 tree-sitter/openpyxl，也不导入或重新运行 Finder。
从 tools/edt-freeze-finder 运行：

```powershell
& 'D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe' -B repair/main/python/repair.py --input 'finder-output.jsonl' --output 'repair-intake.jsonl'
```

--input 接受 find_sources.py 的 UTF-8 JSONL（支持文件开头BOM），版本必须为 finder-source-locations/1。
--output 父目录必须存在，文件必须不存在；不会覆盖输入或已有结果。汇总输出到 stderr。
退出码：0=非空输入全部接收；2=存在拒收或空输入；I/O等运行错误为非零，可能保留部分输出，不能当完整结果。

## 接收规则

检查入口所需字段类型、schema版本、原堆栈SHA-256、线程/帧ID唯一性及引用、源码相对路径/行范围/哈希格式、selected与候选/状态的一致性、帧状态统计。
拒收损坏JSON、重复JSON键、非有限数值及同一工作簿内重复record_id。逐行保留拒收原因并继续后续记录，空白行也会拒收。
这是入口字段与引用校验，不是完整JSON Schema验证器，也不核实工作簿来源、源码当前内容或Finder的语义结论。

ACCEPTED仅表示输入合同检查通过：PARTIAL/FAILED解析记录及UNRESOLVED/AMBIGUOUS定位信息仍原样保留，不自动变为可修复。
不读取source_root指定的源码，也不据输入路径执行文件操作；后续源码核验尚未实现。

## 输出 repair-intake/1

每个输入行对应一个输出对象：

```json
{
  "schema_version": "repair-intake/1",
  "input_line": 1,
  "record_id": "workbook-row-2",
  "intake_status": "ACCEPTED",
  "errors": [],
  "repair_status": "NOT_STARTED",
  "source_verification": "NOT_PERFORMED",
  "finder": {"说明": "这里实际保存完整原始Finder对象，不做字段删减或证据升级"}
}
```

拒收时 intake_status=REJECTED，errors为原因列表，finder保留已解析内容；无法解析时finder=null并增加raw_input保留原始行。
后续Repair步骤只从ACCEPTED记录开始，但必须另行评估证据完整性/源码有效性，不能把ACCEPTED作为修复准入。
原始Finder格式：[字段说明](../finder/docs/OUTPUT-FORMAT.md)。

## 测试

```powershell
& 'D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe' -B repair/tests/test_repair_entry.py
```

当前只运行新的入口测试。tests中的旧测试依赖已备份清空的实现，不纳入此次通过声明。
# Q1 堆栈源码定位（2026-09-26）

`main/kotlin/src/org/jetbrains/research/lockrepair/classification/Q1ExpensiveWorkRelocationClassifier.kt` 消费 Finder 的帧和源码映射。
使用 cause_thread_ids 与 ui_thread_ids 的并集，保留未定位帧及所有歧义候选，核对路径边界、文件 SHA256 和方法范围。
这是源码位置提取，不判定 Q1 入池、根因或最终修复点；不重新实现 Finder 搜索器。

从 tools/edt-freeze-finder 运行（需要 Java、Python；首次下载固定版本 Kotlin 编译器和 Gson）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.pq1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$classpath = (Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -B repair/main/python/repair.py --input <finder.jsonl> --output <new-result.jsonl> --q1-classpath $classpath
```

可用 `--source-root` 指定源码根目录、`--java` 指定 Java。默认不带 `--q1-classpath` 时保持原接收行为。
构建临时产物默认在系统 TEMP，可用 `-OutputDirectory` 指定新位置；未恢复旧 JPS/Bazel 模块。
第一版每条记录启动一次 JVM，适合单条/小批验证，尚未优化全量吞吐。

原 repair-intake/1 对象完整保留 finder，启用时新增 `q1`：

- schema_version = repair-q1-locations/1；problem_family = Q1。
- problem_assessment / repair_point_selection = NOT_PERFORMED。
- frames：thread_id、frame_id、symbol、class_name、method_name、stack_file、stack_line、finder_status、reason、locations。
- locations：原 Finder 候选字段及 verification；HASH_MATCHED 时附 absolute_path、source_text、finder_selected、call_sites。
- call_sites 保留 Finder 的调用行/表达式/receiver/证据等级，仅返回当前候选方法范围内的调用。
- verification=UNAVAILABLE 时附 verification_error，例如 SOURCE_CHANGED、PATH_OUTSIDE_ROOT 或文件读取错误。
- locations 为空表示 Finder 未提供源码候选。旧 stack_line 不作为当前源码精确行；当前坐标使用 start_line/end_line 和 call_sites.line。

顶层 source_verification=SEE_Q1_LOCATIONS，逐候选查看验证结果；repair_status 仍为 NOT_STARTED。
HASH_MATCHED 只证明文件与 Finder 证据一致。多个调用、重载和 Kotlin 候选均不升级为已确认卡点。

验证命令：

```powershell
$env:Q1_CLASSPATH = (Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw -Encoding UTF8).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -B repair/tests/test_repair_entry.py
```

2026-09-26：编译 exit0；10 tests OK、0 skipped。包括真实第2条的1225/1226两个调用候选、原行号1159保留、
JDK未定位帧、模块名前缀、源码哈希变化、越界路径、Python→Kotlin 实际调用及原7项接收回归。
未运行历史 Repair 测试，未重跑5891条；当前无可用 IDE lint MCP。
# Q2 同步等待候选分类器

S1 P2 已新增候选生成入口 `--s1-p2`；公共方法提取器为 `pool/extract_method.kt`（`--extract-method`）。旧 Q16Repairer 已迁移。文件结构、输出协议、覆盖边界和验证见 [S1 P2 原型](docs/S1-P2-2026-09-27.md)。

Q1.6 修复器第一步现支持 `--s1-q16-method`：从 Q1.6 命中帧定位完整业务方法，见 [入口、字段和1238验证](docs/Q16-METHOD-LOCATION.md)。

`Q2SynchronousWaitControlClassifier.kt` 接收同一份 Finder 数据；仅检查 UI 线程，要求完整等待栈顶，再匹配最近调用者及嵌套等待上下文。普通事件队列等待、显式获取锁、BLOCKED 和缺失栈顶返回检查原因。六类定义见 [原表报告](../maintenance/raw-q2-20260926-final/REPORT.md)。规则基于本批真实栈，未命中不代表不存在等待问题。

复用 `main/scripts/build-q1.ps1` 同时编译 Q1/Q2，不改变 Q1 行为：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH = (Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw).Trim()
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_repair_entry.py
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -m unittest discover -s repair/tests -p test_q2_classifier.py
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input "$env:TEMP/finder-full-state-20260926-run2/sources.jsonl" --output "$env:TEMP/q2-full-classification.jsonl" --q2-classpath $env:Q1_CLASSPATH
```

输出路径须不存在。`--q2-classpath` 可单独使用，也可与 Q1 参数并用。Q2 不读取或验证源码；完整 Finder 数据仍保留在 `finder`。`repair_status` 保持 `NOT_STARTED`。

新增 `q2` 对象：`schema_version=repair-q2-classification/1`、`problem_family=Q2`、`record_id`、`classification`。分类字段：

- `q2_count`：记录级 0/1；`categories`：Q2.1–Q2.6 多标签，每类最多计一次。
- `ui_checks`：线程状态、栈顶、最近调用者及未通过原因。
- `matched_frames` / `matched_methods`：等待原语、直接调用者及嵌套等待证据；`frame_id` 可回查 Finder 源码映射。方法统计为每记录去重的证据方法数，不是调用次数。
- 每个类别保留 `category`、`count`、`matched_methods`、`frame_ids`。
- `injected_test_path`：明确测试路径，不自动剔除；`write_intent_permit_context`：写意图许可上下文，可供 Q4 复用，不是锁根因判定。

2026-09-26 验证：编译 exit 0；原有 14 测试通过；新增 1 测试含 13 个边界案例通过；全量 CLI exit 0，5891 accepted/0 rejected，1363 候选，类别数 526/34/672/33/100/31。逐行类别与原表审核完全相同，Finder 对象保持一致，帧引用有效。17 条测试路径，1023 条写意图许可上下文。结果见 [验证数据](docs/Q2-VALIDATION-2026-09-26.json)。没有执行修复；无可用 IDE lint MCP。
# 修复方案选择

`repair.py --s1-p1 --q1-classpath <classpath>`: generate a source-bound experimental P1 reload candidate patch (unapplied), including background disk identity/version checks and guarded EDT commit. Currently blocked by a sync-refresh correctness regression (`eligible_for_application=false`); see [paired validation](docs/P1-ROW4746-VERIFICATION-2026-09-27.md).

`repair.py --repair-selection --q1-classpath <classpath>`: stack-based P1/P2 triage and source checks; try P3 only after both fail. The dedicated P1 reload patch is currently available via `--s1-p1`, not this selector. P3 patch generation remains unimplemented. See [REPAIR-SELECTION.md](docs/REPAIR-SELECTION.md).

`repair.py --s1-regex --q1-classpath <classpath>`: extract the classified Pattern.compile caller and generate a source-bound P1 precompilation reference candidate. Runtime plugin version remains unknown; no automatic application. See [Pattern.compile case](docs/PATTERN-COMPILE-2026-09-27.md).

## S2 method context and conditional selection

Use `--q2-classpath <classpath> --s2-repair-selection` to extract up to five source method layers and propose conditional P1/P2/P3/G1 plans. `--s2-extract-method` extracts only. No S2 patches are generated. See [S2 interfaces and verification](docs/S2-CONTEXT-SELECTION-2026-09-28.md).
# S2 P3 source analysis (2026-09-28)

Q2 output also includes `wait_resource_evidence`: observations link `thread_id`
to a record-local `resource_id` parsed from Finder `threads[].details` when the
thread is WAITING, TIMED_WAITING or BLOCKED. Preserve the reported class/hash,
raw description and stack hash; do not join IDs across records. These are
reported object labels (identity hashes can collide), not owner/producer proof.
CompletableFuture Signaller nodes are explicitly distinguished from Futures.
Missing labels remain unavailable; resource cycles are NOT_ANALYZED.
EDT observations with reported state BLOCKED additionally emit
`wait_kind=MONITOR_ENTRY_BLOCKED`, with `monitor_object_status` equal to
`REPORTED_LABEL_LINKED` or `LABEL_MISSING_OR_UNRECOGNIZED`. This is a state-based
monitor-entry/reentry classification, not a lock-owner or deadlock inference.
WAITING/Object.wait and background threads are not assigned this EDT marker.
`monitor_owner_associations` links each EDT monitor observation to the explicit
`owned by` name using an exact, unique thread-name match within the same record.
REPORTED_OWNER_LINKED includes owner_thread_id/state; absent names, missing
threads, duplicate names and self-owner contradictions have separate statuses.
Resources refer to this association table through SEE_MONITOR_OWNER_ASSOCIATIONS;
ownership is not inferred from thread roles or class names. This does not prove
a resource cycle or establish a cross-record runtime identity.
`q2.monitor_cycle_repair` separately recognizes the AWT tree-lock/disposal
cycle candidate and selects the business caller before setAvailable as a repair
entry. It runs even for BLOCKED/non-Q2 records. It is an admission diagnostic,
not a patch generator; row3587 is blocked on missing plugin caller source.

`--s2-repair-selection` now runs `P3PreconditionAnalyzer` on extracted background
dispatch candidates. Kotlin PSI and the JDK Java parser parse verified method fragments; output includes
dispatch/callback/continuation facts and four evidence-bearing checks. This is
intraprocedural analysis without type/alias resolution. Unavailable callback
bodies, external effects and unresolved lifecycle contracts remain UNKNOWN.
Known blocking write-transfer conflicts are FAIL for direct async replacement;
ordering, scope and failure-routing changes are NEEDS_ADAPTATION. There is no
automatic all-PASS admission or patch generator yet. The runtime classpath from
`build-q1.ps1` now includes the existing Kotlin compiler dependencies for PSI.
