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

Latest check: kernel #20's run **failed** at uptime215 with `Resource busy`
from the gauge endpoint, despite the bounded lock wait. Charging OFF was
verified; no restart performed. The next investigation is which vendor gauge
command holds the shared lock beyond the deadline. Prior deployment observations
below remain valid, but the reliability run is no longer active. Evidence:
local `logs/gauge-bounded-lock-progress.txt`.

Kernel #19's serialized gauge endpoint is installed and boot-tested; the full
boot-partition readback matched. Root/home unlock and automatic charging handoff
passed. Three physical unplug/reconnect cycles on the same broker passed with
no logged kernel gauge errors. Longer-run reliability remains unproven. The subsequent run stopped on a genuine
vendor-lock collision (`Resource busy`), with charging OFF verified. A revised
candidate now waits for the shared lock inside the original 30 ms acquisition
budget; lock timeout and measurement/cleanup failures remain fatal. Six adapter
scenarios, shared-core tests and kernel compilation passed. Kernel #20 is now
installed with full readback verification; boot/root handoff passed and positive
charging was observed at uptime83 (3514 mV, raw current+224). The bounded
reliability run subsequently failed; charging is stopped. Do not poll it until a fault,
reported completion, or the first segment milestone (~30 minutes).

Controlled `m39-poweroff` shut down on battery, confirmed by the user. USB
insertion without power presses produced a fresh boot and the locked prompt.
Automatic charging preparation began, but the user then left to eat, so charging
was stopped before sustained positive-current validation. Cold-off charging is
therefore only partially validated, not complete.

Current boot `6ff52c18-e2f3-442e-ae51-c4661b4da2f4` is unlocked automatically.
Root/home persistence markers survived; temporary key removed. Broker1964 and
controller2462 are stopped after a fault; screen idle is enabled after30 seconds. Public
status now reports fresh idle broker measurements with process/freshness checks.
Evidence: local `logs/gauge-bounded-lock-root-verified.txt` and
`logs/gauge-bounded-lock-boot-readback.txt`.

Next: inspect the longer bounded gauge run at the first segment milestone or
reported fault, then validate USB-attached shutdown/startup and cutoff/recharge.
Do not raise charge limits. No idle agent polling while charging.

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
