package org.jetbrains.research.lockrepair.pool.s1

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import java.nio.file.Path
import org.jetbrains.research.lockrepair.pool.s1.RelocationPreconditions.Check
import org.jetbrains.research.lockrepair.pool.s1.RelocationPreconditions.Verdict

/** Diagnose deferral units independently of the selector's P1/P2 fallback gate. */
object P3DeferExpensiveOperation {
  fun check(context: JsonObject, root: Path): JsonObject {
    val source = RelocationPreconditions.sourceCheck(context, root)
    val known = RelocationPreconditions.knownImagePreparation(context, source)
    val common = listOf(source, RelocationPreconditions.shapeCheck(known))
    val operation = RelocationPreconditions.report("P3", "DEFER_PREPARATION_ONLY", common + listOf(
      Check("NO_IMMEDIATE_RESULT_CONSUMER", if (known) Verdict.FAIL else Verdict.UNKNOWN,
        if (known) "ImageIO.read -> writeTransparentIco(image) -> createIcon(bytes) -> setOverlayIcon; CANNOT_DEFER_PRODUCER_ALONE"
        else "NEED_DATA_DEPENDENCIES_OF_OPERATION_RESULT")
    ))
    val enclosing = RelocationPreconditions.report("P3", "DEFER_TASK_WITH_CONSUMERS", common + listOf(
      Check("NOT_REQUIRED_FOR_CURRENT_TASK", Verdict.UNKNOWN,
        "NEED_CALLER_OR_BUSINESS_CONTRACT; VOID_RETURN_AND_BADGE_NAME_DO_NOT_PROVE_OPTIONAL_WORK"),
      Check("ORDERING_PRESERVED", Verdict.UNKNOWN,
        if (known) "SHOW_HIDE_AND_FRAME_ACTIVATION_ORDER_MUST_SURVIVE_DEFERRAL" else "NEED_EVENT_AND_SIDE_EFFECT_ORDER"),
      Check("CAPTURED_STATE_VALID", Verdict.UNKNOWN,
        "NEED_CAPTURE_OWNERSHIP_LIFETIME_DISPOSAL_AND_STALE_REQUEST_HANDLING"),
      Check("DEFERRED_EXECUTION_BOUNDARY", Verdict.UNKNOWN,
        "NEED_CONCRETE_SCHEDULING_POINT_THREAD_LOCK_REQUIREMENTS_AND_PROGRESS; INVOKE_LATER_ALONE_MAY_FREEZE_NEXT_EVENT"),
      Check("ERROR_AND_CANCELLATION_SEMANTICS", Verdict.UNKNOWN,
        "NEED_EXCEPTION_DELIVERY_RETRY_AND_CANCEL_POLICY_WITHOUT_SYNCHRONOUS_EDT_WAIT")
    ))
    // Failure of preparation-only deferral does not reject deferral of the whole task.
    return JsonObject().apply {
      addProperty("strategy", "P3")
      addProperty("status", enclosing["status"].asString)
      addProperty("generator_status", "NOT_IMPLEMENTED")
      addProperty("applied", false)
      add("scopes", JsonArray().apply { add(operation); add(enclosing) })
    }
  }
}
