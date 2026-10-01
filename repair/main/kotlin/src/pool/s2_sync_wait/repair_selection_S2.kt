package org.jetbrains.research.lockrepair.pool.s2

import com.google.gson.JsonArray
import com.google.gson.JsonNull
import com.google.gson.JsonObject

/** Ranks conditional S2 plans. A recommendation is not proof of semantic safety or a generated patch. */
object RepairSelectionS2 {
  fun select(context: JsonObject): JsonObject {
    require(context["schema_version"].asString == "repair-s2-method-context/1")
    val decisions = JsonArray()
    for (value in context.getAsJsonArray("operations")) {
      val operation = value.asJsonObject
      val categories = operation.getAsJsonArray("categories").map { it.asString }.toSet()
      val symbols = operation.getAsJsonArray("stack_path").map { it.asJsonObject["symbol"].asString }
      val methods = operation.getAsJsonArray("method_contexts").map { it.asJsonObject }
      val located = methods.filter { it["status"].asString == "METHOD_LOCATED" }
      val missing = methods.filter { it["source_reason"]?.takeUnless { r -> r.isJsonNull }?.asString == "SOURCE_FILE_NOT_FOUND" }
      val interrupted = operation["stop_reason"].asString == "INCOMPLETE_STACK_PATH"
      val onEdt = operation["is_ui_thread"].asBoolean
      val injected = operation["injected_test_path"].asBoolean
      val resultWait = categories.any { it in setOf("Q2.1", "Q2.2", "Q2.3", "Q2.4", "Q2.5") }
      val dispatch = symbols.any { it in ExtractMethodS2.dispatchMethods }
      val waitCalls = JsonArray().apply {
        for (layer in located) {
          for (site in layer.getAsJsonObject("method").getAsJsonArray("call_sites").map { it.asJsonObject }) {
            if (site["name"].asString in setOf("get", "await", "join", "joinBlocking", "wait", "poll", "take",
                                             "sleep", "invokeAndWait", "awaitWithCheckCanceled", "waitForPing")) {
              add(site.deepCopy().apply { add("method_frame_id", layer["method_frame_id"]) })
            }
          }
        }
      }
      val readyToRank = located.isNotEmpty() && !interrupted && !injected
      val waitAssessment = if (readyToRank) AwaitWithCheckCanceledRepair.assess(operation) else null
      val preferred = when {
        !readyToRank -> null
        waitAssessment != null -> null
        dispatch && !onEdt -> "P3_ASYNC_DISPATCH"
        resultWait -> "P2_ASYNC_CONTINUATION"
        else -> null
      }
      val candidates = JsonArray()
      fun candidate(id: String, applicable: Boolean, reason: String, requirements: List<String>, guard: Boolean = false) {
        candidates.add(JsonObject().apply {
          addProperty("strategy", id)
          addProperty("role", if (guard) "DEFENSIVE_GUARD" else "REPAIR_STRATEGY")
          addProperty("status", if (applicable) "REQUIRES_SEMANTIC_REVIEW" else "NOT_APPLICABLE")
          addProperty("reason", reason)
          addProperty("recommended", preferred == id)
          add("checks", JsonArray().apply {
            add(JsonObject().apply {
              addProperty("id", "CURRENT_SOURCE_CONTEXT")
              addProperty("status", if (located.isEmpty()) "UNKNOWN" else "PASS")
            })
            for (requirement in requirements) add(JsonObject().apply {
              addProperty("id", requirement)
              addProperty("status", "UNKNOWN")
            })
          })
          addProperty("generator_status", "NOT_IMPLEMENTED")
          addProperty("patch_generated", false)
        })
      }
      candidate("P1_BOUND_WAIT", resultWait,
                if (resultWait) "WAIT_OBSERVED_BUT_OVERALL_BOUND_AND_TIMEOUT_POLICY_UNKNOWN" else "SLEEP_IS_NOT_AN_UNBOUNDED_RESULT_WAIT",
                listOf("UNBOUNDED_OVERALL_WAIT", "TIMEOUT_API_AVAILABLE", "BUSINESS_DEADLINE_AND_EDT_BUDGET",
                       "TIMEOUT_CANCELLATION_FAILURE_AND_CLEANUP_POLICY"))
      candidate("P2_ASYNC_CONTINUATION", resultWait,
                if (resultWait) "PREFER_REMOVING_UI_WAIT_IF_CONSUMER_CAN_CONTINUE_ASYNCHRONOUSLY" else "NO_TASK_RESULT_CONTINUATION_ESTABLISHED",
                listOf("TASK_COMPLETION_HANDLE", "RETURN_VALUE_AND_CONSUMER_CAN_BE_SPLIT", "CALLBACK_THREAD_AND_LIFETIME",
                       "FAILURE_CANCELLATION_ORDERING_AND_LOCK_RELEASE"))
      candidate("P3_ASYNC_DISPATCH", dispatch && !onEdt,
                if (onEdt) "CURRENT_Q2_OPERATION_IS_ON_UI_NOT_A_BGT_SENDER" else "REQUIRES_EXACT_SYNCHRONOUS_EDT_DISPATCH_PATH",
                listOf("SENDER_IS_BGT_AND_TARGET_IS_EDT", "NO_SYNCHRONOUS_RESULT_OR_COMPLETION_DEPENDENCY",
                       "LOCK_TRANSACTION_AND_MODALITY_PRESERVED", "LIFETIME_AND_CAPTURED_DATA_VALID",
                       "ASYNC_FAILURE_HANDLING_PRESERVED"))
      val dispatchCandidate = candidates.map { it.asJsonObject }.single { it["strategy"].asString == "P3_ASYNC_DISPATCH" }
      dispatchCandidate.getAsJsonArray("checks")[1].asJsonObject.addProperty(
        "status", if (onEdt) "FAIL" else if (dispatch) "PASS" else "UNKNOWN")
      // Stack dispatch evidence alone cannot establish the four business contracts.
      dispatchCandidate.addProperty("preconditions_status", if (onEdt) "REJECTED_SENDER" else "INSUFFICIENT_EVIDENCE")
      dispatchCandidate.addProperty("eligible_for_generation", false)
      dispatchCandidate.add("analysis_context", JsonObject().apply {
        addProperty("sender_source_available", located.isNotEmpty() && !onEdt)
        addProperty("result_dependency_analysis", "NOT_PERFORMED")
        addProperty("lock_transaction_analysis", "NOT_PERFORMED")
        addProperty("lifetime_capture_analysis", "NOT_PERFORMED")
        addProperty("exception_flow_analysis", "NOT_PERFORMED")
        addProperty("transferred_write_action_observed", symbols.any { it.contains("WithTransferredWriteAction") })
        addProperty("edt_task_association", "NOT_ESTABLISHED")
      })
      if (!onEdt && dispatch) {
        val analysis = P3PreconditionAnalyzer.analyze(operation)
        dispatchCandidate.add("semantic_analysis", analysis)
        dispatchCandidate.addProperty("preconditions_status", analysis["status"].asString)
        val checks = dispatchCandidate.getAsJsonArray("checks")
        while (checks.size() > 2) checks.remove(2)
        analysis.getAsJsonArray("checks").forEach { checks.add(it.deepCopy()) }
        dispatchCandidate.addProperty("recommended", false)
        dispatchCandidate.addProperty("status", analysis["status"].asString)
        dispatchCandidate.addProperty("reason", "SOURCE_AST_ANALYSIS_WITH_UNRESOLVED_EXTERNAL_CONTRACTS")
        for (key in listOf("result_dependency_analysis", "lock_transaction_analysis",
                           "lifetime_capture_analysis", "exception_flow_analysis")) {
          dispatchCandidate.getAsJsonObject("analysis_context").addProperty(key, "PERFORMED_WITH_LIMITATIONS")
        }
      }
      candidate("G1_FAIL_FAST_ON_EDT", onEdt, "UI_THREAD_OBSERVED_IS_NOT_PROOF_THAT_BLOCKING_IS_FORBIDDEN",
                listOf("EXPLICIT_NO_EDT_BLOCKING_CONTRACT", "CALLER_HANDLES_REJECTION", "NO_PARTIAL_SIDE_EFFECTS"), guard = true)
      if (waitAssessment != null) {
        val async = candidates.map { it.asJsonObject }.single { it["strategy"].asString == "P2_ASYNC_CONTINUATION" }
        async.addProperty("status", "REJECTED_LOCAL_REWRITE")
        async.addProperty("reason", "SYNCHRONOUS_VFS_RESULT_REQUIRES_UPPER_CONSUMER_REFACTORING")
        async.getAsJsonArray("checks").add(JsonObject().apply {
          addProperty("id", "LOCAL_WAIT_CAN_RETURN_BEFORE_RESULT")
          addProperty("status", "FAIL")
        })
      }
      decisions.add(JsonObject().apply {
        add("thread_id", operation["thread_id"])
        add("categories", operation["categories"].deepCopy())
        add("evidence_frames", operation["evidence_frames"].deepCopy())
        addProperty("status", when {
          injected -> "SKIPPED_TEST_PATH"
          located.isEmpty() && missing.isNotEmpty() -> "SKIPPED_SOURCE_UNAVAILABLE"
          waitAssessment != null -> "BLOCKED_CONTRACT"
          dispatchCandidate["preconditions_status"].asString == "REJECTED_CONTRACT" -> "BLOCKED_CONTRACT"
          !onEdt && dispatch -> dispatchCandidate["preconditions_status"].asString
          !readyToRank || preferred == null -> "INSUFFICIENT_EVIDENCE"
          else -> "CANDIDATES_RANKED"
        })
        addProperty("recommended_strategy", preferred.takeUnless {
          !onEdt && dispatch
        })
        if (waitAssessment != null) add("await_repair", waitAssessment)
        add("selected_strategy", JsonNull.INSTANCE)
        addProperty("selection_basis", "Q2_WAIT_KIND_AND_VERIFIED_METHOD_CONTEXT_NOT_SEMANTIC_PROOF")
        add("source_method_frame_ids", JsonArray().apply { located.forEach { add(it["method_frame_id"]) } })
        add("missing_source_contexts", JsonArray().apply { missing.forEach { add(it.deepCopy()) } })
        add("source_wait_call_candidates", waitCalls)
        addProperty("call_type_resolution", "NOT_PERFORMED")
        addProperty("overall_wait_bound", "NOT_ESTABLISHED_TIMED_INNER_CALLS_MAY_REPEAT")
        add("stop_reason", operation["stop_reason"])
        add("write_intent_permit_context", operation["write_intent_permit_context"])
        add("candidates", candidates)
        addProperty("next_action", if (waitAssessment != null) waitAssessment["next_action"].asString
                                  else if (injected || located.isEmpty() && missing.isNotEmpty()) "CONTINUE_NEXT_FREEZE_POINT"
                                  else "REVIEW_WAIT_PRODUCER_CONSUMER_AND_COMPLETION_CONTRACT")
        addProperty("patch_generated", false)
        addProperty("eligible_for_application", false)
      })
    }
    return JsonObject().apply {
      addProperty("schema_version", "repair-s2-selection/1")
      add("record_id", context["record_id"])
      add("decisions", decisions)
      addProperty("status", when {
        decisions.isEmpty -> "NOT_APPLICABLE"
        decisions.all { it.asJsonObject["status"].asString == "CANDIDATES_RANKED" } -> "CANDIDATES_RANKED"
        decisions.any { it.asJsonObject["status"].asString == "CANDIDATES_RANKED" } -> "PARTIAL"
        decisions.any { it.asJsonObject["status"].asString == "BLOCKED_CONTRACT" } -> "BLOCKED_CONTRACT"
        decisions.all { it.asJsonObject["status"].asString.startsWith("SKIPPED_") } -> "SKIPPED"
        else -> "INSUFFICIENT_EVIDENCE"
      })
      addProperty("patch_generated", false)
      addProperty("applied", false)
    }
  }

}
