# Experimental battery support

Target: removable BL-25BI, MT6328 charger, native Alpine. Temperature sensing
is deferred. This is a bounded engineering setup, not unattended/full charging.

## Policy

- Nominal 300 mA; hardware CV ceiling 3.9 V.
- Hardware four-second watchdog and nonextendable kernel lease.
- Session ends within 30 minutes, at the voltage ceiling, on unplug, or on fault.
- Fresh voltage, PMIC-die temperature and fuel-gauge checks remain enabled.
- PMIC-die temperature is **not battery temperature**.
- No automatic replay after a completed/faulted session while USB stays connected.
- Reconnect starts another bounded session while the service is armed.

The optional `--bounded-charge-startup` image arms after stable external power,
validates watchdog cutoff, then starts the service. Low voltage, an already
reached ceiling or failed validation prevents startup. Manual-only images keep
charging off until `m39-charge arm`.

## Commands on the phone

```sh
m39-charge status
m39-charge stop  # also cancels pending automatic startup for this boot
m39-charge arm   # explicitly rearms after a stop
```

Status distinguishes the time limit, voltage limit, unplug and faults using
matching boot/PID and verified charger-off evidence. A voltage cutoff does not
mean the battery is full. Percentage/capacity remain unavailable.

## Recovery and persistence

Keep the verified manual-only image
`artifacts/alpine-m39-source-battery-reporting-aux.partition.img` locally.
SHA-256: `0f98501b68365bc85c63f89f46b0e4a959ad460c17418c91515d6a318e04b9a9`.
Backups and images are intentionally excluded from Git. Flash only the checked
boot partition, verify the complete readback, and preserve eMMC boot areas and
calibration partitions. Historical generated flash scripts contain exact image
hashes and must not be reused blindly.

## Deferred

Battery temperature sensor identification/calibration, cell thermal protection,
4.2 V full-charge termination, percentage/capacity calibration and unlimited
unattended charging. These are not prerequisites for the explicitly limited
experimental baseline, but remain required for normal-phone battery management.

## Current validation

Installed experimental startup image:
`alpine-m39-battery-experimental-unplug.partition.img`, SHA-256
`401be1b2493107a5a5f8f4ed2982b8ae4c0d927150c5f02f086118f6d5e41856`.
Full boot-partition readback matched. Software reboot returned Alpine;
startup passed the hardware watchdog-cutoff test and started net charging.
`m39-charge stop` reported matching-controller cleanup, released the lease,
removed runtime locks and read back both charger gates off.

Host tests cover low voltage, voltage ceiling, startup cancellation/failure,
regulation faults, stale completion records, time/voltage outcomes and service
connect/disconnect/no-replay behavior. Physical unplug/reconnect passed on the startup image: Alpine stayed on,
the boot UUID was unchanged, cleanup verified charging off at113mV USB input,
and session2 resumed net charging. The follow-up image booted with the same kernel, passed its watchdog test
and corrects unplug classification; host fault tests verify it does not hide unrelated failures. Original recovery kernel/DTB are unchanged.

Build with the existing separately acquired inputs:

```sh
python3 tools/build-source-boot.py --name alpine-m39-battery-experimental-unplug \
  --dtb analysis/boot-base-m39-backlight.dtb --initcall-trace \
  --charge-tools --bounded-charge-startup
python3 tools/verify-source-boot.py artifacts/alpine-m39-battery-experimental-unplug.json
```

Omit `--bounded-charge-startup` to build the manual-only variant.
