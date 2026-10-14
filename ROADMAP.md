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

Kernel #22 is installed with full boot readback verification. Its charging-off
probe completed1599 snapshots over180 seconds without logged gauge errors.
Kernel #21 failed after one snapshot; its trace identified command5 (battery
voltage AUXADC) contending for an unnecessarily shared lock. The fix preserves
vendor command serialization and protects all gauge/unknown commands with the
latch mutex, while four reviewed AUXADC callbacks use only the dispatch mutex.
Acquisition deadlines, watchdog, voltage/current limits and fault shutdown are
unchanged. Evidence: local `logs/gauge-lock-scope-probe-result.txt`.

Current boot `59baaba0-14b9-400e-9183-ffe829fd3af9` is unlocked; root/home
persistence markers survived and the temporary key was removed. Charging-off
sampling passes, but longer charging reliability still needs verification.
A fresh bounded charging broker has been explicitly launched; the user monitors
its first segment (~30 minutes). Check on completion/fault, not idle agent polls.
Next: validate that segment, then USB-attached shutdown/startup and cutoff/recharge.

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
