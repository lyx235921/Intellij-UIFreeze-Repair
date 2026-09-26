"""Finder steps 1-5: workbook intake, thread selection, source locations and call-site checks."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from real_stack_input import read_records
from source_locator import SourceLocator


SCHEMA_VERSION = "finder-source-locations/1"


def locate_record(record, locator):
  threads, edges, entries = [], [], []
  for ti, thread in enumerate(record["threads"]):
    frames = []
    for fi, frame in enumerate(thread["frames"]):
      previous = frames[-1] if frames and frame["index"] == frames[-1]["index"] + 1 else None
      item = {**frame, "frame_id": f"t{ti}:f{fi}", "source": locator.locate(frame, previous)}
      frames.append(item)
      if frame["label"] or fi == 0:
        entries.append({"frame_id": item["frame_id"], "reason": frame["label"] or "THREAD_TOP"})
      if previous:
        edges.append(locator.call_edge(item, previous))
    threads.append({**thread, "thread_id": f"t{ti}", "frames": frames})
  statuses = Counter(f["source"]["status"] for t in threads for f in t["frames"])
  # Call expressions live on edges; avoid copying every method's calls into every frame.
  for thread in threads:
    for frame in thread["frames"]:
      source = frame["source"]
      source["candidates"] = [{k: v for k, v in method.items() if k != "calls"} for method in source["candidates"]]
      if source["selected"]:
        source["selected"] = {k: v for k, v in source["selected"].items() if k != "calls"}
  return {"schema_version": SCHEMA_VERSION, "record_id": record["record_id"],
          "input": {"sheet": record["sheet"], "row": record["row"], "occurrences": record["occurrences"],
                    "stack_sha256": hashlib.sha256(record["raw_stack"].encode()).hexdigest(),
                    "raw_stack": record["raw_stack"]},
          "parse": {"status": record["status"], "diagnostics": record["diagnostics"],
                    "unparsed_lines": record["unparsed_lines"]},
          "threads": threads, "ui_thread_ids": [t["thread_id"] for t in threads if t["is_ui_thread"]],
          "cause_thread_ids": [t["thread_id"] for t in threads if t["role"] == "cause"],
          "entry_frames": entries, "call_edges": edges,
          "location_summary": dict(statuses), "repair_analysis": "NOT_PERFORMED"}


def main(argv=None):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--workbook", type=Path, required=True)
  parser.add_argument("--source-root", type=Path, required=True)
  parser.add_argument("--output", type=Path, required=True, help="New JSONL path; parent must exist")
  parser.add_argument("--row", type=int, action="append", help="Excel row to select; repeatable; default: all")
  args = parser.parse_args(argv)
  if args.output.exists():
    parser.error("Output already exists")
  locator = SourceLocator(args.source_root)
  wanted = set(args.row or [])
  found, frame_counts, edge_counts = set(), Counter(), Counter()
  workbook_hash = hashlib.sha256(args.workbook.read_bytes()).hexdigest()
  with args.output.open("x", encoding="utf-8") as stream:
    for record in read_records(args.workbook):
      if wanted and record["row"] not in wanted:
        continue
      result = locate_record(record, locator)
      result["source_root"] = str(locator.root)
      result["workbook_sha256"] = workbook_hash
      result["index_diagnostics"] = locator.index_errors
      stream.write(json.dumps(result, ensure_ascii=False) + "\n")
      found.add(record["row"])
      frame_counts.update(result["location_summary"])
      edge_counts.update(e["status"] for e in result["call_edges"])
  if wanted - found:
    parser.error(f"Requested rows absent; output contains only available rows: {sorted(wanted - found)}")
  print(json.dumps({"records": len(found), "frames": dict(frame_counts), "edges": dict(edge_counts),
                    "source_files_read": len(locator.cache), "index_errors": locator.index_errors}), file=sys.stderr)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
