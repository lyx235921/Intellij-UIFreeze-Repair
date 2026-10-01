package org.jetbrains.research.lockrepair

import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

/** Q1 candidate rules over runtime stack evidence; does not select or perform repairs. */
object Q1ExpensiveWorkRelocationClassifier {
  private val methodCategories = mapOf(
    "com.intellij.json.syntax._JsonLexer.advance" to "Q1.5",
    "com.intellij.json.syntax._JsonLexer.codePoint" to "Q1.5",
    "com.intellij.lexer.FlexAdapter.locateToken" to "Q1.5",
    "com.intellij.lexer.MergingLexerAdapter\$MyMergeFunction.merge" to "Q1.5",
    "com.intellij.openapi.vfs.newvfs.persistent.DefaultInMemoryInvertedNameIndex.deleteDataInner" to "Q1.3",
    "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.getName" to "Q1.3",
    "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.getNameByNameId" to "Q1.3",
    "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.readAttribute" to "Q1.3",
    "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.readSymlinkTarget" to "Q1.3",
    "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.update" to "Q1.3",
    "com.intellij.openapi.vfs.newvfs.persistent.FSRecordsImpl.updateSymlinksForNewChildren" to "Q1.3",
    "com.intellij.openapi.vfs.newvfs.persistent.PersistentFSContentAccessor.acquireContentRecord" to "Q1.3",
    "com.intellij.platform.syntax.impl.builder.MarkerProduction.addMarker" to "Q1.5",
    "com.intellij.platform.syntax.impl.builder.MarkerProduction.findLinearly" to "Q1.5",
    "com.intellij.platform.syntax.impl.builder.MarkerProduction.findMarkerAtLexeme" to "Q1.5",
    "com.intellij.platform.syntax.impl.builder.SyntaxTreeBuilderImpl\$WhitespaceBalancer.balanceMarkerAndReturnNewIndex" to "Q1.5",
    "com.intellij.platform.syntax.impl.builder.SyntaxTreeBuilderImpl.remapCurrentToken" to "Q1.5",
    "com.intellij.platform.syntax.impl.builder.SyntaxTreeBuilderImpl.rollbackTo\$intellij_platform_syntax" to "Q1.5",
    "com.intellij.platform.syntax.lexer.Builder.performLexing" to "Q1.5",
    "com.intellij.platform.syntax.psi.ParsingDiagnostics.registerLexing" to "Q1.5",
    "com.intellij.platform.syntax.psi.impl.NodeData.createLeaf" to "Q1.5",
    "com.intellij.platform.syntax.psi.impl.NodeData.getInternedText" to "Q1.5",
    "com.intellij.platform.syntax.psi.impl.NodeData.insertLeaves" to "Q1.5",
    "com.intellij.platform.syntax.util.runtime.Modifiers.access\$get_NONE_\$cp" to "Q1.5",
    "com.intellij.platform.syntax.util.runtime.impl.MyList.trimSize-impl" to "Q1.5",
    "com.intellij.platform.syntax.util.runtime.impl.SyntaxGeneratedParserRuntimeImpl.enter_section_-T529yjc" to "Q1.5",
    "com.intellij.platform.syntax.util.runtime.impl.SyntaxGeneratedParserRuntimeImpl.exit_section_" to "Q1.5",
    "com.intellij.platform.syntax.util.runtime.impl.SyntaxGeneratedParserRuntimeImpl.nextTokenIsSlow" to "Q1.5",
    "com.intellij.textmate.joni.JoniRegexFacade.match-ZRjI0jQ" to "Q1.4",
    "com.intellij.ui.svg.SvgCacheManagerKt.createIconCacheKey-2Mr4RHQ" to "Q1.7",
    "com.intellij.ui.svg.SvgCacheManagerKt.readImage" to "Q1.7",
    "com.intellij.ui.svg.SvgKt.loadSvgAndCacheIfApplicable-F6nGey4" to "Q1.7",
    "com.intellij.util.io.SimpleStringPersistentEnumerator.enumerate" to "Q1.3",
    "com.intellij.util.lang.UrlClassLoader.findClass" to "Q1.2",
    "com.intellij.workspaceModel.core.fileIndex.impl.ExcludedFileSet\$ByFileKind.computeMasks" to "Q1.3",
    "com.intellij.workspaceModel.core.fileIndex.impl.WorkspaceFileIndexDataImpl.ensureIsUpToDate" to "Q1.3",
    "com.intellij.workspaceModel.core.fileIndex.impl.WorkspaceFileIndexDataImpl.getFileInfo" to "Q1.3",
    "com.intellij.workspaceModel.core.fileIndex.impl.WorkspaceFileIndexImpl\$processContentUnderDirectory\$visitor\$1.visitFileEx" to "Q1.3",
    "com.intellij.workspaceModel.core.fileIndex.impl.WorkspaceFileIndexImpl.getMainIndexData" to "Q1.3",
    "com.intellij.workspaceModel.core.fileIndex.impl.WorkspaceFileIndexImpl.processContentFilesUnderExcludedDirectory\$lambda\$0" to "Q1.3",
    "com.sun.imageio.plugins.png.PNGImageReader.createRaster" to "Q1.7",
    "com.sun.imageio.plugins.png.PNGImageReader.decodePass" to "Q1.7",
    "java.io.FileOutputStream.writeBytes" to "Q1.1",
    "java.io.WinNTFileSystem.canonicalize" to "Q1.1",
    "java.lang.ClassLoader.defineClass" to "Q1.2",
    "java.lang.ClassLoader.defineClass0" to "Q1.2",
    "java.lang.ClassLoader.defineClass2" to "Q1.2",
    "java.lang.ClassLoader.defineClassSourceLocation" to "Q1.2",
    "java.lang.ClassLoader.loadClass" to "Q1.2",
    "java.util.regex.Matcher.match" to "Q1.4",
    "java.util.regex.Pattern\$BmpCharProperty.match" to "Q1.4",
    "java.util.regex.Pattern\$SliceNode.study" to "Q1.4",
    "java.util.regex.Pattern\$Start.match" to "Q1.4",
    "java.util.regex.Pattern.compile" to "Q1.4",
    "java.util.regex.Pattern.expr" to "Q1.4",
    "java.util.zip.Inflater.end" to "Q1.6",
    "java.util.zip.Inflater.inflateBufferBuffer" to "Q1.6",
    "java.util.zip.Inflater.inflateBufferBytes" to "Q1.6",
    "javax.imageio.stream.FileCacheImageInputStream\$StreamDisposerRecord.dispose" to "Q1.7",
    "jdk.internal.loader.NativeLibraries.load" to "Q1.2",
    "org.jetbrains.plugins.textmate.regex.CaffeineCachingRegexProvider.withRegex" to "Q1.4",
    "org.jetbrains.plugins.textmate.regex.TextMateRangeKt.get-Sp08x1s" to "Q1.4",
    "org.jetbrains.plugins.textmate.regex.TextMateRegexFacadeRememberLastMatch.match-ZRjI0jQ" to "Q1.4",
    "sun.nio.ch.FileDispatcherImpl.read0" to "Q1.1",
    "sun.nio.fs.WindowsNativeDispatcher.CreateFile0" to "Q1.1",
    "sun.nio.fs.WindowsNativeDispatcher.DeleteFile0" to "Q1.1",
    "sun.nio.fs.WindowsNativeDispatcher.FindClose" to "Q1.1",
    "sun.nio.fs.WindowsNativeDispatcher.FindFirstFile0" to "Q1.1",
    "sun.nio.fs.WindowsNativeDispatcher.FindNextFile0" to "Q1.1",
    "sun.nio.fs.WindowsNativeDispatcher.GetFileAttributesEx" to "Q1.1",
    "sun.nio.fs.WindowsNativeDispatcher.GetFileAttributesEx0" to "Q1.1",
    "sun.nio.fs.WindowsNativeDispatcher.GetFinalPathNameByHandle" to "Q1.1",
    "sun.nio.fs.WindowsNativeDispatcher.GetFullPathName0" to "Q1.1",
    "sun.nio.fs.WindowsNativeDispatcher.GetLogicalDrives" to "Q1.1",
    "sun.nio.fs.WindowsNativeDispatcher.SetEndOfFile" to "Q1.1",
  )

  private fun normalizedSymbol(frame: JsonObject): String? =
    frame["symbol"].takeUnless { it.isJsonNull }?.asString
      ?.replace(Regex("^(?:[^/]+//|[^/]+/)(?=[A-Za-z_])"), "")

  private val waitingTops = setOf(
    "jdk.internal.misc.Unsafe.park", "sun.misc.Unsafe.park",
    "java.lang.Object.wait", "java.lang.Object.wait0",
    "java.lang.Thread.sleep", "java.lang.Thread.sleep0", "java.lang.Thread.sleepNanos0",
    "java.lang.Thread.join", "java.util.concurrent.locks.LockSupport.park",
    "java.util.concurrent.locks.LockSupport.parkNanos", "java.util.concurrent.locks.LockSupport.parkUntil",
    "java.util.concurrent.FutureTask.get", "java.util.concurrent.FutureTask.awaitDone",
  )

  fun classify(record: JsonObject): JsonObject {
    val uiIds = record.getAsJsonArray("ui_thread_ids").map { it.asString }.toSet()
    val matches = JsonArray()
    val checks = JsonArray()
    for (value in record.getAsJsonArray("threads")) {
      val thread = value.asJsonObject
      if (thread["thread_id"].asString !in uiIds) continue
      val frames = thread.getAsJsonArray("frames")
      val top = frames.firstOrNull()?.asJsonObject
      val topSymbol = top?.let { normalizedSymbol(it) }
      val reason = when {
        thread["state"].asString != "RUNNABLE" -> "STATE_NOT_RUNNABLE"
        top == null || top["index"].asInt != 0 || top["elided"].asBoolean || topSymbol.isNullOrBlank() -> "TOP_FRAME_UNAVAILABLE"
        topSymbol in waitingTops -> "TOP_WAIT_METHOD"
        else -> "PASSED"
      }
      checks.add(JsonObject().apply {
        add("thread_id", thread["thread_id"])
        add("state", thread["state"])
        addProperty("top_symbol", topSymbol)
        addProperty("result", reason)
      })
      if (reason != "PASSED") continue
      for (frameValue in thread.getAsJsonArray("frames")) {
        val frame = frameValue.asJsonObject
        val normalized = normalizedSymbol(frame) ?: continue
        if (normalized in methodCategories) matches.add(JsonObject().apply {
          add("thread_id", thread["thread_id"])
          add("thread_state", thread["state"])
          add("frame_id", frame["frame_id"])
          addProperty("symbol", normalized)
          addProperty("category", methodCategories.getValue(normalized))
        })
      }
    }
    return JsonObject().apply {
      add("rules", JsonArray().apply { methodCategories.keys.forEach { add(it) } })
      add("matched_methods", JsonArray().apply {
        matches.map { it.asJsonObject["symbol"].asString }.distinct().forEach { add(it) }
      })
      addProperty("scope", "RUNNABLE_UI_WITH_NON_WAIT_TOP_EXACT_SYMBOL")
      add("ui_checks", checks)
      addProperty("q1_count", if (matches.size() > 0) 1 else 0)
      addProperty("decision", when {
        matches.size() > 0 -> "CANDIDATE"
        checks.none { it.asJsonObject["result"].asString == "PASSED" } -> "UI_CHECK_NOT_PASSED"
        else -> "NO_RULE_MATCH"
      })
      add("categories", JsonArray().apply {
        matches.groupBy { it.asJsonObject["category"].asString }.toSortedMap().forEach { (category, frames) ->
          add(JsonObject().apply {
            addProperty("category", category)
            addProperty("count", 1)
            add("matched_methods", JsonArray().apply {
              frames.map { it.asJsonObject["symbol"].asString }.distinct().forEach { add(it) }
            })
            add("frame_ids", JsonArray().apply { frames.forEach { add(it.asJsonObject["frame_id"]) } })
          })
        }
      })
      add("matched_frames", matches)
    }
  }

  fun locate(record: JsonObject, root: Path): JsonObject {
    require(record["schema_version"].asString == "finder-source-locations/1")
    val sourceRoot = root.toRealPath()
    val ids = (record.getAsJsonArray("cause_thread_ids") + record.getAsJsonArray("ui_thread_ids"))
      .map { it.asString }.toSet()
    val locations = JsonArray()
    for (threadValue in record.getAsJsonArray("threads")) {
      val thread = threadValue.asJsonObject
      if (thread["thread_id"].asString !in ids) continue
      for (frameValue in thread.getAsJsonArray("frames")) {
        val frame = frameValue.asJsonObject
        val source = frame.getAsJsonObject("source")
        val result = JsonObject()
        result.add("thread_id", thread["thread_id"])
        result.add("thread_name", thread["name"])
        result.add("thread_state", thread["state"])
        result.add("thread_role", thread["role"])
        result.add("is_ui_thread", thread["is_ui_thread"])
        result.add("frame_id", frame["frame_id"])
        result.add("symbol", frame["symbol"])
        val symbol = frame["symbol"].takeUnless { it.isJsonNull }?.asString.orEmpty()
        result.addProperty("class_name", symbol.replace(Regex("^[^/]+@[^/]+/"), "").substringBeforeLast('.', ""))
        result.addProperty("method_name", symbol.substringAfterLast('.'))
        result.add("stack_file", frame["file"])
        result.add("stack_line", frame["line"])
        result.add("finder_status", source["status"])
        result.add("reason", source["reason"])
        val candidates = JsonArray()
        for (candidateValue in source.getAsJsonArray("candidates")) {
          val candidate = candidateValue.asJsonObject.deepCopy()
          try {
            val path = sourceRoot.resolve(candidate["path"].asString).normalize()
            require(path.startsWith(sourceRoot) && path.toRealPath().startsWith(sourceRoot)) { "PATH_OUTSIDE_ROOT" }
            val bytes = Files.readAllBytes(path)
            val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            require(hash == candidate["sha256"].asString) { "SOURCE_CHANGED" }
            val lines = bytes.toString(Charsets.UTF_8).lines()
            val start = candidate["start_line"].asInt
            val end = candidate["end_line"].asInt
            require(start >= 1 && end >= start && end <= lines.size) { "INVALID_RANGE" }
            candidate.addProperty("verification", "HASH_MATCHED")
            candidate.addProperty("absolute_path", path.toString())
            candidate.addProperty("source_text", lines.subList(start - 1, end).joinToString("\n"))
            candidate.addProperty("finder_selected", candidateValue == source["selected"])
            val calls = JsonArray()
            for (edgeValue in record.getAsJsonArray("call_edges")) {
              val edge = edgeValue.asJsonObject
              if (edge["caller_frame_id"] != frame["frame_id"]) continue
              for (siteValue in edge.getAsJsonArray("call_sites")) {
                val site = siteValue.asJsonObject
                if (site["path"] == candidate["path"] && site["sha256"] == candidate["sha256"] &&
                    site["line"].asInt in start..end) calls.add(site.deepCopy())
              }
            }
            candidate.add("call_sites", calls)
          }
          catch (error: Exception) {
            candidate.addProperty("verification", "UNAVAILABLE")
            candidate.addProperty("verification_error", error.message ?: error.javaClass.simpleName)
          }
          candidates.add(candidate)
        }
        result.add("locations", candidates)
        locations.add(result)
      }
    }
    return JsonObject().apply {
      addProperty("schema_version", "repair-q1-locations/1")
      addProperty("problem_family", "Q1")
      add("record_id", record["record_id"])
      add("workbook_sha256", record["workbook_sha256"])
      add("input", record["input"].deepCopy())
      add("parse", record["parse"].deepCopy())
      addProperty("source_root", sourceRoot.toString())
      val classification = classify(record)
      addProperty("problem_assessment", classification["decision"].asString)
      add("classification", classification)
      addProperty("repair_point_selection", "NOT_PERFORMED")
      add("frames", locations)
    }
  }

  @JvmStatic
  fun main(args: Array<String>) {
    val gson = Gson()
    System.`in`.bufferedReader(Charsets.UTF_8).useLines { lines ->
      for (line in lines) {
        val record = JsonParser.parseString(line).asJsonObject
        val result = if ("--count-only" in args) JsonObject().apply {
          addProperty("schema_version", "repair-q1-classification/1")
          addProperty("problem_family", "Q1")
          add("record_id", record["record_id"])
          add("classification", classify(record))
        }
        else locate(record, Path.of(args.firstOrNull { !it.startsWith("--") } ?: record["source_root"].asString))
        if (args.any { it in setOf("--s1-q16-method", "--extract-method", "--s1-p2", "--repair-selection",
                                  "--s1-regex", "--s1-q13", "--s1-storage", "--s1-loading") }) {
          require("--count-only" !in args)
          val context = org.jetbrains.research.lockrepair.pool.s1.ExtractMethod.locateMethod(
            record, result, if ("--s1-q16-method" in args && args.none {
              it in setOf("--repair-selection", "--s1-q13", "--s1-storage", "--s1-loading")
            }) "Q1.6" else null)
          result.add("method_context", context)
          val q13 = if ("--s1-q13" in args || "--s1-storage" in args || "--repair-selection" in args) {
            org.jetbrains.research.lockrepair.pool.s1.P1StorageRelocation.propose(
              record, result, Path.of(result["source_root"].asString))
          } else null
          if ("--s1-q13" in args) result.add("s1_q13", q13)
          if ("--s1-storage" in args) result.add("s1_storage", q13)
          val loading = if ("--s1-loading" in args || "--repair-selection" in args) {
            org.jetbrains.research.lockrepair.pool.s1.P1ClassLoadingPreload.propose(record, result, Path.of(result["source_root"].asString))
          } else null
          if ("--s1-loading" in args) result.add("s1_loading", loading)
          if ("--s1-regex" in args) result.add("s1_regex", org.jetbrains.research.lockrepair.pool.s1.P1RegexPrecompilation.propose(
            context, Path.of(result["source_root"].asString)))
          if ("--s1-q16-method" in args) result.add("s1_q16", context)
          if ("--repair-selection" in args) {
            val selection = org.jetbrains.research.lockrepair.pool.s1.RepairSelection.select(
              result.getAsJsonObject("classification"), context, Path.of(result["source_root"].asString), q13, loading)
            result.add("repair_selection", selection)
            if ("--s1-p2" in args) result.add("s1_p2", selection["p2_evaluation"].deepCopy())
          }
          else if ("--s1-p2" in args) {
            result.add("s1_p2", org.jetbrains.research.lockrepair.pool.s1.P2ExpensiveWorkRelocation.propose(
              context, Path.of(result["source_root"].asString)))
          }
        }
        if ("--s1-p1" in args) {
          require("--count-only" !in args)
          result.add("s1_p1", org.jetbrains.research.lockrepair.pool.s1.P1PreloadBeforeCriticalRegion.propose(
            record, result, Path.of(result["source_root"].asString)))
        }
        System.out.write((gson.toJson(result) + "\n").toByteArray(Charsets.UTF_8))
        System.out.flush()
      }
    }
  }
}
