# Pattern.compile：第 4238 行定位与 S1 候选

2026-09-27，未提交。第 4746 行继续暂停，本轮只处理正则编译案例。

## 真实记录与定位结果

重新读取 `D:\intellij-community-master\intellij底座问题堆栈-1.xlsx` 的“问题线程堆栈”工作表，按完整方法名 `java.util.regex.Pattern.compile`（允许 JVM 模块前缀）检索，命中 4238、4240、4241、4242 四条记录，不把同一记录中的多个 compile 帧重复计数。4238/4241 为 `org.wso2.lsp4intellij`，4240/4242 为 Huawei fork。

选取 4238，真实 EDT RUNNABLE 调用链：

```text
IntellijLanguageClient.isExtensionSupported
→ keySet.stream().anyMatch
→ lambda$isExtensionSupported$2
→ String.matches
→ Pattern.matches
→ Pattern.compile
→ Pattern$SliceNode.study（栈顶）
```

上层来自文件删除事件处理和 `AceChangeApplier.beforeVfsChange`。原始堆栈行号：`IntellijLanguageClient.java:200/201`。线程和调用路径来自真实记录，不从方法名推断。

第一次在当前 IntelliJ 工程运行 Finder → Repair：两命令 exit 0，1 accepted，Q1.4；Finder 266 帧中 49 LOCATED、35 CANDIDATE、6 AMBIGUOUS、176 UNRESOLVED。**目标插件方法没有源码，五层提取结果 UNRESOLVED**，不能把更上层 IntelliJ 框架源码当作目标位置。

## 补充源码的范围

只下载公开仓库的一份历史源文件作为参考，没有 clone、worktree 或引入生产依赖：

https://github.com/ballerina-platform/lsp4intellij/blob/8037f7bfccd21bd9c34e6e43b51700d743b52672/src/main/java/org/wso2/lsp4intellij/IntellijLanguageClient.java

所查最新版本 `f37ef3ba18dad231adbbf987c12dcee976cce536` 已改用 DefinitionRegistry，不符合原栈调用结构，因此没有拿最新代码强行对应事故。上述历史版本中的方法体为：

```java
public static boolean isExtensionSupported(VirtualFile virtualFile) {
    return extToServerDefinition.keySet().stream().anyMatch(keyMap ->
            keyMap.getLeft().equals(virtualFile.getExtension()) || (virtualFile.getName().matches(keyMap.getLeft())));
}
```

以该单文件参考目录作为 `--source-root`，**再次从真实工作簿运行** Finder 和 Repair：Finder 1 LOCATED / 265 UNRESOLVED；Repair 五层结果 PARTIAL，完整定位 `isExtensionSupported:175-178`。lambda 和缺失的其他插件方法仍保持未定位，没有修改五层限制或伪造 lambda 的源码定位。

已独立核对返回方法的源码 SHA256、行范围和正文：

```text
55a9574465d9e165f0800bc1604f25d2d89930c80a31adc73062de821326bde3
```

这是**固定参考源码的正确位置**，不是运行二进制版本匹配证明。用户明确表示不知道事故插件版本/提交号。保存的参考源文件比下载文本多一个尾部空行，哈希固定的是该保存副本；保留 Apache-2.0 版权头及 provenance。不能将该候选直接应用到未知的 Huawei fork。

## 修复方式：P1 注册阶段预编译

新增 `repair/main/kotlin/src/pool/s1_expensive_work/P1RegexPrecompilation.kt`，通过 `repair.py --s1-regex` 调用，前置检查位于 `RelocationPreconditions.checkRegexPrecompilation`。

源码显示规则来自 `processDefinition` 的注册流程。候选在规则发布到 `extToServerDefinition` 之前预编译，文件类型查询保持同步：

```java
// 注册阶段：早于规则进入查询集合
prepareRegex(ext);
extToServerDefinition.put(keyPair, definition);

// 热路径（保留扩展名相等时的短路）
keyMap.getLeft().equals(virtualFile.getExtension()) ||
    matchesPreparedRegex(virtualFile.getName(), keyMap.getLeft());
```

核心辅助方法：

```java
private static boolean matchesPreparedRegex(String fileName, String regex) {
    Pattern pattern = preparedRegexes.get(regex);
    return pattern == null ? fileName.matches(regex) : pattern.matcher(fileName).matches();
}
```

- 缓存以不可变正则字符串为键，最多 256 条，注册线程同步控制容量；查询只有 ConcurrentHashMap.get，不持有编译锁。
- 共享 Pattern，每次创建新的 Matcher，不共享可变匹配状态。
- 在注册阶段遇到非法正则只忽略预编译失败，不提前拒绝注册；后续直接扩展名命中仍合法，实际进入正则分支才按原来的 String.matches 抛错。
- 容量满时不预编译新规则，查询回退原行为。移除注册不会因缓存残留变成命中，活跃规则仍由原注册表决定。保留最多 256 个历史 pattern，容量可能被已移除规则占据，这是当前有界方案的优化范围限制。
- 同时替换 `editorOpened` 中另外两处同类匹配，避免同一规则在兄弟调用点继续重复编译。
- `isExtensionSupported` 仍同步返回 boolean，没有 future.get/join，也不改变调用者的完成时序。

选择 P1 是因为编译输入在注册阶段已经可用；不是把同步 boolean 查询强行改成异步。**注册线程是否为 BGT 未建立，因此不保证首次注册编译离开 EDT**。该候选减少已准备规则的重复编译，不解决匹配回溯本身的耗时，也不保证容量外的规则获得改善。

生成器要求真实分类命中 Pattern.compile、提取到指定调用方，并通过路径边界、文件哈希、完整方法范围和固定版本检查。未定位、源文件变化、其他 owner/方法不会生成此补丁。不绑定 Excel 行号。

输出 `s1_regex`：`CANDIDATE_PATCH`、`applied=false`、`eligible_for_application=false`、`source_basis=PINNED_UPSTREAM_REFERENCE_RUNTIME_VERSION_UNCONFIRMED`。暂未接入通用 repair_selection 自动选择，使用专用入口。

## 测试结果

- Kotlin 构建 exit 0。
- `test_regex_precompilation.py`：生成补丁在副本上 `git apply --check`、实际 apply、全文一致性通过；源文件修改、非 RUNNABLE UI、未命中 compile 的拒绝检查通过。
- 抽取原始/生成后的注册方法和查询方法，以真实 JDK regex 编译运行；Pair、VirtualFile、日志和定义对象是受控替身。测试扩展名短路、非法正则异常时机、空扩展名、flags、Unicode 文件名、重复注册、移除规则、容量回退及 8 线程并发匹配。
- 24 项相关测试全部通过，9.763 秒，0 failure/error/skip。没有恢复或重跑暂停的 4746 行实验。
- 单次受控 JDK 工作负载：200 个 alternatives，预热后 3000 次查询，原实现 22.611 ms，预编译候选 1.2495 ms。使用真实编译/匹配，无人工延迟；并非真实 IDE 卡顿复现，也不是统计基准或事故改善幅度。

没有编译完整插件、应用生产补丁或验证真实 IDE 卡顿消失。当前工程真实 IDE 测试仍有先前记录的缺失 JPS 模块问题，本轮未为插件参考源码实验修改模块注册。

## 复现与产物

以下命令在 `tools/edt-freeze-finder` 执行。Finder 输入始终是原工作簿；只在第二次替换 source-root。

```powershell
# 第二次 Finder：固定公开参考源码
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -B -c "import sys,runpy;sys.path.insert(0,'C:/Users/Administrator/AppData/Local/Temp/finder-source-deps-wheel-20260926');sys.path.insert(0,'finder/main');sys.argv=['find_sources.py','--workbook','D:/intellij-community-master/intellij底座问题堆栈-1.xlsx','--source-root','out/edt-freeze-finder/pattern-20260927/upstream-source','--row','4238','--output','out/edt-freeze-finder/pattern-20260927/upstream-finder.jsonl'];runpy.run_path('finder/main/find_sources.py',run_name='__main__')"
powershell -NoProfile -ExecutionPolicy Bypass -File repair/main/scripts/build-q1.ps1 -Python D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe
$env:Q1_CLASSPATH=(Get-Content "$env:TEMP/repair-q1-build/classpath.txt" -Raw).Trim()
& D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/main/python/repair.py --input out/edt-freeze-finder/pattern-20260927/upstream-finder.jsonl --output out/edt-freeze-finder/pattern-20260927/regex-repair-final.jsonl --q1-classpath $env:Q1_CLASSPATH --s1-regex
```

输出文件排他创建，重跑需改输出名称。首次 Finder 的 source-root 为 `D:/intellij-community-master`，输出 `finder.jsonl`，对应 `repair.jsonl`。

```powershell
@'
import sys,unittest
sys.path.insert(0,'repair/tests')
r=unittest.TextTestRunner().run(unittest.TestLoader().loadTestsFromNames([
 'test_regex_precompilation','test_repair_entry','test_repair_selection',
 'test_extract_method','test_p2_relocation','test_q2_classifier']))
sys.exit(not r.wasSuccessful())
'@ | D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe -
```

所有本轮产物在 `out/edt-freeze-finder/pattern-20260927/`：`matches.json`、两次 Finder/Repair 输出、`regex-repair-final.jsonl`、`source-provenance.json`、`context.md`、`proposal.json`、`candidate.patch`、`IntellijLanguageClient.patched.java`。早期 `regex-repair.jsonl` 的补丁尾空行问题已修复，该文件不作为最终结果。

下一步只需针对实际插件源码/安装包确认调用方版本和注册路径，再应用匹配版本的候选并运行插件集成与 EDT 验证；版本缺失时保留为参考候选。研究仓库 HEAD `83a21329f4f811fca1b5a4a555eb6504f2ff4d78` 本轮检查未变化，无新增阅读。
