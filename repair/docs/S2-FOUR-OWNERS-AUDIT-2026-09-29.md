# Four waiting monitor owners: source/stack audit

2026-09-29. Read-only investigation using saved Finder full-repair-20260928/finder.jsonl and s2-monitor-owners-20260929/summary.json. No new automatic cycle classifier or repair patch.

| Row | Explicit monitor owner | Observed owner wait | Verdict |
| --- | --- | --- | --- |
| 3587 | DefaultDispatcher-worker-41; AWTTreeLock@53d0e90b | Object.wait → EventQueue.invokeAndWait → Window.doDispose/dispose | Direct wait for EDT dispatch completion supported |
| 3623 | DefaultDispatcher-worker-40; SynchronizedLazyImpl@239cda26 | Thread.sleep → TimeUnit.sleep → ConfirmingTrustManager.createForStorage | Observed sleep while retaining lazy monitor; no direct EDT completion wait shown |
| 3643 | DefaultDispatcher-worker-39; SynchronizedLazyImpl@429c6eb | Same sleep path | Same verdict |
| 3656 | DefaultDispatcher-worker-44; SynchronizedLazyImpl@57ad64d2 | Same sleep path | Same verdict |

3587 evidence: EDT BLOCKED in Container.findComponentAt, explicit owned-by worker41. Owner WAITING on EventQueue$1AWTInvocationLock@a92443e. Owner frames0–5 show Object.wait0/wait/wait, EventQueue.invokeAndWait, Window.doDispose, Window.dispose; frames14–16 ActionButton.removeNotify, Container.remove(int), Container.remove(Component). Upper business path includes BetaClubProjectActivity.blockIssusReport/execute (Huawei plugin).

Read local JBR25 lib/src.zip at C:/programdata/_bazel/j66whxgf/external/+jbr_toolchains+remotejbr25_win/lib/src.zip:

- java.desktop/java/awt/Container.java:1224–1231 holds getTreeLock across comp.removeNotify;2679–2681 findComponentAt acquires same tree lock.
- EventQueue.java:1304–1327 creates InvocationEvent, posts it, loops while !event.isDispatched() with lock.wait(),then propagates failure. No timeout argument; interruption remains an exit.
- Window.java:1207–1223 runs DisposeAction directly on EDT, otherwise invokes EventQueue.invokeAndWait(this,action).

Thus3587 has strong support for the cycle EDT → tree monitor → worker41 → EDT dispatch completion. Direct BGT-to-EDT wait is verified against current JBR source. Historical exact JBR build/AppContext identity and dispatch-event object association remain unverified; no permanent-deadlock/runtime reproduction claim. Object.wait releases its invocation monitor, not the outer AWT tree monitor.

Other three owners have complete visible stack paths through SynchronizedLazyImpl initialization and certificate setup, ending in sleep rather than invokeAndWait/Future completion wait. Current platform/platform-api/src/com/intellij/util/net/ssl/ConfirmingTrustManager.java createForStorage simply constructs the manager, with no TimeUnit.sleep. Historical implementation/instrumentation is different or unavailable; do not invent a sleep duration, purpose or EDT-dependent polling condition. These snapshots do not establish a return edge to EDT and do not exclude unseen dependencies elsewhere in time.

Remote research43be46f995a0f5c49e905c002a404efaccdd3b2a checked unchanged; no new materials read. No code changed/tests run; only saved evidence and source inspected. Next: prioritize3587 for business-entry threading repair review rather than blindly replacing JDK disposal waits; remaining three require historical createForStorage source to explain sleep. S1/4746 unchanged.
