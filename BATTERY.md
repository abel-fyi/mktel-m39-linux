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

## Native sampling update

A native ADC helper replaces the slow shell ADC transaction when installed.
Phone measurements took about 20 ms; complete controller guards took about
60–80 ms. A 256 MiB write to encrypted root passed with positive sampled fuel
current and no watchdog fault. The controller now tolerates isolated current
dips but aborts after three consecutive nonpositive samples. Reaching the
voltage ceiling during charging is a controlled stop, not a generic fault.
These fixes do not change the 300 mA/3.9 V/session limits. Automatic full-charge
termination, recharge policy and low-voltage recovery still require work.

## Charging-only boot shutdown

LK can boot Alpine with tag 9 (`LOW_POWER_OFF_CHARGING_BOOT`). With the vendor
`CONFIG_MTK_KERNEL_POWER_OFF_CHARGING` option enabled, the PMIC USB-removal
interrupt and battery thread explicitly shut down the system. This explains
a software shutdown path even while Alpine is running. The experimental
replacement kernel disables that charging-only behavior; low-voltage hardware
protection stays in place. Physical unplug/reconnect passed on kernel #16: boot ID stayed unchanged,
encrypted root/home stayed mounted, and session 2 restarted net charging.
The new unlock bootstrap also starts bounded charging before passphrase entry.

## Ceiling characterization

`m39-charge-ceiling-test.sh` is an explicit supervised test, not a boot service.
It runs at most three existing bounded 300 mA/3.9 V sessions, with a 60-second
pause between verified timed completions and a 95-minute outer limit. Faults,
unplug/manual stop, changed controller identity or unverified cleanup stop it.
A voltage cutoff stops it too. It does not implement normal automatic recharge
or claim a full battery. State and logs remain under `/run` on the phone.

Kernel #17 with debug-only PMIC access logging completed three consecutive
30-minute sessions without a watchdog/charger fault. Final voltage was 3.606 V;
charging stopped at the test time budget and shutdown was verified. The 3.9 V
ceiling was not reached, so cutoff/recharge behavior remains unverified.

`m39-battery-status` reports charging only from a fresh matching-boot record,
a live controller and positive raw fuel current. It rejects stale/malformed
records and never translates voltage into percentage or claims a full battery.
Percentage/full/cell temperature remain null pending verification/calibration.

## Shutdown charging test

Software power-off with USB attached returned automatically to charger boot mode
(tag 8), with encrypted root/home still locked. A live bounded controller reported
3.600 V and positive fuel-gauge counts. This verifies charging after that shutdown
path; cold-off USB insertion and depleted-battery recovery remain unverified.

An experimental automatic policy broker is staged but disabled. Integration tests
cover cutoff/hold/recharge hysteresis, unplug/reconnect, exclusive ADC access and
fault shutdown without retries. Hardware cutoff and recharge still need testing;
the prototype retains an overall time budget and does not provide full charging.

## Automatic broker guard validation

The disabled broker rejects stale or future-dated records, foreign boot/controller
identities, reused PIDs, unverified shutdown and changed voltage limits. Actual
shell integration tests also cover clean timed restart and operator cancellation.
Checks use explicit failure exits: `set -e` alone does not reject every failed
command in an AND list. These changes do not alter the active charging limits.

## Full-charge detector work still required

The local vendor source exposes a CV detector at CHR_CON2 (`0x0f4c`), bit 6;
CV detection alone does not prove full charge. The linear-charging implementation
uses repeated calibrated charge-current readings for termination. Its current
conversion uses sense-minus-battery voltage, a measured offset and a board-specific
sense resistance. Neither that resistance/offset nor fuel-gauge amperage conversion
is verified for this board. Thus raw counts cannot yet define a termination-current
threshold. Next validate the 3.9 V cutoff against an independent meter, characterize
CV/taper and current calibration, then implement and test full-charge termination.
The existing higher-level completion callback deliberately reports unsupported.
