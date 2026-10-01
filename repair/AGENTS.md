# Repair 目录约定

- 当前状态、唯一活动任务、证据门及下一步只维护在 `../PROGRESS.md`。不要重建 IMPLEMENTATION.md 或另一份活动任务表。
- 每次开始或恢复 S1 修复器构造，必须先读取并遵循 [S1 修复器构造工作规范](docs/S1-REPAIR-CONSTRUCTION-WORKFLOW.md)：真实堆栈选例 → Finder 定位 → Repair 分类与五层上下文提取 → P1/P2 初选及源码筛选（均失效后尝试 P3）→ 前置检查与候选补丁 → 行为及卡顿验证 → 结果记录。该规范不替代 PROGRESS 的当前任务，也不表示流程已全部自动化。
- 活动源码、CLI、演示和维护脚本只放 main：Python 在 main/python，Kotlin 在 main/kotlin/src，Shell 脚本在 main/scripts。旧路径不加副本或转发入口。
- Repair 测试与测试数据只放 tests。tests/fixtures 和 tests/kotlin/testData 中的代码是测试输入，不能当作活动修复器。
- docs 是参考与历史报告，evidence 是冻结实验结果；旧命令与旧任务不覆盖 PROGRESS。历史快照保留为 ZIP，不修改归档成员。
- 入口及测试命令见 README.md。目录修改须同步调用者、模块登记、测试与文档链接；模块名称和 Kotlin 包名不随目录改变。
- 新输出默认写入仓库 out/edt-freeze-finder，不把临时结果写进源码目录。
- 命名规则（用户要求，2026-09-27）：以后新建 P1 相关文件统一以 `P1` 开头，不用 `Q` 或 `Q1.x` 作为文件名前缀。问题分类标识可保留在文件内容中；不要把问题类别用作 P1 修复文件名。
