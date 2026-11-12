# ANDREWS

Controlled AI Engineering Operator — Phase 1 Guardian foundation.

This repository currently contains project scaffolding, configuration validation, structured logging, and an independent Guardian authorization core. It does not automate a browser, create a VM, connect to Gemini, install Ollama, or download a model.

## Requirements

- Windows 11 host
- Python 3.13+
- Node.js 20+ and npm
- Git

VirtualBox and Ollama are not required for Phase 0.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s backend/tests -p "test_*.py" -v
python -m backend.andrews.cli check-config
```

The default data root is `E:\ANDREWS`. Set `ANDREWS_DATA_ROOT` to another location for local development. Runtime data, VM disks, models, and logs must not be stored on C: by default.

## Phase status

Phase 1 implements permission leases, expiry, action authorization, heartbeat supervision, emergency stop, and append-only JSONL audit events. Phase 2 adds a restricted diagnostic broker with strict request/response schemas and timeouts; it does not install Ollama or download Qwen automatically. Phase 3 adds the SQLite-backed Task Manager with bounded workloads, status transitions, checkpoints, interruption recovery, and evidence-required verification. Phase 4 adds the safe Operator state machine and VM/browser isolation contracts; VirtualBox, Playwright, and real websites remain disabled. Phase 5 adds a manual-first Gemini adapter with bounded retries and untrusted-response handling; it stores no credentials. Phase 6 adds the dashboard safety-state model and UI scaffold; live backend, VM viewer, and Guardian transport remain pending. Phase 7 adds safe HTML/CSV reporting, diagnostic history summaries, and a verified-fix knowledge base. Phase 8 formalizes security validation, recovery, known limitations, and release readiness; real-site testing remains blocked pending infrastructure and owner approval.

