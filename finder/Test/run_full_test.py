"""Run find_sources on every workbook row, verify output and count thread states/statuses."""

import argparse
from collections import Counter
from contextlib import redirect_stderr
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys
from time import perf_counter

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(TEST_DIR.parent / "main"))
import find_sources
from real_stack_input import read_records
from verify_real_output import verify


def summarize(records):
  """Count each thread once, and each record once per distinct state in each scope."""
  groups = {scope: {} for scope in ("all_threads", "ui_threads", "cause_threads")}
  parse, frames, edges = Counter(), Counter(), Counter()
  ids, occurrences = set(), 0
  for record in records:
    if record["record_id"] in ids:
      raise ValueError(f"Duplicate record: {record['record_id']}")
    ids.add(record["record_id"])
    weight = record["input"]["occurrences"]
    if isinstance(weight, bool) or not isinstance(weight, int) or weight < 0:
      raise ValueError(f"Invalid occurrences in {record['record_id']}: {weight}")
    occurrences += weight
    parse[record["parse"]["status"]] += 1
    for thread in record["threads"]:
      frames.update(frame["source"]["status"] for frame in thread["frames"])
    edges.update(edge["status"] for edge in record["call_edges"])
    scopes = {"all_threads": record["threads"],
              "ui_threads": [t for t in record["threads"] if t["thread_id"] in record["ui_thread_ids"]],
              "cause_threads": [t for t in record["threads"] if t["thread_id"] in record["cause_thread_ids"]]}
    for scope, threads in scopes.items():
      seen = set()
      for thread in threads:
        state = thread["state"]
        counts = groups[scope].setdefault(state, {"thread_entries": 0, "records": 0,
                                                 "weighted_thread_entries": 0, "weighted_records": 0})
        counts["thread_entries"] += 1
        counts["weighted_thread_entries"] += weight
        if state not in seen:
          counts["records"] += 1
          counts["weighted_records"] += weight
          seen.add(state)
  return {"records": len(ids), "occurrences": occurrences,
          "thread_states": {scope: dict(sorted(values.items())) for scope, values in groups.items()},
          "parse_statuses": dict(sorted(parse.items())), "source_statuses": dict(sorted(frames.items())),
          "call_edge_statuses": dict(sorted(edges.items()))}


def main(argv=None):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--workbook", type=Path, required=True)
  parser.add_argument("--source-root", type=Path, required=True)
  parser.add_argument("--output-dir", type=Path, required=True, help="New directory for JSONL, log and report")
  args = parser.parse_args(argv)
  if not __debug__:
    parser.error("Do not use -O: output verification requires assertions")
  args.output_dir.mkdir(parents=True, exist_ok=False)
  output = args.output_dir / "sources.jsonl"
  report = {"status": "RUNNING", "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "command": sys.orig_argv, "workbook": str(args.workbook.resolve()),
            "source_root": str(args.source_root.resolve()), "output": str(output.resolve()),
            "versions": {p: version(p) for p in ("openpyxl", "tree-sitter", "tree-sitter-java")}}
  started = perf_counter()
  try:
    report["workbook_sha256"] = hashlib.sha256(args.workbook.read_bytes()).hexdigest()
    files = [*sorted((TEST_DIR.parent / "main").glob("*.py")), Path(__file__).resolve(), TEST_DIR / "verify_real_output.py"]
    report["code_sha256"] = {str(p.relative_to(TEST_DIR.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with (args.output_dir / "finder.log").open("x", encoding="utf-8") as log, redirect_stderr(log):
      code = find_sources.main(["--workbook", str(args.workbook), "--source-root", str(args.source_root),
                                "--output", str(output)])
    report["finder_seconds"] = round(perf_counter() - started, 3)
    if code != 0:
      raise RuntimeError(f"find_sources returned {code}")
    report["verification"] = verify(output)
    expected = {r["record_id"]: (r["occurrences"], hashlib.sha256(r["raw_stack"].encode()).hexdigest())
                for r in read_records(args.workbook)}

    def checked_records():
      with output.open(encoding="utf-8") as stream:
        for line in stream:
          record = json.loads(line)
          actual = (record["input"]["occurrences"], record["input"]["stack_sha256"])
          if expected.pop(record["record_id"], None) != actual:
            raise ValueError("Output/input coverage or content mismatch")
          if record["index_diagnostics"]:
            raise ValueError("Incomplete source index")
          yield record

    report["statistics"] = summarize(checked_records())
    if expected:
      raise ValueError(f"Missing {len(expected)} workbook rows")
    if hashlib.sha256(args.workbook.read_bytes()).hexdigest() != report["workbook_sha256"]:
      raise ValueError("Workbook changed during run")
    report["output_bytes"] = output.stat().st_size
    report["status"] = "PASSED"
  except BaseException as error:
    report["status"] = "FAILED"
    report["error"] = f"{type(error).__name__}: {error}"
    raise
  finally:
    report["total_seconds"] = round(perf_counter() - started, 3)
    (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  print(json.dumps(report["statistics"], ensure_ascii=False, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
