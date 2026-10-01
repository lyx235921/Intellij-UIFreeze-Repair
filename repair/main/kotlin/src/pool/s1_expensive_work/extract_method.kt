package org.jetbrains.research.lockrepair.pool.s1

import com.google.gson.JsonArray
import com.google.gson.JsonObject

/** Locate the enclosing project method on a classified stack path. Does not edit source. */
object ExtractMethod {
  private const val MAX_METHOD_LAYERS = 5
  fun locateMethod(finder: JsonObject, q1: JsonObject, category: String? = null): JsonObject {
    require(q1["schema_version"].asString == "repair-q1-locations/1")
    val verified = q1.getAsJsonArray("frames").associate { it.asJsonObject["frame_id"].asString to it.asJsonObject }
    val hits = q1.getAsJsonObject("classification").getAsJsonArray("matched_frames")
      .map { it.asJsonObject }.filter { category == null || it["category"].asString == category }
    val results = JsonArray()
    for (hit in hits) {
      val thread = finder.getAsJsonArray("threads").map { it.asJsonObject }
        .single { it["thread_id"] == hit["thread_id"] }
      val frames = thread.getAsJsonArray("frames").map { it.asJsonObject }
      val start = frames.indexOfFirst { it["frame_id"] == hit["frame_id"] }
      require(start >= 0)
      val path = JsonArray()
      var layers = 0
      fun newResult(): JsonObject = JsonObject().apply {
        add("thread_id", hit["thread_id"])
        add("trigger_frame_id", hit["frame_id"])
        add("trigger_symbol", hit["symbol"])
        add("problem_category", hit["category"])
        addProperty("status", "UNRESOLVED")
        addProperty("reason", "NO_PROJECT_METHOD")
        addProperty("method_layer", layers)
        add("stack_path", path.deepCopy())
      }
      for (i in start until frames.size) {
        val frame = frames[i]
        val symbol = frame["symbol"].takeUnless { it.isJsonNull }?.asString.orEmpty()
          .replace(Regex("^(?:[^/]+//|[^/]+/)(?=[A-Za-z_])"), "")
        path.add(JsonObject().apply {
          add("frame_id", frame["frame_id"])
          addProperty("symbol", symbol)
        })
        if (frame["elided"].asBoolean || symbol.isBlank() ||
            (i > start && frame["index"].asInt != frames[i - 1]["index"].asInt + 1)) {
          results.add(newResult().apply { addProperty("reason", "INCOMPLETE_STACK_PATH") })
          break
        }
        // Runtime frames do not consume a layer. Unresolved project frames do, and remain in the output.
        if (listOf("java.", "javax.", "jdk.", "sun.", "com.sun.").any { symbol.startsWith(it) }) continue
        layers++
        val result = newResult()
        val location = verified.getValue(frame["frame_id"].asString)
        result.add("source_status", location["finder_status"])
        result.add("source_reason", location["reason"])
        result.add("source_file", location["stack_file"])
        result.add("method_frame_id", frame["frame_id"])
        result.add("method_symbol", frame["symbol"])
        val candidates = location.getAsJsonArray("locations")
        result.add("candidates", candidates.deepCopy())
        val selected = candidates.map { it.asJsonObject }.filter { it["finder_selected"]?.asBoolean == true }
        if (selected.size == 1 && selected.single()["verification"].asString == "HASH_MATCHED") {
          result.addProperty("status", "METHOD_LOCATED")
          result.addProperty("reason", "PROJECT_FRAME_WITHIN_FIVE_LAYERS")
          result.add("method", selected.single().deepCopy())
        }
        else {
          result.addProperty("reason", "PROJECT_METHOD_UNAVAILABLE_OR_AMBIGUOUS")
        }
        results.add(result)
        if (layers == MAX_METHOD_LAYERS) break
      }
      if (layers == 0 && results.none { it.asJsonObject["trigger_frame_id"] == hit["frame_id"] }) {
        results.add(newResult())
      }
    }
    return JsonObject().apply {
      addProperty("schema_version", "repair-method-context/1")
      addProperty("problem_category", category ?: "ALL_MATCHED_CATEGORIES")
      add("record_id", finder["record_id"])
      addProperty("status", when {
        hits.isEmpty() -> "NOT_APPLICABLE"
        results.all { it.asJsonObject["status"].asString == "METHOD_LOCATED" } -> "METHOD_LOCATED"
        results.any { it.asJsonObject["status"].asString == "METHOD_LOCATED" } -> "PARTIAL"
        else -> "UNRESOLVED"
      })
      addProperty("repair_status", "NOT_STARTED")
      addProperty("max_method_layers", MAX_METHOD_LAYERS)
      addProperty("selection_basis", "UP_TO_FIVE_PROJECT_FRAMES_NOT_PROVEN_RELOCATION_BOUNDARY")
      add("results", results)
    }
  }
}
