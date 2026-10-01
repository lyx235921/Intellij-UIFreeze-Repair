package org.jetbrains.research.lockrepair.pool.s2

import com.google.gson.JsonArray
import com.google.gson.JsonObject

/** Record-local links from explicit Finder descriptions; never infer a producer or a wait cycle. */
object WaitResourceEvidence {
  private val objectLabel = Regex("^on ([A-Za-z_$][A-Za-z0-9_.$]*)@([0-9a-fA-F]+)(?: owned by (.+))?$")

  fun extract(finder: JsonObject): JsonObject {
    val uiIds = finder.getAsJsonArray("ui_thread_ids").map { it.asString }.toSet()
    val observations = JsonArray()
    val owners = JsonArray()
    val threads = finder.getAsJsonArray("threads").map { it.asJsonObject }
    val resources = linkedMapOf<String, JsonObject>()
    for (value in finder.getAsJsonArray("threads")) {
      val thread = value.asJsonObject
      val id = thread["thread_id"].asString
      val details = thread["details"]?.takeUnless { it.isJsonNull }?.asString.orEmpty()
      val state = thread["state"].asString
      val match = objectLabel.matchEntire(details)
      val waiting = state in setOf("WAITING", "TIMED_WAITING", "BLOCKED")
      observations.add(JsonObject().apply {
        addProperty("thread_id", id)
        addProperty("is_ui_thread", id in uiIds)
        addProperty("thread_state", state)
        addProperty("wait_kind", when {
          id in uiIds && state == "BLOCKED" -> "MONITOR_ENTRY_BLOCKED"
          waiting -> "UNCLASSIFIED_WAIT"
          else -> "NOT_WAITING"
        })
        if (id in uiIds && state == "BLOCKED") {
          addProperty("wait_kind_basis", "REPORTED_JAVA_THREAD_STATE_BLOCKED")
          addProperty("monitor_object_status", if (match == null) "LABEL_MISSING_OR_UNRECOGNIZED" else "REPORTED_LABEL_LINKED")
        }
        addProperty("source_field", "threads[$id].details")
        addProperty("raw_details", details)
        addProperty("status", when {
          !waiting -> "NOT_WAITING"
          match == null -> "RESOURCE_LABEL_UNAVAILABLE"
          else -> "REPORTED_WAIT_OBJECT"
        })
        if (waiting && match != null) {
          val className = match.groupValues[1]
          val hash = match.groupValues[2].lowercase()
          val label = "$className@$hash"
          val resource = resources.getOrPut(label) {
            JsonObject().apply {
              addProperty("resource_id", "r${resources.size}")
              addProperty("reported_label", label)
              addProperty("class_name", className)
              addProperty("identity_hash_text", hash)
              addProperty("identity_scope", "THIS_RECORD_ONLY_REPORTED_LABEL_NOT_UNIQUE_OBJECT_PROOF")
              addProperty("owner_status", "NOT_ESTABLISHED")
              addProperty("producer_status", "NOT_ESTABLISHED")
              addProperty("semantic_resource_status", if (className.endsWith("\$Signaller"))
                "WAITER_NODE_NOT_THE_FUTURE" else "REPORTED_OBJECT_ONLY")
              add("waiting_thread_ids", JsonArray())
            }
          }
          resource.getAsJsonArray("waiting_thread_ids").add(id)
          add("resource_id", resource["resource_id"])
        }
        if (id in uiIds && state == "BLOCKED") {
          val ownerName = match?.groupValues?.get(3).orEmpty()
          val candidates = if (ownerName.isEmpty()) emptyList() else threads.filter {
            it["name"]?.takeUnless { name -> name.isJsonNull }?.asString == ownerName
          }
          val ownerStatus = when {
            match == null -> "RESOURCE_LABEL_UNAVAILABLE"
            ownerName.isEmpty() -> "OWNER_NOT_REPORTED"
            candidates.isEmpty() -> "OWNER_THREAD_MISSING"
            candidates.size > 1 -> "OWNER_NAME_AMBIGUOUS"
            candidates.single()["thread_id"].asString == id -> "INCONSISTENT_SELF_OWNER"
            else -> "REPORTED_OWNER_LINKED"
          }
          addProperty("monitor_owner_status", ownerStatus)
          this["resource_id"]?.let { resourceId ->
            resources.values.single { it["resource_id"] == resourceId }
              .addProperty("owner_status", "SEE_MONITOR_OWNER_ASSOCIATIONS")
          }
          val observation = this
          owners.add(JsonObject().apply {
            addProperty("waiting_thread_id", id)
            observation["resource_id"]?.let { add("resource_id", it) }
            addProperty("status", ownerStatus)
            addProperty("reported_owner_name", ownerName)
            addProperty("raw_details", details)
            addProperty("basis", "EXPLICIT_OWNED_BY_AND_EXACT_UNIQUE_NAME_IN_SAME_RECORD")
            add("candidate_thread_ids", JsonArray().apply { candidates.forEach { add(it["thread_id"]) } })
            if (ownerStatus == "REPORTED_OWNER_LINKED") {
              val owner = candidates.single()
              add("owner_thread_id", owner["thread_id"])
              add("owner_thread_state", owner["state"])
              addProperty("owner_is_ui_thread", owner["thread_id"].asString in uiIds)
            }
          })
        }
      })
    }
    return JsonObject().apply {
      addProperty("schema_version", "repair-wait-resource-evidence/1")
      add("record_id", finder["record_id"])
      finder.getAsJsonObject("input")?.get("stack_sha256")?.let { add("stack_sha256", it) }
      add("observations", observations)
      add("monitor_owner_associations", owners)
      add("resources", JsonArray().apply { resources.values.forEach { add(it) } })
      addProperty("resource_cycle_status", "NOT_ANALYZED")
    }
  }
}
