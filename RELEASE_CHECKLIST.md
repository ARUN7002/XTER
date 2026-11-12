# Supervised-testing release checklist

- [x] Guardian lease, authorization, heartbeat, audit, and emergency-stop tests pass.
- [x] Diagnostic broker validation and timeout tests pass.
- [x] Task limits, transitions, checkpoints, and verification tests pass.
- [x] Operator isolation and manual-takeover tests pass.
- [x] Gemini manual-transfer and untrusted-output tests pass.
- [x] Dashboard state-model tests pass.
- [x] Reporting and knowledge-base tests pass.
- [x] Security suite passes in the harmless local test environment.
- [ ] Install and benchmark VirtualBox/Ubuntu on the actual host.
- [ ] Install Ollama and test Qwen 2B locally.
- [ ] Implement and test authenticated host-to-VM IPC.
- [ ] Run the frontend production build after dependency installation.
- [ ] Owner approves any real Gemini/practice-site integration.
- [ ] Owner approves the first supervised real session.

Release remains blocked for real-site testing until the unchecked infrastructure and owner-approval items are complete.

