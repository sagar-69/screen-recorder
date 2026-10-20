#!/usr/bin/env python3
"""Windows ConsentStore registry dumper.

Dumps the CapabilityAccessManager ConsentStore registry entries to find
which apps have used screen-capture-related capabilities.

Registry path:
  HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\<capability>\NonPackaged\<app_path>

Capabilities of interest:
  - graphicsCaptureProgrammatic  (Windows Graphics Capture API)
  - graphicsCaptureWithoutBorder (borderless capture)
  - webcam (for reference/comparison — known to work)
  - microphone (for reference/comparison — known to work)

Values:
  - LastUsedTimeStart (FILETIME as uint64): when the app started using the capability
  - LastUsedTimeStop  (FILETIME as uint64): when it stopped (0 = still in use)

Usage (Windows only):
  python spike\\win_consent_store.py [--all] [--watch SECONDS]

Requirements:
  - Windows 10 version 2004+ or Windows 11
  - Normal user account (no elevation needed for HKCU)
"""

import sys
import json
import time
import argparse
from datetime import datetime, timezone, timedelta

# Check for Windows
if sys.platform != "win32":
    print("This script only runs on Windows.", file=sys.stderr)
    print("On macOS/Linux, use the macOS spike scripts instead.", file=sys.stderr)
    sys.exit(1)

import winreg

# Registry base path
CONSENT_STORE_BASE = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"

# Capabilities to check (screen-capture focused + reference ones)
CAPABILITIES = {
    "graphicsCaptureProgrammatic": "Graphics Capture API (programmatic)",
    "graphicsCaptureWithoutBorder": "Graphics Capture API (borderless)",
    "webcam": "Webcam (reference — known to work)",
    "microphone": "Microphone (reference — known to work)",
}

# Also check these if --all is passed
EXTRA_CAPABILITIES = {
    "appDiagnostics": "App diagnostics",
    "broadFileSystemAccess": "Broad file system access",
    "documentsLibrary": "Documents library",
    "picturesLibrary": "Pictures library",
    "videosLibrary": "Videos library",
}

# Windows FILETIME epoch: 1601-01-01 00:00:00 UTC
# The difference between FILETIME epoch and Unix epoch in 100-nanosecond intervals
FILETIME_UNIX_DIFF = 116444736000000000


def filetime_to_datetime(ft: int) -> datetime | None:
    """Convert a Windows FILETIME (100-nanosecond intervals since 1601-01-01) to datetime."""
    if ft == 0:
        return None
    try:
        # Convert to microseconds since Unix epoch
        microseconds = (ft - FILETIME_UNIX_DIFF) // 10
        return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=microseconds)
    except (ValueError, OverflowError, OSError):
        return None


def decode_app_path(encoded: str) -> str:
    """Decode a registry app path (# replaces \\)."""
    return encoded.replace("#", "\\")


def read_capability_entries(capability: str) -> list[dict]:
    """Read all NonPackaged app entries for a given capability."""
    entries = []

    # Try NonPackaged subkey
    for subkey_name in ["NonPackaged"]:
        reg_path = f"{CONSENT_STORE_BASE}\\{capability}\\{subkey_name}"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path)
        except FileNotFoundError:
            continue
        except PermissionError:
            print(f"  Permission denied: {reg_path}", file=sys.stderr)
            continue

        # Enumerate subkeys (each is an app)
        i = 0
        while True:
            try:
                app_key_name = winreg.EnumKey(key, i)
                app_path = decode_app_path(app_key_name)

                # Open the app's subkey and read values
                try:
                    app_key = winreg.OpenKey(key, app_key_name)
                    entry = {
                        "capability": capability,
                        "subkey": subkey_name,
                        "app_key_name": app_key_name,
                        "app_path": app_path,
                        "app_name": app_path.split("\\")[-1] if "\\" in app_path else app_path,
                    }

                    # Read all values
                    j = 0
                    while True:
                        try:
                            name, data, vtype = winreg.EnumValue(app_key, j)
                            if name == "LastUsedTimeStart":
                                entry["last_used_start_raw"] = data
                                dt = filetime_to_datetime(data)
                                entry["last_used_start"] = dt.isoformat() if dt else "never"
                            elif name == "LastUsedTimeStop":
                                entry["last_used_stop_raw"] = data
                                if data == 0:
                                    entry["last_used_stop"] = "IN USE NOW"
                                    entry["is_active"] = True
                                else:
                                    dt = filetime_to_datetime(data)
                                    entry["last_used_stop"] = dt.isoformat() if dt else "unknown"
                                    entry["is_active"] = False
                            elif name == "Value":
                                entry["consent_value"] = data
                            else:
                                entry[f"reg_{name}"] = str(data)
                            j += 1
                        except OSError:
                            break

                    winreg.CloseKey(app_key)
                    entries.append(entry)

                except (FileNotFoundError, PermissionError) as e:
                    print(f"  Cannot read {app_key_name}: {e}", file=sys.stderr)

                i += 1
            except OSError:
                break

        winreg.CloseKey(key)

    # Also try packaged apps (directly under the capability key)
    reg_path = f"{CONSENT_STORE_BASE}\\{capability}"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path)
        i = 0
        while True:
            try:
                sub_name = winreg.EnumKey(key, i)
                if sub_name != "NonPackaged":
                    # This might be a packaged app entry
                    try:
                        app_key = winreg.OpenKey(key, sub_name)
                        entry = {
                            "capability": capability,
                            "subkey": "Packaged",
                            "app_key_name": sub_name,
                            "app_path": sub_name,
                            "app_name": sub_name,
                        }
                        j = 0
                        while True:
                            try:
                                name, data, vtype = winreg.EnumValue(app_key, j)
                                if name == "LastUsedTimeStart":
                                    entry["last_used_start_raw"] = data
                                    dt = filetime_to_datetime(data)
                                    entry["last_used_start"] = dt.isoformat() if dt else "never"
                                elif name == "LastUsedTimeStop":
                                    entry["last_used_stop_raw"] = data
                                    if data == 0:
                                        entry["last_used_stop"] = "IN USE NOW"
                                        entry["is_active"] = True
                                    else:
                                        dt = filetime_to_datetime(data)
                                        entry["last_used_stop"] = dt.isoformat() if dt else "unknown"
                                        entry["is_active"] = False
                                elif name == "Value":
                                    entry["consent_value"] = data
                                else:
                                    entry[f"reg_{name}"] = str(data)
                                j += 1
                            except OSError:
                                break
                        winreg.CloseKey(app_key)
                        entries.append(entry)
                    except (FileNotFoundError, PermissionError):
                        pass
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except (FileNotFoundError, PermissionError):
        pass

    return entries


def emit_event(entry: dict) -> None:
    """Emit a schema v1 event for an active capture entry."""
    is_active = entry.get("is_active", False)
    signal = "usage_record_active" if is_active else "usage_record_ended"

    event = {
        "v": 1,
        "ts": datetime.now(timezone.utc).isoformat(),
        "os": "windows",
        "sensor": "consent_store",
        "signal": signal,
        "class": "reliable",
        "app": {
            "name": entry["app_name"],
            "pid": 0,
            "path": entry["app_path"],
            "publisher": "",
            "signed": False,
        },
        "method_hint": "graphics_capture" if "graphicsCapture" in entry["capability"] else "unknown",
        "ended": not is_active,
        "session_id": f"consent_store:{entry['app_name']}:{entry['capability']}",
        "detail": {
            "capability": entry["capability"],
            "last_used_start": entry.get("last_used_start", ""),
            "last_used_stop": entry.get("last_used_stop", ""),
            "consent_value": entry.get("consent_value", ""),
        },
    }
    print(json.dumps(event))


def main():
    parser = argparse.ArgumentParser(description="Windows ConsentStore registry dumper")
    parser.add_argument("--all", action="store_true",
                        help="Check all capabilities, not just screen-capture ones")
    parser.add_argument("--watch", type=int, default=0,
                        help="Re-check every N seconds (0 = one-shot)")
    parser.add_argument("--json-events", action="store_true",
                        help="Also emit schema v1 JSON events to stdout")
    args = parser.parse_args()

    caps = {**CAPABILITIES}
    if args.all:
        caps.update(EXTRA_CAPABILITIES)

    print("=" * 70, file=sys.stderr)
    print("Windows ConsentStore Registry Dumper", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"Checking capabilities: {', '.join(caps.keys())}", file=sys.stderr)
    print("-" * 70, file=sys.stderr)

    def scan():
        all_entries = []
        for cap_id, cap_desc in caps.items():
            entries = read_capability_entries(cap_id)
            print(f"\n[{cap_desc}] ({cap_id}): {len(entries)} entries", file=sys.stderr)

            for entry in entries:
                status = "🔴 ACTIVE" if entry.get("is_active") else "⚪ inactive"
                print(f"  {status} {entry['app_name']}", file=sys.stderr)
                print(f"    Path: {entry['app_path']}", file=sys.stderr)
                print(f"    Start: {entry.get('last_used_start', 'N/A')}", file=sys.stderr)
                print(f"    Stop:  {entry.get('last_used_stop', 'N/A')}", file=sys.stderr)

                if args.json_events:
                    emit_event(entry)

            all_entries.extend(entries)

        active = [e for e in all_entries if e.get("is_active")]
        print(f"\n--- Summary: {len(all_entries)} total entries, {len(active)} currently active ---", file=sys.stderr)
        return all_entries

    if args.watch > 0:
        try:
            scan_num = 0
            while True:
                scan_num += 1
                print(f"\n{'=' * 70}", file=sys.stderr)
                print(f"Scan #{scan_num} at {datetime.now().isoformat()}", file=sys.stderr)
                scan()
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped by user.", file=sys.stderr)
    else:
        scan()


if __name__ == "__main__":
    main()
