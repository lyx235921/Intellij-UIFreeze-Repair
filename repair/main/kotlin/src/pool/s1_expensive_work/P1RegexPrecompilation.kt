package org.jetbrains.research.lockrepair.pool.s1

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import java.nio.file.Path

/** Precompile registered filename regexes before publishing them to the synchronous lookup path. */
object P1RegexPrecompilation {
  fun propose(context: JsonObject, root: Path): JsonObject {
    val result = JsonObject().apply {
      addProperty("schema_version", "repair-s1-regex-proposal/1")
      addProperty("strategy", "P1_PRELOAD_BEFORE_CRITICAL_REGION")
      addProperty("status", "NO_SUPPORTED_METHOD")
      addProperty("applied", false)
      addProperty("eligible_for_application", false)
      addProperty("source_basis", "PINNED_UPSTREAM_REFERENCE_RUNTIME_VERSION_UNCONFIRMED")
      addProperty("upstream_commit", "8037f7bfccd21bd9c34e6e43b51700d743b52672")
    }
    val layers = context.getAsJsonArray("results").map { it.asJsonObject }
      .filter { it["trigger_symbol"]?.asString == "java.util.regex.Pattern.compile" &&
                it["status"]?.asString == "METHOD_LOCATED" }
    for (layer in layers) {
      val method = layer.getAsJsonObject("method")
      val checked = RelocationPreconditions.checkRegexPrecompilation(method, root)
      if (checked.status == "UNSUPPORTED") continue
      result.add("method_context", layer.deepCopy())
      if (checked.sourceText == null) {
        result.addProperty("status", checked.status)
        result.addProperty("reason", checked.reason)
        return result
      }
      val before = checked.sourceText.replace("\r\n", "\n")
      var after = before
      fun edit(old: String, new: String) {
        require(after.indexOf(old) >= 0 && after.indexOf(old) == after.lastIndexOf(old)) { "REGEX_TEMPLATE_ANCHOR_MISMATCH" }
        after = after.replace(old, new)
      }
      try {
        val declaration = "    private static final Map<String, LSPExtensionManager> extToExtManager = new ConcurrentHashMap<>();"
        edit(declaration, declaration + "\n\n" + support)
        edit("virtualFile.getName().matches(keyMap.getLeft())", "matchesPreparedRegex(virtualFile.getName(), keyMap.getLeft())")
        // Keep the two editor-open fallbacks consistent with the same registration and matching policy.
        require(after.split("fileName.matches(keyPair.getLeft())").size == 3) { "REGEX_SIBLING_CALLS_CHANGED" }
        after = after.replace("fileName.matches(keyPair.getLeft())", "matchesPreparedRegex(fileName, keyPair.getLeft())")
        val registration = "        for (String ext : extensions) {\n            Pair<String, String> keyPair = new ImmutablePair<>(ext, projectUri);"
        edit(registration, "        for (String ext : extensions) {\n            prepareRegex(ext);\n" +
                           "            Pair<String, String> keyPair = new ImmutablePair<>(ext, projectUri);")
        val oldLines = before.removeSuffix("\n").lines()
        val newLines = after.removeSuffix("\n").lines()
        val path = method["path"].asString
        result.addProperty("status", "CANDIDATE_PATCH")
        result.addProperty("readiness", "REQUIRES_INCIDENT_PLUGIN_SOURCE_AND_INTEGRATION_VALIDATION")
        result.addProperty("path", path)
        result.addProperty("expected_sha256", method["sha256"].asString)
        result.addProperty("replacement_source", after)
        result.addProperty("helper_source", support)
        result.addProperty("patch", buildString {
          append("--- a/$path\n+++ b/$path\n@@ -1,${oldLines.size} +1,${newLines.size} @@\n")
          oldLines.forEach { append('-').append(it).append('\n') }
          newLines.forEach { append('+').append(it).append('\n') }
        })
        result.add("limits", JsonArray().apply {
          add("Registration thread is not established; moves compile before lookup, not necessarily off EDT")
          add("Cache holds at most 256 distinct regex strings; over-capacity and invalid patterns retain original matching behavior")
          add("Pattern reuse eliminates repeated compilation for prepared rules, not expensive regex matching/backtracking")
          add("Public upstream source has matching structure but incident plugin version/fork is unknown")
        })
      }
      catch (e: Exception) {
        result.addProperty("status", "UNAVAILABLE")
        result.addProperty("reason", e.message ?: e.javaClass.simpleName)
      }
      return result
    }
    result.addProperty("reason", "NO_VERIFIED_PATTERN_COMPILE_CALLER")
    return result
  }

  private val support = """
    // Bounded by distinct regex strings; immutable Pattern objects are shared, Matchers are not.
    private static final Map<String, java.util.regex.Pattern> preparedRegexes = new ConcurrentHashMap<>();

    private static synchronized void prepareRegex(String regex) {
        if (preparedRegexes.containsKey(regex) || preparedRegexes.size() >= 256) return;
        try {
            preparedRegexes.put(regex, java.util.regex.Pattern.compile(regex));
        } catch (java.util.regex.PatternSyntaxException ignored) {
            // Keep registration accepting literal extensions that are not valid regexes.
            // A later regex lookup still throws from String.matches, just as before.
        }
    }

    private static boolean matchesPreparedRegex(String fileName, String regex) {
        java.util.regex.Pattern pattern = preparedRegexes.get(regex);
        return pattern == null ? fileName.matches(regex) : pattern.matcher(fileName).matches();
    }
  """.trimIndent().prependIndent("    ")
}
