# Agreed project goals

Updated 2026-10-14. This is the agreed direction, not a claim that hardware
validation is complete. Update milestone evidence as work progresses.

## End goal

A usable Alpine Linux phone: encrypted storage, reliable boot, dependable
charging and unplugged operation, networking, and a lightweight interface.
Preserve recovery paths and document experimental limitations.

## Established baseline

- Alpine boots with a physical terminal, fastfetch and USB shell.
- LUKS2 internal root and microSD home unlock and retain data across reboot.
- Software reboot works; backups and recovery/build tools are preserved.
- Bounded charging and unplugged operation have worked. One automatic physical
  unplug/reconnect test passed; repeatable reliability remains unproven.

## Ordered milestones

Battery acceptance criteria and work order are in
[BATTERY-MILESTONE.md](BATTERY-MILESTONE.md). Temperature is explicitly excluded
from that completion scope and remains a separate limitation.

1. **Dependable development baseline.** Diagnose and fix or safely handle the
   fuel-gauge release failure, establish reliable shutdown, and preserve
   encrypted boot. Require repeatable hardware results before declaring success.
2. **Limited, usable battery support.** Automatic charging while Linux runs,
   conservative cutoff/recharge, unplugged operation, reconnect handling and
   clear fault reporting. Validate these behaviors on hardware. Retain current,
   voltage, watchdog and fault protections; label remaining limits experimental.
3. **Useful Linux phone.** Investigate Wi-Fi and SSH, improve keypad/screen
   integration, then bring up a lightweight interface. Networking and graphics
   feasibility require investigation; Sxmo/backend selection remains provisional.
4. **Complete battery support.** Validate low-battery recovery, cold powered-off
   charging and full-charge termination. Address temperature sensing last.
   Report percentage only after defensible calibration. Until then, this is
   supervised experimental charging, not normal unattended phone charging.

Modern-kernel work and a firmware/security audit remain later objectives.
Do not block all useful Linux work on finishing every battery feature once the
limited development baseline is dependable. Do not bypass hardware protections.

## Immediate checkpoint

Current session: boot `24158b89-ab33-4286-aea7-466cbbd3fa87` unlocked remotely;
encrypted root/home mounted. Automatic charging passed through root handoff,
then was explicitly stopped while the user went away; charging OFF verified.

Vendor gauge transactions lack a lock shared with our userspace helper.
Contention is a plausible cause of the earlier release failure, not yet proven.
A candidate kernel serializes vendor transactions and a new bounded raw-current
endpoint. The same fault-tested acquisition core is reused; supported kernels
never fall back after endpoint read failure. Kernel compilation, adapter/backend
tests and encrypted image verification passed. Candidate
`alpine-m39-encrypted-serialized-gauge.partition.img` is **not flashed or boot-tested**.
Previous installed image remains intact. Updated root helper is installed.

`m39-poweroff` and a `poweroff` alias are installed in root. They stop charging,
verify OFF, sync and remount storage read-only, then request kernel poweroff
directly (custom PID 1 has no BusyBox shutdown handler). Ordering/failure tests
passed; actual poweroff behavior still needs hardware verification.

Next: when the user returns, verify current state, deploy/readback-test the
candidate boot, unlock automatically, validate the kernel endpoint and repeat
charging. Then test controlled shutdown on battery. Do not raise charge limits.

## Working agreement

- Choose one concrete deliverable per session, test it appropriately, and save
  a checkpoint with evidence and remaining blockers.
- Separate implemented software, simulated tests and verified hardware behavior.
- For charging/build waits, give a monitoring command and the next trigger for
  work. Do not spend agent turns polling elapsed time.
- Investigate faults from evidence instead of blindly restarting jobs.
- Follow [AGENTS.md](AGENTS.md); keep substantive changes locally committed.
  Push only when requested. Preserve encrypted data, recovery files and secrets.

This roadmap does not activate or resume an autonomous `/goal`.
