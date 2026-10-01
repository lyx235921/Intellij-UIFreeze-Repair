package org.jetbrains.research.lockrepair

import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.nio.file.Path
import org.jetbrains.research.lockrepair.pool.s2.ExtractMethodS2
import org.jetbrains.research.lockrepair.pool.s2.RepairSelectionS2
import org.jetbrains.research.lockrepair.pool.s2.WaitResourceEvidence
import org.jetbrains.research.lockrepair.pool.s2.MonitorCycleRepair

/** Stack-based synchronous wait candidates, not root-cause or repair decisions. */
object Q2SynchronousWaitControlClassifier {
  private val methodCategories = mapOf(
    "com.intellij.openapi.progress.util.ProgressIndicatorUtils.awaitWithCheckCanceled" to "Q2.1",
    "com.intellij.util.io.SafeFileOutputStream.waitForBackup" to "Q2.1",
    "org.jetbrains.concurrency.AsyncPromise.get" to "Q2.1",
    "com.huawei.deveco.database.databaseplugin.utils.DatabasesUtil.executeBmCommandsAndCollectResults" to "Q2.1",
    "kotlinx.coroutines.BlockingCoroutine.joinBlocking\$lambda\$0" to "Q2.2",
    "com.intellij.openapi.progress.util.EventStealer.waitForPing" to "Q2.3",
    "com.intellij.openapi.progress.util.EternalEventStealer.dispatchExistingEvent" to "Q2.3",
    "com.intellij.openapi.progress.util.EventStealer.dispatchEvents" to "Q2.3",
    "com.intellij.openapi.actionSystem.impl.AltEdtDispatcher.runOwnQueueBlockingAndSwitchBackToEDT\$lambda\$0" to "Q2.4",
    "sun.java2d.metal.MTLRenderQueue\$QueueFlusher.flushNow" to "Q2.5",
    "sun.awt.AWTThreading.execute" to "Q2.5",
    "javax.swing.ImageIcon.loadImage" to "Q2.5",
    "com.sun.java2d.metal.MTLRenderQueue.flushNow" to "Q2.6",
    "com.intellij.openapi.progress.util.SuvorovProgress.sleep" to "Q2.6",
    "com.intellij.internal.UIFreezeAction.actionPerformed" to "Q2.6",
  )
  private val waitingTops = setOf(
    "jdk.internal.misc.Unsafe.park", "sun.misc.Unsafe.park", "java.lang.Object.wait", "java.lang.Object.wait0",
    "java.lang.Thread.sleep", "java.lang.Thread.sleep0", "java.lang.Thread.sleepNanos0",
  )
  private val lockMethods = setOf(
    "java.util.concurrent.locks.ReentrantLock.lock", "java.util.concurrent.locks.StampedLock.writeLock",
    "java.util.concurrent.locks.ReentrantReadWriteLock\$WriteLock.lock",
    "java.util.concurrent.locks.ReentrantReadWriteLock\$ReadLock.lock",
  )
  private const val FILE_WAIT = "com.intellij.openapi.fileEditor.impl.FileEditorManagerImplKt.waitBlockingAndPumpEdt"
  private const val MODAL_WAIT = "com.intellij.openapi.progress.impl.PlatformTaskSupport.runWithModalProgressBlockingInternal"
  private const val PROGRESS_SLEEP = "com.intellij.openapi.progress.util.SuvorovProgress.sleep"

  private fun symbol(frame: JsonObject): String? = frame["symbol"]?.takeUnless { it.isJsonNull }?.asString
    ?.replace(Regex("^(?:[^/]+//|[^/]+/)(?=[A-Za-z_])"), "")

  fun classify(record: JsonObject): JsonObject {
    val uiIds = record.getAsJsonArray("ui_thread_ids").map { it.asString }.toSet()
    val checks = JsonArray()
    val matches = JsonArray()
    var injected = false
    var lockContext = false
    for (value in record.getAsJsonArray("threads")) {
      val thread = value.asJsonObject
      if (thread["thread_id"].asString !in uiIds) continue
      val frames = thread.getAsJsonArray("frames").map { it.asJsonObject }
      val symbols = frames.map { symbol(it) }
      val top = frames.firstOrNull()
      val topSymbol = symbols.firstOrNull()
      val callerIndex = symbols.indexOfFirst { s ->
        s != null && !s.startsWith("java.") && !s.startsWith("jdk.") && !s.startsWith("sun.misc.")
      }
      val caller = symbols.getOrNull(callerIndex)
      val state = thread["state"].asString
      val categories = linkedSetOf<String>()
      val reason = when {
        top == null || top["index"].asInt != 0 || top["elided"].asBoolean || topSymbol.isNullOrBlank() -> "TOP_FRAME_UNAVAILABLE"
        state == "BLOCKED" -> "MONITOR_OR_NATIVE_BLOCKED"
        state !in setOf("RUNNABLE", "WAITING", "TIMED_WAITING") -> "UNSUPPORTED_STATE"
        topSymbol !in waitingTops -> "NO_CURRENT_WAIT_EVIDENCE"
        symbols.take(12).any { it in lockMethods } -> "EXPLICIT_LOCK_ACQUISITION"
        caller == "com.intellij.ide.IdeEventQueue.getNextEvent" -> when {
          FILE_WAIT in symbols -> { categories.addAll(listOf("Q2.2", "Q2.3")); "PASSED" }
          MODAL_WAIT in symbols -> { categories.add("Q2.3"); "PASSED" }
          else -> "ORDINARY_EVENT_QUEUE_WAIT"
        }
        caller in methodCategories -> {
          categories.add(methodCategories.getValue(caller!!))
          if (caller == PROGRESS_SLEEP) categories.add("Q2.3")
          "PASSED"
        }
        else -> "NO_RULE_MATCH"
      }
      checks.add(JsonObject().apply {
        add("thread_id", thread["thread_id"])
        add("state", thread["state"])
        addProperty("top_symbol", topSymbol)
        addProperty("matching_caller", caller)
        addProperty("result", reason)
      })
      if (categories.isEmpty()) continue
      injected = injected || symbols.any {
        it == "com.sun.java2d.metal.MTLRenderQueue.testFreeze" || it == "com.intellij.internal.UIFreezeAction.actionPerformed"
      }
      lockContext = lockContext || symbols.any {
        it == "com.intellij.platform.locking.impl.NestedLocksThreadingSupport\$ComputationState.acquireWriteIntentPermit"
      }
      for (category in categories) {
        // Keep the waiting primitive, immediate caller and any nested-wait discriminator as evidence.
        for (i in frames.indices.filter { it == 0 || it == callerIndex || symbols[it] in setOf(FILE_WAIT, MODAL_WAIT) }) {
          matches.add(JsonObject().apply {
            add("thread_id", thread["thread_id"])
            add("thread_state", thread["state"])
            add("frame_id", frames[i]["frame_id"])
            addProperty("symbol", symbols[i])
            addProperty("category", category)
          })
        }
      }
    }
    return JsonObject().apply {
      addProperty("scope", "UI_CURRENT_WAIT_WITH_EXACT_CALLER_CONTEXT")
      add("ui_checks", checks)
      addProperty("q2_count", if (matches.size() > 0) 1 else 0)
      addProperty("decision", if (matches.size() > 0) "CANDIDATE" else "UI_CHECK_NOT_PASSED_OR_NO_RULE_MATCH")
      addProperty("injected_test_path", injected)
      addProperty("write_intent_permit_context", lockContext)
      add("matched_methods", JsonArray().apply {
        matches.map { it.asJsonObject["symbol"].asString }.distinct().forEach { add(it) }
      })
      add("categories", JsonArray().apply {
        matches.groupBy { it.asJsonObject["category"].asString }.toSortedMap().forEach { (category, evidence) ->
          add(JsonObject().apply {
            addProperty("category", category)
            addProperty("count", 1)
            add("matched_methods", JsonArray().apply {
              evidence.map { it.asJsonObject["symbol"].asString }.distinct().forEach { add(it) }
            })
            add("frame_ids", JsonArray().apply {
              evidence.map { it.asJsonObject["frame_id"].asString }.distinct().forEach { add(it) }
            })
          })
        }
      })
      add("matched_frames", matches)
    }
  }

  @JvmStatic
  fun main(args: Array<String>) {
    val gson = Gson()
    System.`in`.bufferedReader(Charsets.UTF_8).useLines { lines ->
      for (line in lines) {
        val record = JsonParser.parseString(line).asJsonObject
        require(record["schema_version"].asString == "finder-source-locations/1")
        val result = JsonObject().apply {
          addProperty("schema_version", "repair-q2-classification/1")
          addProperty("problem_family", "Q2")
          add("record_id", record["record_id"])
          add("classification", classify(record))
          add("wait_resource_evidence", WaitResourceEvidence.extract(record))
          add("monitor_cycle_repair", MonitorCycleRepair.assess(record, getAsJsonObject("wait_resource_evidence")))
        }
        if ("--s2-extract-method" in args || "--s2-repair-selection" in args) {
          val root = Path.of(args.firstOrNull { !it.startsWith("--") } ?: record["source_root"].asString)
          val context = ExtractMethodS2.extract(record, result.getAsJsonObject("classification"), root)
          result.add("method_context_s2", context)
          if ("--s2-repair-selection" in args) result.add("repair_selection_s2", RepairSelectionS2.select(context))
        }
        System.out.write((gson.toJson(result) + "\n").toByteArray(Charsets.UTF_8))
        System.out.flush()
      }
    }
  }
}
