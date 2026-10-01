import java.nio.file.Files
import java.nio.file.Path
import java.net.URLClassLoader
import java.security.MessageDigest
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.locks.ReentrantLock
import java.util.function.IntPredicate
import javax.swing.SwingUtilities
import javax.tools.ToolProvider

// Controlled index/critical-section experiment, not an IntelliJ write-action replay.
fun main(args: Array<String>) {
  val repo = Path.of(args[0])
  val out = Files.createDirectory(Path.of(args[1]))
  val deps = repo.resolve("out/edt-freeze-finder/m1-m2-index-2026-09-17-1/runtime-classpath")
  val jars = Files.list(deps).use { it.filter { p -> p.toString().endsWith(".jar") }.sorted().toList() }
  val before = repo.resolve("out/edt-freeze-finder/indexed-bucket-v2-runs/row694-20260918-v2-1/before.java.raw")
  val after = repo.resolve("platform/platform-impl/src/com/intellij/openapi/vfs/newvfs/persistent/DefaultInMemoryInvertedNameIndex.java")
  val sources = listOf(before, after)
  val hashes = sources.map { p -> MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p)).joinToString("") { "%02x".format(it) } }
  check(hashes[0] == "5b8f9c8e423ffcb149be4f746c1bdeb725457578b07e94b110a7d024d1665355")
  Files.writeString(out.resolve("identity.txt"), "java=${System.getProperty("java.version")}\nbefore=${sources[0]} ${hashes[0]}\nafter=${sources[1]} ${hashes[1]}\n")
  val loaders = sources.mapIndexed { i, p ->
    val dir = Files.createDirectory(out.resolve(if (i == 0) "before" else "after"))
    val source = dir.resolve("DefaultInMemoryInvertedNameIndex.java")
    Files.copy(p, source)
    check(ToolProvider.getSystemJavaCompiler().run(null, null, null, "-proc:none", "-classpath",
      jars.joinToString(java.io.File.pathSeparator), "-d", dir.toString(), source.toString()) == 0)
    URLClassLoader((listOf(dir) + jars).map { it.toUri().toURL() }.toTypedArray(), ClassLoader.getPlatformClassLoader())
  }
  fun bucket(i: Int): Triple<Any, java.lang.reflect.Method, () -> List<Int>> {
    val loader = loaders[i]
    val type = loader.loadClass("com.intellij.openapi.vfs.newvfs.persistent.DefaultInMemoryInvertedNameIndex")
    val obj = type.getDeclaredConstructor().newInstance()
    val update = type.getMethod("updateFileName", Int::class.javaPrimitiveType, Int::class.javaPrimitiveType, Int::class.javaPrimitiveType)
    val keys = loader.loadClass("it.unimi.dsi.fastutil.ints.IntArraySet").getConstructor(IntArray::class.java).newInstance(intArrayOf(1))
    val visit = type.getMethod("forEachFileIds", loader.loadClass("it.unimi.dsi.fastutil.ints.IntCollection"), IntPredicate::class.java)
    return Triple(obj, update) {
      val values = ArrayList<Int>()
      visit.invoke(obj, keys, IntPredicate { values.add(it); true })
      values
    }
  }
  SwingUtilities.invokeAndWait {}
  try {
    // Validate exact survivor order at promotion/demotion boundaries and absent-id deletion.
    for (size in listOf(1, 2, 3, 128, 129, 1000)) for (variant in 0..1) {
      val (obj, update, values) = bucket(variant)
      val expected = (1..size).toMutableList()
      expected.forEach { update.invoke(obj, it, 0, 1) }
      update.invoke(obj, size + 1, 1, 0)
      check(values() == expected)
      for (id in (1..size).shuffled(java.util.Random(4938))) {
        update.invoke(obj, id, 1, 0); expected.remove(id)
        check(values() == expected) { "Incorrect deletion variant=$variant size=$size id=$id" }
      }
    }
    Files.writeString(out.resolve("correctness.txt"), "PASS: both variants, 6 sizes, seeded random deletion, every survivor/order checked, absent id checked\n")
    out.resolve("samples.csv").toFile().printWriter().use { log ->
      log.println("size,round,variant,critical_ms,edt_wait_ms,edt_queue_response_ms")
      for (size in listOf(128, 16000, 128000)) for (round in -1..4) {
        for (variant in if (round % 2 == 0) listOf(1, 0) else listOf(0, 1)) {
          val (obj, update, values) = bucket(variant)
          for (id in 1..size) update.invoke(obj, id, 0, 1)
          val lock = ReentrantLock()
          val ready = CountDownLatch(1)
          val finished = CountDownLatch(1)
          var critical = 0L
          var wait = 0L
          var response = 0L
          var failure: Throwable? = null
          val worker = Thread {
            lock.lock()
            try {
              SwingUtilities.invokeLater {
                val start = System.nanoTime()
                ready.countDown()
                lock.lock()
                try { wait = System.nanoTime() - start } finally { lock.unlock() }
              }
              check(ready.await(10, TimeUnit.SECONDS))
              val posted = System.nanoTime()
              SwingUtilities.invokeLater { response = System.nanoTime() - posted; finished.countDown() }
              val start = System.nanoTime()
              for (id in 1..size) update.invoke(obj, id, 1, 0)
              critical = System.nanoTime() - start
            } catch (t: Throwable) { failure = t } finally { lock.unlock() }
          }
          worker.start(); worker.join(30000)
          check(!worker.isAlive); failure?.let { throw it }
          check(finished.await(10, TimeUnit.SECONDS)); check(values().isEmpty())
          if (round >= 0) log.println("$size,$round,${if (variant == 0) "before" else "after"},${critical / 1e6},${wait / 1e6},${response / 1e6}")
          log.flush()
        }
      }
    }
  } finally { loaders.forEach { it.close() } }
}
