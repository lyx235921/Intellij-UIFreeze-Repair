package org.jetbrains.research.lockrepair.pool.s1

import com.google.gson.JsonObject
import com.google.gson.JsonArray
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import org.jetbrains.research.lockrepair.pool.s1.RelocationPreconditions.Check
import org.jetbrains.research.lockrepair.pool.s1.RelocationPreconditions.Verdict

/** Source-bound experimental P1 patch; never applies changes to the target checkout. */
object P1PreloadBeforeCriticalRegion {
  private const val RELOAD_PATH = "platform/platform-impl/src/com/intellij/openapi/fileEditor/impl/FileDocumentManagerImpl.java"
  private const val RELOAD_SHA = "3b2be0365dfc949f19785f569543f8b6b02538ba5e87e0c623177505aed8f9dc"

  fun propose(finder: JsonObject, q1: JsonObject, root: Path): JsonObject {
    val result = JsonObject().apply {
      addProperty("schema_version", "repair-s1-p1-proposal/2")
      add("record_id", finder["record_id"])
      addProperty("strategy", "PRELOAD_BEFORE_CRITICAL_REGION")
      addProperty("status", "NOT_APPLICABLE")
      addProperty("patch_generated", false)
      addProperty("applied", false)
    }
    val hits = q1.getAsJsonObject("classification").getAsJsonArray("matched_frames").map { it.asJsonObject }
      .filter { it["symbol"].asString in setOf("sun.nio.fs.WindowsNativeDispatcher.GetFileAttributesEx",
                                              "sun.nio.fs.WindowsNativeDispatcher.GetFileAttributesEx0") }
    val paths = JsonArray()
    for (thread in finder.getAsJsonArray("threads").map { it.asJsonObject }) {
      val hit = hits.firstOrNull { it["thread_id"] == thread["thread_id"] } ?: continue
      val frames = thread.getAsJsonArray("frames").map { it.asJsonObject }
      val start = frames.indexOfFirst { it["frame_id"] == hit["frame_id"] }
      if (start < 0) continue
      val path = JsonArray()
      val symbols = mutableListOf<String>()
      for (i in start until frames.size) {
        val frame = frames[i]
        val symbol = frame["symbol"].takeUnless { it.isJsonNull }?.asString.orEmpty()
          .replace(Regex("^(?:[^/]+//|[^/]+/)(?=[A-Za-z_])"), "")
        if (frame["elided"].asBoolean || symbol.isBlank() ||
            (i > start && frame["index"].asInt != frames[i - 1]["index"].asInt + 1)) break
        path.add(frame.deepCopy())
        symbols.add(symbol)
        if (symbol == "com.intellij.openapi.fileEditor.impl.FileDocumentManagerImpl.reloadFromDisk") {
          val expected = listOf("java.nio.file.Files.size",
            "com.intellij.openapi.vfs.impl.local.LocalFileSystemBase.readIfNotTooLarge",
            "com.intellij.openapi.fileEditor.impl.LoadTextUtil.loadText",
            "com.intellij.openapi.fileEditor.impl.FileDocumentManagerImpl.setNewText", symbol)
          var cursor = 0
          for (s in symbols) if (cursor < expected.size && s == expected[cursor]) cursor++
          if (cursor == expected.size) paths.add(JsonObject().apply {
            add("thread_id", thread["thread_id"])
            add("frames", path)
          })
          break
        }
      }
    }
    if (paths.isEmpty) {
      result.addProperty("reason", "NO_COMPLETE_CLASSIFIED_RELOAD_PATH")
      return result
    }
    result.add("stack_evidence", paths)
    try {
      val base = root.toRealPath()
      val file = base.resolve(RELOAD_PATH).normalize()
      require(file.startsWith(base) && file.toRealPath().startsWith(base)) { "PATH_OUTSIDE_ROOT" }
      val bytes = Files.readAllBytes(file)
      val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
      require(hash == RELOAD_SHA) { "UNREVIEWED_RELOAD_SOURCE_VERSION" }
      val lines = bytes.toString(Charsets.UTF_8).lines()
      result.add("source_contexts", JsonArray().apply {
        for ((name, range) in listOf("prepareChange" to (692..743), "contentsChanged" to (760..797),
                                    "reloadFromDisk" to (799..850), "setNewText" to (852..869))) {
          add(JsonObject().apply {
            addProperty("method", name)
            addProperty("path", RELOAD_PATH)
            addProperty("sha256", hash)
            addProperty("start_line", range.first)
            addProperty("end_line", range.last)
            addProperty("source_text", lines.subList(range.first - 1, range.last).joinToString("\n"))
            addProperty("location_basis", "REVIEWED_SOURCE_TEMPLATE_OUTSIDE_FIVE_LAYER_EXTRACTOR")
          })
        }
      })
      val original = bytes.toString(Charsets.UTF_8).replace("\r\n", "\n")
      val replacement = buildReplacement(original)
      result.addProperty("status", "CANDIDATE_PATCH")
      result.addProperty("patch_generated", true)
      result.addProperty("readiness", "BLOCKED_BY_SYNC_REFRESH_CONTRACT")
      result.addProperty("validation_status", "CONTROLLED_CORRECTNESS_FAILURE")
      result.addProperty("eligible_for_application", false)
      result.addProperty("replacement_source", replacement)
      result.addProperty("patch", buildString {
        append("--- a/$RELOAD_PATH\n+++ b/$RELOAD_PATH\n")
        val oldLines = original.trimEnd('\n').split('\n')
        val newLines = replacement.trimEnd('\n').split('\n')
        append("@@ -1,${oldLines.size} +1,${newLines.size} @@\n")
        oldLines.forEach { append('-').append(it).append('\n') }
        newLines.forEach { append('+').append(it).append('\n') }
      })
      result.add("steps", JsonArray().apply {
        add("PREPARE: capture after the VFS event is applied, then prepare bytes on a pooled thread before the document write action; preserve the public synchronous reload API")
        add("CAPTURE: identify relevant external content-change event, document identity/stamp, file identity and incoming content version; exclude unsupported binary/large/nonlocal paths")
        add("READ: compare fileKey/size/mtime before and after a bounded direct disk read; at most three attempts; reject errors rather than commit empty text")
        add("HANDOFF: EDT-confined coalescing requests, at most 32 document slots and one read per slot, maximum 1 MiB payload each; no background VFS/document mutations")
        add("VALIDATE: at commit check event/file/document identity and versions; reject stale or conflicting payloads; define retry behavior without an EDT wait")
        add("COMMIT: supply prepared content to the reload path inside the existing command/external-change/write-action boundary; preserve BOM/charset detection and replaceText semantics")
        add("COMPLETE: keep reload listeners, unsaved-document cleanup and range-marker updates after successful application; preserve public synchronous behavior")
      })
      result.add("unresolved_conditions", JsonArray().apply {
        add("Controlled paired validation: contentsChanged returns before document replacement; violates synchronous refresh visibility expected by FileDocumentManagerImplTest.testExternalReplaceWithTheSameText. Do not apply this candidate")
        add("Optimistic fileKey/size/mtime checks cannot exclude same-metadata writes or changes after the final disk check; no atomic filesystem transaction is claimed")
        add("Only ordinary local text refresh events with known length/time and files <=1 MiB enter this route; other paths retain synchronous behavior")
        add("After three failed reads leave the document unchanged and log; a future event/manual reload is needed. No synchronous fallback for accepted requests")
        add("Decode still runs on EDT using the original byte decoder after BOM/charset reset; verify real text transformers and metadata side effects")
        add("Verify listener ordering, document edits, deletion, charset changes and project disposal in target IDE tests")
      })
    }
    catch (e: Exception) {
      result.addProperty("status", "UNAVAILABLE")
      result.addProperty("reason", e.message ?: e.javaClass.simpleName)
    }
    return result
  }

  private fun buildReplacement(original: String): String {
    fun String.edit(before: String, after: String): String {
      require(indexOf(before) >= 0 && indexOf(before) == lastIndexOf(before)) { "P1_TEMPLATE_ANCHOR_MISMATCH" }
      return replace(before, after)
    }
    val eventBranch = "      if (document.getModificationStamp() == event.getOldModificationStamp() || !isDocumentUnsaved(document)) {\n"
    var patched = original.edit(eventBranch + "        reloadFromDisk(document);",
                                eventBranch + "        if (!p1ScheduleReload(event, document)) reloadFromDisk(document);")
    patched = patched.edit("  @Override\n  public void reloadFromDisk(@NotNull Document document, @Nullable Project project) {", reloadSupport + "\n\n" + """
        @Override
        public void reloadFromDisk(@NotNull Document document, @Nullable Project project) {
          P1Slot slot = myP1Reloads.get(document);
          if (slot != null) slot.latest = null;
          p1ReloadFromDisk(document, project, null, null);
        }

        private void p1ReloadFromDisk(@NotNull Document document, @Nullable Project project,
                                      @Nullable P1Reload request, byte @Nullable [] prepared) {
    """.trimIndent().prependIndent("  "))
    patched = patched.edit("      if (!fireBeforeFileContentReload(file, document)) {", """
            if (request != null && !p1Current(request)) return null;
            if (!fireBeforeFileContentReload(file, document)) {
    """.trimIndent().prependIndent("      "))
    patched = patched.edit("      boolean[] isReloadable = {isReloadable(file, document, project)};", """
            if (request != null && !p1Current(request)) return null;
            boolean[] applied = {request == null};
            boolean[] isReloadable = {isReloadable(file, document, project)};
    """.trimIndent().prependIndent("      "))
    patched = patched.edit("              if (!isBinaryWithoutDecompiler(file)) {", """
                  if (request != null) {
                    if (p1Current(request)) applied[0] = p1SetPreparedText(request, prepared);
                  }
                  else if (!isBinaryWithoutDecompiler(file)) {
    """.trimIndent().prependIndent("              "))
    patched = patched.edit("      if (isReloadable[0]) {\n        ApplicationManager", "      if (!applied[0]) return null;\n      if (isReloadable[0]) {\n        ApplicationManager")
    return patched
  }

  private val reloadSupport = """
    // Experimental P1 route. All request state is confined to EDT.
    private static final int P1_MAX_BYTES = 1024 * 1024;
    private final java.util.Map<Document, P1Slot> myP1Reloads = new java.util.IdentityHashMap<>();

    private static final class P1Slot {
      P1Reload latest;
    }

    private record P1Reload(Document document, VirtualFile file, Project project, java.nio.file.Path path,
                            long documentStamp, long eventStamp, long length, long timestamp,
                            ModalityState modality, Object fileType, P1Slot slot) {}

    private boolean p1ScheduleReload(VFileContentChangeEvent event, Document document) {
      ThreadingAssertions.assertEventDispatchThread();
      VirtualFile file = event.getFile();
      P1Slot slot = myP1Reloads.get(document);
      // Even an ineligible event invalidates an older asynchronous request.
      if (slot != null) slot.latest = null;
      if (!event.isFromRefresh() || !file.isValid() || file.isDirectory() ||
          file.getFileSystem() != com.intellij.openapi.vfs.LocalFileSystem.getInstance() ||
          file.getFileType().isBinary() || isDocumentUnsaved(document) ||
          event.getNewLength() < 0 || event.getNewLength() > P1_MAX_BYTES ||
          FileUtilRt.isTooLarge(event.getNewLength()) || event.getNewTimestamp() < 0 ||
          file.getModificationStamp() != event.getModificationStamp() ||
          file.getLength() != event.getNewLength() || file.getTimeStamp() != event.getNewTimestamp() ||
          (slot == null && myP1Reloads.size() >= 32)) return false;
      java.nio.file.Path path;
      try {
        path = file.toNioPath();
      }
      catch (UnsupportedOperationException e) {
        return false;
      }
      boolean start = slot == null;
      if (start) {
        slot = new P1Slot();
        myP1Reloads.put(document, slot);
      }
      P1Reload request = new P1Reload(document, file, ProjectLocator.getInstance().guessProjectForFile(file), path,
        document.getModificationStamp(), event.getModificationStamp(), event.getNewLength(), event.getNewTimestamp(),
        ModalityState.current(), file.getFileType(), slot);
      slot.latest = request;
      if (start) p1Prepare(request, 1);
      return true;
    }

    private boolean p1Current(P1Reload r) {
      ThreadingAssertions.assertEventDispatchThread();
      return !ApplicationManager.getApplication().isDisposed() && (r.project() == null || !r.project().isDisposed()) &&
        myP1Reloads.get(r.document()) == r.slot() && r.slot().latest == r && r.file().isValid() &&
        getFile(r.document()) == r.file() && getCachedDocument(r.file()) == r.document() &&
        r.document().getModificationStamp() == r.documentStamp() && !isDocumentUnsaved(r.document()) &&
        r.file().getModificationStamp() == r.eventStamp() && r.file().getLength() == r.length() &&
        r.file().getTimeStamp() == r.timestamp() && r.file().getFileType() == r.fileType() &&
        r.file().toNioPath().equals(r.path());
    }

    private void p1Prepare(P1Reload r, int attempt) {
      ApplicationManager.getApplication().executeOnPooledThread(() -> {
        byte[] bytes = null;
        Exception failure = null;
        try {
          bytes = p1ReadSnapshot(r.path(), r.length(), r.timestamp());
        }
        catch (java.io.IOException | RuntimeException e) {
          failure = e;
        }
        catch (LinkageError e) {
          failure = new java.io.IOException("P1 native file identity unavailable", e);
        }
        byte[] prepared = bytes;
        Exception error = failure;
        ApplicationManager.getApplication().invokeLater(() -> {
          P1Reload latest = r.slot().latest;
          if (latest != r) {
            if (latest != null && p1Current(latest)) p1Prepare(latest, 1);
            else myP1Reloads.remove(r.document());
            return;
          }
          if (!p1Current(r)) {
            myP1Reloads.remove(r.document());
            return;
          }
          if (prepared == null && attempt < 3) {
            p1Prepare(r, attempt + 1);
            return;
          }
          try {
            if (prepared != null) p1ReloadFromDisk(r.document(), r.project(), r, prepared);
            else LOG.warn("P1 reload preparation exhausted; document kept unchanged", error);
          }
          finally {
            // A reload listener can synchronously publish a newer event.
            P1Reload next = r.slot().latest;
            if (next != null && next != r && p1Current(next)) p1Prepare(next, 1);
            else myP1Reloads.remove(r.document());
          }
        }, r.modality());
      });
    }

    private static byte[] p1ReadSnapshot(java.nio.file.Path path, long length, long timestamp) throws java.io.IOException {
      if (javax.swing.SwingUtilities.isEventDispatchThread()) throw new IllegalStateException("Disk read on EDT");
      java.nio.file.attribute.BasicFileAttributes before = java.nio.file.Files.readAttributes(
        path, java.nio.file.attribute.BasicFileAttributes.class, java.nio.file.LinkOption.NOFOLLOW_LINKS);
      if (!before.isRegularFile() || before.size() != length ||
          length < 0 || length > P1_MAX_BYTES || before.lastModifiedTime().toMillis() != timestamp) return null;
      Object identity = p1FileIdentity(path, before);
      byte[] bytes;
      try (java.io.InputStream input = java.nio.file.Files.newInputStream(path, java.nio.file.LinkOption.NOFOLLOW_LINKS)) {
        bytes = input.readNBytes(P1_MAX_BYTES + 1);
      }
      java.nio.file.attribute.BasicFileAttributes after = java.nio.file.Files.readAttributes(
        path, java.nio.file.attribute.BasicFileAttributes.class, java.nio.file.LinkOption.NOFOLLOW_LINKS);
      if (!after.isRegularFile() || !identity.equals(p1FileIdentity(path, after)) || before.size() != after.size() ||
          !before.lastModifiedTime().equals(after.lastModifiedTime()) || bytes.length != length) return null;
      return bytes;
    }

    private static Object p1FileIdentity(java.nio.file.Path path, java.nio.file.attribute.BasicFileAttributes attributes)
      throws java.io.IOException {
      if (attributes.fileKey() != null) return attributes.fileKey();
      // Windows JDK returns a null fileKey. Restrict native fallback to the host's default Windows filesystem.
      if (path.getFileSystem() != java.nio.file.FileSystems.getDefault() || !com.sun.jna.Platform.isWindows()) {
        throw new java.io.IOException("P1 filesystem does not expose a stable file identity");
      }
      com.sun.jna.platform.win32.Kernel32 kernel = com.sun.jna.platform.win32.Kernel32.INSTANCE;
      com.sun.jna.platform.win32.WinNT.HANDLE handle = kernel.CreateFile(path.toString(),
        com.sun.jna.platform.win32.WinNT.FILE_READ_ATTRIBUTES,
        com.sun.jna.platform.win32.WinNT.FILE_SHARE_READ | com.sun.jna.platform.win32.WinNT.FILE_SHARE_WRITE |
        com.sun.jna.platform.win32.WinNT.FILE_SHARE_DELETE, null,
        com.sun.jna.platform.win32.WinNT.OPEN_EXISTING, com.sun.jna.platform.win32.WinNT.FILE_FLAG_OPEN_REPARSE_POINT, null);
      if (com.sun.jna.platform.win32.WinBase.INVALID_HANDLE_VALUE.equals(handle)) {
        throw new java.io.IOException("P1 file identity open failed: " + kernel.GetLastError());
      }
      try (com.sun.jna.Memory info = new com.sun.jna.Memory(com.sun.jna.platform.win32.WinBase.FILE_ID_INFO.sizeOf())) {
        if (!kernel.GetFileInformationByHandleEx(handle, com.sun.jna.platform.win32.WinBase.FileIdInfo,
              info, new com.sun.jna.platform.win32.WinDef.DWORD(info.size()))) {
          throw new java.io.IOException("P1 file identity query failed: " + kernel.GetLastError());
        }
        // FILE_ID_INFO contains the volume serial number and 128-bit file ID.
        return java.util.HexFormat.of().formatHex(info.getByteArray(0, (int)info.size()));
      }
      finally {
        kernel.CloseHandle(handle);
      }
    }

    private boolean p1SetPreparedText(P1Reload r, byte[] bytes) {
      Document document = r.document();
      VirtualFile file = r.file();
      if (!p1Current(r) || !isReloadable(file, document, r.project())) return false;
      // Preserve the original reset -> byte decoder -> document replacement ordering.
      LoadTextUtil.clearCharsetAutoDetectionReason(file);
      file.setBOM(null);
      file.setCharset(null, null, false);
      boolean wasWritable = document.isWritable();
      document.setReadOnly(false);
      try {
        CharSequence text = LoadTextUtil.getTextByBinaryPresentation(bytes, file);
        // Listeners/transformers may have edited the document or delivered a newer event.
        if (!p1Current(r)) return false;
        ((DocumentEx)document).replaceText(text, r.eventStamp());
        setDocumentTooLarge(document, false);
        return true;
      }
      finally {
        document.setReadOnly(!wasWritable);
      }
    }
  """.trimIndent().prependIndent("  ")

  fun check(context: JsonObject, root: Path): JsonObject {
    val source = RelocationPreconditions.sourceCheck(context, root)
    val known = RelocationPreconditions.knownImagePreparation(context, source)
    val checks = listOf(
      source,
      RelocationPreconditions.shapeCheck(known),
      Check("INPUTS_AVAILABLE_EARLY", if (known) Verdict.PASS else Verdict.UNKNOWN,
        if (known) "FIXED_RESOURCE_PATH_IN_AppIcon.class.getResourceAsStream; IMAGE_INPUT_DOES_NOT_DEPEND_ON_FRAME_OR_VISIBLE"
        else "NEED_INPUT_DEFINITIONS_AND_EARLY_AVAILABILITY"),
      Check("PRELOAD_INSERTION_POINT", Verdict.UNKNOWN,
        "NEED_CONCRETE_EARLIER_ENTRY_OUTSIDE_UI_CRITICAL_PATH; MOVING_BEFORE_SYNCHRONIZED_ON_EDT_IS_NOT_ENOUGH"),
      Check("RESULT_VALID_UNTIL_USE", Verdict.UNKNOWN,
        "NEED_PRELOAD_TO_CONSUMER_LIFETIME_AND_PUBLICATION; EXISTING_FINAL_ICON_CACHE_DOES_NOT_PROVE_PRELOAD_SAFETY"),
      Check("THREAD_AND_LOCK_REQUIREMENTS", Verdict.UNKNOWN,
        "NEED_RELOCATION_UNIT_AND_DESTINATION; KEEP_UI_NATIVE_CONSUMER_AND_SHARED_STATE_REQUIREMENTS"),
      Check("SIDE_EFFECTS_AND_EXCEPTIONS", Verdict.UNKNOWN,
        if (known) "CURRENT_PREPARATION_IS_GUARDED_BY_VISIBLE_AND_CACHE_MISS_AND_CATCHES_THROWABLE; PRESERVE_CONDITIONAL_WORK_AND_RETRY"
        else "NEED_ORDERING_EXCEPTION_AND_RESOURCE_LIFETIME_EVIDENCE"),
      Check("NO_EDT_WAIT_FOR_PRELOAD", Verdict.UNKNOWN,
        "NEED_READY_RESULT_HANDOFF_OR_ASYNC_CONTINUATION_WITHOUT_GET_JOIN_OR_OTHER_EDT_WAIT")
    )
    return RelocationPreconditions.report("P1", "PRELOAD_DATA_BEFORE_CRITICAL_REGION", checks)
  }
}
