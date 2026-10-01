"""Repair entry point: accept Finder JSONL evidence without starting repair analysis."""

import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys
import subprocess


FINDER_SCHEMA = "finder-source-locations/1"
INTAKE_SCHEMA = "repair-intake/1"
SOURCE_STATUSES = {"LOCATED", "CANDIDATE", "AMBIGUOUS", "UNRESOLVED"}


def field(obj, key, kind):
  if not isinstance(obj, dict) or key not in obj or not isinstance(obj[key], kind):
    raise ValueError(f"Missing or invalid field: {key}")
  if (kind is int or isinstance(kind, tuple) and int in kind) and isinstance(obj[key], bool):
    raise ValueError(f"Expected integer: {key}")
  return obj[key]


def strings(obj, key):
  values = field(obj, key, list)
  if not all(isinstance(v, str) for v in values):
    raise ValueError(f"Expected string array: {key}")
  return values


def hash_field(obj, key):
  value = field(obj, key, str)
  if not re.fullmatch(r"[0-9a-f]{64}", value):
    raise ValueError(f"Invalid SHA256: {key}")
  return value


def source_location(value, method=False):
  path = field(value, "path", str)
  if not path or PureWindowsPath(path).anchor or PurePosixPath(path).is_absolute() or ".." in path.replace("\\", "/").split("/"):
    raise ValueError("Source path must be relative and contain no parent traversal")
  hash_field(value, "sha256")
  if method:
    for key in ("owner", "method", "declaration", "language", "basis"):
      field(value, key, str)
    if value["language"] not in {"java", "kt"} or value["basis"] not in {"JAVA_AST", "KOTLIN_LEXICAL_CANDIDATE"}:
      raise ValueError("Unknown source language or basis")
    if not 1 <= field(value, "start_line", int) <= field(value, "end_line", int):
      raise ValueError("Invalid source line range")
  else:
    for key in ("name", "expression", "evidence"):
      field(value, key, str)
    field(value, "receiver", (str, type(None)))
    if field(value, "line", int) < 1 or value["evidence"] not in {"JAVA_AST_CALL", "KOTLIN_LEXICAL_CALL_CANDIDATE"}:
      raise ValueError("Invalid call-site evidence")


def validate_finder(record):
  """Validate intake fields and references; do not read or authenticate source files."""
  if field(record, "schema_version", str) != FINDER_SCHEMA:
    raise ValueError("UNSUPPORTED_FINDER_SCHEMA")
  record_id = field(record, "record_id", str)
  workbook_hash = hash_field(record, "workbook_sha256")
  field(record, "source_root", str)
  info = field(record, "input", dict)
  field(info, "sheet", str)
  if field(info, "row", int) < 1 or "occurrences" not in info or not record_id:
    raise ValueError("Invalid input metadata")
  raw = field(info, "raw_stack", str)
  if hashlib.sha256(raw.encode("utf-8")).hexdigest() != hash_field(info, "stack_sha256"):
    raise ValueError("STACK_HASH_MISMATCH")
  parse = field(record, "parse", dict)
  if field(parse, "status", str) not in {"PARSED", "PARTIAL", "FAILED"}:
    raise ValueError("Unknown parse status")
  strings(parse, "diagnostics")
  strings(parse, "unparsed_lines")
  strings(record, "index_diagnostics")
  if field(record, "repair_analysis", str) != "NOT_PERFORMED":
    raise ValueError("Unexpected Finder repair analysis")
  threads, frames, counts = {}, {}, Counter()
  for thread in field(record, "threads", list):
    tid = field(thread, "thread_id", str)
    if not tid or tid in threads:
      raise ValueError("Duplicate or empty thread_id")
    threads[tid] = thread
    for key in ("name", "state"):
      field(thread, key, str)
    field(thread, "details", (str, type(None)))
    field(thread, "is_ui_thread", bool)
    if field(thread, "role", str) not in {"blocked", "cause"}:
      raise ValueError("Unknown thread role")
    strings(thread, "unparsed_lines")
    for frame in field(thread, "frames", list):
      fid = field(frame, "frame_id", str)
      if not fid or fid in frames:
        raise ValueError("Duplicate or empty frame_id")
      frames[fid] = tid
      field(frame, "index", int)
      for key in ("label", "symbol", "location", "file"):
        field(frame, key, (str, type(None)))
      field(frame, "line", (int, type(None)))
      field(frame, "elided", bool)
      field(frame, "raw", str)
      source = field(frame, "source", dict)
      status = field(source, "status", str)
      if status not in SOURCE_STATUSES:
        raise ValueError("Unknown source status")
      counts[status] += 1
      field(source, "reason", (str, type(None)))
      if field(source, "historical_identity", str) != "NOT_CHECKED":
        raise ValueError("Unexpected historical identity")
      if field(source, "selection_basis", (str, type(None))) not in {None, "UNIQUE_OWNER_METHOD", "ADJACENT_CALLEE_NAME"}:
        raise ValueError("Unknown selection basis")
      for diagnostic in field(source, "source_diagnostics", list):
        field(diagnostic, "path", str)
        field(diagnostic, "reason", str)
      candidates = field(source, "candidates", list)
      for candidate in candidates:
        source_location(candidate, method=True)
      selected = field(source, "selected", (dict, type(None)))
      if (selected is not None) != (status in {"LOCATED", "CANDIDATE"}):
        raise ValueError("Selected source/status mismatch")
      if selected is not None and selected not in candidates:
        raise ValueError("Selected source absent from candidates")
  for key, predicate in (("ui_thread_ids", lambda t: t["is_ui_thread"]), ("cause_thread_ids", lambda t: t["role"] == "cause")):
    refs = strings(record, key)
    if len(refs) != len(set(refs)) or set(refs) != {tid for tid, t in threads.items() if predicate(t)}:
      raise ValueError(f"Invalid thread references: {key}")
  for entry in field(record, "entry_frames", list):
    if field(entry, "frame_id", str) not in frames or field(entry, "reason", str) not in {"THREAD_TOP", "topStack", "problemModuleStack"}:
      raise ValueError("Invalid entry frame")
  for edge in field(record, "call_edges", list):
    caller, callee = field(edge, "caller_frame_id", str), field(edge, "callee_frame_id", str)
    if caller not in frames or callee not in frames or caller == callee or frames[caller] != frames[callee]:
      raise ValueError("Invalid call-edge references")
    if field(edge, "type_resolution", str) != "NOT_PERFORMED":
      raise ValueError("Unexpected type-resolution claim")
    field(edge, "reason", (str, type(None)))
    status = field(edge, "status", str)
    sites = field(edge, "call_sites", list)
    if status not in {"CALL_SITE_CANDIDATE", "UNVERIFIED"} or bool(sites) != (status == "CALL_SITE_CANDIDATE"):
      raise ValueError("Call-site/status mismatch")
    for site in sites:
      source_location(site)
  if field(record, "location_summary", dict) != dict(counts):
    raise ValueError("Location summary mismatch")
  return workbook_hash, record_id


def unique_object(pairs):
  result = {}
  for key, value in pairs:
    if key in result:
      raise ValueError(f"Duplicate JSON key: {key}")
    result[key] = value
  return result


def reject_constant(value):
  raise ValueError(f"Non-standard JSON constant: {value}")


def finite_float(value):
  number = float(value)
  if not math.isfinite(number):
    raise ValueError("JSON number out of range")
  return number


def receive(stream):
  seen = set()
  for line_number, line in enumerate(stream, 1):
    record = None
    errors = []
    try:
      record = json.loads(line, object_pairs_hook=unique_object, parse_constant=reject_constant, parse_float=finite_float)
      key = validate_finder(record)
      if key in seen:
        raise ValueError("DUPLICATE_FINDER_RECORD")
      seen.add(key)
    except (ValueError, TypeError, KeyError) as error:
      errors.append(str(error))
    result = {"schema_version": INTAKE_SCHEMA, "input_line": line_number,
              "record_id": record.get("record_id") if isinstance(record, dict) else None,
              "intake_status": "REJECTED" if errors else "ACCEPTED", "errors": errors,
              "repair_status": "NOT_STARTED", "source_verification": "NOT_PERFORMED", "finder": record}
    if record is None:
      result["raw_input"] = line.rstrip("\r\n")
    yield result


def main(argv=None):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--input", type=Path, required=True, help="find_sources.py JSONL")
  parser.add_argument("--output", type=Path, required=True, help="New repair intake JSONL; parent must exist")
  parser.add_argument("--q1-classpath", help="Enable Kotlin Q1; classpath containing Q1, Kotlin stdlib and Gson")
  parser.add_argument("--q2-classpath", help="Enable Kotlin Q2 stack classification; uses the same build as Q1")
  parser.add_argument("--java", default="java", help="Java executable for Q1")
  parser.add_argument("--source-root", type=Path, help="Override Finder source root for Q1 and S2 extraction")
  parser.add_argument("--q1-count-only", action="store_true", help="Classify stack symbols without reading source files")
  parser.add_argument("--s1-q16-method", action="store_true", help="Locate the complete project method on a Q1.6 stack path")
  parser.add_argument("--extract-method", action="store_true", help="Extract project method context for Q1 matched categories")
  parser.add_argument("--s1-p2", action="store_true", help="Extract context and generate a supported P2 candidate patch without applying it")
  parser.add_argument("--repair-selection", action="store_true", help="Select P1/P2 from stack and source context; defer P3 until both fail")
  parser.add_argument("--s1-p1", action="store_true", help="Generate an experimental source-bound P1 reload patch without applying it")
  parser.add_argument("--s1-regex", action="store_true", help="Generate a source-bound P1 regex precompilation candidate")
  parser.add_argument("--s1-q13", action="store_true", help="Evaluate five Q1.3 storage triggers and generate supported relocation candidates")
  parser.add_argument("--s1-storage", action="store_true", help="Evaluate storage and filesystem path preload bindings")
  parser.add_argument("--s1-loading", action="store_true", help="Evaluate class and native library preload bindings")
  parser.add_argument("--s2-extract-method", action="store_true", help="Extract up to five method contexts for each Q2 wait")
  parser.add_argument("--s2-repair-selection", action="store_true", help="Extract Q2 context and rank conditional P1/P2/P3 plans and G1 guard; no patches")
  args = parser.parse_args(argv)
  if args.q1_count_only and not args.q1_classpath:
    parser.error("--q1-count-only requires --q1-classpath")
  if (args.s2_extract_method or args.s2_repair_selection) and not args.q2_classpath:
    parser.error("S2 extraction/selection requires --q2-classpath")
  if (args.s1_q16_method or args.extract_method or args.s1_p2 or args.repair_selection or args.s1_p1 or args.s1_regex or args.s1_q13 or args.s1_storage or args.s1_loading) and (not args.q1_classpath or args.q1_count_only):
    parser.error("Method extraction/P2 requires --q1-classpath without --q1-count-only")
  counts = Counter()
  q1_count = 0
  method_counts = Counter()
  category_counts = Counter()
  q2_count = 0
  q2_methods = Counter()
  q2_categories = Counter()
  source_skipped_points = 0
  source_skipped_records = 0
  with ExitStack() as resources:
    source = resources.enter_context(args.input.open(encoding="utf-8-sig"))
    target = resources.enter_context(args.output.open("x", encoding="utf-8"))
    if args.q2_classpath:
      q2_command = [args.java, "-cp", args.q2_classpath, "org.jetbrains.research.lockrepair.Q2SynchronousWaitControlClassifier"]
      if args.s2_extract_method or args.s2_repair_selection:
        if args.source_root:
          q2_command.append(str(args.source_root))
        q2_command.append("--s2-repair-selection" if args.s2_repair_selection else "--s2-extract-method")
      q2_worker = resources.enter_context(subprocess.Popen(
        q2_command,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding="utf-8"))
    if args.q1_classpath:
      command = [args.java, "-cp", args.q1_classpath, "org.jetbrains.research.lockrepair.Q1ExpensiveWorkRelocationClassifier"]
      if args.source_root:
        command.append(str(args.source_root))
      if args.q1_count_only:
        command.append("--count-only")
      if args.s1_q16_method:
        command.append("--s1-q16-method")
      if args.extract_method:
        command.append("--extract-method")
      if args.repair_selection:
        command.append("--repair-selection")
      if args.s1_p1:
        command.append("--s1-p1")
      if args.s1_regex:
        command.append("--s1-regex")
      if args.s1_q13:
        command.append("--s1-q13")
      if args.s1_storage:
        command.append("--s1-storage")
      if args.s1_loading:
        command.append("--s1-loading")
      if args.s1_p2:
        command.append("--s1-p2")
      worker = resources.enter_context(subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding="utf-8"))
    for result in receive(source):
      if args.q2_classpath and result["intake_status"] == "ACCEPTED":
        q2_worker.stdin.write(json.dumps(result["finder"]) + "\n")
        q2_worker.stdin.flush()
        response = q2_worker.stdout.readline()
        if not response:
          raise RuntimeError("Q2 worker exited without a response")
        result["q2"] = json.loads(response)
        classification = result["q2"]["classification"]
        q2_count += classification["q2_count"]
        q2_methods.update(set(classification["matched_methods"]))
        q2_categories.update({c["category"] for c in classification["categories"]})
      if args.q1_classpath and result["intake_status"] == "ACCEPTED":
        worker.stdin.write(json.dumps(result["finder"]) + "\n")
        worker.stdin.flush()
        response = worker.stdout.readline()
        if not response:
          raise RuntimeError("Q1 worker exited without a response")
        result["q1"] = json.loads(response)
        q1_count += result["q1"]["classification"]["q1_count"]
        method_counts.update(set(result["q1"]["classification"]["matched_methods"]))
        category_counts.update({c["category"] for c in result["q1"]["classification"]["categories"]})
        if not args.q1_count_only:
          result["source_verification"] = "SEE_Q1_LOCATIONS"
        selection = result["q1"].get("repair_selection", {})
        skipped = sum(d["status"] == "SKIPPED_SOURCE_UNAVAILABLE" for d in selection.get("decisions", []))
        source_skipped_points += skipped
        source_skipped_records += bool(skipped)
      target.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
      counts[result["intake_status"]] += 1
    if args.q1_classpath:
      worker.stdin.close()
      if worker.wait() != 0:
        raise RuntimeError("Q1 worker failed")
    if args.q2_classpath:
      q2_worker.stdin.close()
      if q2_worker.wait() != 0:
        raise RuntimeError("Q2 worker failed")
  print(json.dumps({"q1_candidates": q1_count, "q1_methods": dict(method_counts), "q1_categories": dict(category_counts), "records": sum(counts.values()), "accepted": counts["ACCEPTED"],
                    "rejected": counts["REJECTED"], "q2_candidates": q2_count,
                    "q2_methods": dict(q2_methods), "q2_categories": dict(q2_categories),
                    "source_skipped_points": source_skipped_points, "source_skipped_records": source_skipped_records,
                    "repair_status": "NOT_STARTED"}), file=sys.stderr)
  return 0 if counts["ACCEPTED"] and not counts["REJECTED"] else 2


if __name__ == "__main__":
  raise SystemExit(main())
