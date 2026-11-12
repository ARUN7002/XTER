# Phase 0 architecture

ANDREWS will separate the independent Windows Host Guardian from the Ubuntu VM Operator and all AI services. Phase 0 provides only the configuration and logging contracts that later phases will use.

The intended storage root is `E:\ANDREWS`, with application code, Guardian, Operator, intelligence, workload, monitoring, permissions, tests, reports, database, logs, backups, models, and VM data kept in separate directories. The root is configurable for development and is validated before startup.

Phase 1 adds `backend/andrews/guardian.py`. The Guardian owns the permission lease, approved origins and action categories, action budget, heartbeat timeout, emergency-stop latch, and audit events. The Operator can request authorization but cannot change Guardian state. `OperatorSupervisor` is the narrow supervision hook that stops the Operator when the Guardian reports an expired lease or lost heartbeat.

Phase 2 adds `backend/andrews/diagnostics.py`. The broker accepts a bounded diagnostic request, sanitizes it, calls an injected local model client, enforces a timeout, and validates an exact response schema. Its output is data only; it exposes no command, permission, browser, or filesystem operation.

Phase 3 adds `backend/andrews/tasks.py`. The Task Manager owns SQLite session/task records, bounded workloads, duplicate detection, a legal status-transition graph, correction limits, deadlines, checkpoints, interruption states, and independent verification evidence.

Phase 4 adds `backend/andrews/operator.py`. The Operator requires a dedicated-VM browser attachment, authorizes every input through Guardian, pauses on browser failure, stops on Guardian loss, and revokes automated input before manual takeover. Desktop and browser automation remain behind future adapters.

Phase 5 adds `backend/andrews/gemini.py`. The adapter defaults to owner-mediated manual transfer, bounds retries, rejects empty or incomplete responses, and marks every response as untrusted data. Credentials, cookies, and website sessions are not accepted or stored.

Phase 6 adds a React/Vite dashboard state model and UI scaffold. Health is derived from observed signals and staleness, manual takeover requires input revocation confirmation, and dashboard disconnect does not mutate Guardian state. Live transport and VM display integration remain future adapters.

Phase 7 adds `backend/andrews/reporting.py`. Reports escape untrusted values, export task summaries to HTML/CSV, preserve diagnostic and error summaries, and label verification sources. The knowledge base accepts only local-test, owner-review, or independent-check evidence. Cleanup is restricted to files directly inside an explicit directory and approved report/log suffixes.

No component in this phase has permission to control a browser, VM, AI model, or external service. The process/IPC packaging and authenticated host-to-VM transport remain later work.

