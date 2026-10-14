# Experimental battery support

MKTEL M39, MT6737M/MT6328, removable BL-25BI battery: label 3.7 V,
2500 mAh, maximum charge voltage 4.2 V. Normal-phone battery support is unfinished.
Battery temperature sensing is deferred; PMIC-die temperature is not cell temperature.

## Current limits

- Nominal charging setting: 300 mA. Actual amperage is not independently calibrated.
- Hardware CV ceiling and software target: 3.9 V. This is not a full-charge claim.
- Four-second hardware watchdog and independent, nonextendable kernel lease.
- Each charging controller runs at most 1770 seconds.
- Fresh ADC, input-voltage, regulation, PMIC-die and current-direction checks.
- Faults stop charging and do not automatically retry.

The default boot startup launches bounded experimental charging before encrypted
root unlock and again after transition to root. Its legacy service does not restart
a completed session while USB stays connected. The explicit validation broker
adds verified timed restarts and target/recharge policy, with an overall 190-minute
test budget. It is not integrated into boot and is not an unattended charging setup.

## Verified on hardware

- Alpine can run on battery and survive USB unplug/reconnect.
- Charging starts at the locked encrypted-root prompt.
- Software shutdown with USB attached returns to charger boot mode and starts
  charging while root/home remain locked. Cold-off USB insertion is still untested.
- Hardware watchdog expiry clears the charger enable gates.
- Manual stop verifies charger-off and releases the lease.
- The broker completed timed segments, stopped/released ownership, rested, then
  validated watchdog cutoff and started distinct controllers automatically.
- An ADC fault stopped the broker without retrying; charging-off was verified.
- Keypad-wake backlight idle reduces load: raw signed fuel-gauge counts increased
  from +216 to +485 with the display dark. These counts are not calibrated amperes.
- Encrypted root/home and persistence markers survived shutdown/reboot/unlock.

The current broker test was last observed charging at 3.792 V. Actual target cutoff,
hold and recharge have not yet been demonstrated on hardware. Several later timed
segments passed without the earlier ADC fault recurring; its cause remains unknown.

## Commands

On the phone:

```sh
m39-charge status
m39-battery-status
m39-charge stop
m39-charge arm
m39-screen on 30
m39-screen off
cat /run/m39-broker.json /run/m39-charge-status.json
```

`stop` also cancels pending startup and the explicit broker for this boot. `arm`
explicitly validates and rearms the legacy bounded service. The broker is launched
separately with `/usr/local/libexec/m39/m39-charge-broker.sh --run` for hardware
validation, after other coordinators are stopped and ownership release is verified.
Never start overlapping controllers or replace an executing shell script.

The status tool validates boot/process identity and sample freshness, rejects invalid
numeric records, and reports uncalibrated signed current counts. Percentage, capacity,
full-charge state and cell temperature remain unavailable; none are inferred from CV.

## Diagnostics and tests

ADC errors emit `ADC_ERROR stage=N` on stderr and never produce a valid sample:

| Stage | Failure |
| --- | --- |
| 1 / 2 | Identity read / unexpected chip |
| 10–12 | Clock state acquisition |
| 20–22 | Clock enable/readback |
| 30 | ADC trigger |
| 40–44 | Channel read |
| 50–54 | ADC ready timeout |
| 60 | Elapsed-time overrun |
| 70–72 | Clock restoration |
| 80 | Output write |

The acquisition deadline remains 30 ms. A charging-off test passed 1000 consecutive
snapshots. Host tests exercise the actual transaction's failure/cleanup paths and
actual shell broker/status scripts, including stale/future/foreign records, PID reuse,
cleanup failure, manual cancellation, timed restart, hysteresis and fault shutdown.
Simulation does not prove physical cutoff/recharge or calibration.

## Remaining work

1. Verify actual 3.9 V cutoff, hold and recharge against independent measurements.
2. Validate higher-voltage regulation and calibrated current/taper detection before
   implementing full-charge termination. The existing completion callback reports
   unsupported; CV detection alone is insufficient. Vendor current conversion needs
   board-specific sense resistance and offset, which are not verified here.
3. Verify low-battery recovery and cold-off plug-in charging end to end.
4. Integrate the verified automatic policy into encrypted startup and normal operation.
5. Calibrate charge percentage/capacity if reliable board/cell data can be established.
6. Identify/calibrate battery temperature sensing and implement cell thermal protection.

Temperature work is last per user preference. Keep experimental charging supervised
until cell thermal protection is established; voltage/current bounds do not supply it.

## Recovery

Preserve private eMMC backups, LUKS headers, keys, calibration partitions and boot areas.
The verified manual-only recovery image is
`artifacts/alpine-m39-source-battery-reporting-aux.partition.img`, SHA-256
`0f98501b68365bc85c63f89f46b0e4a959ad460c17418c91515d6a318e04b9a9`.
Artifacts/backups/credentials are excluded from Git. Flash only the checked boot
partition with complete readback verification; do not blindly reuse old flash scripts.
Local `CURRENT-STATE.md` and logs hold the latest device state and detailed evidence.
