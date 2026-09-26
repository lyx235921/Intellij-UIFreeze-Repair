"""Check cross-references, counts and current-source hashes in a completed Finder JSONL run."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def verify(path):
  totals, statuses, edges = Counter(), Counter(), Counter()
  sources, ids = {}, set()
  with Path(path).open(encoding="utf-8") as stream:
    for line in stream:
      record = json.loads(line)
      assert record["schema_version"] == "finder-source-locations/1"
      assert record["repair_analysis"] == "NOT_PERFORMED"
      assert record["record_id"] not in ids
      ids.add(record["record_id"])
      assert hashlib.sha256(record["input"]["raw_stack"].encode()).hexdigest() == record["input"]["stack_sha256"]
      totals["records"] += 1
      totals["occurrences"] += record["input"]["occurrences"]
      threads = {t["thread_id"]: t for t in record["threads"]}
      assert len(threads) == len(record["threads"])
      assert set(record["ui_thread_ids"]) <= threads.keys()
      assert set(record["cause_thread_ids"]) <= threads.keys()
      frames = {f["frame_id"]: f for t in threads.values() for f in t["frames"]}
      assert len(frames) == sum(len(t["frames"]) for t in threads.values())
      for entry in record["entry_frames"]:
        assert entry["frame_id"] in frames
      record_statuses = Counter(f["source"]["status"] for f in frames.values())
      assert dict(record_statuses) == record["location_summary"]
      statuses.update(record_statuses)
      root = Path(record["source_root"]).resolve()

      def check_source(item):
        target = (root / item["path"]).resolve()
        assert target.is_relative_to(root)
        if target not in sources:
          data = target.read_bytes()
          sources[target] = (hashlib.sha256(data).hexdigest(), data.decode("utf-8-sig").splitlines())
        digest, lines = sources[target]
        assert digest == item["sha256"], target
        if "start_line" in item:
          assert 1 <= item["start_line"] <= item["end_line"] <= len(lines)
        else:
          assert 1 <= item["line"] <= len(lines)
          excerpt = "\n".join(lines[item["line"] - 1:item["line"] + item["expression"].count("\n")])
          assert item["expression"].replace("\r\n", "\n") in excerpt, (target, item)

      for frame in frames.values():
        source = frame["source"]
        assert source["historical_identity"] == "NOT_CHECKED"
        assert (source["selected"] is not None) == (source["status"] in {"LOCATED", "CANDIDATE"})
        if source["selected"]:
          assert source["selected"] in source["candidates"]
        for candidate in source["candidates"]:
          check_source(candidate)
      for edge in record["call_edges"]:
        assert edge["caller_frame_id"] in frames and edge["callee_frame_id"] in frames
        assert edge["type_resolution"] == "NOT_PERFORMED"
        assert bool(edge["call_sites"]) == (edge["status"] == "CALL_SITE_CANDIDATE")
        edges[edge["status"]] += 1
        for site in edge["call_sites"]:
          check_source(site)
  return {**totals, "frames": dict(statuses), "edges": dict(edges), "verified_source_files": len(sources)}


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("jsonl", type=Path)
  args = parser.parse_args()
  print(json.dumps(verify(args.jsonl), indent=2))
