package org.jetbrains.research.lockrepair.pool.s2

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import org.jetbrains.kotlin.cli.jvm.compiler.EnvironmentConfigFiles
import org.jetbrains.kotlin.cli.jvm.compiler.KotlinCoreEnvironment
import org.jetbrains.kotlin.com.intellij.openapi.util.Disposer
import org.jetbrains.kotlin.com.intellij.psi.PsiElement
import org.jetbrains.kotlin.com.intellij.psi.PsiErrorElement
import org.jetbrains.kotlin.config.CompilerConfiguration
import org.jetbrains.kotlin.psi.*
import com.sun.source.tree.*
import com.sun.source.util.JavacTask
import com.sun.source.util.TreePathScanner
import com.sun.source.util.Trees
import java.net.URI
import javax.tools.DiagnosticCollector
import javax.tools.JavaFileObject
import javax.tools.SimpleJavaFileObject
import javax.tools.ToolProvider
import javax.lang.model.element.Modifier

/** Intraprocedural syntax analysis. Unresolved effects and external contracts never imply safety. */
object P3PreconditionAnalyzer {
  private val factory by lazy {
    val disposable = Disposer.newDisposable()
    Runtime.getRuntime().addShutdownHook(Thread { Disposer.dispose(disposable) })
    KtPsiFactory(KotlinCoreEnvironment.createForProduction(
      disposable, CompilerConfiguration(), EnvironmentConfigFiles.JVM_CONFIG_FILES).project, false)
  }
  private fun nodes(element: PsiElement): Sequence<PsiElement> = sequence {
    yield(element)
    for (child in element.children) yieldAll(nodes(child))
  }
  private fun ancestors(element: PsiElement): Sequence<PsiElement> = generateSequence(element.parent) { it.parent }
  private val ids = listOf("NO_SYNCHRONOUS_RESULT_OR_COMPLETION_DEPENDENCY", "LOCK_TRANSACTION_AND_MODALITY_PRESERVED",
                           "LIFETIME_AND_CAPTURED_DATA_VALID", "ASYNC_FAILURE_HANDLING_PRESERVED")

  fun analyze(operation: JsonObject): JsonObject {
    val checks = ids.map { id -> JsonObject().apply {
      addProperty("id", id)
      addProperty("status", "UNKNOWN")
      add("evidence", JsonArray())
      addProperty("remaining_obligation", when (id) {
        ids[0] -> "PROVE_CALLBACK_EFFECTS_AND_ALL_COMPLETION_CONSUMERS"
        ids[1] -> "PROVE_CALLER_LOCK_TRANSACTION_AND_TARGET_MODALITY"
        ids[2] -> "RESOLVE_CALLBACK_CAPTURES_MUTABILITY_DISPOSAL_AND_SCOPE"
        else -> "PROVE_CALLBACK_FAILURE_AND_CANCELLATION_POLICY"
      })
    } }
    val facts = JsonArray()
    val diagnostics = JsonArray()
    var parsed = 0
    val path = operation.getAsJsonArray("stack_path").map { it.asJsonObject["symbol"].asString }
    val verified = operation.getAsJsonArray("method_contexts").map { it.asJsonObject }.filter {
      it["status"].asString == "METHOD_LOCATED" && it.getAsJsonObject("method")["verification"].asString == "HASH_MATCHED"
    }
    // Immediate extracted stack callers may wrap dispatch; names only nominate sites, not resolve their types.
    val dispatchNames = (ExtractMethodS2.dispatchMethods.map { it.substringAfterLast('.') } +
      path.zipWithNext().filter { it.first in ExtractMethodS2.dispatchMethods }.map { it.second.substringAfterLast('.') }).toSet()
    for (layer in verified) {
      val method = layer.getAsJsonObject("method")
      val source = method["source_text"].asString
      if (method["path"].asString.endsWith(".java")) {
        if (analyzeJava(layer, dispatchNames, checks, facts, diagnostics)) parsed++
        continue
      }
      if (!method["path"].asString.endsWith(".kt")) {
        diagnostics.add("UNSUPPORTED_LANGUAGE:${method["path"].asString}")
        continue
      }
      val file = factory.createFile("analysis.kt", source)
      if (nodes(file).any { it is PsiErrorElement }) {
        diagnostics.add("PARSE_ERROR:${layer["method_frame_id"].asString}")
        continue
      }
      val function = file.declarations.filterIsInstance<KtNamedFunction>().singleOrNull()
      if (function == null || function.bodyExpression == null) {
        diagnostics.add("METHOD_BODY_UNAVAILABLE:${layer["method_frame_id"].asString}")
        continue
      }
      parsed++
      fun evidence(element: PsiElement, reason: String): JsonObject = JsonObject().apply {
        add("frame_id", layer["method_frame_id"])
        add("path", method["path"])
        add("sha256", method["sha256"])
        addProperty("line", method["start_line"].asInt + source.take(element.textOffset).count { it == '\n' })
        addProperty("reason", reason)
        addProperty("text", element.text.take(1200))
      }
      fun flag(index: Int, element: PsiElement, reason: String, status: String = "NEEDS_ADAPTATION") {
        val check = checks[index]
        if (check["status"].asString != "FAIL") check.addProperty("status", status)
        check.getAsJsonArray("evidence").add(evidence(element, reason))
      }
      val calls = nodes(function).filterIsInstance<KtCallExpression>().toList()
      val transfer = layer["method_symbol"].asString ==
        "com.intellij.openapi.application.impl.InternalThreading.invokeAndWaitWithTransferredWriteAction"
      for (call in calls) {
        val name = call.calleeExpression?.text.orEmpty()
        if (transfer && name == "transferWriteActionAndBlock") {
          flag(1, call, "BLOCKING_WRITE_TRANSFER_CANNOT_BE_REPLACED_BY_PLAIN_POST", "FAIL")
        }
        if (name == "captureContextCancellationForRunnableThatDoesNotOutliveContextScope") {
          flag(2, call, "CAPTURED_CONTEXT_HAS_EXPLICIT_SCOPE_LIMIT")
        }
        if (name !in dispatchNames) continue
        val statement = generateSequence<PsiElement>(call) { it.parent }
          .firstOrNull { it.parent is KtBlockExpression }
        val block = statement?.parent as? KtBlockExpression
        val following = block?.statements?.dropWhile { it != statement }?.drop(1).orEmpty()
        val callback = call.lambdaArguments.singleOrNull()?.getLambdaExpression()
          ?: call.valueArguments.mapNotNull { it.getArgumentExpression() as? KtLambdaExpression }.singleOrNull()
        val callbackNodes = callback?.let { nodes(it).toList() }.orEmpty()
        val callbackCalls = callbackNodes.filterIsInstance<KtCallExpression>()
        val references = callbackNodes.filterIsInstance<KtNameReferenceExpression>().map { it.getReferencedName() }.toSet()
        val assigned = callbackNodes.filterIsInstance<KtBinaryExpression>().filter {
          it.operationReference.text in setOf("=", "+=", "-=", "*=", "/=")
        }.flatMap { expression -> expression.left?.let { nodes(it).filterIsInstance<KtNameReferenceExpression>()
          .map { it.getReferencedName() }.toList() }.orEmpty() }.toSet()
        val consumed = following.flatMap { nodes(it).filterIsInstance<KtNameReferenceExpression>()
          .map { reference -> reference.getReferencedName() }.toList() }.toSet()
        facts.add(evidence(call, "DISPATCH_SITE_CANDIDATE").apply {
          addProperty("call_type_resolution", "NOT_PERFORMED")
          addProperty("callback_status", if (callback == null) "INDIRECT_OR_UNAVAILABLE" else "INLINE")
          add("callback_reference_names", JsonArray().apply { references.sorted().forEach { add(it) } })
          add("callback_written_names", JsonArray().apply { assigned.sorted().forEach { add(it) } })
          add("following_statements", JsonArray().apply { following.forEach { add(it.text.take(1200)) } })
        })
        if ((assigned intersect consumed).isNotEmpty()) {
          flag(0, call, "CALLBACK_WRITE_AND_FOLLOWING_READ_REQUIRE_ALIAS_AND_ORDER_REVIEW")
        }
        else if (following.isNotEmpty()) flag(0, call, "CONTINUATION_AFTER_DISPATCH_REQUIRES_EFFECT_ORDER_REVIEW")
        if (ancestors(call).takeWhile { it != function }.any { it is KtReturnExpression || it is KtProperty }) {
          flag(0, call, "DISPATCH_EXPRESSION_RESULT_IS_CONSUMED")
        }
        for (scope in ancestors(call).takeWhile { it != function }.filterIsInstance<KtCallExpression>()) {
          if (scope.calleeExpression?.text in setOf("synchronized", "withLock", "runWriteAction", "writeAction",
                                                   "runReadAction", "readAction", "runWriteIntentReadAction")) {
            flag(1, scope, "DISPATCH_WITHIN_LOCK_OR_ACTION_SCOPE")
          }
        }
        if (callback != null && (references.isNotEmpty() || callbackCalls.isNotEmpty())) {
          checks[2].getAsJsonArray("evidence").add(evidence(callback, "CAPTURE_AND_CALLEE_LIFETIME_MUST_BE_RESOLVED"))
        }
        for (scope in ancestors(call).takeWhile { it != function }.filterIsInstance<KtTryExpression>()) {
          if (scope.catchClauses.isNotEmpty() || scope.finallyBlock != null) {
            flag(3, scope, "SENDER_CATCH_OR_FINALLY_WILL_NOT_ENCLOSE_DEFERRED_CALLBACK")
          }
        }
      }
      // Structural throw expressions (including nested lambdas), never comment/string matches.
      for (throwExpression in nodes(function).filterIsInstance<KtThrowExpression>()) {
        flag(3, throwExpression, "SENDER_OR_WRAPPER_HAS_THROW_PATH_REQUIRING_FAILURE_ROUTING")
      }
    }
    return JsonObject().apply {
      addProperty("schema_version", "p3-precondition-analysis/1")
      addProperty("analysis_scope", "JAVA_KOTLIN_INTRAPROCEDURAL_AST_WITH_STACK_WRAPPER_CANDIDATES")
      addProperty("candidate_transformation", "SYNCHRONOUS_DISPATCH_TO_ASYNC_POST")
      addProperty("parsed_methods", parsed)
      add("checks", JsonArray().apply { checks.forEach { add(it) } })
      add("dispatch_sites", facts)
      add("diagnostics", diagnostics)
      addProperty("status", when {
        checks.any { it["status"].asString == "FAIL" } -> "REJECTED_CONTRACT"
        checks.any { it["status"].asString == "NEEDS_ADAPTATION" } -> "NEEDS_ADAPTATION"
        else -> "INSUFFICIENT_EVIDENCE"
      })
      addProperty("eligible_for_generation", false)
    }
  }

  private fun analyzeJava(layer: JsonObject, names: Set<String>, checks: List<JsonObject>,
                          facts: JsonArray, diagnostics: JsonArray): Boolean {
    val compiler = ToolProvider.getSystemJavaCompiler()
    if (compiler == null) {
      diagnostics.add("JAVA_COMPILER_UNAVAILABLE")
      return false
    }
    val method = layer.getAsJsonObject("method")
    val source = method["source_text"].asString
    val prefix = "class Analysis {\n"
    val unitSource = prefix + source + "\n}"
    val input = object : SimpleJavaFileObject(URI.create("string:///Analysis.java"), JavaFileObject.Kind.SOURCE) {
      override fun getCharContent(ignoreEncodingErrors: Boolean): CharSequence = unitSource
    }
    val errors = DiagnosticCollector<JavaFileObject>()
    compiler.getStandardFileManager(errors, null, Charsets.UTF_8).use { manager ->
      val task = compiler.getTask(null, manager, errors, listOf("-proc:none"), null, listOf(input)) as JavacTask
      val unit = task.parse().single()
      if (errors.diagnostics.any { it.kind == javax.tools.Diagnostic.Kind.ERROR }) {
        diagnostics.add("PARSE_ERROR:${layer["method_frame_id"].asString}")
        return false
      }
      val positions = Trees.instance(task).sourcePositions
      fun evidence(tree: Tree, reason: String): JsonObject = JsonObject().apply {
        add("frame_id", layer["method_frame_id"])
        add("path", method["path"])
        add("sha256", method["sha256"])
        val offset = (positions.getStartPosition(unit, tree).toInt() - prefix.length).coerceIn(0, source.length)
        addProperty("line", method["start_line"].asInt + source.take(offset).count { it == '\n' })
        addProperty("reason", reason)
        addProperty("text", tree.toString().take(1200))
      }
      fun flag(index: Int, tree: Tree, reason: String) {
        if (checks[index]["status"].asString != "FAIL") checks[index].addProperty("status", "NEEDS_ADAPTATION")
        checks[index].getAsJsonArray("evidence").add(evidence(tree, reason))
      }
      object : TreePathScanner<Unit, Unit>() {
        override fun visitMethodInvocation(node: MethodInvocationTree, data: Unit?) {
          val name = node.methodSelect.toString().substringAfterLast('.')
          if (name in names) {
            val parents = generateSequence(currentPath.parentPath) { it.parentPath }.map { it.leaf }.toList()
            val statement = (listOf<Tree>(node) + parents).zipWithNext().firstOrNull { it.second is BlockTree }?.first
            val block = parents.filterIsInstance<BlockTree>().firstOrNull()
            val following = block?.statements?.dropWhile { it !== statement }?.drop(1).orEmpty()
            val callback = node.arguments.filterIsInstance<LambdaExpressionTree>().singleOrNull()
            facts.add(evidence(node, "DISPATCH_SITE_CANDIDATE").apply {
              addProperty("call_type_resolution", "NOT_PERFORMED")
              addProperty("callback_status", if (callback == null) "INDIRECT_OR_UNAVAILABLE" else "INLINE")
              if (callback != null) addProperty("callback_source", callback.toString())
              add("following_statements", JsonArray().apply { following.forEach { add(it.toString().take(1200)) } })
            })
            if (following.isNotEmpty()) flag(0, node, "CONTINUATION_AFTER_DISPATCH_REQUIRES_EFFECT_ORDER_REVIEW")
            if (parents.takeWhile { it !is MethodTree }.any { it is ReturnTree || it is VariableTree || it is AssignmentTree }) {
              flag(0, node, "DISPATCH_EXPRESSION_RESULT_IS_CONSUMED")
            }
            for (scope in parents.takeWhile { it !is MethodTree }) {
              if (scope is SynchronizedTree || scope is MethodTree && Modifier.SYNCHRONIZED in scope.modifiers.flags) {
                flag(1, scope, "DISPATCH_WITHIN_MONITOR_SCOPE")
              }
              if (scope is TryTree && (scope.catches.isNotEmpty() || scope.finallyBlock != null || scope.resources.isNotEmpty())) {
                flag(3, scope, "SENDER_HANDLER_OR_RESOURCE_SCOPE_WILL_NOT_ENCLOSE_DEFERRED_CALLBACK")
              }
            }
            val enclosing = parents.filterIsInstance<MethodTree>().firstOrNull()
            if (enclosing != null && Modifier.SYNCHRONIZED in enclosing.modifiers.flags) {
              flag(1, enclosing, "DISPATCH_WITHIN_SYNCHRONIZED_METHOD")
            }
            if (callback != null) checks[2].getAsJsonArray("evidence").add(
              evidence(callback, "CAPTURE_AND_CALLEE_LIFETIME_MUST_BE_RESOLVED"))
          }
          super.visitMethodInvocation(node, data)
        }
        override fun visitThrow(node: ThrowTree, data: Unit?) {
          flag(3, node, "SENDER_OR_CALLBACK_THROW_PATH_REQUIRES_FAILURE_ROUTING")
          super.visitThrow(node, data)
        }
      }.scan(unit, Unit)
      return true
    }
  }
}
