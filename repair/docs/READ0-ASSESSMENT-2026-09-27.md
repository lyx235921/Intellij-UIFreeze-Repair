# FileDispatcherImpl.read0 真实记录核验

2026-09-27，暂不继续第124行，改查Q1.1中的read0。重新用Finder从原工作簿读取1247、1248、1249、1791、1792、1793、1794，再用Repair --s1-p2定位。两入口exit0；7 accepted，7 Q1.1，7识别，0现有补丁。6条PARTIAL、1249为UNRESOLVED。独立复核所有返回方法的当前文件SHA256与完整行范围正文，全部一致。未改生产代码。

| 类型 | 行号 | 证据 |
| --- | --- | --- |
| 字符宽度/文本布局 | 1247、1791、1792、1793 | read0 ← FileChannelImpl.read ← TrueTypeFont.readBlock ← glyph advance/FontDesignMetrics ← DefaultFontLayoutService.charWidth2D ← FontInfo.charWidth2D。1247/1792/1793到SimpleTextFragment构造，1791到CharWidthCache缓存未命中计算。 |
| 通知文字绘制 | 1248 | TrueTypeFont.readBlock、glyph image、drawString、Swing文本绘制；项目上下文为NotificationCenterPanel.paintChildren等。 |
| 字体字符支持/回退 | 1794 | TrueTypeFont.getTableBuffer ← CMap.initialize ← TrueTypeGlyphMapper ← Font.canDisplay；定位到FallBackInfo.canDisplay，其他层保留歧义/未定位。 |
| 配置/XML读取 | 1249 | read0 ← FileChannelImpl.read ← ChannelInputStream.read；索引9–15不可解析，上方仍见SafeStAXStreamBuilder和FileBasedStorage.loadLocalData。提取器遇到缺口停止，不能把缺口当成已核验调用边。 |

7条均是UI RUNNABLE真实堆栈。6条字体路径不能简单等同于可在后台执行的普通文件读写；尤其不能把Swing paint方法整体搬到BGT。P1字体/字形准备与P2独立布局计算均可能是候选，当前方法名级P2_FIRST不是源码可迁移结论。

下一步可从1791 CharWidthCache.calcValue入手：同步结果如何消费、EditorView/字体和渲染上下文的线程要求、缓存失效与提交时序仍需核验。现有缓存不意味着cache miss没有卡顿，也不代表缓存对象可跨线程写。本文只完成分组及局部源码核验，不宣称已有安全迁移边界或复现性能。

输出：`out/edt-freeze-finder/read0-20260927/{finder.jsonl,repair.jsonl,context.md,summary.json}`。context.md保留7条原始堆栈和所提取完整方法。当前源码版本与堆栈存在差异。

运行方式与ROW124-CONTEXT-2026-09-27.md相同：使用便携Python及tree-sitter 0.25.2临时依赖，find_sources.py追加 `--row 1247 --row 1248 --row 1249 --row 1791 --row 1792 --row 1793 --row 1794`，输出上述finder.jsonl；repair.py --input对应文件 --output对应repair.jsonl --q1-classpath读取TEMP/repair-q1-build/classpath.txt --s1-p2。Finder共833帧：579 UNRESOLVED、94 CANDIDATE、140 LOCATED、20 AMBIGUOUS，读取102源码文件，无索引错误。

第124行缺ScanPanel源码的限制仍存在，但不阻塞本次read0调查。research HEAD83a21329未变，无新增阅读。
