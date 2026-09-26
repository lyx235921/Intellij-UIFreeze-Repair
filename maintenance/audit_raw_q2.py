"""Workbook-only Q2 candidate inventory; no Finder/Repair imports or execution.

Rules describe observed waiting paths, not proven incident root causes.
Run: python maintenance/audit_raw_q2.py --input workbook.xlsx --output directory
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

import openpyxl

HEADER = re.compile(r"(?m)^(?:cause freeze thread:)?\[([^\]]+)\]\s+(\w+)[^\n]*")
FRAME = re.compile(r"(?m)^(?:(?:topStack|problemModuleStack):\s*)?(\d+)\s+([^\s(]+)\(")
P = "com.intellij.openapi.progress.util."
FAMILIES = {
    P + "ProgressIndicatorUtils.awaitWithCheckCanceled": "Q2.1",
    "com.intellij.util.io.SafeFileOutputStream.waitForBackup": "Q2.1",
    "org.jetbrains.concurrency.AsyncPromise.get": "Q2.1",
    "com.huawei.deveco.database.databaseplugin.utils.DatabasesUtil.executeBmCommandsAndCollectResults": "Q2.1",
    "kotlinx.coroutines.BlockingCoroutine.joinBlocking$lambda$0": "Q2.2",
    P + "EventStealer.waitForPing": "Q2.3",
    P + "EternalEventStealer.dispatchExistingEvent": "Q2.3",
    P + "EventStealer.dispatchEvents": "Q2.3",
    "com.intellij.openapi.actionSystem.impl.AltEdtDispatcher.runOwnQueueBlockingAndSwitchBackToEDT$lambda$0": "Q2.4",
    "sun.java2d.metal.MTLRenderQueue$QueueFlusher.flushNow": "Q2.5",
    "sun.awt.AWTThreading.execute": "Q2.5",
    "javax.swing.ImageIcon.loadImage": "Q2.5",
    "com.sun.java2d.metal.MTLRenderQueue.flushNow": "Q2.6",
    P + "SuvorovProgress.sleep": "Q2.6",
    "com.intellij.internal.UIFreezeAction.actionPerformed": "Q2.6",
}
WAIT_TOP = {
    "jdk.internal.misc.Unsafe.park", "sun.misc.Unsafe.park",
    "java.lang.Object.wait", "java.lang.Object.wait0",
    "java.lang.Thread.sleep", "java.lang.Thread.sleep0", "java.lang.Thread.sleepNanos0",
}
LOCKS = {
    "java.util.concurrent.locks.StampedLock.writeLock",
    "java.util.concurrent.locks.ReentrantLock.lock",
    "java.util.concurrent.locks.ReentrantReadWriteLock$WriteLock.lock",
    "java.util.concurrent.locks.ReentrantReadWriteLock$ReadLock.lock",
}


def classify(frames, state):
    symbols = [f["method"] for f in frames]
    top = symbols[0] if symbols else ""
    caller = next((s for s in symbols if not s.startswith(("java.", "jdk.", "sun.misc."))), top)
    labels = set()
    if state == "BLOCKED":
        status = "NATIVE_PROCESS_START_UNRESOLVED" if top == "java.lang.ProcessImpl.create" else "MONITOR_BLOCKED"
    elif not frames or frames[0]["index"] != 0:
        status = "INCOMPLETE_TOP"
    elif state not in ("WAITING", "TIMED_WAITING") and top not in WAIT_TOP:
        status = "NO_CURRENT_WAIT_EVIDENCE"
    elif any(s in LOCKS for s in symbols[:12]):
        status = "EXPLICIT_LOCK_ACQUISITION"
    elif caller == "com.intellij.ide.IdeEventQueue.getNextEvent":
        if "com.intellij.openapi.fileEditor.impl.FileEditorManagerImplKt.waitBlockingAndPumpEdt" in symbols:
            labels.update(("Q2.2", "Q2.3"))
            status = "Q2_CANDIDATE"
        elif "com.intellij.openapi.progress.impl.PlatformTaskSupport.runWithModalProgressBlockingInternal" in symbols:
            labels.add("Q2.3")
            status = "Q2_CANDIDATE"
        else:
            status = "ORDINARY_EVENT_QUEUE_WAIT"
    elif caller in FAMILIES and top in WAIT_TOP:
        labels.add(FAMILIES[caller])
        if caller == P + "SuvorovProgress.sleep":
            labels.add("Q2.3")
        status = "Q2_CANDIDATE"
    else:
        status = "UNRESOLVED_WAIT"
    injected = any(s in ("com.sun.java2d.metal.MTLRenderQueue.testFreeze", "com.intellij.internal.UIFreezeAction.actionPerformed") for s in symbols)
    return status, sorted(labels), caller, injected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    book = openpyxl.load_workbook(args.input, read_only=True, data_only=True)
    sheet = book["\u95ee\u9898\u7ebf\u7a0b\u5806\u6808"]
    rows = []
    for row_number, cells in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
        raw = "".join(str(v) for v in cells[1:] if v is not None)
        if not raw.strip():
            continue
        headers = list(HEADER.finditer(raw))
        ui = [(i, h) for i, h in enumerate(headers) if re.fullmatch(r"AWT-EventQueue-\d+", h[1])]
        if len(ui) != 1:
            raise ValueError(f"Row {row_number}: expected one UI thread, got {len(ui)}")
        i, h = ui[0]
        block = raw[h.start():headers[i + 1].start() if i + 1 < len(headers) else len(raw)]
        frames = [{"index": int(n), "method": re.sub(r"^(?:[^/]+//|[^/]+/)(?=[A-Za-z_])", "", s)} for n, s in FRAME.findall(block)]
        status, labels, caller, injected = classify(frames, h[2])
        rows.append(dict(row=row_number, occurrences=cells[0], state=h[2], status=status,
                         categories=labels, matching_caller=caller, injected_test_path=injected,
                         frames=frames, ui_stack=block, raw_sha256=hashlib.sha256(raw.encode()).hexdigest()))
    book.close()
    categories, methods = defaultdict(list), defaultdict(list)
    for r in rows:
        for c in r["categories"]:
            categories[c].append(r["row"])
        if r["categories"]:
            methods[r["matching_caller"]].append(r["row"])
    summary = dict(workbook_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(), records=len(rows),
                   states=dict(Counter(r["state"] for r in rows)), statuses=dict(Counter(r["status"] for r in rows)),
                   candidates=sum(bool(r["categories"]) for r in rows),
                   injected_candidates=sum(bool(r["categories"]) and r["injected_test_path"] for r in rows),
                   category_rows=dict(sorted(categories.items())), method_rows=dict(sorted(methods.items())),
                   rules=FAMILIES)
    for name, data in (("summary.json", summary),):
        (args.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, records in (("rows.jsonl", rows), ("candidates.jsonl", [r for r in rows if r["categories"]])):
        with (args.output / name).open("w", encoding="utf-8") as out:
            for r in records:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("category_rows", "method_rows", "rules")}))
    print({k: len(v) for k, v in categories.items()})


if __name__ == "__main__":
    main()
