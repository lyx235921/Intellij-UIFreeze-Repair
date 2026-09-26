"""Current-source locations and call-site evidence, not repair decisions or JVM binding."""

from collections import defaultdict
import hashlib
from importlib.metadata import version
import os
from pathlib import Path
import re

from tree_sitter import Language, Parser
import tree_sitter_java


SKIP_DIRS = {".git", ".idea", "out", "build", "target", "node_modules", "__pycache__",
             "test", "tests", "testsrc", "testdata", "fixtures", "golden", "evidence"}
JAVA_TYPES = {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration"}


def masked(text):
  """Blank comments and literals without changing character offsets or line numbers."""
  pattern = re.compile(r'//[^\n]*|/\*.*?\*/|""".*?"""|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)
  return pattern.sub(lambda m: "".join("\n" if c == "\n" else " " for c in m[0]), text)


def pairs(text):
  stack, result = [], {}
  for i, char in enumerate(text):
    if char in "({[":
      stack.append((char, i))
    elif char in ")}]":
      if not stack or stack[-1][0] != {")": "(", "}": "{", "]": "["}[char]:
        return None
      _, start = stack.pop()
      result[start] = i
  return result if not stack else None


def walk(node):
  yield node
  for child in node.named_children:
    yield from walk(child)


def symbol_parts(frame):
  symbol = frame.get("symbol") or ""
  if "/0x" in symbol or "$$Lambda" in symbol:
    return None
  symbol = symbol.split("/", 1)[-1]
  owner, sep, member = symbol.rpartition(".")
  if not sep or member in {"invokeSuspend", "<clinit>"} or "lambda$" in member or "$" in member:
    return None
  return owner, member


class SourceLocator:
  def __init__(self, root):
    if version("tree-sitter") != "0.25.2":
      raise RuntimeError("Install finder/main/requirements.txt: tree-sitter 0.25.2 is required (0.26.0 crashes on this corpus)")
    self.root = Path(root).resolve()
    if not self.root.is_dir():
      raise ValueError(f"Source root is not a directory: {root}")
    self.paths = defaultdict(list)
    self.cache = {}
    self.parser = Parser(Language(tree_sitter_java.language()))
    self.index_errors = []
    for directory, dirs, files in os.walk(self.root, onerror=lambda e: self.index_errors.append(str(e))):
      dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP_DIRS and not Path(directory, d).is_symlink())
      for name in sorted(files):
        path = Path(directory, name)
        if path.suffix in {".java", ".kt"} and not path.is_symlink():
          self.paths[name].append(path)

  def load(self, path):
    if path in self.cache:
      return self.cache[path]
    result = {"methods": [], "error": None}
    try:
      data = path.read_bytes()
      text = data.decode("utf-8-sig")
      # Normalize BOM consistently for byte-based AST offsets; hash remains of original file.
      content = text.encode("utf-8")
      clean = masked(text)
      package_match = re.search(r"(?m)^\s*package\s+([\w.]+)", clean)
      package = package_match[1] if package_match else ""
      source = {"path": path.relative_to(self.root).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(), "language": path.suffix[1:]}
      if path.suffix == ".java":
        tree = self.parser.parse(content)
        if tree.root_node.has_error:
          result["error"] = "JAVA_PARSE_ERROR"
        else:
          for node in walk(tree.root_node):
            if node.type not in {"method_declaration", "constructor_declaration"}:
              continue
            owners, parent, unsupported = [], node.parent, False
            while parent:
              if parent.type in JAVA_TYPES:
                owners.append(parent.child_by_field_name("name").text.decode())
              if parent.type in {"object_creation_expression", "method_declaration", "constructor_declaration"}:
                unsupported = True
              parent = parent.parent
            if not owners or unsupported:
              continue
            name = node.child_by_field_name("name").text.decode()
            if node.type == "constructor_declaration":
              name = "<init>"
            body = node.child_by_field_name("body")
            calls = []
            if body:
              pending = list(body.named_children)
              while pending:
                child = pending.pop()
                if child.type in JAVA_TYPES | {"lambda_expression", "class_body"}:
                  continue
                if child.type == "method_invocation":
                  method = child.child_by_field_name("name")
                  receiver = child.child_by_field_name("object")
                  calls.append({"name": method.text.decode(), "line": child.start_point.row + 1,
                                "expression": child.text.decode(), "receiver": receiver.text.decode() if receiver else None,
                                "evidence": "JAVA_AST_CALL"})
                pending.extend(child.named_children)
            result["methods"].append({**source, "owner": (package + "." if package else "") + "$".join(reversed(owners)),
                                      "method": name, "start_line": node.start_point.row + 1,
                                      "end_line": node.end_point.row + 1,
                                      "declaration": content[node.start_byte:(body.start_byte if body else node.end_byte)].decode().strip(),
                                      "basis": "JAVA_AST", "calls": sorted(calls, key=lambda c: c["line"])})
      else:
        result["methods"], result["error"] = self.kotlin_methods(text, clean, package, source)
    except (OSError, UnicodeError) as error:
      result["error"] = f"SOURCE_READ_ERROR: {error}"
    self.cache[path] = result
    return result

  @staticmethod
  def kotlin_methods(text, clean, package, source):
    """Conservative lexical candidates; never claim compiler-resolved Kotlin identities."""
    brackets = pairs(clean)
    if brackets is None:
      return [], "KOTLIN_UNBALANCED_OR_UNSUPPORTED_SYNTAX"
    classes = []
    for match in re.finditer(r"\b(?:class|object|interface)\s+([A-Za-z_]\w*)", clean):
      pos = match.end()
      while pos < len(clean):
        if clean[pos] in "([" and pos in brackets:
          pos = brackets[pos] + 1
          continue
        if clean[pos] == "{":
          classes.append((match.start(), pos, brackets[pos], match[1]))
          break
        if clean[pos] in "\n;}":
          break
        pos += 1
    methods = []
    for match in re.finditer(r"\bfun\s+([A-Za-z_]\w*)\s*\(", clean):
      opening = clean.index("(", match.start(), match.end())
      pos = brackets.get(opening, opening) + 1
      while pos < len(clean) and clean[pos] not in "{=;\n}":
        pos += 1
      if pos >= len(clean) or clean[pos] != "{":
        continue
      end = brackets[pos]
      owners = [c for c in classes if c[1] < match.start() < c[2]]
      owners.sort()
      # Refuse local functions: enclosing braces must correspond to class bodies.
      enclosing = [i for i, j in brackets.items() if clean[i] == "{" and i < match.start() < j]
      if set(enclosing) != {c[1] for c in owners}:
        continue
      if owners:
        owner = "$".join(c[3] for c in owners)
      else:
        owner = Path(source["path"]).stem + "Kt"
      owner = (package + "." if package else "") + owner
      calls = []
      for call in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", clean[pos + 1:end]):
        offset = pos + 1 + call.start()
        call_open = clean.index("(", offset, pos + 1 + call.end())
        call_end = brackets.get(call_open)
        if call_end is None or call[1] in {"if", "for", "while", "when", "catch", "fun"}:
          continue
        prefix = re.search(r"([A-Za-z_][\w.]*)\s*\??\.\s*$", clean[pos + 1:offset])
        receiver = prefix[1] if prefix else None
        expression_start = pos + 1 + prefix.start() if prefix else offset
        calls.append({"name": call[1], "line": text.count("\n", 0, expression_start) + 1,
                      "expression": text[expression_start:call_end + 1], "receiver": receiver,
                      "evidence": "KOTLIN_LEXICAL_CALL_CANDIDATE"})
      methods.append({**source, "owner": owner, "method": match[1],
                      "start_line": text.count("\n", 0, match.start()) + 1,
                      "end_line": text.count("\n", 0, end) + 1,
                      "declaration": text[match.start():pos].strip(), "basis": "KOTLIN_LEXICAL_CANDIDATE", "calls": calls})
    return methods, None

  def locate(self, frame, callee=None):
    result = {"status": "UNRESOLVED", "reason": None, "candidates": [], "selected": None,
              "selection_basis": None, "source_diagnostics": [], "historical_identity": "NOT_CHECKED"}
    parts = symbol_parts(frame)
    if parts is None:
      result["reason"] = "MISSING_OR_SYNTHETIC_SYMBOL"
      return result
    owner, name = parts
    filename = frame.get("file")
    if not filename:
      location = frame.get("location") or ""
      filename = location if re.fullmatch(r"[^/\\]+\.(java|kt)", location) else owner.rsplit(".", 1)[-1].split("$")[0] + ".java"
    paths = self.paths.get(filename, [])
    for path in paths:
      loaded = self.load(path)
      if loaded["error"]:
        result["source_diagnostics"].append({"path": path.relative_to(self.root).as_posix(), "reason": loaded["error"]})
      result["candidates"].extend(m for m in loaded["methods"] if m["owner"] == owner and m["method"] == name)
    candidates = result["candidates"]
    if not candidates:
      result["reason"] = "METHOD_NOT_FOUND" if paths else "SOURCE_FILE_NOT_FOUND"
      return result
    chosen = candidates
    basis = "UNIQUE_OWNER_METHOD"
    callee_parts = symbol_parts(callee or {})
    if len(chosen) > 1 and callee_parts:
      matching = [m for m in chosen if any(c["name"] == callee_parts[1] for c in m["calls"])]
      if matching:
        chosen = matching
        basis = "ADJACENT_CALLEE_NAME"
    # Old line numbers are exposed, never used alone to break overload ambiguity.
    if len(chosen) == 1 and not result["source_diagnostics"] and not self.index_errors:
      result["status"] = "LOCATED" if chosen[0]["basis"] == "JAVA_AST" and basis == "UNIQUE_OWNER_METHOD" else "CANDIDATE"
      result["selected"] = chosen[0]
      result["selection_basis"] = basis
    else:
      result["status"] = "AMBIGUOUS"
      result["reason"] = "MULTIPLE_DECLARATIONS_OR_INCOMPLETE_INDEX"
    return result

  @staticmethod
  def call_edge(caller, callee):
    edge = {"caller_frame_id": caller["frame_id"], "callee_frame_id": callee["frame_id"],
            "status": "UNVERIFIED", "reason": None, "call_sites": [], "type_resolution": "NOT_PERFORMED"}
    if caller["index"] != callee["index"] + 1 or caller["elided"] or callee["elided"]:
      edge["reason"] = "NON_ADJACENT_OR_ELIDED_FRAMES"
      return edge
    method = caller["source"]["selected"]
    target = symbol_parts(callee)
    if method is None or target is None:
      edge["reason"] = "CALLER_UNRESOLVED_OR_CALLEE_SYNTHETIC"
      return edge
    edge["call_sites"] = [{"path": method["path"], "sha256": method["sha256"], **c}
                          for c in method["calls"] if c["name"] == target[1]]
    edge["status"] = "CALL_SITE_CANDIDATE" if edge["call_sites"] else "UNVERIFIED"
    edge["reason"] = "MATCHING_CALL_NAME_ONLY" if edge["call_sites"] else "NO_MATCHING_CALL_EXPRESSION"
    return edge
