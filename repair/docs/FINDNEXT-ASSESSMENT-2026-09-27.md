# FindNextFile0 两例核验

2026-09-27，重新读取真实工作簿1344、4384两行并运行Finder→Repair --s1-p2；均exit0，2 accepted，2 Q1.1命中，两个PARTIAL各2完整方法，0现有补丁。四份返回正文独立通过当前文件SHA256及行范围核验。未改生产代码。

1344：AWT-EventQueue-0 RUNNABLE → ScanPanel.onComplete回调(ScanPanel.java:237) → refreshWithoutFileWatcher → RefreshWorker.fullDirRefresh → listWithAttributesImpl → visitDirectory → DirectoryIterator.hasNext/readNextEntry → FindNextFile0。与124同属插件发起VFS刷新路径，停在枚举下一目录项而非打开枚举。定位到visitDirectory:57–105与listWithAttributesImpl:467–487，仍缺业务ScanPanel源码，不能据此认定比124更易修。

4384：AWT-EventQueue-0 RUNNABLE → VFS after事件/消息总线 → com.huawei.snap.chat.skills.filelistener.AbstractFileActionListener.after(:37) → com.huawei.snap.chat.task.TaskApplicationService.isInterestedAction(:202) → Stream.findFirst → Files$2.hasNext → DirectoryIterator → FindNextFile0。可见是业务判断中消费目录流；不能仅凭符号确定过滤规则、遍历范围或返回值使用方式。提取到的两个方法是MessageBusImplKt.invokeMethod/invokeListener，不是业务读取实现，不应修改消息总线统一异步派发来修这个业务问题。

在当前源码树（排除.git/.idea/out/build/target/node_modules）按ScanPanel、TaskApplicationService、AbstractFileActionListener的.java/.kt文件名搜索，均未找到。Finder亦返回未定位。未调查其他目录或反编译插件。

若4384源码可得，可评估将完整“目录查询→后续处理”任务后台化；若必须立即返回判断，则另评估预加载/缓存。但不得将布尔返回函数直接改为future或在EDT等待。当前仅为候选方向，尚未证明可行。

两例均非当前可直接落地的简单P2模板；主要缺口是插件业务源码而非native调用深度。若优先快速完成本地可验证修复，应优先选择业务入口及消费者均在当前源码树内的案例，或提供4384两份业务类源码。

运行：沿用ROW124-CONTEXT-2026-09-27.md便携Python/tree-sitter依赖配置，find_sources.py参数 --row 1344 --row 4384，输出 out/edt-freeze-finder/findnext-20260927/finder.jsonl；repair.py --input该文件 --output同目录repair.jsonl --q1-classpath读取TEMP/repair-q1-build/classpath.txt --s1-p2。Finder235帧：167未定位、28定位、37候选、3歧义，读取84源码文件，无索引错误。同目录context.md保存完整原始栈及方法正文，summary.json保存核验摘要。

research HEAD83a21329未变，无新增阅读；没有性能测试或生产修复结论。
