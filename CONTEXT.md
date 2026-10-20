# CONTEXT.md — Screen-Use Detector

*Last updated: Stage 0, 2026-10-11*

---

## 1. Read me first

Screen-Use Detector is a desktop app (macOS + Windows) that tells you which apps are **capturing, recording or sharing your screen** in near real time. It combines several weak OS signals, scores confidence (high / medium / low), and shows results in a tray/menu-bar UI. All data stays local. This is a defensive privacy tool — it never stores screen contents.

**To resume work:** read this file → `FEATURES.md` → `ARCHITECTURE.md` → pick up from "Current stage" below.

---

## 2. Current stage

**Stage 1 — Signal Spike (throwaway Python in `spike/`)**

| # | Task | Status |
|---|------|--------|
| 1 | macOS: TCC permission list reader | in-progress |
| 2 | macOS: Unified log watcher script | planned |
| 3 | macOS: Running apps with code-signature info | planned |
| 4 | Windows: ConsentStore registry dumper | planned |
| 5 | Windows: Registry change watcher | planned |
| 6 | Windows: Process module scanner | planned |
| 7 | Create lab/protocol.md with test matrix steps | planned |
| 8 | Create frame-grabbing test fixture | planned |
| 9 | Run macOS scripts and record findings | planned |
| 10 | Fill docs/signal-findings.md | planned |
| 11 | Update scoring rules based on findings | planned |
| 12 | Commit and tag stage-1 | planned |

**Blocked:** Windows scripts need a Windows machine to test.

---

## 3. Decisions log

| Date | Decision | Reason | Alternatives rejected |
|------|----------|--------|-----------------------|
| 2026-10-11 | Event schema v1: added optional `ended` boolean field and `session_id` string to support session-based signals | Allows sensors to report when a capture session ends, so the core can end detections promptly instead of waiting for a full-cycle timeout | Relying only on absence-based detection (would cause delayed end-of-detection) |
| 2026-10-11 | `detail` field is a free-form JSON object per sensor, not a fixed schema | Each OS sensor surfaces different raw data; forcing a union type would be fragile | Fixed `detail` enum across sensors |
| 2026-10-11 | scripts/check-docs written in Python 3 (no dependencies) | Python is available on macOS and Windows; avoids requiring Bash on Windows | Bash script (not cross-platform), Node script (heavier) |
| 2026-10-11 | Rust not yet installed; deferring to Stage 2 | Not needed until core implementation; avoids unnecessary system-wide installs now | Install Rust in Stage 0 |
| 2026-10-11 | Tauri CLI not yet installed; deferring to Stage 5 | Not needed until interface stage | Install now |

---

## 4. Findings

See [`docs/signal-findings.md`](docs/signal-findings.md) — empty template, to be filled in Stage 1.

---

## 5. Open questions

- Will Windows `graphicsCaptureProgrammatic` / `graphicsCaptureWithoutBorder` registry keys actually record per-app timestamps? (Test in Stage 1)
- On macOS Sequoia+, do apps using the system picker appear in TCC at all? (Test in Stage 1)
- What is the real-world latency of the unified log for screen-capture events? (Measure in Stage 1)

---

## 6. Risks

- **Signal coverage gaps**: Neither OS guarantees a single API to detect all captures. The confidence model is the mitigation.
- **macOS log format instability**: Apple changes unified log formats between releases. Must re-test on each supported version.
- **False positives from loaded modules**: Many apps load graphics DLLs without capturing. Module-only detections must stay at "low" confidence.
- **Rust / Tauri not installed**: Need to install before Stage 2. Will ask user first per the rules.

---

## 7. Environment

| Item | Version | Status |
|------|---------|--------|
| macOS | (current, Apple Silicon) | Available — primary dev machine |
| Windows | Not available locally | Need user's Windows machine for testing |
| Python | 3.14.7 | ✓ Installed |
| Node.js | 26.0.0 | ✓ Installed |
| npm | 11.12.1 | ✓ Installed |
| Swift | 6.4 | ✓ Installed |
| Rust | — | ✗ Not installed (needed Stage 2) |
| Cargo | — | ✗ Not installed (needed Stage 2) |
| Tauri CLI | — | ✗ Not installed (needed Stage 5) |

---

## 8. Stage log

| Date | Stage | Summary | Verified | Not verified |
|------|-------|---------|----------|--------------|
| 2026-10-11 | 0 — Foundation | Repo initialised, folder layout created, all docs written, event schema v1 defined, check-docs script and pre-commit hook working, toolchain audited | check-docs script, pre-commit hook, all docs consistency | Nothing OS-specific in this stage |
