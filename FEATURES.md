# FEATURES.md — Screen-Use Detector

*Last updated: Stage 0, 2026-10-11*

---

## Feature table

| ID | Feature | Stage | Status | Verified on | Notes |
|----|---------|-------|--------|-------------|-------|
| **Signals — Windows** | | | | | |
| W-SIG-01 | Capability usage store (ConsentStore registry) | 1, 3 | planned | | Hypothesis: `graphicsCaptureProgrammatic` records per-app timestamps |
| W-SIG-02 | Process and loaded module scan | 1, 3 | planned | | Look for `Windows.Graphics.Capture.dll` and duplication-related DLLs |
| W-SIG-03 | Known-app matcher (process name + publisher) | 3 | planned | | Match on name AND code-signing publisher |
| W-SIG-04 | Registry change watcher (`RegNotifyChangeKeyValue`) | 3 | planned | | Real-time alternative to polling |
| W-SIG-05 | ETW graphics tracing | 7+ | planned | | Optional, needs admin; late experiment only |
| **Signals — macOS** | | | | | |
| M-SIG-01 | TCC Screen Recording permission list | 1, 4 | planned | | Needs Full Disk Access; shows who MAY record |
| M-SIG-02 | Unified log stream (TCC + screencapture + screencaptureui) | 1, 4 | planned | | Predicate on `com.apple.TCC`, `screencapture`, `screencaptureui` |
| M-SIG-03 | Running apps with code-signature info | 1, 4 | planned | | `NSWorkspace.runningApplications` + signature |
| M-SIG-04 | Full Disk Access self-check | 4 | planned | | For onboarding; detect reduced mode |
| **Core** | | | | | |
| C-01 | Event model (schema v1, serde, versioned) | 2 | planned | | JSON-lines contract between sensors and core |
| C-02 | Signal classification (reliable / corroborating) | 2 | planned | | |
| C-03 | Confidence scorer (pure function) | 2 | planned | | High / Medium / Low rules |
| C-04 | Detection state machine with grace period | 2 | planned | | Start, sustain, flicker-resist, end |
| C-05 | SQLite storage (detections table) | 2 | planned | | Schema from design reference section 3 |
| C-06 | Known-app config file | 2 | planned | | TOML or JSON; name + publisher pairs |
| C-07 | CLI `detector-cli` (replay JSON-lines) | 2 | planned | | Reads from file or stdin, prints detections |
| **Interface** | | | | | |
| U-01 | Tray / menu-bar status icon | 5 | planned | | Shows active count |
| U-02 | Status banner (count + last update time) | 5 | planned | | "No screen capture detected" when idle |
| U-03 | Live tab — detection list (App, Method, Since, Level) | 5 | planned | | |
| U-04 | Evidence panel (publisher, signals, level explanation) | 5 | planned | | Fills on row selection |
| U-05 | History tab (past detections from DB) | 6 | planned | | |
| U-06 | Settings tab | 6 | planned | | |
| U-07 | Tray / menu-bar popover (summary + Open / Pause) | 5 | planned | | |
| U-08 | Alert notifications (new detections ≥ medium) | 5, 6 | planned | | Click opens evidence |
| U-09 | Degraded-mode banner | 5 | planned | | "Running with fewer signals: grant Full Disk Access" |
| U-10 | Empty states | 5 | planned | | No detections, no history |
| U-11 | Footer: "Stored on this device only" | 5 | planned | | |
| U-12 | Sidecar sensor process management | 5 | planned | | Launch, monitor, restart sensors |
| **Settings & Privacy** | | | | | |
| S-01 | Silence list (mute alerts per app) | 6 | planned | | "Silence app" button in evidence panel |
| S-02 | Pause alerts toggle | 6 | planned | | |
| S-03 | Alert threshold setting (default: medium) | 6 | planned | | |
| S-04 | Export history (JSON + CSV) | 6 | planned | | |
| S-05 | Delete history | 6 | planned | | |
| S-06 | Copy report (evidence as text) | 6 | planned | | |
| S-07 | Privacy audit (no network, no screenshots, no window titles) | 6 | planned | | CI check that fails on network crate |
| **Hardening & Release** | | | | | |
| H-01 | False-positive tuning (quiet-baseline test) | 7 | planned | | |
| H-02 | Start at login | 7 | planned | | |
| H-03 | Logging and crash recovery | 7 | planned | | |
| H-04 | CPU and memory budget | 7 | planned | | Measure idle usage |
| H-05 | Permission onboarding flow | 7 | planned | | Guide user through Full Disk Access |
| H-06 | Windows installer | 7 | planned | | |
| H-07 | macOS .dmg installer | 7 | planned | | |
| H-08 | Code signing and notarization | 7 | planned | | Needs user's accounts |

---

## Known limitations

*To be updated as signals are tested in Stage 1.*

- Neither OS provides a single API to detect all screen captures.
- macOS apps using the system picker may bypass the TCC permission list entirely.
- Windows capability usage store may not record timestamps for all capture methods.
- Module scanning produces false positives — many apps load graphics DLLs without capturing.
- The tool can miss captures; the UI says "not detected", never "safe".
- No window title capture in v1 (privacy rule).
- No remote-viewing detection in v1.
