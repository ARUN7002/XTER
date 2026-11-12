# Guardian — Phase 1

The implementation is in `backend/andrews/guardian.py` and is intentionally independent from the dashboard, Operator, browser, Gemini, Qwen, and VM layers.

Current guarantees:

- Permission leases expire automatically.
- Origins, action categories, operator identity, and action budgets are checked.
- Heartbeat loss stops the active session.
- Emergency stop latches until a new Guardian instance/explicit restart policy is introduced.
- Audit events are append-only JSONL when a path is configured.
- The dashboard is not required for authorization or emergency-stop behavior.

The network transport, process packaging, authenticated IPC, and Windows service integration are not implemented yet.

