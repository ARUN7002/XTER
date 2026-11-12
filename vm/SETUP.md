# Phase 4 VM and browser setup contract

VirtualBox and Ubuntu are not installed by this phase. Before real deployment, the owner must create a dedicated Ubuntu Desktop VM with:

- 2 vCPUs and 4 GB RAM initially
- Dedicated browser profile created inside the VM
- Shared folders disabled
- Shared clipboard disabled
- No Windows password manager or personal browser profile
- Host-only or otherwise explicitly restricted networking
- No access to personal Windows folders

The Phase 4 Operator accepts only a browser attachment marked as `dedicated_vm=True` and a profile path inside the VM. The current implementation does not launch VirtualBox, Playwright, or an external website.

