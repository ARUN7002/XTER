# Phase 0 architecture

ANDREWS will separate the independent Windows Host Guardian from the Ubuntu VM Operator and all AI services. Phase 0 provides only the configuration and logging contracts that later phases will use.

The intended storage root is `E:\ANDREWS`, with application code, Guardian, Operator, intelligence, workload, monitoring, permissions, tests, reports, database, logs, backups, models, and VM data kept in separate directories. The root is configurable for development and is validated before startup.

Phase 1 adds `backend/andrews/guardian.py`. The Guardian owns the permission lease, approved origins and action categories, action budget, heartbeat timeout, emergency-stop latch, and audit events. The Operator can request authorization but cannot change Guardian state. `OperatorSupervisor` is the narrow supervision hook that stops the Operator when the Guardian reports an expired lease or lost heartbeat.

Phase 2 adds `backend/andrews/diagnostics.py`. The broker accepts a bounded diagnostic request, sanitizes it, calls an injected local model client, enforces a timeout, and validates an exact response schema. Its output is data only; it exposes no command, permission, browser, or filesystem operation.

Phase 3 adds `backend/andrews/tasks.py`. The Task Manager owns SQLite session/task records, bounded workloads, duplicate detection, a legal status-transition graph, correction limits, deadlines, checkpoints, interruption states, and independent verification evidence.

No component in this phase has permission to control a browser, VM, AI model, or external service. The process/IPC packaging and authenticated host-to-VM transport remain later work.

