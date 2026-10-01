# 十一个方法的修复器构造尝试

日期：2026-09-27。工作规范：[S1 流程](S1-REPAIR-CONSTRUCTION-WORKFLOW.md)。本轮接着已完成的[真实案例定位与绑定](P1-BINDINGS-2026-09-27.md)，不是重新把方法名单绑定一遍。

**结果：11 个方法均评估了具体变换；2 个方法能生成受限候选补丁，另外 9 个尚未形成补丁生成器。没有新增真实 IDE 已修复结果。** 不能把方案草图或拒绝原因算作修复器完成。

复用上一阶段已运行 Finder 的九条真实记录和五层源码定位结果，本轮重新运行 Repair，重新读取并核验源码。额外补读的调用者明确属于人工源码审阅，不冒充五层提取器输出。第 4746 行仍暂停。

## 逐方法结果

以下行号均为真实堆栈表记录号。相同底层方法在不同业务场景中不保证同样可修。

| 卡顿点方法 | 选例 | 尝试的业务变换 | 本轮结果 |
|---|---|---|---|
| `java.io.WinNTFileSystem.canonicalize` | 874 | 在图片使用之前后台准备图片，从而提前触发 native 库路径规范化 | 未生成：`ToolkitImage.getWidth` 后存在连续缺帧，无法确定拥有图片与准备入口的业务方法；不能插入全局 `System.loadLibrary` 代替原类加载器加载 |
| `WindowsNativeDispatcher.GetFinalPathNameByHandle` | 1346 | 提前获取符号链接目标；或把 ScanPanel 发起的整次刷新改成异步 | 未生成：`RefreshWorker.checkAndScheduleChildRefresh` 本次扫描立即使用目标生成符号链接事件；缓存缺少同一轮扫描的一致性约束。完整栈到 ScanPanel，但其源码缺失，无法调整刷新后的消费者 |
| `WindowsNativeDispatcher.GetFullPathName0` | 4490 | 在 `FSRecordsImpl.update` 前准备 canonical name | 未生成：`PersistentFSImpl.findChildInfo` 在更新回调里根据本次 children/childData 决定真实名称和创建 child record；移出需重新验证父目录/名称及重试，现有同步接口没有准备结果传入点。不能用旧名称或异步占位值替代 |
| `WindowsNativeDispatcher.GetLogicalDrives` | 1347 | 放弃永久盘符缓存；复用 `refreshWithoutFileWatcher` 的异步 dirty-marking P2 模板 | **生成候选**：完整栈经过 `extractRootPath → getCanonicalFile → markDirtyRecursively → refreshWithoutFileWatcher callback → fireEventsInWriteAction`，符合现有受限模板。P1 仍未知，实际方案 P2 |
| `UrlClassLoader.findClass` | 211 | 在编辑器创建之前预加载 `EditorCompositeKt`；保留 UI 对象在 EDT 构造 | 未生成：五层定位到 `createCompositeInstance`，这是 `@RequiresEdt` 同步返回方法；整段迁移不可行。局部 `Class.forName(..., false, loader)` 不执行栈中 `<clinit>`；提前初始化需要合适的启动入口，事故栈的 `openFilesOnStartup` 未在当前对应文件中定位，未构造跨版本入口 |
| `ClassLoader.defineClass` | 211、888、1031 | 分别尝试编辑器类预加载、工具栏类预加载、JCEF 提前初始化 | 未生成：三个场景的初始化约束不同，不能用一个 class-name 缓存补丁修复；具体限制见下文 |
| `ClassLoader.defineClass0` | 890 | 后台构造 `AWTEventListener`，切回 EDT 后初始化焦点并注册 | **生成候选 P1**：源码固定版本，保持相同 service scope；真实 Kotlin 协程 + Swing 的受控方法片段测试通过；目标 IDE 未验证 |
| `ClassLoader.defineClass2` | 888 | 在 `GitToolbarWidgetAction.update` 的 BGT 阶段预加载按钮类 | 未生成：`update` 的 BGT 声明存在，但不能据此证明首个 `createCustomComponent` 之前必然完成预加载；后台构造 `GitBranchToolbarComboButton(model)` 又会把 Swing 组件构造移出 EDT。只加 `Class.forName` 无法认定排除了首次 EDT 加载 |
| `ClassLoader.defineClassSourceLocation` | 1031 | 在 `JCEFAccessor.getCefApp` 之前后台准备 CefApp | 未生成：当前代码先看 `CefApp.getState()!=NONE` 才 `getInstance`，且关联共享 accessor/实例字段；把 `getInstance` 提前会改变生命周期，直接初始化 CefApp 也会触发 native server 探测。未建立安全发布与初始化入口 |
| `ClassLoader.loadClass` | 211、888、1031 | 与各自业务入口共同预加载，不改 ClassLoader 本身 | 未生成：分别受编辑器启动、工具栏首建、JCEF 生命周期限制；没有独立通用加载模板 |
| `NativeLibraries.load` | 1787；补看 1788、1789 | 图片/字体工作第一次使用前预热 | 未生成：1787 的图片业务栈有缺口；1788/1789 原始栈是 HBShaper 初始化，经 `TextLayout → paintSafely`。补读 Darcula/TextField 的 paint 方法仍是即时 Swing 绘制，不能整个放后台；合适预热时机、实际字体/输入、JBR 25 native 初始化约束未解决 |

## 两份可生成候选

### 890：监听器 bootstrap 先于 UI 阶段

实现放入现有 `P1ClassLoadingPreload.kt`，前置条件在 `RelocationPreconditions.checkTerminalListener`。

检查真实 `defineClass0 → LambdaMetafactory → TerminalFocusFusService.installAWTListener` 路径、提取的方法身份、源码范围和完整文件 SHA。不绑定 Excel 行号，不接受其他调用者或变更后的源码。

原流程：

```kotlin
coroutineScope.launch(Dispatchers.UI + CoroutineName("TerminalFocusFusService initialization")) {
  initializeState()
  installAWTListener() // 此处创建 SAM lambda，再注册
}
```

候选：

```kotlin
coroutineScope.launch(Dispatchers.Default + CoroutineName("TerminalFocusFusService initialization")) {
  val listener = createAWTListener()
  kotlinx.coroutines.withContext(Dispatchers.UI) {
    initializeState()
    installAWTListener(listener)
  }
}
```

`createAWTListener` 仅创建原回调；读取 KeyboardFocusManager 和更新状态仍在事件派发时执行。注册和原有 job completion 清理保持原逻辑。准备期间取消时不进入 UI 安装阶段。

限制：首次注册延后，初始化前短暂焦点变化仍不会被观察；协程自身及 UI 注册部分也可能有首次加载成本。这不是所有 `defineClass0` 的通用修复，更不能仅凭受控实验断言第 890 行已修好。

### 1347：复用异步刷新模板

扩展现有 `P1StorageRelocation` 与 `checkQ13` 的受限调用链支持，不新建重复文件。五层定位提供盘符/路径上下文，完整原始栈用于确认 dirty-marking 所在的刷新边界；原有人工补读方法与源码 SHA 门保持。

```java
ReadAction.nonBlocking(() -> {
  markRootsDirty.run(); // 本例中会到 getRootDirectories
  return (Void)null;
}).expireWith(this)
  .finishOnUiThread(ModalityState.defaultModalityState(), unused -> refresh(true))
  .submit(AppExecutorUtil.getAppExecutorService());
```

仅变换异步刷新分支，同步分支保持原流程。复用已有 Q1.3 候选：实际策略 **P2**，不是 P1 盘符缓存。NBRA/取消/并发刷新语义仍需真实 IDE 验证；已有模拟测试不能证明这些平台语义。

同时修正 `repair_selection` 对专用生成器硬编码选择 P2 的问题，现在从生成器决策读取 P1/P2。

## 未生成案例的具体尝试与否决范围

以下是审阅过但未实现的方案草图，不是可应用补丁：

```java
// 1346：不能把前一时刻解析的 target 直接用于本轮事件。
var target = cachedSymlinkTarget;
checkSymbolicLinkChange(events, child, child.getCanonicalPath(), target);

// 4490：不能在 FSRecords 更新之外得到 name 后不验证就提交。
var canonicalName = preloadedName;
child = makeChildRecord(parent, parentId, canonicalName, childData, fs, null, false);

// 211/888：不初始化类的预加载并不执行 <clinit>，也没有消费者排序保证。
Class.forName(targetClassName, false, originalClassLoader);

// 1031：不得跳过原 getState 检查而抢先取得 CefApp 实例。
var app = CefApp.getInstance();
```

拒绝这些具体草图不表示 P1/P2 所有方案都失败，输出仍保留 `INSUFFICIENT_EVIDENCE`，P3 仍为 `DEFERRED`。874/1787 的缺口不通过扩大五层或补造路径绕过。1788/1789 只作为补充人工栈/源码审阅，未宣称跑过这两条的 Finder。

## 产物与验证

最终结果：构建 exit 0；Repair CLI exit 0、9 accepted / 0 rejected；27 项测试全部通过，0 失败、错误、跳过，24.279 秒。测试中的初次拒绝用例因未匹配 JVM 模块前缀而未实际修改栈，已修正用例为后缀匹配；不是生产调用路径的放行漏洞。

产物目录：`out/edt-freeze-finder/p1-construction-20260927/`。

- `repair.jsonl`：实际 Repair CLI 九条记录、11 个目标方法及 15 个目标方法-记录决策。
- `workbook-row-890-s1_loading-0.patch`、`workbook-row-1347-s1_storage-0.patch`：两份未应用候选。
- 对应 JSON：策略、完整 replacement_source、适用范围、源码 SHA 和限制。
- `attempts.json`：11 个方法的状态及下一缺口；`reviewed-sources.json`：补读来源哈希。
- `run.json`、`tests.json`、`tests.log`：准确执行命令、结果及测试日志。

构建命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw).Trim()
```

Repair 命令：

```powershell
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/p1-bindings-20260927/finder.jsonl --output out/edt-freeze-finder/p1-construction-20260927/repair.jsonl --q1-classpath $env:Q1_CLASSPATH --s1-storage --s1-loading --repair-selection
```

测试模块：`P1_loading_candidate_test`、`P1_preload_bindings_test`、`test_q13_relocation`、`test_regex_precompilation`、`test_repair_entry`、`test_repair_selection`、`test_extract_method`、`test_p2_relocation`、`test_q2_classifier`。设置上述 classpath 后，通过 Python `unittest.TestLoader().loadTestsFromNames`（`sys.path.insert(0,'repair/tests')`）执行，精确模块列表和统计保存于 tests.json。

受控验证范围：候选在源码副本中 `git apply --check/apply`；终端候选提取实际变换的方法体，用 Kotlin 2.1.20、真实 kotlinx.coroutines 和 Swing 编译运行，替代 IntelliJ UI dispatcher 与焦点状态计算。人工 latch 阻塞准备阶段，验证原版阻塞 EDT、候选准备时 EDT 可响应；验证重复初始化只注册一次、事件回调在 EDT、结束清理、准备期间取消和准备异常不安装。该实验没有测量真实类加载耗时，也不是完整插件编译。

真实 IDE 验证尚未进行，既有 JPS 缺失 `repair/main/kotlin/intellij.tools.readWriteLock.repair.iml` 的障碍仍在。生产源码未修改；工作区未提交。研究仓库 HEAD `83a21329f4f811fca1b5a4a555eb6504f2ff4d78` 本轮检查未变，无新增阅读。
