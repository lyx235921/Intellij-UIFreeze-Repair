package org.jetbrains.research.lockrepair.pool.s1

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import java.nio.file.Path

/** Stack-based ordering followed by source-template admission. Does not apply patches. */
object RepairSelection {
  // Kept in sync with Q1-P1-P3-MAPPING-2026-09-27.json by the selection tests.
  private val priorities: Map<String, String> = mapOf(
    "com.intellij.json.syntax._JsonLexer.advance" to "P2_FIRST",
    "com.intellij.json.syntax._JsonLexer.codePoint" to "CONTEXT_FIRST",
    "com.intellij.lexer.FlexAdapter.locateToken" to "P2_FIRST",
    "com.intellij.lexer.MergingLexerAdapter\$MyMergeFunction.merge" to "P2_FIRST",
    "com.intellij.openapi.vfs.newvfs.persistent.DefaultInMemoryInvertedNameIndex.deleteDataInner" to "CONTEXT_FIRST",
    "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.getName" to "P1_FIRST",
    "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.getNameByNameId" to "P1_FIRST",
    "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.readAttribute" to "P1_FIRST",
    "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.readSymlinkTarget" to "P1_FIRST",
    "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.update" to "CONTEXT_FIRST",
    "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.updateSymlinksForNewChildren" to "CONTEXT_FIRST",
    "com.intellij.openapi.vfs.newvfs.persistent.PersistentFSContentAccessor.acquireContentRecord" to "CONTEXT_FIRST",
    "com.intellij.platform.syntax.impl.builder.MarkerProduction.addMarker" to "P2_FIRST",
    "com.intellij.platform.syntax.impl.builder.MarkerProduction.findLinearly" to "P2_FIRST",
    "com.intellij.platform.syntax.impl.builder.MarkerProduction.findMarkerAtLexeme" to "P2_FIRST",
    "com.intellij.platform.syntax.impl.builder.SyntaxTreeBuilderImpl\$WhitespaceBalancer.balanceMarkerAndReturnNewIndex" to "P2_FIRST",
    "com.intellij.platform.syntax.impl.builder.SyntaxTreeBuilderImpl.remapCurrentToken" to "P2_FIRST",
    "com.intellij.platform.syntax.impl.builder.SyntaxTreeBuilderImpl.rollbackTo\$intellij_platform_syntax" to "P2_FIRST",
    "com.intellij.platform.syntax.lexer.Builder.performLexing" to "P2_FIRST",
    "com.intellij.platform.syntax.psi.ParsingDiagnostics.registerLexing" to "CONTEXT_FIRST",
    "com.intellij.platform.syntax.psi.impl.NodeData.createLeaf" to "P2_FIRST",
    "com.intellij.platform.syntax.psi.impl.NodeData.getInternedText" to "CONTEXT_FIRST",
    "com.intellij.platform.syntax.psi.impl.NodeData.insertLeaves" to "P2_FIRST",
    "com.intellij.platform.syntax.util.runtime.Modifiers.access\$get_NONE_\$cp" to "CONTEXT_FIRST",
    "com.intellij.platform.syntax.util.runtime.impl.MyList.trimSize-impl" to "CONTEXT_FIRST",
    "com.intellij.platform.syntax.util.runtime.impl.SyntaxGeneratedParserRuntimeImpl.enter_section_-T529yjc" to "P2_FIRST",
    "com.intellij.platform.syntax.util.runtime.impl.SyntaxGeneratedParserRuntimeImpl.exit_section_" to "P2_FIRST",
    "com.intellij.platform.syntax.util.runtime.impl.SyntaxGeneratedParserRuntimeImpl.nextTokenIsSlow" to "P2_FIRST",
    "com.intellij.textmate.joni.JoniRegexFacade.match-ZRjI0jQ" to "P2_FIRST",
    "com.intellij.ui.svg.SvgCacheManagerKt.createIconCacheKey-2Mr4RHQ" to "CONTEXT_FIRST",
    "com.intellij.ui.svg.SvgCacheManagerKt.readImage" to "P2_FIRST",
    "com.intellij.ui.svg.SvgKt.loadSvgAndCacheIfApplicable-F6nGey4" to "P2_FIRST",
    "com.intellij.util.io.SimpleStringPersistentEnumerator.enumerate" to "CONTEXT_FIRST",
    "com.intellij.util.lang.UrlClassLoader.findClass" to "P1_FIRST",
    "com.intellij.workspaceModel.core.fileIndex.impl.ExcludedFileSet\$ByFileKind.computeMasks" to "CONTEXT_FIRST",
    "com.intellij.workspaceModel.core.fileIndex.impl.WorkspaceFileIndexDataImpl.ensureIsUpToDate" to "CONTEXT_FIRST",
    "com.intellij.workspaceModel.core.fileIndex.impl.WorkspaceFileIndexDataImpl.getFileInfo" to "P1_FIRST",
    "com.intellij.workspaceModel.core.fileIndex.impl.WorkspaceFileIndexImpl\$processContentUnderDirectory\$visitor\$1.visitFileEx" to "P2_FIRST",
    "com.intellij.workspaceModel.core.fileIndex.impl.WorkspaceFileIndexImpl.getMainIndexData" to "CONTEXT_FIRST",
    "com.intellij.workspaceModel.core.fileIndex.impl.WorkspaceFileIndexImpl.processContentFilesUnderExcludedDirectory\$lambda\$0" to "P2_FIRST",
    "com.sun.imageio.plugins.png.PNGImageReader.createRaster" to "P2_FIRST",
    "com.sun.imageio.plugins.png.PNGImageReader.decodePass" to "P2_FIRST",
    "java.io.FileOutputStream.writeBytes" to "CONTEXT_FIRST",
    "java.io.WinNTFileSystem.canonicalize" to "P1_FIRST",
    "java.lang.ClassLoader.defineClass" to "P1_FIRST",
    "java.lang.ClassLoader.defineClass0" to "P1_FIRST",
    "java.lang.ClassLoader.defineClass2" to "P1_FIRST",
    "java.lang.ClassLoader.defineClassSourceLocation" to "P1_FIRST",
    "java.lang.ClassLoader.loadClass" to "P1_FIRST",
    "java.util.regex.Matcher.match" to "P2_FIRST",
    "java.util.regex.Pattern\$BmpCharProperty.match" to "P2_FIRST",
    "java.util.regex.Pattern\$SliceNode.study" to "P1_FIRST",
    "java.util.regex.Pattern\$Start.match" to "P2_FIRST",
    "java.util.regex.Pattern.compile" to "P1_FIRST",
    "java.util.regex.Pattern.expr" to "P1_FIRST",
    "java.util.zip.Inflater.end" to "CONTEXT_FIRST",
    "java.util.zip.Inflater.inflateBufferBuffer" to "P2_FIRST",
    "java.util.zip.Inflater.inflateBufferBytes" to "P2_FIRST",
    "javax.imageio.stream.FileCacheImageInputStream\$StreamDisposerRecord.dispose" to "CONTEXT_FIRST",
    "jdk.internal.loader.NativeLibraries.load" to "P1_FIRST",
    "org.jetbrains.plugins.textmate.regex.CaffeineCachingRegexProvider.withRegex" to "CONTEXT_FIRST",
    "org.jetbrains.plugins.textmate.regex.TextMateRangeKt.get-Sp08x1s" to "CONTEXT_FIRST",
    "org.jetbrains.plugins.textmate.regex.TextMateRegexFacadeRememberLastMatch.match-ZRjI0jQ" to "P2_FIRST",
    "sun.nio.ch.FileDispatcherImpl.read0" to "P2_FIRST",
    "sun.nio.fs.WindowsNativeDispatcher.CreateFile0" to "CONTEXT_FIRST",
    "sun.nio.fs.WindowsNativeDispatcher.DeleteFile0" to "CONTEXT_FIRST",
    "sun.nio.fs.WindowsNativeDispatcher.FindClose" to "CONTEXT_FIRST",
    "sun.nio.fs.WindowsNativeDispatcher.FindFirstFile0" to "P2_FIRST",
    "sun.nio.fs.WindowsNativeDispatcher.FindNextFile0" to "P2_FIRST",
    "sun.nio.fs.WindowsNativeDispatcher.GetFileAttributesEx" to "P1_FIRST",
    "sun.nio.fs.WindowsNativeDispatcher.GetFileAttributesEx0" to "P1_FIRST",
    "sun.nio.fs.WindowsNativeDispatcher.GetFinalPathNameByHandle" to "P1_FIRST",
    "sun.nio.fs.WindowsNativeDispatcher.GetFullPathName0" to "P1_FIRST",
    "sun.nio.fs.WindowsNativeDispatcher.GetLogicalDrives" to "P1_FIRST",
    "sun.nio.fs.WindowsNativeDispatcher.SetEndOfFile" to "CONTEXT_FIRST"
  )

  internal fun isP2Preferred(symbol: String): Boolean = priorities[symbol] == "P2_FIRST"

  internal fun initialPriority(symbol: String): String = priorities[symbol] ?: "CONTEXT_FIRST"

  enum class Outcome { CANDIDATE, NOT_APPLICABLE, FAILED, NOT_IMPLEMENTED, INSUFFICIENT_EVIDENCE }

  /** Unknown applicability or a missing generator is not evidence that a strategy failed. */
  fun canTryP3(p1: Outcome, p2: Outcome): Boolean =
    listOf(p1, p2).all { it == Outcome.NOT_APPLICABLE || it == Outcome.FAILED }

  fun select(classification: JsonObject, context: JsonObject, root: Path,
             q13: JsonObject? = null, loading: JsonObject? = null): JsonObject {
    require(context["schema_version"].asString == "repair-method-context/1")
    val p2 = P2ExpensiveWorkRelocation.propose(context, root)
    val proposals = p2.getAsJsonArray("proposals")
    val decisions = JsonArray()
    for (value in classification.getAsJsonArray("matched_frames")) {
      val hit = value.asJsonObject
      val matchingContexts = context.getAsJsonArray("results").map { it.asJsonObject }.filter {
        it["thread_id"] == hit["thread_id"] && it["trigger_frame_id"] == hit["frame_id"] &&
          it["trigger_symbol"] == hit["symbol"]
      }
      val missingSources = matchingContexts.filter {
        it["source_reason"]?.takeUnless { reason -> reason.isJsonNull }?.asString == "SOURCE_FILE_NOT_FOUND" &&
          it["status"].asString != "METHOD_LOCATED"
      }
      fun skipMissingSources(): JsonObject = JsonObject().apply {
        add("trigger", hit.deepCopy())
        addProperty("initial_priority", initialPriority(hit["symbol"].asString))
        addProperty("status", "SKIPPED_SOURCE_UNAVAILABLE")
        addProperty("reason", "REQUIRED_METHOD_SOURCE_NOT_FOUND")
        addProperty("next_action", "CONTINUE_NEXT_FREEZE_POINT")
        addProperty("retry_condition", "RERUN_FINDER_WITH_REQUIRED_SOURCE")
        addProperty("patch_generated", false)
        addProperty("p3_eligible", false)
        addProperty("p3_status", "DEFERRED")
        add("missing_source_contexts", JsonArray().apply { missingSources.forEach { add(it.deepCopy()) } })
      }
      val bound = listOf("q13_evaluation" to q13, "loading_evaluation" to loading).firstNotNullOfOrNull { (pool, evaluation) ->
        evaluation?.getAsJsonArray("decisions")?.map { it.asJsonObject }?.firstOrNull {
          val trigger = it.getAsJsonObject("trigger")
          trigger["symbol"] == hit["symbol"] && trigger["thread_id"] == hit["thread_id"]
        }?.let { pool to it }
      }
      if (bound != null) {
        val (pool, storageDecision) = bound
        if (!storageDecision["patch_generated"].asBoolean && missingSources.isNotEmpty()) {
          decisions.add(skipMissingSources().apply {
            addProperty("evaluation_pool", pool)
            add("source_evaluation", storageDecision.deepCopy())
          })
          continue
        }
        decisions.add(storageDecision.deepCopy().apply {
          addProperty("evaluation_pool", pool)
          add("trigger", hit.deepCopy())
          add("initial_candidates", JsonArray().apply { add("P1"); add("P2") })
          addProperty("initial_tie", false)
          addProperty("p3_eligible", false)
          addProperty("status", if (storageDecision["patch_generated"].asBoolean) "CANDIDATE_SELECTED" else "PENDING")
          if (storageDecision["patch_generated"].asBoolean) {
            addProperty("selected_strategy", storageDecision["selected_strategy"].asString.substringBefore('_'))
            addProperty("selected_proposal_pool", pool)
            add("selected_proposal_index", storageDecision["proposal_index"])
          }
        })
        continue
      }
      val priority = priorities[hit["symbol"].asString] ?: "CONTEXT_FIRST"
      val contexts = matchingContexts.filter { it["status"].asString == "METHOD_LOCATED" }
      if (contexts.isEmpty() && missingSources.isNotEmpty()) {
        decisions.add(skipMissingSources())
        continue
      }
      val preconditions = JsonArray()
      for (methodContext in matchingContexts.ifEmpty { listOf(JsonObject()) }) {
        preconditions.add(JsonObject().apply {
          add("method_frame_id", methodContext["method_frame_id"])
          add("method_layer", methodContext["method_layer"])
          add("p1", org.jetbrains.research.lockrepair.pool.s1.P1PreloadBeforeCriticalRegion.check(methodContext, root))
          add("p3", org.jetbrains.research.lockrepair.pool.s1.P3DeferExpensiveOperation.check(methodContext, root))
        })
      }
      // The current template relocates ImageIO preparation, not native setOverlayIcon.
      val eligible = proposals.mapIndexedNotNull { index, element ->
        val proposal = element.asJsonObject
        if (proposal["status"].asString != "CANDIDATE_PATCH") return@mapIndexedNotNull null
        val matching = contexts.filter {
          val method = it.getAsJsonObject("method")
          method["path"] == proposal["path"] && method["start_line"] == proposal["start_line"] &&
            method["sha256"] == proposal["expected_sha256"] &&
            it.getAsJsonArray("stack_path").any { frame ->
              frame.asJsonObject["symbol"].asString == "javax.imageio.ImageIO.read"
            }
        }.minByOrNull { it["method_layer"].asInt }
        matching?.let { index to it }
      }.sortedWith(compareBy({ it.second["method_layer"].asInt }, { it.first }))
      if (eligible.isEmpty() && missingSources.isNotEmpty()) {
        decisions.add(skipMissingSources())
        continue
      }
      fun preconditionStatus(strategy: String): String = when {
        preconditions.any { it.asJsonObject.getAsJsonObject(strategy)["status"].asString == "PRECONDITIONS_MET" } -> "PRECONDITIONS_MET"
        preconditions.all { it.asJsonObject.getAsJsonObject(strategy)["status"].asString == "NOT_APPLICABLE" } -> "NOT_APPLICABLE"
        else -> "INSUFFICIENT_EVIDENCE"
      }
      val p1Status = preconditionStatus("p1")
      val p1Outcome = when (p1Status) {
        "PRECONDITIONS_MET" -> Outcome.NOT_IMPLEMENTED // Preconditions are not a generated patch.
        "NOT_APPLICABLE" -> Outcome.NOT_APPLICABLE
        else -> Outcome.INSUFFICIENT_EVIDENCE
      }
      val p2Outcome = if (eligible.isNotEmpty()) Outcome.CANDIDATE else Outcome.INSUFFICIENT_EVIDENCE
      decisions.add(JsonObject().apply {
        add("trigger", hit.deepCopy())
        addProperty("initial_priority", priority)
        add("initial_candidates", JsonArray().apply {
          add(if (priority == "P2_FIRST") "P2" else "P1")
          add(if (priority == "P2_FIRST") "P1" else "P2")
        })
        addProperty("initial_tie", priority == "CONTEXT_FIRST")
        addProperty("p1_status", p1Status)
        addProperty("p1_generator_status", "NOT_IMPLEMENTED")
        add("source_preconditions", preconditions)
        addProperty("p2_status", p2Outcome.name)
        addProperty("p2_reason", when {
          eligible.isNotEmpty() -> "VERIFIED_SOURCE_TEMPLATE_AND_RELOCATED_STACK_PATH"
          contexts.isEmpty() -> "NO_VERIFIED_METHOD_CONTEXT"
          else -> "NO_SUPPORTED_TEMPLATE_ON_RELOCATED_PATH"
        })
        addProperty("p3_precondition_status", preconditionStatus("p3"))
        addProperty("p3_generator_status", "NOT_IMPLEMENTED")
        addProperty("p3_status", if (canTryP3(p1Outcome, p2Outcome)) preconditionStatus("p3") else "DEFERRED")
        addProperty("p3_eligible", canTryP3(p1Outcome, p2Outcome))
        addProperty("p3_reason", "REQUIRES_BOTH_PRIMARY_FAILURES_AND_DEFERRABLE_WORK_EVIDENCE")
        addProperty("status", if (eligible.isNotEmpty()) "CANDIDATE_SELECTED" else "PENDING")
        if (eligible.isNotEmpty()) {
          addProperty("selected_strategy", "P2")
          addProperty("selected_proposal_index", eligible.first().first)
          add("method_frame_id", eligible.first().second["method_frame_id"])
          add("method_layer", eligible.first().second["method_layer"])
        }
      })
    }
    return JsonObject().apply {
      addProperty("schema_version", "repair-selection/1")
      add("record_id", context["record_id"])
      addProperty("status", when {
        decisions.size() == 0 -> "NOT_APPLICABLE"
        decisions.all { it.asJsonObject["status"].asString == "CANDIDATE_SELECTED" } -> "CANDIDATE_SELECTED"
        decisions.any { it.asJsonObject["status"].asString == "CANDIDATE_SELECTED" } -> "PARTIAL"
        decisions.all { it.asJsonObject["status"].asString == "SKIPPED_SOURCE_UNAVAILABLE" } -> "SKIPPED_SOURCE_UNAVAILABLE"
        else -> "PENDING"
      })
      addProperty("selection_basis", "SUPPORTED_SOURCE_TEMPLATE_THEN_NEAREST_METHOD_LAYER")
      addProperty("optimality", "BEST_AVAILABLE_SUPPORTED_CANDIDATE_NOT_GLOBAL_OPTIMUM")
      addProperty("applied", false)
      add("decisions", decisions)
      add("p2_evaluation", p2)
      if (q13 != null) add("q13_evaluation", q13)
      if (loading != null) add("loading_evaluation", loading)
    }
  }
}
