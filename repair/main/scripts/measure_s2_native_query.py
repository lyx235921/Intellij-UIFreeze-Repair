"""Measure the Windows native leg of fetchCaseSensitivity, NOT the complete IDE path."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time


def main():
  output = Path(sys.argv[1]).resolve()
  output.mkdir(parents=True, exist_ok=False)
  kernel = ctypes.WinDLL("kernel32", use_last_error=True)
  native = ctypes.WinDLL("ntdll")
  kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
  kernel.CreateFileW.restype = wintypes.HANDLE
  kernel.CloseHandle.argtypes = [wintypes.HANDLE]
  kernel.CloseHandle.restype = wintypes.BOOL
  class IoStatus(ctypes.Structure):
    _fields_ = [("status", ctypes.c_void_p), ("information", ctypes.c_size_t)]
  native.NtQueryInformationFile.argtypes = [wintypes.HANDLE, ctypes.POINTER(IoStatus), ctypes.c_void_p,
                                           wintypes.ULONG, ctypes.c_int]
  native.NtQueryInformationFile.restype = wintypes.LONG

  def query(path):
    start = time.perf_counter_ns()
    handle = kernel.CreateFileW("\\\\?\\" + str(path), 0, 7, None, 3, 0x02000000, None)
    if handle == ctypes.c_void_p(-1).value:
      raise ctypes.WinError(ctypes.get_last_error())
    try:
      flags = ctypes.c_ulong(0xffffffff)
      status = native.NtQueryInformationFile(handle, ctypes.byref(IoStatus()), ctypes.byref(flags),
                                             ctypes.sizeof(flags), 71)
      if status != 0:
        raise RuntimeError(f"NtQueryInformationFile status {status:#x}")
      assert flags.value in (0, 1), flags.value
    finally:
      assert kernel.CloseHandle(handle)
    return (time.perf_counter_ns() - start) / 1e6, flags.value

  rows = []
  # First query includes cold Python call-path overhead, not a flushed OS disk cache.
  for batch in range(3):
    for i in range(3000):
      elapsed, flags = query(output)
      rows.append(dict(group="repeated_local_directory", batch=batch, index=i, ms=elapsed, flags=flags))
    for i in range(100):
      path = output / f"probe-{batch}-{i}"
      path.mkdir()
      elapsed, flags = query(path)
      rows.append(dict(group="newly_created_directory_not_cold_cache", batch=batch, index=i, ms=elapsed, flags=flags))
  summary = {}
  for group in sorted({r["group"] for r in rows}):
    values = sorted(r["ms"] for r in rows if r["group"] == group)
    summary[group] = dict(n=len(values), p50_ms=values[math.ceil(len(values)*.5)-1],
                         p95_ms=values[math.ceil(len(values)*.95)-1], p99_ms=values[math.ceil(len(values)*.99)-1],
                         max_ms=max(values), exceeded={str(t): sum(v > t for v in values) for t in [20, 50, 100, 200]})
  source = Path(__file__).resolve().parents[5] / "platform/util/src/com/intellij/openapi/util/io/FileSystemUtil.java"
  result = dict(scope="NATIVE_WINDOWS_LEG_ONLY_PYTHON_FFI_NOT_IDE_OR_JNA", platform=platform.platform(),
                python=sys.version, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                first_call_ms=rows[0]["ms"], summary=summary, samples=rows)
  (output / "native.json").write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
  print(json.dumps(summary, indent=2))


if __name__ == "__main__":
  main()
