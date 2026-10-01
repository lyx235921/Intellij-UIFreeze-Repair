# 剩余八个方法：逐例推进结果

日期：2026-09-27。遵循 [S1 工作规范](S1-REPAIR-CONSTRUCTION-WORKFLOW.md)。**本轮八项均运行了真实案例流程；三项新增可生成候选，五项未完成生成器，不能称八项都已修好。** 用户确认没有 Huawei 插件源码，要求先处理其他案例、最终记录缺口。

## 逐项结果

| 剩余方法 | 本轮真实记录 | Finder / Repair 与源码核验 | 构造结果 / 停止位置 |
|---|---|---|---|
| `java.io.WinNTFileSystem.canonicalize` | 874 | 原生库路径规范化 → BytePackedRaster 初始化 → 图片变换 → ToolkitImage.getWidth；后续连续缺帧，提取器按规则停在缺口 | **无补丁，停在步骤 4/5**。无法确定图片的业务拥有者和提前准备入口；不能凭图片栈擅自插入全局 System.loadLibrary |
| `WindowsNativeDispatcher.GetFinalPathNameByHandle` | 1346 | 核验 MultiRoutingFsPath.toRealPath、LocalFileSystemBase.resolveSymLink、RefreshWorker.checkAndScheduleChildRefresh/generateUpdateEvents；完整原栈最后到 ScanPanel | **无补丁，停在步骤 5**。本次扫描立即用解析结果生成 symlink 事件；缺少 ScanPanel 刷新后的消费者源码，不能强改异步完成。按用户答复记录插件源码缺失 |
| `WindowsNativeDispatcher.GetFullPathName0` | 4490–4498（全部九条） | 4490/4491 定位 canonical name 查询和 PersistentFSImpl.findChildInfo；4492–4498 同为 TaskApplicationService.isInterestedAction → after，仅提取到框架消息总线方法 | **无补丁，停在步骤 4/5**。前两例的名称参与 FSRecords 更新，提前查询需版本化提交/重试；另七例缺插件源码，消息总线不是替代修复位置 |
| `com.intellij.util.lang.UrlClassLoader.findClass` | 211、902 | 211 仍是编辑器创建；另选 902，真实栈到 IdeMessagePanel.showErrorNotification，核验 Notification/NotificationAction 的构造和配置源码 | **新增 P1 候选，步骤 7 受控验证通过**。后台创建通知及 action，EDT 检查状态并显示气泡。真实 IDE 阶段未完成 |
| `java.lang.ClassLoader.defineClass` | 902、1007；另保留 211/1031 | 902 到通知；1007 完整原始栈到 Git activate。五层提取结果原样保留，额外运行时路径和人工方法正文单独记录 | **新增候选覆盖**：复用通知或 Git 监听器模板，不能按底层方法名对所有调用者套用 |
| `java.lang.ClassLoader.defineClass2` | 902、1007 | 同上；连续原始栈核验同线程、frame ID、索引和缺口 | **新增候选覆盖**：与 defineClass 共用补丁，不把同一补丁重复计数 |
| `java.lang.ClassLoader.defineClassSourceLocation` | 1031（已知唯一例） | 重新定位 HwFacadeHelper.JCEFAccessor.getCefApp，补读 JBCefApp 的 native 启动与实例创建 | **无补丁，停在步骤 5**。提前 getInstance 会绕过原先 CefApp 状态门并改变 native 生命周期；只加载而不初始化不能替代栈中的初始化。尚无准备完成后的安全业务消费边界 |
| `jdk.internal.loader.NativeLibraries.load` | 1787、1788、1789（全部三条） | 1787 图片路径有缺口；1788/1789 实际 Finder 定位 paintSafely 及 JText 组件绘制路径，原栈经 HBShaper/SystemLookup 初始化 | **无补丁，停在步骤 5**。绘制依赖当前 Graphics/组件，不可整段迁移；随意预热一种字体/字符不保证覆盖真实 shaping 初始化。缺合适准备入口与目标 JBR 验证条件 |

本轮新增三个“方法有具体案例候选”，原十一方法累计为 **6 个有案例候选、5 个仍无补丁生成器**。这只是当前受限模板覆盖，不是六类方法全部可修或六个事故已经解决。

## 步骤 1–4：真实输入和位置证据

重新读取 `D:/intellij-community-master/intellij底座问题堆栈-1.xlsx`，一次运行 Finder 18 行：211、874、902、1007、1031、1346、1787–1789、4490–4498。

- Finder：195 LOCATED、360 CANDIDATE、27 AMBIGUOUS、1622 UNRESOLVED；103 个源文件；index_errors 为空。
- Repair：18 accepted、0 rejected，18 条均进入 Q1；本轮只使用对应分类命中和实际上下文，不把接受输入视为修复成功。
- 对实际提取到的正文范围逐项比对磁盘内容与 SHA，共 25 个不同源码范围通过独立核验。
- 1788/1789 此次真正运行了 Finder，区别于前轮只有人工补读原栈。
- `method_context` 仍最多五层。新增完整栈路径作为 `supplemental_runtime_path`；人工源码作为 `supplemental_context`，不改写 UNRESOLVED。

## 步骤 5–6：实现

仍在现有 `P1ClassLoadingPreload.kt` 增加同类生成方法，未另起 Q 文件。

1. **通知对象提前准备**（新增 `notificationPatch`）：把 `new Notification(...).setIcon(...).addAction(...)` 移至线程池；气泡创建、布局、主题和所有 UI 状态检查仍在 EDT。
2. **Git 模板扩大真实路径支持**：之前仅能使用五层内的 loadClass 触发；现在 `checkGitListener` 接收真实 Finder 记录，核验从每个命中帧到 activate 的完整连续栈，再使用既有固定源码模板。因此 defineClass/defineClass2 也能关联到同一候选。
3. **统一条件**：`RelocationPreconditions.pathToCaller` 拒绝不同线程、缺帧、索引不连续、触发帧缺失；`checkNotificationPreparation` 固定三份已审阅源码 SHA（IdeMessagePanel、Notification、NotificationAction）。不修改分类名单、UI 门或提取层数。

通知变换概要：

```java
if (myP1Disposed || project.isDisposed() || balloon != null ||
    !myP1NotificationPending.compareAndSet(false, true)) return;
executeOnPooledThread(() -> {
  Notification notification = prepareErrorNotification();
  invokeLater(() -> {
    try {
      // 再查 disposed、unread state、frame active、display type、balloon。
      showPreparedErrorNotification(project, frame, notification);
    }
    finally {
      myP1NotificationPending.set(false);
    }
  });
});
```

完整候选另含准备前销毁检查、异常清理和 dispose 标记；以上仅为结构摘要。准备任务合并，失效结果不展示。未缓存业务事件、不让 EDT 等待。

通知准备可能增加显示延迟；被丢弃的过期通知不会显示；首次类初始化、真实消息池并发和应用调度仍需目标 IDE 检查。P1/P2 不明确失败的剩余案例保持 UNKNOWN，不自动启用 P3。

## 步骤 7：验证

最终构建 exit 0；29 项相关测试全部通过，0 失败、错误、跳过，29.228 秒。生产目标及被审阅通知 API 源码与测试快照逐字节相同，未修改生产文件。

新增 `P1_notification_loading_test.py`：使用真实第 902 行、固定源码副本及生成后的实际 Java 方法体，验证补丁应用和 javac 编译。Swing 为真实调度，Application、MessagePool、Notification 等为明确的平台替身。

测试用 latch 在通知构造处模拟耗时：原方法卡住 EDT；候选准备阶段 EDT 心跳可执行。检查单个 pending 任务、重复请求合并、UI 提交、panel/project 销毁、无未读错误、窗口失活、关闭通知、构造异常后的清理和重试。没有宣称测得真实类加载加速。

扩展 Git 测试：三个方法命中同一补丁；栈尾缺口与索引不连续拒绝。原源码哈希变化、已打补丁不可重打、各既有模板回归均保留。

真实 IDE 验证尚未进行：既有 `repair/main/kotlin/intellij.tools.readWriteLock.repair.iml` 缺失问题仍在；未改变模块元数据。所有候选 `eligible_for_application=false`，生产源码未应用补丁，第 4746 行仍暂停。

## 步骤 8：产物和复现

目录 `out/edt-freeze-finder/p1-remaining-eight-20260927/`：

- `finder.jsonl`、`before.jsonl`、`candidates.jsonl`：本轮真实执行结果。
- `verified-contexts.json`：25 个范围的源码内容与校验信息。
- `workbook-row-902.patch`、`workbook-row-1007.patch`：一份新模板候选、一份扩大命中支持的旧模板候选。
- `attempts.json`：八方法逐项结果，不把未生成标为完成。
- `tests.json`、`tests.log`：完整测试模块列表、结果。

Finder（输出排他创建，复跑需新文件名）：

```powershell
@'
import runpy,sys
sys.path[:0]=['C:/Users/Administrator/AppData/Local/Temp/finder-source-deps-wheel-20260926','finder/main']
sys.argv=['find_sources.py','--workbook','D:/intellij-community-master/intellij\u5e95\u5ea7\u95ee\u9898\u5806\u6808-1.xlsx','--source-root','D:/intellij-community-master','--output','out/edt-freeze-finder/p1-remaining-eight-20260927/finder.jsonl']
for row in [874,1346,4490,4491,4492,4493,4494,4495,4496,4497,4498,1031,1787,1788,1789,1007,902,211]:
    sys.argv+=['--row',str(row)]
runpy.run_path('finder/main/find_sources.py',run_name='__main__')
'@ | D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw).Trim()
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/p1-remaining-eight-20260927/finder.jsonl --output out/edt-freeze-finder/p1-remaining-eight-20260927/candidates.jsonl --q1-classpath $env:Q1_CLASSPATH --s1-loading --s1-storage --repair-selection
```

测试：设置上面的 Q1_CLASSPATH，Python 加入 `repair/tests` 到 sys.path，使用 `unittest.TestLoader().loadTestsFromNames` 执行 tests.json 中的全部模块。源码快照在 `repair/tests/fixtures/P1-notification-loading`，SHA 门和真实记录使模板不依赖任意同名调用方。

研究预检 HEAD `83a21329f4f811fca1b5a4a555eb6504f2ff4d78` 未变，无新增阅读。工作区未提交；未清理用户的其他修改。
