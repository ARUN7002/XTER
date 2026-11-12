# Known limitations

- VirtualBox and Ollama are not installed on the current host.
- The dashboard is currently a tested UI/state scaffold, not a live transport client.
- The Operator has safe adapter boundaries but does not drive a VM or browser.
- Gemini integration is manual-first; no credentials or cookies are stored.
- Host-to-VM authenticated IPC and process packaging remain unfinished.
- The SQLite audit/history design is not tamper-proof against a fully compromised host.
- Frontend production build has not been run because npm dependencies are not installed.

