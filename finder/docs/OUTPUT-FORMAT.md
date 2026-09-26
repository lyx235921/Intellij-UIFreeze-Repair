# Finder → Repair：finder-source-locations/1

入口：`finder/main/find_sources.py`。UTF-8 JSONL，每行一个 Excel 记录；stdout 不输出记录，stderr 输出本次统计。
机器可读格式见 [output.schema.json](output.schema.json)；完整实例见 [row2-output.json](row2-output.json)。
`--row` 可重复，省略时处理所有记录。输出文件必须不存在，父目录必须存在。失败可能留下部分输出，不应作为完成结果使用。

## 职责与证据等级

Finder 执行：1 输入完整性检查；2 提取 UI/致因线程；3 选择栈顶和原表标记帧；4 映射当前源码；5 检查相邻帧的调用表达式。
不判定根因、卡顿机制、修复点或安全改法，`repair_analysis` 固定为 `NOT_PERFORMED`。

Java 使用 tree-sitter AST，核对包、声明类（含具名内部类）和方法名；Kotlin 使用去除注释/字面量后的括号与声明匹配，
明确标为词法候选，不能当成编译器绑定。当前不支持 Kotlin 扩展/泛型/表达式体函数、生成的属性访问器、匿名类和协程/合成帧绑定。
旧行号只作为原始输入保留，不用于强行解除重载歧义。同名方法可结合相邻被调用帧的方法名缩小候选，但不证明 JVM 签名身份。

调用关系保留栈中的方向：较大的 index 是 caller，较小的是 callee。只检查连续编号的相邻帧。
`CALL_SITE_CANDIDATE` 表示在 caller 当前源码中发现与 callee 同名的调用表达式，不代表接收者类型、重载、动态分派或运行时目标已解析。
Kotlin 调用表达式是词法候选，可能位于 lambda/局部作用域；不得据此推断其同步执行或线程。
Java lambda/内部类体的调用不归入外围方法。`UNVERIFIED` 不表示不存在调用关系。

## 顶层字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| schema_version | string | 固定 finder-source-locations/1，消费者应拒绝不支持的版本 |
| record_id | string | workbook-row-N；只在同一个工作簿内唯一，跨工作簿用 workbook_sha256 + record_id |
| workbook_sha256 | string | CLI 输入工作簿 SHA-256 |
| source_root | string | 当前源码根目录绝对路径 |
| input | object | sheet、row、occurrences、stack_sha256、完整 raw_stack |
| parse | object | status=PARSED/PARTIAL/FAILED；diagnostics、unparsed_lines 保留缺失和异常 |
| threads | array | 每个线程仅存一份，含完整结构化栈 |
| ui_thread_ids | string[] | 名称匹配 AWT-EventQueue-N 的线程 ID；不推断其他 UI 线程 |
| cause_thread_ids | string[] | 原表 cause freeze thread 标记的线程 ID，不代表独立因果证明 |
| entry_frames | array | frame_id、reason；reason 是 THREAD_TOP/topStack/problemModuleStack |
| call_edges | array | 相邻帧及对应源码调用表达式检查结果 |
| location_summary | object | 按帧统计定位状态，缺省键表示零 |
| index_diagnostics | string[] | 索引访问失败；非空时不声称搜索完整 |
| repair_analysis | string | 固定 NOT_PERFORMED |

## 线程和帧

线程：thread_id（t0、t1…）、name、state、details（string/null）、role（blocked/cause）、is_ui_thread、frames、unparsed_lines。
线程 role 是输入区段归属，不是独立验证的等待关系。

帧：frame_id（t0:f0…，使用数组位置，因此原始 index 重复时仍唯一）、index、label、symbol、location、file、line、elided、raw、source。
原始 line 是堆栈行号；source 中行号才是当前源码坐标。file/line/symbol/label 可为 null。

`source`：

- status：LOCATED（唯一 Java AST 声明）、CANDIDATE（Kotlin 词法候选或借相邻调用名缩小的 Java 重载候选）、AMBIGUOUS（多解/搜索不完整）、UNRESOLVED（未找到或不支持）。
- reason：失败或歧义原因，可为 null；source_diagnostics 保存源码读取/解析错误。
- candidates：所有包/类/方法名匹配的声明，不静默丢弃重载和重复文件。
- selected：唯一或由相邻调用名称缩小后的声明；没有唯一结果则 null。结合 selection_basis 使用，不代表历史方法身份。
- selection_basis：UNIQUE_OWNER_METHOD / ADJACENT_CALLEE_NAME / null。
- historical_identity：固定 NOT_CHECKED。

声明字段：path（相对于 source_root 的 POSIX 路径）、sha256（源文件原始字节）、language（java/kt）、owner、method、
start_line、end_line（1-based，含首尾行）、declaration（签名文本）、basis（JAVA_AST/KOTLIN_LEXICAL_CANDIDATE）。
源码正文不复制进输出；Repair 读取 path 前应核对 sha256，文件变化则重新定位。

## call_edges

caller_frame_id、callee_frame_id、status（CALL_SITE_CANDIDATE/UNVERIFIED）、reason、call_sites、type_resolution（固定 NOT_PERFORMED）。
每个 call_site 含 path、sha256、name、line（表达式起始行）、expression、receiver（string/null）、evidence（JAVA_AST_CALL/KOTLIN_LEXICAL_CALL_CANDIDATE）。多个表达式全部保留。receiver 为 null 不证明隐式 this；Kotlin 仅提取简单限定接收者。

## 搜索边界和消费约定

索引一次建立，按栈帧文件名检索，再检查包/声明类；没有文件名时尝试 Java 顶层类文件名。
排除 .git/.idea/out/build/target/node_modules/__pycache__/test/tests/testsrc/testdata/fixtures/golden/evidence（目录名忽略大小写）及符号链接。
这意味着外部 JDK/依赖源码和被排除的测试、构建目录通常不能定位；UNRESOLVED 必须保留，不得伪造本地路径。

Repair 应以 input/threads 作为原始证据、source/edges 作为当前源码定位线索，分别检查 parse/status、定位等级、索引诊断及文件哈希。
即使是 LOCATED，也只说明找到了当前声明，不证明卡顿根因、安全修改位置或运行时版本一致。
当前自动结果不能代替第6～7步的 Repair 分析。
