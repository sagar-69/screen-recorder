#!/usr/bin/env python3
"""macOS Unified Log watcher for screen capture events.

Streams the macOS unified log filtering for screen-capture-related entries:
  - com.apple.TCC subsystem (permission decisions)
  - screencapture process (screenshot/recording events)
  - screencaptureui process (UI for screen recording)

Usage:
  python3 spike/macos_log_watcher.py [--duration SECONDS]

Requirements:
  - macOS 13+
  - May need admin rights for some log entries
"""

import subprocess
import sys
import json
import re
import signal
import argparse
from datetime import datetime, timezone


# Log stream predicates to watch for screen capture activity.
# We combine several predicates with OR.
LOG_PREDICATE = (
    '(subsystem == "com.apple.TCC")'
    ' OR '
    '(process == "screencapture")'
    ' OR '
    '(process == "screencaptureui")'
    ' OR '
    '(eventMessage CONTAINS "ScreenCapture")'
    ' OR '
    '(eventMessage CONTAINS "screen capture")'
    ' OR '
    '(eventMessage CONTAINS "screen recording")'
    ' OR '
    '(eventMessage CONTAINS "kTCCServiceScreenCapture")'
)

# Patterns to classify log messages
PATTERNS = {
    "recording_started": [
        re.compile(r"recording", re.IGNORECASE),
        re.compile(r"capture.*start", re.IGNORECASE),
        re.compile(r"begin.*capture", re.IGNORECASE),
        re.compile(r"startCapture", re.IGNORECASE),
    ],
    "recording_ended": [
        re.compile(r"stop.*record", re.IGNORECASE),
        re.compile(r"end.*capture", re.IGNORECASE),
        re.compile(r"stopCapture", re.IGNORECASE),
    ],
    "permission_prompt": [
        re.compile(r"prompt.*screen", re.IGNORECASE),
        re.compile(r"requesting.*access", re.IGNORECASE),
        re.compile(r"TCCAccessRequest", re.IGNORECASE),
    ],
    "permission_granted": [
        re.compile(r"allowed.*screen", re.IGNORECASE),
        re.compile(r"kTCCServiceScreenCapture.*ALLOWED", re.IGNORECASE),
    ],
    "permission_denied": [
        re.compile(r"denied.*screen", re.IGNORECASE),
        re.compile(r"kTCCServiceScreenCapture.*DENIED", re.IGNORECASE),
    ],
}


def classify_message(message: str) -> str:
    """Classify a log message into a signal type."""
    for signal_type, patterns in PATTERNS.items():
        for pattern in patterns:
            if pattern.search(message):
                return signal_type
    return "unknown"


def parse_log_line(line: str) -> dict | None:
    """Parse a single line from `log stream` output.
    
    log stream --style ndjson outputs one JSON object per line.
    """
    line = line.strip()
    if not line:
        return None

    try:
        entry = json.loads(line)
        return entry
    except json.JSONDecodeError:
        # Fallback: try to parse the default text format
        # Format: timestamp thread type activity pid
        return {"raw_line": line}


def emit_event(log_entry: dict, signal_type: str) -> None:
    """Emit a schema v1 event from a log entry."""
    process = log_entry.get("processImagePath", "")
    process_name = process.split("/")[-1] if process else log_entry.get("process", "unknown")
    sender = log_entry.get("senderImagePath", "")
    message = log_entry.get("eventMessage", log_entry.get("raw_line", ""))

    event = {
        "v": 1,
        "ts": datetime.now(timezone.utc).isoformat(),
        "os": "macos",
        "sensor": "unified_log",
        "signal": f"log_{signal_type}",
        "class": "reliable" if signal_type in ("recording_started", "recording_ended", "permission_denied") else "corroborating",
        "app": {
            "name": process_name,
            "pid": log_entry.get("processID", 0),
            "path": process,
            "publisher": "",
            "signed": False,
        },
        "method_hint": "screen_recording",
        "ended": signal_type == "recording_ended",
        "session_id": f"log:{process_name}:{log_entry.get('processID', 0)}",
        "detail": {
            "subsystem": log_entry.get("subsystem", ""),
            "category": log_entry.get("category", ""),
            "sender": sender,
            "message_preview": message[:200] if message else "",
            "signal_classification": signal_type,
        },
    }
    print(json.dumps(event))
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="macOS unified log watcher for screen capture events")
    parser.add_argument("--duration", type=int, default=0,
                        help="How long to watch in seconds (0 = indefinite)")
    parser.add_argument("--output", type=str, default="",
                        help="Also write raw log lines to this file")
    parser.add_argument("--ndjson", action="store_true", default=True,
                        help="Use ndjson output format from log stream (default)")
    args = parser.parse_args()

    print("=" * 60, file=sys.stderr)
    print("macOS Unified Log Watcher — Screen Capture Events", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Predicate: {LOG_PREDICATE}", file=sys.stderr)
    print(f"Duration: {'indefinite' if args.duration == 0 else f'{args.duration}s'}", file=sys.stderr)
    print("Waiting for events... (trigger a screen capture to see output)", file=sys.stderr)
    print("-" * 60, file=sys.stderr)

    output_file = None
    if args.output:
        output_file = open(args.output, "a")
        print(f"Also writing raw lines to: {args.output}", file=sys.stderr)

    cmd = [
        "log", "stream",
        "--predicate", LOG_PREDICATE,
        "--style", "ndjson",
        "--level", "info",
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        start_time = datetime.now()
        event_count = 0

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue

            # Write raw line to file if requested
            if output_file:
                output_file.write(line + "\n")
                output_file.flush()

            # Parse the log entry
            entry = parse_log_line(line)
            if entry is None:
                continue

            # Get the message
            message = entry.get("eventMessage", entry.get("raw_line", ""))
            signal_type = classify_message(message)

            # Report all captured lines to stderr for debugging
            process = entry.get("process", "?")
            subsystem = entry.get("subsystem", "?")
            print(f"  [{signal_type:>20}] process={process} subsystem={subsystem}", file=sys.stderr)
            print(f"                        msg={message[:120]}", file=sys.stderr)

            # Emit schema v1 event
            emit_event(entry, signal_type)
            event_count += 1

            # Check duration
            if args.duration > 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= args.duration:
                    print(f"\nDuration reached ({args.duration}s). Stopping.", file=sys.stderr)
                    break

    except KeyboardInterrupt:
        print(f"\nStopped by user. Total events captured: {event_count}", file=sys.stderr)
    finally:
        if output_file:
            output_file.close()
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print(f"\nTotal events: {event_count}", file=sys.stderr)


if __name__ == "__main__":
    main()
