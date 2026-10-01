# 第 1007 行：Git 设置监听器提前构造

日期：2026-09-27。按 [S1 工作规范](S1-REPAIR-CONSTRUCTION-WORKFLOW.md) 完成选例、Finder、Repair、源码补读、候选生成和受控验证。尚未完成真实 IDE 验证。

## 1. 真实例子

工作簿 `D:/intellij-community-master/intellij底座问题堆栈-1.xlsx` 第 1007 行。UI 线程 RUNNABLE，栈顶 `ClassLoader.defineClass2`。相关路径包含 `defineClass`、UrlClassLoader/PluginClassLoader 加载链、`ClassLoader.loadClass`，随后是 `GitBranchIncomingOutgoingManager.lambda$activate$4`。

这次从剩余方法的其他真实案例寻找准备边界，没有继续套用第 888 行的 Swing 工具栏构造方案。

## 2. 实际 Finder 输出

本轮重新读取工作簿、运行 Finder：1 条记录；5 LOCATED、12 CANDIDATE、48 UNRESOLVED；读取 19 个源文件；index_errors 为空。保存 `out/edt-freeze-finder/p1-loading-row1007-20260927/finder.jsonl`。

Finder 对 `lambda$activate$4` 返回 `MISSING_OR_SYNTHETIC_SYMBOL`，没有宣称定位到完整 activate。

## 3. Repair 与五层提取

本轮运行 Repair CLI：1 accepted / 0 rejected，分类 Q1.2，命中 `defineClass2`、`defineClass`、`loadClass`。

- `defineClass2/defineClass` 的五层均在类加载器内部，未到达 Git 业务入口。
- `loadClass` 的第一层是无法解析的 `lambda$activate$4`，后续能够提取 `TransactionGuardImpl.runWithWritingAllowed`。
- 没有改变五层上限、合成方法处理或栈缺口规则。

初始输出 `repair.jsonl`，最终候选输出 `final.jsonl`。当前只对 **loadClass** 的路径自动生成候选，不把另两个方法也登记为完成。

## 4. 必要源码补读

人工定位并阅读 `plugins/git4idea/backend/src/branch/GitBranchIncomingOutgoingManager.java` 的 activate、构造器、dispose、updateIncomingScheduling。固定完整文件 SHA256：`c2b30ca5f5e0aa931a54966e7ef1f72eaa746f0f6dcdeee3539d1c657fbee937`。

activate 已经通过 invokeLater 异步注册监听器。在 UI 回调内首次创建匿名 `GitVcsSettingsListener`；该对象创建只捕获 manager，业务访问留在回调执行时。连接、订阅、调度器字段仍需保持 EDT 操作。

补读标为 `MANUALLY_REVIEWED_ENCLOSING_METHOD_NOT_EXTRACTOR_LOCATION`，没有改写 Finder 的 UNRESOLVED。事故版本与当前源码一致性未独立确认。

## 5. 策略与候选

选择 P1：后台提前创建监听器，然后提交 EDT 注册；不修改 ClassLoader。

```java
ApplicationManager.getApplication().executeOnPooledThread(() -> {
  if (myP1Disposed || myProject.isDisposed()) return;
  var listener = new GitVcsSettings.GitVcsSettingsListener() { /* 原设置回调 */ };
  ApplicationManager.getApplication().invokeLater(() -> {
    if (myP1Disposed || myProject.isDisposed()) return;
    if (myConnection == null) {
      // 原连接与订阅顺序，使用已经创建的 listener
    }
    updateAllBranchesWithOutgoing();
    updateIncomingScheduling();
  });
});
```

添加 volatile disposed 标志，在 dispose 开头设置；设置回调排队后再次检查销毁状态。没有 EDT 等待，没有缓存业务数据。P3 不放行。

限制：后台排队增加初始化延迟，可能改变多个 activate 请求的完成顺序；原方法没有每次请求的独立参数，但真实插件的初始化先后、消息总线生命周期仍须验证。只迁移匿名监听器创建，其他 EDT 类加载成本仍可能存在。

## 6. 实现位置

- `RelocationPreconditions.checkGitListener`：真实连续路径检查、缺口拒绝、固定源码 SHA、人工补充上下文。
- `P1ClassLoadingPreload.gitPatch`：生成 activate/dispose/状态字段补丁，复用已有文件。
- 仍经 `--s1-loading` 和 `repair_selection` 输出；无 Excel 行号绑定。
- `repair/tests/P1_git_loading_test.py` 和 `fixtures/P1-git-loading/`：真实记录、源码快照及受控验证。

## 7. 验证及证据界限

最终：构建 exit 0；Finder/Repair exit 0；28 项相关测试全部通过，0 失败/错误/跳过，26.573 秒。

在副本上 `git apply --check` 和 apply 通过，生成后的正文与 replacement_source 一致。生成 Java 的实际 activate 方法体编译通过，Swing 调度真实，Application/Project/MessageBus 使用替身；在对象构造前注入 latch，观察原流程阻塞 EDT、候选后台准备时 EDT 可响应。验证重复 activate 不重复连接，订阅及更新在 EDT，manager/project 销毁期间不安装，已排队设置回调在销毁后不更新。

负例覆盖：栈缺口、已修改源码不生成补丁。首次测试暴露尾部缺口被误用为人工补读依据，已增加提取结果缺口状态检查。另修复目标 Java 文件没有结尾换行时的 diff 标记，保留其 EOF。

上述测试不验证真实类加载耗时，不验证整个 Git 插件编译，也不等于第 1007 行事故已修好。目标 IDE 检查仍受既有缺失 JPS 模块描述文件约束。生产源码未改，候选 `eligible_for_application=false`。

## 8. 复现命令与记录

```powershell
@'
import runpy,sys
sys.path[:0]=['C:/Users/Administrator/AppData/Local/Temp/finder-source-deps-wheel-20260926','finder/main']
sys.argv=['find_sources.py','--workbook','D:/intellij-community-master/intellij\u5e95\u5ea7\u95ee\u9898\u5806\u6808-1.xlsx','--source-root','D:/intellij-community-master','--output','out/edt-freeze-finder/p1-loading-row1007-20260927/finder.jsonl','--row','1007']
runpy.run_path('finder/main/find_sources.py',run_name='__main__')
'@ | D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw).Trim()
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/p1-loading-row1007-20260927/finder.jsonl --output out/edt-freeze-finder/p1-loading-row1007-20260927/final.jsonl --q1-classpath $env:Q1_CLASSPATH --s1-loading --repair-selection
```

Finder 输出排他创建，复跑时使用新输出路径。测试通过 `unittest.TestLoader().loadTestsFromNames` 执行，模块列表、数量和最终结果在本目录对应 out 目录的 `tests.json`、`tests.log`。候选为 `candidate.patch`。

研究 HEAD `83a21329f4f811fca1b5a4a555eb6504f2ff4d78` 未变，无新增资料阅读；4746 继续暂停。
