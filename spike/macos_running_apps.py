#!/usr/bin/env python3
"""macOS Running Apps with code-signature information.

Lists all currently running applications using pyobjc (NSWorkspace)
and checks their code signatures using the `codesign` command-line tool.

Usage:
  python3 spike/macos_running_apps.py [--known-only] [--watch SECONDS]

Requirements:
  - macOS 13+
  - pyobjc-framework-Cocoa (pip install pyobjc-framework-Cocoa)
    Falls back to ps-based detection if pyobjc is not available.
"""

import subprocess
import sys
import json
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Known screen-capture-related apps.
# Each entry: (process_name_lower, expected_publisher_substring, method_hint)
KNOWN_CAPTURE_APPS = [
    # Recorders
    ("obs", "obs project", "recorder"),
    ("obs64", "obs project", "recorder"),
    ("obs-studio", "obs project", "recorder"),
    # Meeting apps
    ("zoom.us", "zoom video communications", "meeting_share"),
    ("zoom", "zoom video communications", "meeting_share"),
    ("microsoft teams", "microsoft corporation", "meeting_share"),
    ("teams", "microsoft corporation", "meeting_share"),
    ("slack", "slack technologies", "meeting_share"),
    ("discord", "discord", "meeting_share"),
    ("facetime", "apple", "meeting_share"),
    # Screen capture tools
    ("screencapture", "apple", "screenshot"),
    ("screencaptureui", "apple", "screenshot"),
    ("screenshot", "apple", "screenshot"),
    ("cleanshot x", "cleanshot", "screenshot"),
    ("snagit", "techsmith", "screenshot"),
    # Streaming
    ("streamlabs", "streamlabs", "recorder"),
    ("wirecast", "telestream", "recorder"),
    # Remote / screen sharing
    ("screensharingd", "apple", "screen_sharing"),
    ("screen sharing", "apple", "screen_sharing"),
    # Browsers (can do screen sharing via WebRTC)
    ("google chrome", "google", "browser_share"),
    ("firefox", "mozilla", "browser_share"),
    ("safari", "apple", "browser_share"),
    ("microsoft edge", "microsoft corporation", "browser_share"),
    ("arc", "the browser company", "browser_share"),
    # Loom
    ("loom", "loom", "recorder"),
]


def get_running_apps_pyobjc() -> list[dict]:
    """Get running apps using NSWorkspace (requires pyobjc)."""
    try:
        from AppKit import NSWorkspace
    except ImportError:
        return None  # Signal that pyobjc is not available

    workspace = NSWorkspace.sharedWorkspace()
    apps = workspace.runningApplications()

    results = []
    for app in apps:
        bundle_id = app.bundleIdentifier() or ""
        name = app.localizedName() or ""
        url = app.bundleURL()
        path = str(url.path()) if url else ""
        pid = app.processIdentifier()
        is_active = app.isActive()

        results.append({
            "name": name,
            "bundle_id": bundle_id,
            "path": path,
            "pid": pid,
            "is_active": is_active,
        })

    return results


def get_running_apps_ps() -> list[dict]:
    """Fallback: get running apps using ps command."""
    result = subprocess.run(
        ["ps", "-eo", "pid,comm"],
        capture_output=True, text=True
    )
    results = []
    for line in result.stdout.strip().splitlines()[1:]:
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            pid, comm = parts
            results.append({
                "name": comm.split("/")[-1],
                "bundle_id": "",
                "path": comm,
                "pid": int(pid),
                "is_active": False,
            })
    return results


def get_code_signature(path: str) -> dict:
    """Get code signature info for an app at the given path."""
    if not path:
        return {"signed": False, "publisher": "", "error": "no path"}

    try:
        result = subprocess.run(
            ["codesign", "-dvv", path],
            capture_output=True, text=True, timeout=5
        )
        output = result.stderr  # codesign outputs to stderr

        signed = result.returncode == 0
        publisher = ""
        team_id = ""
        identifier = ""

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Authority="):
                if not publisher:  # First Authority line is the leaf
                    publisher = line.split("=", 1)[1]
            elif line.startswith("TeamIdentifier="):
                team_id = line.split("=", 1)[1]
            elif line.startswith("Identifier="):
                identifier = line.split("=", 1)[1]

        return {
            "signed": signed,
            "publisher": publisher,
            "team_id": team_id,
            "identifier": identifier,
        }
    except subprocess.TimeoutExpired:
        return {"signed": False, "publisher": "", "error": "timeout"}
    except Exception as e:
        return {"signed": False, "publisher": "", "error": str(e)}


def match_known_app(name: str, publisher: str) -> tuple[bool, str, str]:
    """Check if an app matches any known capture app.
    
    Returns (is_match, matched_name, method_hint).
    Match requires BOTH name AND publisher to match.
    """
    name_lower = name.lower()
    publisher_lower = publisher.lower()

    for known_name, known_publisher, method in KNOWN_CAPTURE_APPS:
        if known_name in name_lower and known_publisher in publisher_lower:
            return True, known_name, method
    return False, "", ""


def emit_event(app: dict, sig: dict, is_known: bool, method_hint: str) -> None:
    """Emit a schema v1 event."""
    event = {
        "v": 1,
        "ts": datetime.now(timezone.utc).isoformat(),
        "os": "macos",
        "sensor": "running_apps",
        "signal": "known_app_running" if is_known else "app_running",
        "class": "corroborating",
        "app": {
            "name": app["name"],
            "pid": app["pid"],
            "path": app["path"],
            "publisher": sig.get("publisher", ""),
            "signed": sig.get("signed", False),
        },
        "method_hint": method_hint,
        "ended": False,
        "session_id": f"running_apps:{app['name']}:{app['pid']}",
        "detail": {
            "bundle_id": app.get("bundle_id", ""),
            "team_id": sig.get("team_id", ""),
            "identifier": sig.get("identifier", ""),
            "is_active_app": app.get("is_active", False),
        },
    }
    print(json.dumps(event))


def scan_once(known_only: bool = False) -> list[dict]:
    """Scan running apps once. Returns list of matches."""
    print("Scanning running applications...", file=sys.stderr)

    # Try pyobjc first, fall back to ps
    apps = get_running_apps_pyobjc()
    if apps is None:
        print("  pyobjc not available, falling back to ps", file=sys.stderr)
        apps = get_running_apps_ps()
    else:
        print(f"  Using NSWorkspace: {len(apps)} apps found", file=sys.stderr)

    matches = []
    for app in apps:
        name = app.get("name", "")
        if not name:
            continue

        # Quick check: could this be a known app? (name match only, before expensive codesign)
        name_lower = name.lower()
        might_be_known = any(kn in name_lower for kn, _, _ in KNOWN_CAPTURE_APPS)

        if known_only and not might_be_known:
            continue

        # Get code signature (expensive, only for potentially interesting apps)
        sig = {}
        if might_be_known or not known_only:
            sig = get_code_signature(app["path"])

        publisher = sig.get("publisher", "")
        is_known, matched_name, method_hint = match_known_app(name, publisher)

        if is_known:
            print(f"  ★ KNOWN APP: {name} (publisher: {publisher}, method: {method_hint})", file=sys.stderr)
            emit_event(app, sig, True, method_hint)
            matches.append({**app, **sig, "method_hint": method_hint})
        elif not known_only and sig.get("signed"):
            # Report all signed apps for analysis
            print(f"    {name} (publisher: {publisher})", file=sys.stderr)

    return matches


def main():
    parser = argparse.ArgumentParser(description="macOS running apps scanner with code signature info")
    parser.add_argument("--known-only", action="store_true",
                        help="Only report known capture/recording apps")
    parser.add_argument("--watch", type=int, default=0,
                        help="Re-scan every N seconds (0 = scan once)")
    parser.add_argument("--all-signed", action="store_true",
                        help="Show all signed apps (verbose, slow)")
    args = parser.parse_args()

    print("=" * 60, file=sys.stderr)
    print("macOS Running Apps Scanner", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Mode: {'known apps only' if args.known_only else 'all apps'}", file=sys.stderr)
    print(f"Watch: {'every ' + str(args.watch) + 's' if args.watch else 'one-shot'}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)

    if args.watch > 0:
        try:
            scan_num = 0
            while True:
                scan_num += 1
                print(f"\n--- Scan #{scan_num} at {datetime.now().isoformat()} ---", file=sys.stderr)
                scan_once(args.known_only)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped by user.", file=sys.stderr)
    else:
        matches = scan_once(args.known_only)
        print(f"\nKnown capture apps found: {len(matches)}", file=sys.stderr)


if __name__ == "__main__":
    main()
