package org.jetbrains.research.lockrepair.pool.s1

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import java.nio.file.Path

/** Candidate generator for the verified AppIcon shape. Not a general Java async transformer. */
object P2ExpensiveWorkRelocation {
  /** Recognition is independent of patch support. Preserve failed layers and their original diagnostics. */
  fun recognize(context: JsonObject): JsonArray {
    require(context["schema_version"].asString == "repair-method-context/1")
    val groups = linkedMapOf<List<String>, JsonObject>()
    for (element in context.getAsJsonArray("results")) {
      val layer = element.asJsonObject
      val symbol = layer["trigger_symbol"].asString
      if (!RepairSelection.isP2Preferred(symbol)) continue
      val key = listOf(layer["thread_id"].asString, layer["trigger_frame_id"].asString, symbol)
      val operation = groups.getOrPut(key) {
        JsonObject().apply {
          add("thread_id", layer["thread_id"])
          add("trigger_frame_id", layer["trigger_frame_id"])
          add("trigger_symbol", layer["trigger_symbol"])
          add("problem_category", layer["problem_category"])
          addProperty("binding", "P2_FIRST")
          addProperty("repairability", "NOT_ESTABLISHED_BY_RECOGNITION")
          add("method_contexts", JsonArray())
        }
      }
      operation.getAsJsonArray("method_contexts").add(layer.deepCopy())
    }
    return JsonArray().apply {
      for (operation in groups.values) {
        val layers = operation.getAsJsonArray("method_contexts")
        val located = layers.count { it.asJsonObject["status"].asString == "METHOD_LOCATED" }
        operation.addProperty("located_method_count", located)
        operation.addProperty("context_status", when {
          located == 0 -> "UNRESOLVED"
          located == layers.size() -> "METHOD_LOCATED"
          else -> "PARTIAL"
        })
        add(operation)
      }
    }
  }

  fun propose(context: JsonObject, root: Path): JsonObject {
    val recognized = recognize(context)
    val proposals = JsonArray()
    val seen = HashSet<String>()
    for (item in context.getAsJsonArray("results")) {
      val result = item.asJsonObject
      if (result["status"].asString != "METHOD_LOCATED") continue
      val method = result.getAsJsonObject("method")
      val key = "${method["path"].asString}:${method["start_line"].asInt}"
      if (!seen.add(key)) continue
      val proposal = JsonObject().apply {
        add("method_frame_id", result["method_frame_id"])
        add("path", method["path"])
        addProperty("status", "UNSUPPORTED")
      }
      proposals.add(proposal)
      val checked = RelocationPreconditions.checkP2(method, root)
      if (checked.sourceText == null) {
        proposal.addProperty("status", checked.status)
        proposal.addProperty("reason", checked.reason)
        continue
      }
      try {
        val text = checked.sourceText
        val before = method["source_text"].asString
        val start = method["start_line"].asInt
        val end = method["end_line"].asInt
        val replacement = replacement.trimIndent().lines().joinToString("\n") { if (it.isEmpty()) "" else "    $it" }
        proposal.addProperty("status", "CANDIDATE_PATCH")
        proposal.addProperty("expected_sha256", method["sha256"].asString)
        proposal.addProperty("start_line", start)
        proposal.addProperty("end_line", end)
        proposal.addProperty("before", before)
        proposal.addProperty("replacement", replacement)
        // A reviewable method-range patch; file remains untouched.
        val lines = text.lines()
        val contextStart = maxOf(0, start - 4)
        val contextEnd = minOf(lines.size, end + 3)
        val head = lines.subList(contextStart, start - 1)
        val tail = lines.subList(end, contextEnd)
        val patchLines = head.map { " $it" } + before.lines().map { "-$it" } +
          replacement.lines().map { "+$it" } + tail.map { " $it" }
        val diff = "--- a/${method["path"].asString}\n+++ b/${method["path"].asString}\n" +
          "@@ -${contextStart + 1},${contextEnd - contextStart} " +
          "+${contextStart + 1},${head.size + replacement.lines().size + tail.size} @@\n" +
          patchLines.joinToString("\n") + "\n"
        proposal.addProperty("patch", diff)
      }
      catch (error: Exception) {
        proposal.addProperty("status", "UNAVAILABLE")
        proposal.addProperty("reason", error.message ?: error.javaClass.simpleName)
      }
    }
    return JsonObject().apply {
      addProperty("schema_version", "repair-s1-p2-proposal/1")
      addProperty("strategy", "PRECOMPUTE_OUTSIDE_EDT")
      addProperty("status", if (proposals.any { it.asJsonObject["status"].asString == "CANDIDATE_PATCH" })
        "CANDIDATE_PATCH" else "NO_SUPPORTED_METHOD")
      addProperty("applied", false)
      addProperty("validation", "REQUIRES_TARGET_IDE_VALIDATION")
      addProperty("recognized_operation_count", recognized.size())
      add("recognized_operations", recognized)
      add("proposals", proposals)
    }
  }

  private val replacement = """
    // Confined to EDT. Weak keys avoid retaining closed frames.
    private final java.util.Map<JFrame, Object> myP2BadgeRequests = new java.util.WeakHashMap<>();
    private java.util.concurrent.CompletableFuture<byte[]> myP2OkIconBytes;

    @Override
    public void _setOkBadge(@Nullable JFrame frame, boolean visible) {
      EDT.assertIsEdt();
      if (!isValid(frame)) return;
      Object request = new Object();
      myP2BadgeRequests.put(frame, request);
      if (!visible || myOkIcon != null) {
        try {
          Win7TaskBar.setOverlayIcon(frame, visible ? myOkIcon : null, false);
        }
        catch (Throwable e) {
          LOG.error(e);
        }
        return;
      }

      if (myP2OkIconBytes == null) {
        myP2OkIconBytes = java.util.concurrent.CompletableFuture.supplyAsync(() -> {
          try (java.io.InputStream input = Objects.requireNonNull(AppIcon.class.getResourceAsStream("/mac/appIconOk512.png"))) {
            BufferedImage image = ImageIO.read(input);
            if (image == null) throw new java.io.IOException("Unsupported badge image");
            return writeTransparentIco(image);
          }
          catch (java.io.IOException e) {
            throw new java.util.concurrent.CompletionException(e);
          }
        });
      }
      java.util.concurrent.CompletableFuture<byte[]> pending = myP2OkIconBytes;
      java.lang.ref.WeakReference<JFrame> frameRef = new java.lang.ref.WeakReference<>(frame);
      pending.whenComplete((bytes, error) -> javax.swing.SwingUtilities.invokeLater(() -> {
        // Reset failed preparation even when the original request is already stale.
        if (error != null) {
          if (myP2OkIconBytes == pending) {
            myP2OkIconBytes = null;
            LOG.error(error);
          }
          return;
        }
        JFrame target = frameRef.get();
        if (target == null || !isValid(target) || !target.isDisplayable() || myP2BadgeRequests.get(target) != request) return;
        try {
          if (myOkIcon == null) myOkIcon = Win7TaskBar.createIcon(bytes);
          Win7TaskBar.setOverlayIcon(target, myOkIcon, false);
        }
        catch (Throwable e) {
          LOG.error(e);
        }
      }));
    }
  """
}
