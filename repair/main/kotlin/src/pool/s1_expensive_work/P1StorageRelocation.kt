package org.jetbrains.research.lockrepair.pool.s1

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import java.nio.file.Path

/** Storage/path triggers with source-scoped proposals rather than unconditional rewrites of synchronous getters. */
object P1StorageRelocation {
  internal const val FS = "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl."
  internal val triggers = setOf(FS + "getName", FS + "getNameByNameId", FS + "readAttribute", FS + "readSymlinkTarget",
    "com.intellij.workspaceModel.core.fileIndex.impl.WorkspaceFileIndexDataImpl.getFileInfo")
  internal val pathTriggers = setOf(
    "java.io.WinNTFileSystem.canonicalize",
    "sun.nio.fs.WindowsNativeDispatcher.GetFinalPathNameByHandle",
    "sun.nio.fs.WindowsNativeDispatcher.GetFullPathName0",
    "sun.nio.fs.WindowsNativeDispatcher.GetLogicalDrives"
  )

  internal const val REFRESH_PATH = "platform/platform-impl/src/com/intellij/openapi/vfs/impl/local/LocalFileSystemImpl.java"
  internal const val REFRESH_OWNER = "com.intellij.openapi.vfs.impl.local.LocalFileSystemImpl"

  fun propose(finder: JsonObject, q1: JsonObject, root: Path): JsonObject {
    val context = q1.getAsJsonObject("method_context")
    val hits = q1.getAsJsonObject("classification").getAsJsonArray("matched_frames").map { it.asJsonObject }
      .filter { it["symbol"].asString in triggers || it["symbol"].asString in pathTriggers }
      .distinctBy { it["symbol"].asString to it["thread_id"].asString }
    val decisions = JsonArray()
    val patches = JsonArray()
    for (hit in hits) {
      val symbol = hit["symbol"].asString
      val layers = JsonArray().apply {
        context.getAsJsonArray("results").map { it.asJsonObject }.filter {
          it["trigger_symbol"] == hit["symbol"] && it["thread_id"] == hit["thread_id"]
        }.forEach { add(it.deepCopy()) }
      }
      val decision = JsonObject().apply {
        add("trigger", hit.deepCopy())
        add("method_contexts", layers)
        addProperty("initial_priority", RepairSelection.initialPriority(symbol))
        addProperty("status", "INSUFFICIENT_EVIDENCE")
        addProperty("p1_status", "INSUFFICIENT_EVIDENCE")
        addProperty("p2_status", "INSUFFICIENT_EVIDENCE")
        addProperty("p3_status", "DEFERRED")
        addProperty("patch_generated", false)
        addProperty("applied", false)
        addProperty("eligible_for_application", false)
      }
      if (symbol in pathTriggers && !symbol.endsWith(".GetLogicalDrives")) {
        decisions.add(RelocationPreconditions.pendingPreloadDecision(hit, layers, root))
        continue
      }
      if (symbol in pathTriggers) {
        val pending = RelocationPreconditions.pendingPreloadDecision(hit, layers, root)
        for ((key, value) in pending.entrySet()) decision.add(key, value)
      }
      val checked = RelocationPreconditions.checkQ13(finder, hit, layers, root)
      decision.add("preconditions", checked.report)
      decision.addProperty("reason", checked.report["reason"].asString)
      if (checked.source != null && checked.method != null) {
        decision.add("supplemental_context", checked.method)
        decision.addProperty("status", "CANDIDATE_PATCH")
        decision.addProperty("p2_status", "CANDIDATE")
        decision.addProperty("selected_strategy", "P2_PRECOMPUTE_OUTSIDE_EDT")
        decision.addProperty("patch_generated", true)
        decision.addProperty("generator_status", "CANDIDATE_IMPLEMENTED")
        if (patches.isEmpty) patches.add(refreshPatch(checked.source, checked.method))
        decision.addProperty("proposal_index", 0)
      }
      decisions.add(decision)
    }
    return JsonObject().apply {
      addProperty("schema_version", "repair-s1-q13-proposal/1")
      add("record_id", finder["record_id"])
      addProperty("status", when {
        decisions.isEmpty -> "NOT_APPLICABLE"
        patches.isEmpty -> "INSUFFICIENT_EVIDENCE"
        decisions.all { it.asJsonObject["patch_generated"].asBoolean } -> "CANDIDATE_PATCH"
        else -> "PARTIAL"
      })
      add("decisions", decisions)
      add("proposals", patches)
      addProperty("applied", false)
      addProperty("eligible_for_application", false)
    }
  }

  private fun refreshPatch(source: String, method: JsonObject): JsonObject {
    val before = source.replace("\r\n", "\n")
    val oldMethod = method["source_text"].asString
    val after = before.replace(oldMethod, replacement)
    val oldLines = before.removeSuffix("\n").lines()
    val newLines = after.removeSuffix("\n").lines()
    return JsonObject().apply {
      addProperty("status", "CANDIDATE_PATCH")
      addProperty("strategy", "P2_PRECOMPUTE_OUTSIDE_EDT")
      addProperty("path", REFRESH_PATH)
      add("expected_sha256", method["sha256"])
      addProperty("before", oldMethod)
      addProperty("replacement", replacement)
      addProperty("replacement_source", after)
      addProperty("readiness", "REQUIRES_TARGET_IDE_REFRESH_AND_CANCELLATION_VALIDATION")
      addProperty("eligible_for_application", false)
      addProperty("applied", false)
      addProperty("patch", buildString {
        append("--- a/$REFRESH_PATH\n+++ b/$REFRESH_PATH\n@@ -1,${oldLines.size} +1,${newLines.size} @@\n")
        oldLines.forEach { append('-').append(it).append('\n') }
        newLines.forEach { append('+').append(it).append('\n') }
      })
      add("limits", JsonArray().apply {
        add("Only refreshWithoutFileWatcher(asynchronous=true); synchronous callers remain unchanged")
        add("Dirty marking is idempotent; NBRA may retry and disposal may leave partially dirty flags without starting a refresh")
        add("Cancellation is checked between roots; one large subtree or native/storage call can still delay write access")
        add("Actual IDE refresh ordering, concurrent scanning and cancellation require integration validation")
        add("This is not a general asynchronous implementation of readAttribute/readSymlinkTarget")
      })
    }
  }

  internal val replacement = """
  public void refreshWithoutFileWatcher(boolean asynchronous) {
    Runnable markRootsDirty = () -> {
      for (var root : myManagingFS.getRoots(this)) {
        if (asynchronous) com.intellij.openapi.progress.ProgressManager.checkCanceled();
        ((NewVirtualFile)root).markDirtyRecursively();
      }
    };
    Runnable heavyRefresh = () -> {
      if (asynchronous) {
        ReadAction.nonBlocking(() -> {
          markRootsDirty.run();
          return (Void)null;
        }).expireWith(this)
          .finishOnUiThread(com.intellij.openapi.application.ModalityState.defaultModalityState(), unused -> refresh(true))
          .submit(AppExecutorUtil.getAppExecutorService());
      }
      else {
        markRootsDirty.run();
        refresh(false);
      }
    };

    if (asynchronous && myWatcher.isOperational()) {
      RefreshQueue.getInstance().refresh(true, true, heavyRefresh, myManagingFS.getRoots(this));
    }
    else {
      heavyRefresh.run();
    }
  }
  """.trimIndent().prependIndent("  ")
}
