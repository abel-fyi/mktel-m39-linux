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

Kernel #22 is installed and boot-tested. Charging-off gauge probing passed1599
snapshots over180 seconds. The prior ADC-lock conflict is corrected; longer
charging reliability remains unverified.

USB-attached shutdown and cold-off USB insertion both produced fresh boots and
positive charging while root/home remained locked. Two kernel #22 startups and
root handoffs passed, each with one broker/controller. Root/home persistence and
a synced1MiB storage write/read passed. Relevant local evidence:
`logs/kernel22-cold-off-charging.txt`, `logs/kernel22-cold-off-root-verified.txt`,
`logs/usb-shutdown-root-and-io-verified.txt`.

Current boot `ecf543c7-1edb-4a03-90c1-d10a93c47978` is unlocked and charging;
broker7239/controller7736 were observed positive at uptime192. The user watcher
is restored. Screen idle30s is currently enabled. Root init now starts it
on future unlocks; installed by atomic rename, with prior init preserved.
Its next-boot behavior still needs testing. No boot-image change for this addition.

Next: let the current bounded segment run while the user monitors; inspect at
~30 minutes or reported fault. Then validate actual cutoff/recharge, low-battery
recovery and remaining reporting/calibration requirements. Do not raise limits
or spend agent turns polling elapsed charging time.

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
