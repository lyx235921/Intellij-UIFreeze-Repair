"""Targeted portable checks; install pinned Python deps and set Q1_CLASSPATH first."""
import argparse
import os
from pathlib import Path
import sys
import unittest

FINDER = ['test_source_locator.py', 'test_real_stack_input.py', 'test_state_statistics.py']
REPAIR = ['test_repair_entry.py', 'test_q2_classifier.py', 'test_extract_method.py',
    'test_p3_analysis.py', 'test_wait_resource_evidence.py', 'test_monitor_cycle_repair.py',
    'test_repair_selection.py', 'test_p1_plan.py', 'test_p1_reload.py',
    'test_regex_precompilation.py', 'test_p2_relocation.py', 'test_q13_relocation.py']

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lane', choices=['finder', 'repair'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    os.chdir(root)
    (root / 'out').mkdir(exist_ok=True)
    if args.lane == 'repair' and not os.environ.get('Q1_CLASSPATH'):
        parser.error('Q1_CLASSPATH is required; do not certify skipped Kotlin checks')
    folder, patterns = ('finder/Test', FINDER) if args.lane == 'finder' else ('repair/tests', REPAIR)
    suite = unittest.TestSuite(unittest.TestLoader().discover(folder, pattern=p) for p in patterns)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful() or bool(result.skipped))
