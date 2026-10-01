package org.jetbrains.research.lockrepair.pool.s1

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

/** Conditions are scoped to a proposed relocation unit, never inferred from method names alone. */
object RelocationPreconditions {
  private const val ORIGINAL_METHOD_SHA = "e3e0c85f1591f02c90bd9f9c599a64a938da14fc0b9d25cf96ac93c5ddbf8b80"

  private fun sha(bytes: ByteArray): String =
    MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

  internal fun supportsMethodShape(method: JsonObject): Boolean =
    method["owner"].asString == "com.intellij.ui.AppIcon\$Win7AppIcon" &&
      method["method"].asString == "_setOkBadge" &&
      sha(method["source_text"].asString.toByteArray(Charsets.UTF_8)) == ORIGINAL_METHOD_SHA


  enum class Verdict { PASS, FAIL, UNKNOWN }

  data class Check(val id: String, val verdict: Verdict, val evidence: String)

  fun status(checks: List<Check>): String = when {
    checks.any { it.verdict == Verdict.FAIL } -> "NOT_APPLICABLE"
    checks.isEmpty() || checks.any { it.verdict == Verdict.UNKNOWN } -> "INSUFFICIENT_EVIDENCE"
    else -> "PRECONDITIONS_MET"
  }

  fun report(strategy: String, scope: String, checks: List<Check>): JsonObject = JsonObject().apply {
    addProperty("strategy", strategy)
    addProperty("scope", scope)
    addProperty("status", status(checks))
    addProperty("generator_status", "NOT_IMPLEMENTED")
    addProperty("applied", false)
    add("checks", JsonArray().apply {
      for (check in checks) add(JsonObject().apply {
        addProperty("id", check.id)
        addProperty("status", check.verdict.name)
        addProperty("evidence", check.evidence)
      })
    })
  }

  /** P2 consumes the checked snapshot, avoiding a second unchecked file read during diff generation. */
  data class P2Check(val status: String, val reason: String? = null, val sourceText: String? = null)

  fun checkP2(method: JsonObject, root: Path): P2Check {
    if (!supportsMethodShape(method)) return P2Check("UNSUPPORTED", "UNSUPPORTED_METHOD_SHAPE")
    return try {
      P2Check("PRECONDITIONS_MET", sourceText = verifiedSource(method, root, checkGeneratedNames = true))
    }
    catch (e: Exception) {
      P2Check("UNAVAILABLE", e.message ?: e.javaClass.simpleName)
    }
  }

  /** Exact reviewed upstream snapshot, not a claim that it is the incident's binary version. */
  fun checkRegexPrecompilation(method: JsonObject, root: Path): P2Check {
    if (method["owner"]?.asString != "org.wso2.lsp4intellij.IntellijLanguageClient" ||
        method["method"]?.asString != "isExtensionSupported") {
      return P2Check("UNSUPPORTED", "UNSUPPORTED_REGEX_CALLER")
    }
    return try {
      val text = verifiedSource(method, root)
      require(method["sha256"].asString == "55a9574465d9e165f0800bc1604f25d2d89930c80a31adc73062de821326bde3") {
        "UNREVIEWED_REGEX_SOURCE_VERSION"
      }
      P2Check("PRECONDITIONS_MET", sourceText = text)
    }
    catch (e: Exception) {
      P2Check("UNAVAILABLE", e.message ?: e.javaClass.simpleName)
    }
  }

  private fun verifiedSource(method: JsonObject, root: Path, checkGeneratedNames: Boolean = false): String {
    val base = root.toRealPath()
    val path = base.resolve(method["path"].asString).normalize()
    require(path.startsWith(base) && path.toRealPath().startsWith(base)) { "PATH_OUTSIDE_ROOT" }
    val bytes = Files.readAllBytes(path)
    val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    require(hash == method["sha256"].asString) { "SOURCE_CHANGED" }
    val text = bytes.toString(Charsets.UTF_8)
    if (checkGeneratedNames) {
      require(!text.contains("myP2OkIconBytes") && !text.contains("myP2BadgeRequests")) { "GENERATED_NAME_COLLISION" }
    }
    val lines = text.lines()
    require(lines.subList(method["start_line"].asInt - 1, method["end_line"].asInt).joinToString("\n") ==
            method["source_text"].asString) { "METHOD_RANGE_CHANGED" }
    return text
  }

  data class Q13Check(val report: JsonObject, val source: String? = null, val method: JsonObject? = null)

  /** Full runtime stack is supplemental evidence, independent of the five-layer source extraction limit. */
  private fun pathToCaller(finder: JsonObject, hit: JsonObject, caller: String): JsonArray? {
    val thread = finder.getAsJsonArray("threads").map { it.asJsonObject }
      .firstOrNull { it["thread_id"] == hit["thread_id"] } ?: return null
    val frames = thread.getAsJsonArray("frames").map { it.asJsonObject }
    val start = frames.indexOfFirst { it["frame_id"] == hit["frame_id"] }
    if (start < 0) return null
    val path = JsonArray()
    for (i in start until frames.size) {
      val frame = frames[i]
      val symbol = frame["symbol"].takeUnless { it == null || it.isJsonNull }?.asString
        ?.replace(Regex("^(?:[^/]+//|[^/]+/)(?=[A-Za-z_])"), "") ?: return null
      if (symbol.isBlank() || frame["elided"].asBoolean ||
          (i > start && frame["index"].asInt != frames[i - 1]["index"].asInt + 1)) return null
      if (i == start && symbol != hit["symbol"].asString) return null
      path.add(frame.deepCopy().apply { addProperty("normalized_symbol", symbol) })
      if (symbol == caller || (caller.endsWith('$') && symbol.startsWith(caller))) return path
    }
    return null
  }

  internal fun checkGitListener(finder: JsonObject, hit: JsonObject, root: Path): Q13Check {
    val path = pathToCaller(finder, hit, "git4idea.branch.GitBranchIncomingOutgoingManager.lambda\$activate\$")
    fun result(reason: String, source: String? = null, method: JsonObject? = null) = Q13Check(JsonObject().apply {
      addProperty("reason", reason)
      addProperty("status", if (source == null) "INSUFFICIENT_EVIDENCE" else "PRECONDITIONS_MET")
      addProperty("location_basis", "MANUALLY_REVIEWED_ENCLOSING_METHOD_NOT_EXTRACTOR_LOCATION")
      if (path != null) add("supplemental_runtime_path", path)
    }, source, method)
    if (hit["symbol"].asString !in setOf("java.lang.ClassLoader.defineClass2", "java.lang.ClassLoader.defineClass",
                                        "java.lang.ClassLoader.loadClass")) return result("UNSUPPORTED_GIT_LOADING_TRIGGER")
    if (path == null) return result("NO_CONTIGUOUS_GIT_ACTIVATION_PATH")
    return try {
      val base = root.toRealPath()
      val file = base.resolve(P1ClassLoadingPreload.GIT_PATH).normalize()
      require(file.toRealPath().startsWith(base)) { "PATH_OUTSIDE_ROOT" }
      val bytes = Files.readAllBytes(file)
      require(sha(bytes) == P1ClassLoadingPreload.GIT_SHA) { "UNREVIEWED_GIT_SOURCE_VERSION" }
      val source = bytes.toString(Charsets.UTF_8).replace("\r\n", "\n")
      val start = source.indexOf("  public void activate() {")
      val end = source.indexOf("  private void updateIncomingScheduling()", start)
      val method = JsonObject().apply {
        addProperty("path", P1ClassLoadingPreload.GIT_PATH)
        addProperty("sha256", P1ClassLoadingPreload.GIT_SHA)
        addProperty("owner", "git4idea.branch.GitBranchIncomingOutgoingManager")
        addProperty("method", "activate")
        addProperty("start_line", source.take(start).count { it == '\n' } + 1)
        addProperty("source_text", source.substring(start, end).trimEnd())
        addProperty("location_basis", "MANUALLY_REVIEWED_ENCLOSING_METHOD_NOT_EXTRACTOR_LOCATION")
      }
      result("SOURCE_BOUND_GIT_LISTENER_PREPARATION", source, method)
    }
    catch (e: Exception) { result(e.message ?: e.javaClass.simpleName) }
  }

  internal fun checkNotificationPreparation(finder: JsonObject, hit: JsonObject, root: Path): Q13Check {
    val path = pathToCaller(finder, hit, "com.intellij.diagnostic.IdeMessagePanel.showErrorNotification")
    fun result(reason: String, source: String? = null, method: JsonObject? = null) = Q13Check(JsonObject().apply {
      addProperty("reason", reason)
      addProperty("status", if (source == null) "INSUFFICIENT_EVIDENCE" else "PRECONDITIONS_MET")
      if (path != null) add("supplemental_runtime_path", path)
    }, source, method)
    if (path == null || hit["symbol"].asString !in setOf("com.intellij.util.lang.UrlClassLoader.findClass",
        "java.lang.ClassLoader.defineClass", "java.lang.ClassLoader.defineClass2", "java.lang.ClassLoader.loadClass")) {
      return result("NO_REVIEWED_NOTIFICATION_PATH")
    }
    return try {
      val base = root.toRealPath()
      val pins = mapOf(P1ClassLoadingPreload.NOTIFICATION_PATH to P1ClassLoadingPreload.NOTIFICATION_SHA,
        "platform/ide-core/src/com/intellij/notification/Notification.java" to
          "5cb3105cb4b5bc2a61da48bae524f6f71443caed38959e5eaea04806c3119732",
        "platform/ide-core/src/com/intellij/notification/NotificationAction.java" to
          "c1f48ea9d24b75b32b9762734f8764d8b666f21e7eace76f886cd7b315714ccb")
      var source = ""
      for ((relative, hash) in pins) {
        val file = base.resolve(relative).toRealPath()
        require(file.startsWith(base)) { "PATH_OUTSIDE_ROOT" }
        val bytes = Files.readAllBytes(file)
        require(sha(bytes) == hash) { "UNREVIEWED_NOTIFICATION_SOURCE: $relative" }
        if (relative == P1ClassLoadingPreload.NOTIFICATION_PATH) source = bytes.toString(Charsets.UTF_8).replace("\r\n", "\n")
      }
      val start = source.indexOf("  private void showErrorNotification(")
      val end = source.indexOf("  private final class IdeMessagePanelComponent", start)
      val method = JsonObject().apply {
        addProperty("path", P1ClassLoadingPreload.NOTIFICATION_PATH)
        addProperty("sha256", P1ClassLoadingPreload.NOTIFICATION_SHA)
        addProperty("method", "showErrorNotification")
        addProperty("source_text", source.substring(start, end).trimEnd())
        addProperty("start_line", source.take(start).count { it == '\n' } + 1)
        addProperty("location_basis", "REVIEWED_SOURCE_SUPPLEMENT")
      }
      result("SOURCE_BOUND_NOTIFICATION_PREPARATION", source, method)
    }
    catch (e: Exception) { result(e.message ?: e.javaClass.simpleName) }
  }

  /** The captured service is used only when AWT dispatches the event; construction itself reads no UI state. */
  internal fun checkTerminalListener(hit: JsonObject, layers: JsonArray, root: Path): P2Check {
    if (hit["symbol"]?.asString != "java.lang.ClassLoader.defineClass0") {
      return P2Check("UNSUPPORTED", "NO_REVIEWED_LOADING_TEMPLATE")
    }
    val layer = layers.map { it.asJsonObject }.firstOrNull {
      it["status"]?.asString == "METHOD_LOCATED" &&
        it.getAsJsonObject("method")?.get("owner")?.asString ==
        "com.intellij.terminal.frontend.fus.TerminalFocusFusService" &&
        it.getAsJsonObject("method")?.get("method")?.asString == "installAWTListener"
    } ?: return P2Check("UNAVAILABLE", "NO_TERMINAL_LISTENER_CONTEXT")
    return try {
      val method = layer.getAsJsonObject("method")
      require(method["path"].asString == P1ClassLoadingPreload.TERMINAL_PATH) { "UNREVIEWED_LOADING_PATH" }
      val source = verifiedSource(method, root).replace("\r\n", "\n")
      require(method["sha256"].asString == "ec827ad9a0516c7a18b4f4003f54fdf1642a99a251386e0c07f29136c0897830") {
        "UNREVIEWED_TERMINAL_SOURCE_VERSION"
      }
      val path = layer.getAsJsonArray("stack_path").map { it.asJsonObject["symbol"].asString }
      require(path.firstOrNull() == hit["symbol"].asString &&
              "java.lang.invoke.LambdaMetafactory.metafactory" in path) { "NO_LAMBDA_BOOTSTRAP_PATH" }
      P2Check("PRECONDITIONS_MET", "SOURCE_BOUND_LISTENER_PREPARATION", source)
    }
    catch (e: Exception) {
      P2Check("UNAVAILABLE", e.message ?: e.javaClass.simpleName)
    }
  }

  /** Bound methods expose real source evidence and unresolved safety conditions, never synthetic successful patches. */
  internal fun pendingPreloadDecision(hit: JsonObject, layers: JsonArray, root: Path): JsonObject {
    val symbol = hit["symbol"].asString
    require(symbol in P1StorageRelocation.pathTriggers || symbol in P1ClassLoadingPreload.triggers)
    val sourceChecks = layers.map { sourceCheck(it.asJsonObject, root) }
    val verified = sourceChecks.count { it.verdict == Verdict.PASS }
    val changed = sourceChecks.any { it.verdict != Verdict.PASS && it.evidence != "NO_VERIFIED_METHOD_CONTEXT" }
    val requirement = when (symbol) {
      "sun.nio.fs.WindowsNativeDispatcher.GetLogicalDrives" -> "DRIVE_SET_FRESHNESS_AND_ROOT_CONSUMER"
      "sun.nio.fs.WindowsNativeDispatcher.GetFullPathName0" -> "WORKING_DIRECTORY_DRIVE_CONTEXT_AND_PATH_FRESHNESS"
      "java.io.WinNTFileSystem.canonicalize",
      "sun.nio.fs.WindowsNativeDispatcher.GetFinalPathNameByHandle" -> "FILE_IDENTITY_SYMLINK_FRESHNESS_AND_HANDLE_LIFETIME"
      "jdk.internal.loader.NativeLibraries.load" -> "NATIVE_LIBRARY_CLASSLOADER_OWNERSHIP_AND_INITIALIZATION_LIFETIME"
      "java.lang.ClassLoader.defineClass0" -> "LAMBDA_BOOTSTRAP_CAPTURES_AND_INITIALIZATION_THREAD"
      "java.lang.ClassLoader.defineClassSourceLocation" -> "PROTECTION_DOMAIN_CODE_SOURCE_AND_INITIALIZATION_ORDER"
      else -> "CLASSLOADER_IDENTITY_AND_INITIALIZATION_ORDER"
    }
    val checks = mutableListOf(Check("SOURCE", if (verified > 0 && !changed) Verdict.PASS else Verdict.UNKNOWN,
      "VERIFIED_LAYERS=$verified; TOTAL_LAYERS=${layers.size()}; SOURCE_CHANGED=$changed"))
    checks.add(Check(requirement, Verdict.UNKNOWN, "REQUIRES_REVIEWED_PREPARATION_POINT_AND_SAFE_CONSUMER"))
    checks.add(Check("BACKGROUND_THREAD_AND_COMPLETION_CONTRACT", Verdict.UNKNOWN,
      "LOCATED_CALLER_ALONE_DOES_NOT_ESTABLISH_RELOCATION_SAFETY"))
    val reason = when {
      changed -> "SOURCE_CONTEXT_CHANGED"
      verified == 0 -> "NO_VERIFIED_METHOD_CONTEXT"
      else -> "NO_REVIEWED_PRELOAD_TEMPLATE: $requirement"
    }
    return JsonObject().apply {
      add("trigger", hit.deepCopy())
      add("method_contexts", layers.deepCopy())
      addProperty("initial_priority", org.jetbrains.research.lockrepair.pool.s1.RepairSelection.initialPriority(symbol))
      addProperty("binding_status", "BOUND")
      addProperty("verified_context_count", verified)
      addProperty("status", "INSUFFICIENT_EVIDENCE")
      addProperty("reason", reason)
      addProperty("p1_status", "INSUFFICIENT_EVIDENCE")
      addProperty("p2_status", "INSUFFICIENT_EVIDENCE")
      addProperty("p3_status", "DEFERRED")
      addProperty("generator_status", "NOT_IMPLEMENTED")
      addProperty("patch_generated", false)
      addProperty("applied", false)
      addProperty("eligible_for_application", false)
      add("preconditions", report("P1_PRELOAD_BEFORE_CRITICAL_REGION", symbol, checks))
      add("source_checks", JsonArray().apply {
        for ((index, check) in sourceChecks.withIndex()) add(JsonObject().apply {
          add("method_frame_id", layers[index].asJsonObject["method_frame_id"])
          addProperty("status", check.verdict.name)
          addProperty("evidence", check.evidence)
        })
      })
    }
  }

  /** Reviewed async refresh boundary only; unknown storage callers remain unknown, not P3 fallbacks. */
  fun checkQ13(finder: JsonObject, hit: JsonObject, layers: JsonArray, root: Path): Q13Check {
    val symbol = hit["symbol"].asString
    val checks = JsonArray()
    fun result(reason: String, source: String? = null, method: JsonObject? = null): Q13Check = Q13Check(JsonObject().apply {
      addProperty("status", if (source == null) "INSUFFICIENT_EVIDENCE" else "PRECONDITIONS_MET")
      addProperty("reason", reason)
      add("checks", checks)
    }, source, method)
    val located = layers.map { it.asJsonObject }.filter { it["status"]?.asString == "METHOD_LOCATED" }
    if (located.isEmpty()) return result("NO_VERIFIED_METHOD_CONTEXT")
    for (layer in located) {
      val check = sourceCheck(layer, root)
      checks.add(JsonObject().apply {
        add("method_frame_id", layer["method_frame_id"])
        addProperty("status", check.verdict.name)
        addProperty("evidence", check.evidence)
      })
      if (check.verdict != Verdict.PASS) return result("SOURCE_CONTEXT_CHANGED")
    }
    if (symbol == P1StorageRelocation.FS + "getName" || symbol == P1StorageRelocation.FS + "getNameByNameId") {
      return result("NO_REVIEWED_NAME_PRELOAD_BOUNDARY_OR_VERSIONED_SNAPSHOT")
    }
    if (symbol.endsWith("WorkspaceFileIndexDataImpl.getFileInfo")) {
      return result("NO_REVIEWED_INDEX_SNAPSHOT_INVALIDATION_AND_SYNCHRONOUS_CONSUMER_SPLIT")
    }
    val drives = symbol == "sun.nio.fs.WindowsNativeDispatcher.GetLogicalDrives"
    if (!drives && symbol !in setOf(P1StorageRelocation.FS + "readAttribute", P1StorageRelocation.FS + "readSymlinkTarget")) {
      return result("UNSUPPORTED_Q13_TRIGGER")
    }
    val thread = finder.getAsJsonArray("threads").map { it.asJsonObject }
      .firstOrNull { it["thread_id"] == hit["thread_id"] } ?: return result("TRIGGER_THREAD_MISSING")
    val frames = thread.getAsJsonArray("frames").map { it.asJsonObject }
    val start = frames.indexOfFirst { it["frame_id"] == hit["frame_id"] }
    if (start < 0) return result("TRIGGER_FRAME_MISSING")
    val path = JsonArray()
    val symbols = mutableListOf<String>()
    for (i in start until frames.size) {
      val frame = frames[i]
      val name = frame["symbol"].takeUnless { it == null || it.isJsonNull }?.asString.orEmpty()
      if (frame["elided"].asBoolean || name.isBlank() ||
          (i > start && frame["index"].asInt != frames[i - 1]["index"].asInt + 1)) break
      symbols.add(name)
      path.add(frame.deepCopy())
      if (name.startsWith("com.intellij.openapi.vfs.newvfs.RefreshSessionImpl.fireEventsInWriteAction")) break
    }
    val expected = (if (drives) listOf(
      "com.intellij.platform.core.nio.fs.MultiRoutingFileSystem.getRootDirectories",
      "com.intellij.openapi.vfs.impl.local.LocalFileSystemBase.extractRootPath")
    else listOf(P1StorageRelocation.FS + "readSymlinkTarget",
      "com.intellij.openapi.vfs.newvfs.persistent.PersistentFSImpl.resolveSymLink",
      "com.intellij.openapi.vfs.newvfs.impl.VirtualFileSystemEntry.getCanonicalPath")) + listOf(
      "com.intellij.openapi.vfs.newvfs.impl.VirtualFileSystemEntry.getCanonicalFile",
      "com.intellij.openapi.vfs.newvfs.impl.VirtualFileSystemEntry.isRecursiveOrCircularSymlink",
      "com.intellij.openapi.vfs.newvfs.impl.VirtualDirectoryImpl.markDirtyRecursivelyInternal",
      "com.intellij.openapi.vfs.newvfs.impl.VirtualDirectoryImpl.markDirtyRecursively")
    var cursor = 0
    for (name in symbols) if (cursor < expected.size && name == expected[cursor]) cursor++
    if (cursor != expected.size || symbols.none {
        it.startsWith(P1StorageRelocation.REFRESH_OWNER + ".lambda\$refreshWithoutFileWatcher\$")
      } || symbols.lastOrNull()?.startsWith("com.intellij.openapi.vfs.newvfs.RefreshSessionImpl.fireEventsInWriteAction") != true) {
      return result("NO_COMPLETE_ASYNC_REFRESH_PREPARATION_PATH")
    }
    checks.add(JsonObject().apply { addProperty("id", "SAME_THREAD_CONTIGUOUS_REFRESH_PATH"); add("frames", path) })
    return try {
      val base = root.toRealPath()
      val reviewedFiles = mapOf(
        P1StorageRelocation.REFRESH_PATH to "767aa23b30340e50480de3d0ded96f71c3b893e3d9e9ba661d9d85589f67fe9c",
        "platform/platform-impl/src/com/intellij/openapi/vfs/newvfs/impl/VirtualDirectoryImpl.java" to
          "6437d23d1f2a854466d53d8a3dbf9b695e4fedac35818a06fc12b6205cd2383f",
        "platform/platform-impl/src/com/intellij/openapi/vfs/newvfs/impl/VirtualFileSystemEntry.java" to
          "96f25c938d3e8cd8814f852d8c2d515ad6dc32b4e1e59f582822130ae3d8f08e",
        "platform/platform-impl/src/com/intellij/openapi/vfs/newvfs/persistent/FSRecordsImpl.java" to
          "12a9285bb3c63f97cf2b59f2cd8c4ba8748e2e8d59641264edd8b6c2a4ac5420",
        "platform/platform-impl/src/com/intellij/openapi/vfs/newvfs/persistent/PersistentFSImpl.java" to
          "f7c6f8dbdfc14910dbc22a6253d0d011fb201427457e31e6d3b2b01d38511108"
      )
      var source = ""
      for ((relative, expectedSha) in reviewedFiles) {
        val file = base.resolve(relative).normalize()
        require(file.startsWith(base) && file.toRealPath().startsWith(base)) { "PATH_OUTSIDE_ROOT" }
        val bytes = Files.readAllBytes(file)
        require(sha(bytes) == expectedSha) { "UNREVIEWED_Q13_SOURCE_VERSION: $relative" }
        checks.add(JsonObject().apply {
          addProperty("path", relative); addProperty("sha256", expectedSha); addProperty("status", "PASS")
        })
        if (relative == P1StorageRelocation.REFRESH_PATH) source = bytes.toString(Charsets.UTF_8).replace("\r\n", "\n")
      }
      val method = JsonObject().apply {
        addProperty("path", P1StorageRelocation.REFRESH_PATH)
        addProperty("owner", P1StorageRelocation.REFRESH_OWNER)
        addProperty("method", "refreshWithoutFileWatcher")
        addProperty("sha256", reviewedFiles.getValue(P1StorageRelocation.REFRESH_PATH))
        addProperty("start_line", 304); addProperty("end_line", 318)
        addProperty("source_text", source.lines().subList(303, 318).joinToString("\n"))
        addProperty("location_basis", "REVIEWED_SUPPLEMENT_OUTSIDE_FIVE_LAYER_EXTRACTOR")
      }
      val text = method["source_text"].asString
      require(text.startsWith("  public void refreshWithoutFileWatcher(boolean asynchronous) {") && text.endsWith("\n  }")) {
        "REFRESH_METHOD_RANGE_CHANGED"
      }
      require(source.indexOf(text) == source.lastIndexOf(text)) { "AMBIGUOUS_REFRESH_METHOD" }
      result("SOURCE_BOUND_ASYNC_ONLY_P2_CANDIDATE_P1_REMAINS_UNKNOWN", source, method)
    }
    catch (e: Exception) {
      result(e.message ?: e.javaClass.simpleName)
    }
  }

  /** Recheck the file: saved extractor output is not proof about today's source. */
  internal fun sourceCheck(context: JsonObject, root: Path): Check {
    if (context["status"]?.asString != "METHOD_LOCATED") {
      return Check("SOURCE", Verdict.UNKNOWN, "NO_VERIFIED_METHOD_CONTEXT")
    }
    return try {
      val method = context.getAsJsonObject("method")
      require(method["verification"]?.asString == "HASH_MATCHED") { "SOURCE_NOT_VERIFIED" }
      verifiedSource(method, root)
      Check("SOURCE", Verdict.PASS, "HASH_AND_METHOD_RANGE_MATCH")
    }
    catch (e: Exception) {
      Check("SOURCE", Verdict.UNKNOWN, e.message ?: e.javaClass.simpleName)
    }
  }

  internal fun knownImagePreparation(context: JsonObject, source: Check): Boolean =
    source.verdict == Verdict.PASS && supportsMethodShape(context.getAsJsonObject("method")) &&
      context.getAsJsonArray("stack_path").any { it.asJsonObject["symbol"].asString == "javax.imageio.ImageIO.read" }

  internal fun shapeCheck(known: Boolean): Check = Check("OPERATION_CONTEXT", if (known) Verdict.PASS else Verdict.UNKNOWN,
    if (known) "VERIFIED_APP_ICON_IMAGE_PREPARATION_PATH" else "NO_SUPPORTED_SOURCE_TEMPLATE_ON_OPERATION_PATH")
}
