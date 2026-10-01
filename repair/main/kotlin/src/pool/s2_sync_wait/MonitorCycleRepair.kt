package org.jetbrains.research.lockrepair.pool.s2

import com.google.gson.JsonArray
import com.google.gson.JsonObject

/** Admission for the AWT tree-lock/disposal cycle. Does not rewrite a wait while its outer monitor is held. */
object MonitorCycleRepair {
  fun assess(finder: JsonObject, resources: JsonObject): JsonObject {
    val candidates = JsonArray()
    val threads = finder.getAsJsonArray("threads").map { it.asJsonObject }.associateBy { it["thread_id"].asString }
    for (entry in resources.getAsJsonArray("monitor_owner_associations")) {
      val association = entry.asJsonObject
      if (association["status"].asString != "REPORTED_OWNER_LINKED" || association["owner_is_ui_thread"].asBoolean) continue
      val resource = resources.getAsJsonArray("resources").map { it.asJsonObject }
        .single { it["resource_id"] == association["resource_id"] }
      if (resource["class_name"].asString != "java.awt.Component\$AWTTreeLock") continue
      val owner = threads.getValue(association["owner_thread_id"].asString)
      val frames = owner.getAsJsonArray("frames").map { it.asJsonObject }
      if (frames.withIndex().any { it.value["elided"].asBoolean || it.value["index"].asInt != it.index }) continue
      val symbols = frames.map { ExtractMethodS2.symbol(it) }
      val dispatch = symbols.indexOf("java.awt.EventQueue.invokeAndWait")
      val disposal = symbols.indexOf("java.awt.Window.doDispose")
      val removal = symbols.indexOf("java.awt.Container.remove")
      if (owner["state"].asString !in setOf("WAITING", "TIMED_WAITING") || dispatch < 1 ||
          symbols.firstOrNull() !in setOf("java.lang.Object.wait0", "java.lang.Object.wait") ||
          disposal <= dispatch || removal <= disposal) continue
      val uiCall = symbols.indexOf("com.intellij.openapi.wm.impl.ToolWindowImpl.setAvailable")
      if (uiCall <= removal) continue
      val caller = frames.getOrNull(uiCall + 1) ?: continue
      val source = caller.getAsJsonObject("source")
      val missing = source["reason"]?.takeUnless { it.isJsonNull }?.asString == "SOURCE_FILE_NOT_FOUND"
      candidates.add(JsonObject().apply {
        addProperty("strategy", "MOVE_UI_OPERATION_TO_EDT_BEFORE_MONITOR_ACQUISITION")
        addProperty("cycle_evidence", "REPORTED_OWNER_PLUS_SYNCHRONOUS_AWT_DISPATCH")
        addProperty("edt_queue_identity", "NOT_INDEPENDENTLY_VERIFIED")
        add("waiting_thread_id", association["waiting_thread_id"])
        add("owner_thread_id", association["owner_thread_id"])
        add("resource_id", association["resource_id"])
        addProperty("status", if (missing) "BLOCKED_SOURCE_UNAVAILABLE" else "REQUIRES_CALLER_CONTRACT_ANALYSIS")
        addProperty("repair_entry_symbol", ExtractMethodS2.symbol(caller))
        add("repair_entry_frame_id", caller["frame_id"])
        add("source_evidence", source.deepCopy())
        add("evidence_frame_ids", JsonArray().apply {
          for (index in listOf(0, dispatch, disposal, removal, uiCall, uiCall + 1)) add(frames[index]["frame_id"])
        })
        add("required_checks", JsonArray().apply {
          add("DISPATCH_BEFORE_TREE_LOCK_AND_ANY_EDT_REQUIRED_LOCK")
          add("MOVE_COMPLETE_DEPENDENT_UI_OPERATION_NOT_ONLY_WINDOW_DISPOSE")
          add("CALLER_COMPLETION_ORDER_AND_EXCEPTION_POLICY")
          add("PROJECT_DISPOSAL_AND_CALLBACK_CAPTURE_VALIDITY")
          add("CURRENT_SOURCE_AND_INCIDENT_VERSION_COMPATIBILITY")
        })
        addProperty("next_action", if (missing) "PROVIDE_PLUGIN_BUSINESS_SOURCE" else "EXTRACT_AND_VERIFY_CALLER_BODY")
        addProperty("generator_status", "NOT_IMPLEMENTED_PENDING_CALLER_CONTRACT")
        addProperty("patch_generated", false)
        addProperty("eligible_for_application", false)
      })
    }
    return JsonObject().apply {
      addProperty("schema_version", "repair-monitor-cycle/1")
      add("record_id", finder["record_id"])
      add("candidates", candidates)
      addProperty("status", if (candidates.isEmpty) "NO_SUPPORTED_CYCLE_PATTERN" else "CANDIDATE_REQUIRES_SOURCE_REVIEW")
      addProperty("patch_generated", false)
    }
  }
}
