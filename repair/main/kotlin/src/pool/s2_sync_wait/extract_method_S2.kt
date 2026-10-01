package org.jetbrains.research.lockrepair.pool.s2

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

/** One waiting operation per classified thread; evidence frames are not independent repair sites. */
object ExtractMethodS2 {
  internal val dispatchMethods = setOf(
    "java.awt.EventQueue.invokeAndWait", "javax.swing.SwingUtilities.invokeAndWait",
    "com.intellij.openapi.application.impl.ApplicationImpl.invokeAndWait",
    "com.intellij.openapi.application.impl.InternalThreading.invokeAndWaitWithTransferredWriteAction",
  )
  internal fun symbol(frame: JsonObject): String = frame["symbol"]?.takeUnless { it.isJsonNull }?.asString.orEmpty()
    .replace(Regex("^(?:[^/]+//|[^/]+/)(?=[A-Za-z_])"), "")

  fun extract(finder: JsonObject, classification: JsonObject, root: Path): JsonObject {
    val operations = JsonArray()
    val groups = classification.getAsJsonArray("matched_frames").map { it.asJsonObject }
      .groupBy { it["thread_id"].asString }.toMutableMap()
    val senderStarts = mutableMapOf<String, Int>()
    if (groups.isNotEmpty()) {
      val uiIds = finder.getAsJsonArray("ui_thread_ids").map { it.asString }.toSet()
      for (value in finder.getAsJsonArray("threads")) {
        val thread = value.asJsonObject
        val id = thread["thread_id"].asString
        if (id in uiIds || thread["state"].asString !in setOf("WAITING", "TIMED_WAITING")) continue
        val frames = thread.getAsJsonArray("frames").map { it.asJsonObject }
        val dispatchIndex = frames.indexOfFirst { symbol(it) in dispatchMethods }
        if (dispatchIndex < 0 || frames.take(dispatchIndex + 1).withIndex().any {
            it.value["elided"].asBoolean || it.value["index"].asInt != it.index || symbol(it.value).isBlank()
          }) continue
        if (frames.take(dispatchIndex).none {
            symbol(it) in setOf("jdk.internal.misc.Unsafe.park", "sun.misc.Unsafe.park",
                               "java.lang.Object.wait", "java.lang.Object.wait0", "java.util.concurrent.FutureTask.get")
          }) continue
        senderStarts[id] = dispatchIndex
        groups[id] = listOf(JsonObject().apply {
          addProperty("thread_id", id)
          add("frame_id", frames[dispatchIndex]["frame_id"])
          addProperty("category", "P3_SENDER_CANDIDATE")
        })
      }
    }
    for ((threadId, evidence) in groups) {
      val thread = finder.getAsJsonArray("threads").map { it.asJsonObject }.single { it["thread_id"].asString == threadId }
      val frames = thread.getAsJsonArray("frames").map { it.asJsonObject }
      val contexts = JsonArray()
      val path = JsonArray()
      var layers = 0
      var stopReason = "END_OF_STACK"
      for ((index, frame) in frames.withIndex()) {
        val name = symbol(frame)
        if (frame["elided"].asBoolean || name.isBlank() || frame["index"].asInt != index) {
          stopReason = "INCOMPLETE_STACK_PATH"
          break
        }
        path.add(JsonObject().apply {
          add("frame_id", frame["frame_id"])
          add("index", frame["index"])
          addProperty("symbol", name)
        })
        if (index < (senderStarts[threadId] ?: 0)) continue
        if (listOf("java.", "javax.", "jdk.", "sun.", "com.sun.").any { name.startsWith(it) }) continue
        layers++
        val source = frame.getAsJsonObject("source")
        val context = JsonObject().apply {
          addProperty("thread_id", threadId)
          add("method_frame_id", frame["frame_id"])
          addProperty("method_symbol", name)
          addProperty("method_layer", layers)
          addProperty("status", "UNRESOLVED")
          addProperty("reason", "PROJECT_METHOD_UNAVAILABLE_OR_AMBIGUOUS")
          add("source_status", source["status"])
          add("source_reason", source["reason"])
          add("source_file", frame["file"])
          add("stack_path", path.deepCopy())
          add("candidates", source.getAsJsonArray("candidates").deepCopy())
        }
        val selected = source["selected"]?.takeUnless { it.isJsonNull }?.asJsonObject
        if (selected != null && source["status"].asString in setOf("LOCATED", "CANDIDATE")) {
          try {
            require(source.getAsJsonArray("candidates").any { it == selected }) { "SELECTION_NOT_IN_CANDIDATES" }
            val base = root.toRealPath()
            val relative = Path.of(selected["path"].asString)
            require(!relative.isAbsolute) { "PATH_OUTSIDE_ROOT" }
            val file = base.resolve(relative).normalize()
            require(file.startsWith(base) && file.toRealPath().startsWith(base)) { "PATH_OUTSIDE_ROOT" }
            val bytes = Files.readAllBytes(file)
            val sha = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            require(sha == selected["sha256"].asString) { "SOURCE_CHANGED" }
            val lines = bytes.toString(Charsets.UTF_8).lines()
            val start = selected["start_line"].asInt
            val end = selected["end_line"].asInt
            require(start >= 1 && end >= start && end <= lines.size) { "INVALID_RANGE" }
            val method = selected.deepCopy().apply {
              addProperty("verification", "HASH_MATCHED")
              addProperty("absolute_path", file.toString())
              addProperty("source_text", lines.subList(start - 1, end).joinToString("\n"))
              addProperty("historical_identity", "NOT_CHECKED")
              add("call_sites", JsonArray().apply {
                for (edge in finder.getAsJsonArray("call_edges").map { it.asJsonObject }) {
                  if (edge["caller_frame_id"] != frame["frame_id"]) continue
                  for (site in edge.getAsJsonArray("call_sites").map { it.asJsonObject }) {
                    if (site["path"] == selected["path"] && site["sha256"] == selected["sha256"] &&
                        site["line"].asInt in start..end) add(site.deepCopy())
                  }
                }
              })
            }
            context.add("method", method)
            context.addProperty("status", "METHOD_LOCATED")
            context.addProperty("reason", "CURRENT_SOURCE_HASH_AND_RANGE_VERIFIED")
          }
          catch (error: Exception) {
            context.addProperty("reason", "SOURCE_VERIFICATION_FAILED")
            context.addProperty("verification_error", error.message ?: error.javaClass.simpleName)
          }
        }
        contexts.add(context)
        if (layers == 5) {
          stopReason = "MAX_METHOD_LAYERS"
          break
        }
      }
      val located = contexts.count { it.asJsonObject["status"].asString == "METHOD_LOCATED" }
      operations.add(JsonObject().apply {
        addProperty("thread_id", threadId)
        add("thread_state", thread["state"])
        addProperty("is_ui_thread", finder.getAsJsonArray("ui_thread_ids").any { it.asString == threadId })
        addProperty("operation_role", if (threadId in senderStarts) "BACKGROUND_DISPATCH_CANDIDATE" else "UI_WAIT")
        addProperty("edt_task_association", "NOT_ESTABLISHED")
        add("categories", JsonArray().apply { evidence.map { it["category"].asString }.distinct().sorted().forEach { add(it) } })
        add("evidence_frames", JsonArray().apply { evidence.forEach { add(it.deepCopy()) } })
        add("stack_path", path)
        add("method_contexts", contexts)
        addProperty("located_method_count", located)
        addProperty("stop_reason", stopReason)
        addProperty("status", when {
          located == 0 -> "UNRESOLVED"
          located == contexts.size() && stopReason != "INCOMPLETE_STACK_PATH" -> "METHOD_LOCATED"
          else -> "PARTIAL"
        })
        addProperty("injected_test_path", frames.any {
          symbol(it) in setOf("com.sun.java2d.metal.MTLRenderQueue.testFreeze", "com.intellij.internal.UIFreezeAction.actionPerformed")
        })
        addProperty("write_intent_permit_context", frames.any {
          symbol(it) == "com.intellij.platform.locking.impl.NestedLocksThreadingSupport\$ComputationState.acquireWriteIntentPermit"
        })
      })
    }
    return JsonObject().apply {
      addProperty("schema_version", "repair-s2-method-context/1")
      add("record_id", finder["record_id"])
      addProperty("source_root", root.toAbsolutePath().normalize().toString())
      addProperty("max_method_layers", 5)
      addProperty("status", when {
        operations.isEmpty -> "NOT_APPLICABLE"
        operations.all { it.asJsonObject["status"].asString == "METHOD_LOCATED" } -> "METHOD_LOCATED"
        operations.any { it.asJsonObject["located_method_count"].asInt > 0 } -> "PARTIAL"
        else -> "UNRESOLVED"
      })
      add("operations", operations)
      addProperty("patch_generated", false)
    }
  }
}
