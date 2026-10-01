"""Integration check against the named workbook and current checkout (no mocks)."""

import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))
from find_sources import locate_record
from real_stack_input import read_records
from source_locator import SourceLocator


class RealSourceLocationTest(unittest.TestCase):
  def test_row_two_toolbar_call_sites(self):
    root = Path(__file__).resolve().parents[4]
    workbook = root / "intellij底座问题堆栈-1.xlsx"
    records = read_records(workbook)
    try:
      record = next(records)
    finally:
      records.close()
    self.assertEqual(2, record["row"])
    result = locate_record(record, SourceLocator(root))
    frame = result["threads"][0]["frames"][6]
    self.assertIn("ActionToolbarImpl.actionsUpdated", frame["symbol"])
    selected = frame["source"]["selected"]
    self.assertIsNotNone(selected)
    self.assertEqual("CANDIDATE", frame["source"]["status"])
    self.assertIn("forceRebuild: Boolean", selected["declaration"])
    source = (root / selected["path"]).read_bytes()
    self.assertEqual(hashlib.sha256(source).hexdigest(), selected["sha256"])
    edge = next(e for e in result["call_edges"] if e["caller_frame_id"] == frame["frame_id"])
    self.assertEqual("NOT_PERFORMED", edge["type_resolution"])
    expressions = {site["expression"] for site in edge["call_sites"]}
    self.assertIn("removeAll()", expressions)
    self.assertIn("mySecondaryActions.removeAll()", expressions)
    lines = source.decode("utf-8").splitlines()
    for site in edge["call_sites"]:
      self.assertIn(site["expression"], lines[site["line"] - 1])


if __name__ == "__main__":
  unittest.main()
