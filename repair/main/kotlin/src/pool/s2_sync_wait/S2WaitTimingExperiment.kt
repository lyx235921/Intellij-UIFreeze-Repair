package org.jetbrains.research.lockrepair.pool.s2

import com.google.gson.GsonBuilder
import java.nio.file.Files
import java.nio.file.Path
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException

/** Controlled JDK wait experiment. Does not execute ProgressIndicatorUtils or reproduce an IDE incident. */
object S2WaitTimingExperiment {
  @JvmStatic
  fun main(args: Array<String>) {
    val output = Path.of(args.single())
    require(!Files.exists(output))
    val executor = Executors.newSingleThreadExecutor()
    val rows = ArrayList<Map<String, Any>>()
    try {
      for (budget in listOf(20L, 50L, 100L, 200L)) {
        repeat(20) {
          val started = CountDownLatch(1)
          val release = CountDownLatch(1)
          val future = executor.submit<Int> {
            started.countDown()
            check(release.await(5, TimeUnit.SECONDS))
            7
          }
          check(started.await(5, TimeUnit.SECONDS))
          val start = System.nanoTime()
          var timedOut = false
          try {
            future.get(budget, TimeUnit.MILLISECONDS)
          }
          catch (_: TimeoutException) {
            timedOut = true
          }
          finally {
            val elapsed = (System.nanoTime() - start) / 1e6
            release.countDown()
            check(timedOut)
            check(future.get(5, TimeUnit.SECONDS) == 7)
            rows.add(mapOf("budget_ms" to budget, "elapsed_ms" to elapsed, "timed_out" to timedOut))
          }
        }
      }
      // A timed inner poll can expire repeatedly without imposing an overall deadline.
      val release = CountDownLatch(1)
      val future = executor.submit<Int> { check(release.await(5, TimeUnit.SECONDS)); 7 }
      val start = System.nanoTime()
      var expirations = 0
      repeat(6) {
        try {
          future.get(20, TimeUnit.MILLISECONDS)
        }
        catch (_: TimeoutException) {
          expirations++
        }
      }
      val pollElapsed = (System.nanoTime() - start) / 1e6
      release.countDown()
      check(future.get(5, TimeUnit.SECONDS) == 7 && expirations == 6)
      Files.writeString(output, GsonBuilder().setPrettyPrinting().create().toJson(mapOf(
        "scope" to "CONTROLLED_JDK_FUTURE_NOT_IDE", "java_version" to System.getProperty("java.version"),
        "samples" to rows, "repeated_poll_expirations" to expirations, "repeated_poll_elapsed_ms" to pollElapsed
      )))
    }
    finally {
      executor.shutdownNow()
      check(executor.awaitTermination(5, TimeUnit.SECONDS))
    }
  }
}
