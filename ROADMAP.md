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

The latest observed controller aborted with `FG_ERROR stage=10`: fuel-gauge
measurement-latch release failed. Charging shutdown was verified. More detailed
release diagnostics were installed in encrypted root, with seven host tests and
a charging-off hardware sample passing. The boot image still has the earlier
helper. A bounded diagnostic run was launched, but its outcome is not yet known.

The user subsequently disconnected to leave. Do not assume any controller or
charging session remains active. On resumption, inspect the actual connection,
boot identity and process state before mutations. Diagnose the latch failure
and shutdown behavior next; do not raise charging limits.

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
