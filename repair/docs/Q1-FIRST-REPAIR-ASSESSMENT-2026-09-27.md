# Q1 首个修复案例评估

范围：比较已保存的真实栈及当前源码，选择首个 S1 实验；未修改生产代码，未运行新的性能测试，不宣称全量候选难度排序。

## 推荐：Excel 1238 行

现有全量 Q1 输出：Q1.6，命中 `java.util.zip.Inflater.end`。运行栈为 EDT 上 `DumbServiceAppIconProgress.finish` 回调 → `AppIcon$BaseIcon.setOkBadge` → `Win7AppIcon._setOkBadge` → `ImageIO.read` → PNG 解码 → Inflater 清理。业务为图像资源处理；分类器当前没有将其同时标为 Q1.7。

当前源码 `platform/platform-impl/src/com/intellij/ui/AppIcon.java:642` 明确 assert EDT；654–656 行在类监视器内读取固定 `/mac/appIconOk512.png`、编码 ICO、创建原生图标。`myOkIcon` 已有缓存，因此主要针对首次加载，不能声称每次调用都会解码。`DumbServiceAppIconProgress.java` 的 finish 使用 invokeLaterIfNeeded 安排徽标更新。

建议 P2：后台读取 PNG、解码并生成 ICO 字节；EDT 保留原生句柄及最终 UI 更新，直到核对原生 API 的线程契约。也可结合 P1 在实际需要前异步预热，但不能让 EDT 等 Future。该方法为 void，结果用于提示性徽标，较同步返回文件内容更易拆分。

必须覆盖：重复请求只启动一次；加载中收到隐藏请求不能被旧回调重新显示；窗口销毁与状态过期；加载失败可控；资源流关闭。不要把整个 _setOkBadge 原样移到后台。

验证：冷缓存下阻塞/延迟图像准备，确认 EDT 心跳不中断；核对前后 ICO 数据/显示效果；并发显示/隐藏及销毁场景；Windows 实际索引完成场景。真实栈没有耗时分解，不能归因于 Inflater.end 本身，也没有证明这一变更足以解决原事件全部卡顿。

## 比较

- 1807，Q1.1：文件重载读盘，当前 FileDocumentManagerImpl.reloadFromDisk 将读取嵌在写动作及文档替换流程；后台拆分必须处理文件版本、文档修改、事件顺序、编码及冲突。优先级低于1238。
- 1345，Q1.1：字体回退触发文件属性读取；实际属于布局/字体路径。此前仅受控字体实验，不是生产修复；输入字体/文本及缓存状态、并发契约更复杂，不作为第一例。
- 4240–4242，Q1.4：String.matches → Pattern.compile，可考虑预编译，可能与 S5 消除重复工作重叠。但本轮未核对对应第三方业务源码，不列为可立即改动的案例。
- 类加载、索引、PSI 和通用图标加载器：涉及初始化顺序、模型一致性或大量调用方；不因为底层方法命中多就先修改这些公共方法。

结论：先以1238实现小范围 P2 候选，再做行为和 EDT 响应验证。评估结论不等同于已验证安全迁移。

资料预检：research-workspace HEAD 仍为83a21329f4f811fca1b5a4a555eb6504f2ff4d78，无新增阅读，历史未读保持未读。当前 finder/main、repair/main 在父仓库仍为未跟踪；独立发布仓库不代表父工作区已提交。
