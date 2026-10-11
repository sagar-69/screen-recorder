# Screen-Use Detector

A desktop app for macOS and Windows that tells you which apps are **capturing, recording or sharing your screen** in near real time.

> **Status:** Stage 0 — Foundation complete. No product code yet.

## What it does

Screen-Use Detector runs in the background and combines several operating-system signals to detect apps that are actively capturing your screen. Each detection shows the app name, publisher, capture method guess, start time, and a confidence level (high, medium, or low) with the evidence behind it.

The tool can miss captures — the UI says "not detected", never "safe".

## Privacy

- Runs on computers you own only. **All data stays local.**
- Never stores screenshots or screen contents.
- No network access, no telemetry.
- You can delete history and export it as a file.

## Project structure

```
core/              Scoring, event model, SQLite storage (Rust)
sensors/
  windows/         Registry watcher, process/module scan
  macos/           Log stream reader, permission list, app signatures
app/               Tauri 2 shell + React interface
spike/             Throwaway Python experiments
lab/               Test scenarios and manual test steps
scripts/           Helper scripts (check-docs, etc.)
docs/              Design reference, signal findings, decisions
```

## Documents

- [`CONTEXT.md`](CONTEXT.md) — Why and where we are, current stage, decisions, risks
- [`FEATURES.md`](FEATURES.md) — Feature table with status tracking
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — How it's built, event schema, scoring rules
- [`docs/design-reference.md`](docs/design-reference.md) — Original design brief (sections 1–7)

## Requirements

| Tool | Needed for | Status |
|------|-----------|--------|
| Python 3 | Spike scripts, check-docs | ✓ |
| Node.js + npm | Interface (Tauri frontend) | ✓ |
| Swift | macOS sensor | ✓ |
| Rust + Cargo | Core, Windows sensor | ✗ (install before Stage 2) |
| Tauri CLI | Interface build | ✗ (install before Stage 5) |

## Getting started

This project is under active development. See `CONTEXT.md` for the current stage and task list.

## License

Private — not yet licensed for distribution.
