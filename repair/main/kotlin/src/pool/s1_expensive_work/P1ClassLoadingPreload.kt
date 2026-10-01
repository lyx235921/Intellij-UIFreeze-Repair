package org.jetbrains.research.lockrepair.pool.s1

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import java.nio.file.Path

/** Class and native loading need an initialization boundary, not a rewrite of ClassLoader/JDK native methods. */
object P1ClassLoadingPreload {
  internal const val TERMINAL_PATH = "plugins/terminal/frontend/src/com/intellij/terminal/frontend/fus/TerminalFocusFusService.kt"
  internal const val GIT_PATH = "plugins/git4idea/backend/src/branch/GitBranchIncomingOutgoingManager.java"
  internal const val GIT_SHA = "c2b30ca5f5e0aa931a54966e7ef1f72eaa746f0f6dcdeee3539d1c657fbee937"
  internal const val NOTIFICATION_PATH = "platform/platform-impl/src/com/intellij/diagnostic/IdeMessagePanel.java"
  internal const val NOTIFICATION_SHA = "f5dfe6ffa793a09d7f6027a251fcb337324aabfa55935aa2b83854269002bd84"
  internal val triggers = setOf(
    "com.intellij.util.lang.UrlClassLoader.findClass",
    "java.lang.ClassLoader.defineClass",
    "java.lang.ClassLoader.defineClass0",
    "java.lang.ClassLoader.defineClass2",
    "java.lang.ClassLoader.defineClassSourceLocation",
    "java.lang.ClassLoader.loadClass",
    "jdk.internal.loader.NativeLibraries.load"
  )

  fun propose(finder: JsonObject, q1: JsonObject, root: Path): JsonObject {
    val contexts = q1.getAsJsonObject("method_context").getAsJsonArray("results").map { it.asJsonObject }
    val hits = q1.getAsJsonObject("classification").getAsJsonArray("matched_frames").map { it.asJsonObject }
      .filter { it["symbol"].asString in triggers }.distinctBy { it["symbol"].asString to it["thread_id"].asString }
    val decisions = JsonArray()
    val proposals = JsonArray()
    for (hit in hits) {
      val layers = JsonArray().apply {
        contexts.filter { it["trigger_symbol"] == hit["symbol"] && it["thread_id"] == hit["thread_id"] }
          .forEach { add(it.deepCopy()) }
      }
      val decision = RelocationPreconditions.pendingPreloadDecision(hit, layers, root)
      val checked = RelocationPreconditions.checkTerminalListener(hit, layers, root)
      if (checked.sourceText != null) {
        decision.addProperty("status", "CANDIDATE_PATCH")
        decision.addProperty("p1_status", "CANDIDATE")
        decision.addProperty("selected_strategy", "P1_PRELOAD_BEFORE_CRITICAL_REGION")
        decision.addProperty("generator_status", "CANDIDATE_IMPLEMENTED")
        decision.addProperty("reason", checked.reason)
        decision.add("preconditions", RelocationPreconditions.report("P1_PRELOAD_BEFORE_CRITICAL_REGION",
          "TerminalFocusFusService listener construction before UI initialization", listOf(
            RelocationPreconditions.Check("SOURCE_BOUND_LISTENER_PREPARATION", RelocationPreconditions.Verdict.PASS,
              "Pinned whole source; pure listener creation; same service scope; UI initialization and registration remain together")
          )).apply { addProperty("generator_status", "CANDIDATE_IMPLEMENTED") })
        decision.addProperty("patch_generated", true)
        decision.addProperty("proposal_index", proposals.size())
        proposals.add(terminalPatch(checked.sourceText))
      }
      else {
        val gitCheck = RelocationPreconditions.checkGitListener(finder, hit, root)
        val git = if (gitCheck.source != null) gitCheck else RelocationPreconditions.checkNotificationPreparation(finder, hit, root)
        if (git.source != null && git.method != null) {
          decision.addProperty("status", "CANDIDATE_PATCH")
          decision.addProperty("p1_status", "CANDIDATE")
          decision.addProperty("selected_strategy", "P1_PRELOAD_BEFORE_CRITICAL_REGION")
          decision.addProperty("generator_status", "CANDIDATE_IMPLEMENTED")
          decision.addProperty("reason", git.report["reason"].asString)
          decision.add("preconditions", git.report)
          decision.add("supplemental_context", git.method)
          decision.addProperty("patch_generated", true)
          val target = git.method["path"].asString
          val index = proposals.indexOfFirst { it.asJsonObject["path"].asString == target }
          decision.addProperty("proposal_index", if (index < 0) proposals.size() else index)
          if (index < 0) proposals.add(if (target == GIT_PATH) gitPatch(git.source, git.method)
                                    else notificationPatch(git.source, git.method))
        }
      }
      decisions.add(decision)
    }
    return JsonObject().apply {
      addProperty("schema_version", "repair-s1-loading-proposal/1")
      add("record_id", q1["record_id"])
      addProperty("status", when {
        decisions.isEmpty -> "NOT_APPLICABLE"
        proposals.isEmpty -> "INSUFFICIENT_EVIDENCE"
        decisions.all { it.asJsonObject["patch_generated"].asBoolean } -> "CANDIDATE_PATCH"
        else -> "PARTIAL"
      })
      add("decisions", decisions)
      add("proposals", proposals)
      addProperty("applied", false)
      addProperty("eligible_for_application", false)
    }
  }

  private fun notificationPatch(source: String, method: JsonObject): JsonObject {
    val before = method["source_text"].asString
    val createStart = before.indexOf("    var notification = new Notification(")
    val createEnd = before.indexOf("    var layoutData", createStart)
    val creation = before.substring(createStart, createEnd).trimEnd()
    val ui = before.replace("showErrorNotification(@NotNull Project project, @NotNull IdeFrame frame)",
      "showPreparedErrorNotification(@NotNull Project project, @NotNull IdeFrame frame, Notification notification)")
      .replace(creation + "\n\n", "")
      .replace("    if (balloon != null) {", "    if (myP1Disposed || project.isDisposed() || !isActive(frame) ||\n" +
        "        messagePool.getState() != MessagePool.State.UnreadErrors || balloon != null) {")
    val wrapper = """
  private void showErrorNotification(@NotNull Project project, @NotNull IdeFrame frame) {
    if (myP1Disposed || project.isDisposed() || balloon != null || !myP1NotificationPending.compareAndSet(false, true)) return;
    ApplicationManager.getApplication().executeOnPooledThread(() -> {
      try {
        if (myP1Disposed || project.isDisposed()) {
          myP1NotificationPending.set(false);
          return;
        }
        Notification notification = prepareErrorNotification();
        ApplicationManager.getApplication().invokeLater(() -> {
          try {
            showPreparedErrorNotification(project, frame, notification);
          }
          finally {
            myP1NotificationPending.set(false);
          }
        });
      }
      catch (Throwable error) {
        myP1NotificationPending.set(false);
        throw error;
      }
    });
  }

  private Notification prepareErrorNotification() {
    __CREATION__
    return notification;
  }

  @RequiresEdt
    """.trimIndent().prependIndent("  ").replace("    __CREATION__", creation)
    val replacement = wrapper + "\n" + ui
    val after = source.replace(before, replacement)
      .replace("  private Balloon balloon;", "  private Balloon balloon;\n" +
        "  private volatile boolean myP1Disposed;\n  private final AtomicBoolean myP1NotificationPending = new AtomicBoolean();")
      .replace("  public void dispose() {\n    messagePool", "  public void dispose() {\n    myP1Disposed = true;\n    messagePool")
    return JsonObject().apply {
      addProperty("status", "CANDIDATE_PATCH")
      addProperty("strategy", "P1_PRELOAD_BEFORE_CRITICAL_REGION")
      addProperty("path", NOTIFICATION_PATH)
      addProperty("expected_sha256", NOTIFICATION_SHA)
      addProperty("before", before)
      addProperty("replacement", replacement)
      addProperty("replacement_source", after)
      addProperty("eligible_for_application", false)
      addProperty("applied", false)
      addProperty("readiness", "REQUIRES_REAL_IDE_NOTIFICATION_AND_CLASS_LOADING_VALIDATION")
      add("limits", JsonArray().apply {
        add("Notification and action preparation only; balloon/layout/theme access remains on EDT")
        add("Delayed notification is dropped if panel/project disposed, frame inactive, or no unread errors")
        add("Single pending preparation; actual application scheduling and plugin class initialization unverified")
      })
      val oldLines = source.removeSuffix("\n").lines()
      val newLines = after.removeSuffix("\n").lines()
      addProperty("patch", buildString {
        append("--- a/$NOTIFICATION_PATH\n+++ b/$NOTIFICATION_PATH\n@@ -1,${oldLines.size} +1,${newLines.size} @@\n")
        oldLines.forEach { append('-').append(it).append('\n') }
        if (!source.endsWith('\n')) append("\\ No newline at end of file\n")
        newLines.forEach { append('+').append(it).append('\n') }
        if (!after.endsWith('\n')) append("\\ No newline at end of file\n")
      })
    }
  }

  private fun gitPatch(source: String, method: JsonObject): JsonObject {
    val replacement = """
  public void activate() {
    ApplicationManager.getApplication().executeOnPooledThread(() -> {
      if (myP1Disposed || myProject.isDisposed()) return;
      var listener = new GitVcsSettings.GitVcsSettingsListener() {
        @Override
        public void incomingCommitsCheckStrategyChanged(@NotNull GitIncomingRemoteCheckStrategy strategy) {
          ApplicationManager.getApplication().invokeLater(() -> {
            if (!myP1Disposed && !myProject.isDisposed()) updateIncomingScheduling();
          });
        }
      };
      ApplicationManager.getApplication().invokeLater(() -> {
        if (myP1Disposed || myProject.isDisposed()) return;
        if (myConnection == null) {
          myConnection = myProject.getMessageBus().connect(this);
          myConnection.subscribe(GitRepository.GIT_REPO_CHANGE, this);
          myConnection.subscribe(GIT_AUTHENTICATION_SUCCESS, this);
          myConnection.subscribe(GitVcsSettings.GitVcsSettingsListener.TOPIC, listener);
        }
        updateAllBranchesWithOutgoing();
        updateIncomingScheduling();
      });
    });
  }
    """.trimIndent().prependIndent("  ")
    val after = source.replace(method["source_text"].asString, replacement)
      .replace("  private @Nullable MessageBusConnection myConnection;",
        "  private volatile boolean myP1Disposed;\n  private @Nullable MessageBusConnection myConnection;")
      .replace("  public void dispose() {\n    stopScheduling();",
        "  public void dispose() {\n    myP1Disposed = true;\n    stopScheduling();")
    return JsonObject().apply {
      addProperty("status", "CANDIDATE_PATCH")
      addProperty("strategy", "P1_PRELOAD_BEFORE_CRITICAL_REGION")
      addProperty("path", GIT_PATH)
      addProperty("expected_sha256", GIT_SHA)
      add("before", method["source_text"])
      addProperty("replacement", replacement)
      addProperty("replacement_source", after)
      addProperty("eligible_for_application", false)
      addProperty("applied", false)
      addProperty("readiness", "REQUIRES_GIT_PLUGIN_ACTIVATION_ORDER_AND_REAL_CLASS_LOADING_VALIDATION")
      add("limits", JsonArray().apply {
        add("Anonymous listener construction only; message bus subscription and scheduling remain on EDT")
        add("Activation already asynchronous, but pooled preparation adds delay and may reorder multiple activation requests")
        add("Model tests do not prove real plugin lifecycle or matching incident version")
      })
      val oldLines = source.removeSuffix("\n").lines()
      val newLines = after.removeSuffix("\n").lines()
      addProperty("patch", buildString {
        append("--- a/$GIT_PATH\n+++ b/$GIT_PATH\n@@ -1,${oldLines.size} +1,${newLines.size} @@\n")
        oldLines.forEach { append('-').append(it).append('\n') }
        if (!source.endsWith('\n')) append("\\ No newline at end of file\n")
        newLines.forEach { append('+').append(it).append('\n') }
        if (!after.endsWith('\n')) append("\\ No newline at end of file\n")
      })
    }
  }

  private fun terminalPatch(source: String): JsonObject {
    val after = source.replace(
      "coroutineScope.launch(Dispatchers.UI + CoroutineName(\"TerminalFocusFusService initialization\")) {\n" +
        "      initializeState()\n      installAWTListener()\n    }",
      "coroutineScope.launch(Dispatchers.Default + CoroutineName(\"TerminalFocusFusService initialization\")) {\n" +
        "      val listener = createAWTListener()\n" +
        "      kotlinx.coroutines.withContext(Dispatchers.UI) {\n" +
        "        initializeState()\n        installAWTListener(listener)\n      }\n    }"
    ).replace("  private fun installAWTListener() {\n    val listener = AWTEventListener { event ->",
      "  private fun createAWTListener(): AWTEventListener {\n    return AWTEventListener { event ->")
      .replace("    Toolkit.getDefaultToolkit().addAWTEventListener(listener, FOCUS_EVENT_MASK or WINDOW_FOCUS_EVENT_MASK)",
        "  }\n\n  private fun installAWTListener(listener: AWTEventListener) {\n" +
        "    Toolkit.getDefaultToolkit().addAWTEventListener(listener, FOCUS_EVENT_MASK or WINDOW_FOCUS_EVENT_MASK)")
    return JsonObject().apply {
      addProperty("status", "CANDIDATE_PATCH")
      addProperty("strategy", "P1_PRELOAD_BEFORE_CRITICAL_REGION")
      addProperty("path", TERMINAL_PATH)
      addProperty("expected_sha256", "ec827ad9a0516c7a18b4f4003f54fdf1642a99a251386e0c07f29136c0897830")
      addProperty("replacement_source", after)
      addProperty("readiness", "REQUIRES_TARGET_IDE_FOCUS_AND_BOOTSTRAP_VALIDATION")
      addProperty("eligible_for_application", false)
      addProperty("applied", false)
      add("limits", JsonArray().apply {
        add("Only the reviewed TerminalFocusFusService AWT listener bootstrap, not arbitrary defineClass0 calls")
        add("Background preparation delays registration; transient focus events before initialization remain unobserved")
        add("Other UI-side class loading and coroutine bootstrap remain; incident version and real freeze improvement unverified")
      })
      val oldLines = source.removeSuffix("\n").lines()
      val newLines = after.removeSuffix("\n").lines()
      addProperty("patch", buildString {
        append("--- a/$TERMINAL_PATH\n+++ b/$TERMINAL_PATH\n@@ -1,${oldLines.size} +1,${newLines.size} @@\n")
        oldLines.forEach { append('-').append(it).append('\n') }
        newLines.forEach { append('+').append(it).append('\n') }
      })
    }
  }
}
