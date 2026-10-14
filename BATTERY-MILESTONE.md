# Battery completion milestone — temperature excluded

Agreed scope, 2026-10-14. Status: **incomplete**.

## Desired behavior

Connect USB and the phone charges automatically, whether Alpine is running,
storage is locked, or the phone was powered off. Disconnect USB and it keeps
running on battery. Charging stops at its validated target and restarts only
when needed. Shutdown, low-battery recovery and fault handling are dependable.
Normal use requires no manual arming, scripts or battery removal.

“Complete” here means the non-temperature functions below are implemented and
verified. Cell-temperature protection remains excluded and unverified; completing
this milestone does not establish suitability for unattended charging.

## Work order and acceptance checklist

### 1. Reliable measurements and shutdown

- [ ] Diagnose the observed fuel-gauge release failure (`FG_ERROR stage=10`).
      Resolve its cause or implement justified, bounded handling that never
      accepts an invalid sample or hides failed cleanup.
- [ ] Measurement contention, I/O errors and stale records produce clear reasons;
      genuine faults stop charging, verify OFF and latch without blind retries.
- [x] Software shutdown works on battery without removing it.
      User observed scheduled `m39-poweroff` shut down on battery; next USB
      insertion produced a fresh boot (`24814e69-6983-4b75-88d4-88b278521ee4`).
- [x] With USB attached, document and verify whether controlled shutdown enters
      charging mode or stays off on the current installed version.
      Kernel #22 `m39-poweroff` produced a fresh boot with `bootreason=usb`.
      Locked broker186/controller741 charged at3501mV, FG+160 at uptime39,
      root/home mappings absent. Evidence: local `logs/usb-attached-poweroff-result.txt`
      and `logs/usb-attached-locked-charging.txt`.
- [ ] Installed boot and encrypted-root helpers contain the validated fixes.

### 2. Automatic charging and battery operation

- [ ] Charging starts without manual arming while locked and after root unlock.
      Handoff leaves exactly one controller and preserves fault/manual-stop state.
- [x] Three consecutive unplug/reconnect cycles on one boot pass: phone stays
      running unplugged, detach is handled cleanly, reconnect starts valid charging.
      Passed on kernel #19, boot `f03dc355-8f66-4aa8-8ed1-f3c074428677`,
      same broker2040; controllers5699/8603/11225 after reconnect. Evidence:
      local `logs/serialized-gauge-three-reconnects.txt`; no kernel gauge errors logged.
- [ ] Repeat automatic startup after two fresh boots; screen idle/wake and normal
      storage activity do not break charging or cause unexplained shutdowns.
- [ ] Verify sustained net charging and useful unplugged operation, rather than
      assuming that a configured current equals actual battery current.

### 3. Cutoff, recharge and termination

- [ ] Verify the existing 3.9 V cutoff, hold and recharge behavior on hardware,
      using independent voltage readings and recorded controller state.
- [ ] Establish board-specific current calibration and justified taper/termination
      criteria before implementing full-charge detection or raising voltage.
- [ ] Choose and document the final validated charge target. Verify termination
      and subsequent recharge on hardware; CV detection alone is not “full.”
      If the target remains conservative, report target reached, not 100% charged.
- [ ] Replace the experimental 190-minute overall budget with a justified normal
      lifecycle only after these checks pass. Preserve bounded controllers,
      watchdog/lease protection, verified shutdown and fault latching.

### 4. Charging while off and low-battery recovery

- [ ] Starting fully powered off, USB insertion enters a minimal charging path
      without unlocking root/home or repeatedly booting the full OS.
- [ ] Recover a naturally low battery through that path, then boot and unlock
      successfully. Do not deliberately deep-discharge the cell to test this.
- [ ] Removing USB in charging-only mode produces the documented off behavior.
- [ ] Low battery during normal use triggers a controlled shutdown with persistent
      storage intact. Thresholds must be justified and recorded.

### 5. Reporting and final regression

- [ ] Fresh status distinguishes charging, discharging, target hold, fault and
      unavailable data, with voltage, input presence and actionable fault reasons.
- [ ] Calibrated current is reported only when validated. Percentage/capacity may
      remain unavailable; never substitute an invented percentage for calibration.
- [ ] A final boot → unlock → charge → cutoff → unplug → reconnect → recharge →
      shutdown sequence passes with the same installed versions. Cover cold-off
      charging and low-battery recovery separately.
- [ ] Root/home persistence, recovery paths and private credentials are preserved.
      Record exact image/helper versions, test evidence and remaining limitations.

## Evidence and execution rules

Mark a box complete only with an evidence reference: installed version, test,
observed result and relevant log or measurement. Host tests verify software;
they do not replace hardware acceptance. One successful reconnect is preliminary.

Work on the first unresolved dependency, currently fuel-gauge release failure
and shutdown. Keep existing limits until evidence supports a change. For long
charging runs, the user monitors; resume agent work on completion, fault or a
useful independent implementation task. No idle polling loops.

## Explicitly deferred

Cell-temperature sensor identification, calibration and thermal cutoff are a
separate milestone. Keep experimental charging supervised while this protection
is unverified. Wi-Fi, GUI, modern-kernel work and security audit are tracked in
[ROADMAP.md](ROADMAP.md), not prerequisites for this battery checklist.
