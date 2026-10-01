package org.jetbrains.research.lockrepair.pool.s2

import com.google.gson.JsonArray
import com.google.gson.JsonObject

/** Admission checks for the observed DiskQueryRelay path, not a generic rewrite of the wait utility. */
object AwaitWithCheckCanceledRepair {
  fun assess(operation: JsonObject): JsonObject? {
    val symbols = operation.getAsJsonArray("stack_path").map { it.asJsonObject["symbol"].asString }
    if ("com.intellij.openapi.progress.util.ProgressIndicatorUtils.awaitWithCheckCanceled" !in symbols ||
        "com.intellij.openapi.vfs.DiskQueryRelay.accessDiskWithCheckCanceled" !in symbols) return null

    val synchronousMethods = operation.getAsJsonArray("method_contexts").map { it.asJsonObject }.filter {
      it["status"].asString == "METHOD_LOCATED" &&
      it["method_symbol"].asString in setOf(
        "com.intellij.openapi.vfs.impl.local.LocalFileSystemImpl.fetchCaseSensitivity",
        "com.intellij.openapi.vfs.impl.local.LocalFileSystemImpl.getAttributes",
        "com.intellij.openapi.vfs.impl.local.LocalFileSystemImpl.listWithAttributes",
        "com.intellij.openapi.vfs.impl.local.LocalFileSystemImpl.contentsToByteArray"
      ) && it.getAsJsonObject("method")["source_text"].asString.let { source ->
        source.contains(".accessDiskWithCheckCanceled(") && Regex("\\breturn\\b").containsMatchIn(source)
      }
    }
    if (synchronousMethods.isEmpty()) return null
    return JsonObject().apply {
      addProperty("status", "BLOCKED_CONTRACT")
      addProperty("scope", "LOCAL_WAIT_TO_CALLBACK_REWRITE_ONLY")
      addProperty("reason", "VFS_QUERY_RETURNS_REQUIRED_SYNCHRONOUS_RESULT")
      add("source_method_frame_ids", JsonArray().apply { synchronousMethods.forEach { add(it["method_frame_id"]) } })
      addProperty("p1", "UNKNOWN_DEADLINE_AND_TIMEOUT_RESULT_POLICY")
      addProperty("p2", "REJECT_LOCAL_REWRITE_REQUIRES_UPPER_CONSUMER_CONTINUATION")
      addProperty("p3", "NOT_A_SYNCHRONOUS_EDT_DISPATCH")
      addProperty("g1", "UNKNOWN_NO_EDT_CONTRACT_AND_REJECTION_HANDLING")
      addProperty("next_action", "ESTABLISH_UPPER_CONSUMER_ASYNC_BOUNDARY_OR_EXPLICIT_TIMEOUT_POLICY")
      addProperty("generator_status", "NOT_IMPLEMENTED")
      addProperty("patch_generated", false)
      addProperty("eligible_for_application", false)
    }
  }
}
