# P2 补丁 EDT 响应对比

2026-09-27，直接使用 `out/p2-row1238-20260927/proposal.json` 的 before/replacement 分别编译，交替运行3对独立 JVM。测试使用真实 Swing EDT、CompletableFuture 和 PNG 解码，在双方 ICO 准备替身中施加相同500ms延迟。准备开始后向 EDT 投递心跳，测量排队延迟；100ms内是否响应作为受控判据。

| 轮次 | 原方法心跳延迟 ms | 补丁心跳延迟 ms | 原方法完成 ms | 补丁完成 ms |
|---|---:|---:|---:|---:|
| 1 | 513.279 | 1.655 | 525.361 | 519.081 |
| 2 | 501.547 | 1.906 | 507.412 | 516.984 |
| 3 | 504.409 | 1.623 | 512.916 | 519.261 |

6次运行均完成替身徽标更新，错误数0、准备次数1；原方法三次均未在模拟阻塞期间响应，补丁三次均响应。实验命令 exit0，所有断言通过。

结论：当前补丁能将这段准备工作对 EDT 的占用移走；不是让工作本身变快。尚未证明真实1238卡顿已消失。

限制：2×2合成PNG，窗口/原生任务栏/ICO编码为测试替身，ImageIO磁盘缓存只在测试中关闭。未应用生产补丁、未运行目标IDE或Windows任务栏真实场景。测试延迟是人为设置，不是原始记录测得的耗时。本轮只验证调度机制及受控响应，既有行为测试见S1-P2报告。

复现（工作目录 edt-freeze-finder）：

```powershell
D:/intellij-community-master/out/edt-freeze-finder/layout-python/python.exe repair/tests/measure_p2_responsiveness.py --proposal out/p2-row1238-20260927/proposal.json --output repair/docs/P2-RESPONSIVENESS-2026-09-27.json
```

环境及逐次数据、候选文件SHA256见同名JSON。下一证据门仍为目标IDE编译、真实徽标冷加载及交互验证。
