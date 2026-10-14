# Experimental battery support

MKTEL M39 / MT6328, BL-25BI3.7V2500mAh, label maximum4.2V.
**Charging reliability is unresolved.** The latest completed charging trial on
kernel #22 aborted at uptime815 on a fuel-gauge release timeout. Charger OFF
was verified. The charging-off1599-snapshot pass does not supersede this failure.
See [acceptance checklist](BATTERY-MILESTONE.md) and [priorities](ROADMAP.md).

## Current limits and open failure

Nominal300mA (actual amperage uncalibrated), hardware/software ceiling3.9V,
4-second hardware watchdog, nonextendable kernel lease,1770-second controllers
and190-minute broker budget. Faults verify shutdown and latch without automatic
retry. This is supervised experimental charging. Cell-temperature protection is
unverified; PMIC-die temperature is not battery temperature.

The release failure was `stage10 release_stage5 control0xc29`; a later read
found idle0x29. The candidate uses the remaining original30ms acquisition
budget for release confirmation instead of a separate5ms sub-window. Nine core
fault tests and seven adapter scenarios passed. That is a scheduling-delay
hypothesis, not a proven hardware fix. Actual release must still be confirmed;
expired/invalid samples and failed cleanup remain fatal.

Local image metadata, full-readback logs and `CURRENT-STATE.md` identify the
installed version and live test state. Preserve old images; never overwrite
an installed image's metadata with a candidate build.

## Verified behavior and limits of the evidence

- Physical terminal, battery-only operation and encrypted root/home persistence work.
- Three physical reconnect cycles passed on kernel #19; the latest version still
  needs sustained validation and its own final reconnect regression.
- Kernel #22 shutdown works on battery. With USB attached it starts a new USB
  charging boot; root/home remain locked and positive charging was observed.
- Cold-off USB insertion on #22 started positive charging without unlocking root.
  This verifies startup with an available battery, not deeply depleted recovery.
- Two #22 locked charging startups and root handoffs passed with one broker and
  controller active. A synced1MiB storage write/read passed while charging.
- Hardware watchdog expiry, manual stop and real fault shutdown were verified.
- Backlight idle reduces load and is installed for future root startups; that
  automatic next-boot path and physical wake still need final regression.

Actual3.9V cutoff/hold/recharge, calibrated current/taper termination, automatic
low-battery shutdown and depleted-battery recovery remain incomplete. No percentage
or full-charge claim is inferred from voltage. Temperature is a separate deferred
milestone; completing the non-temperature checklist would not establish unattended
charging suitability.

## Ownership and transitions

| Component | Responsibility |
| --- | --- |
| Boot/root startup | Starts one broker; respects manual-stop and fault flags. |
| Broker | Target/recharge policy, segment budget and rest; calls explicit arm/stop. |
| `m39-charge` | Validated arming, watchdog test and serialized manual stop. |
| Plug service | Supervises one controller per connected charging session. |
| Pulse controller | Current/voltage/input guards, watchdog refresh and verified cleanup. |
| Kernel | Exclusive expiring charger lease; separate vendor dispatch/gauge locks. |

Unlock waits for old startup/broker/service cleanup before switching root. The
new root starts its broker only if manual cancellation permits. Fault/manual
flags survive this handoff. An explicit broker `--run` is fresh opt-in revalidation;
`--startup` never clears a fault. Never overlap USB clients or charging owners.

## Commands and reporting

On the phone: `m39-battery-status`, `m39-charge status`, `m39-charge stop`,
`m39-poweroff`, `m39-screen on 30`, `m39-screen off`.
`m39-charge arm` starts the legacy bounded service; normal experimental startup
uses `/usr/local/libexec/m39/m39-charge-broker.sh --startup`.

Status rejects stale/foreign process records and uses existing broker ADC readings
for idle voltage/input presence. It adds no ADC reader. Signed current is raw,
uncalibrated; percentage, full and cell temperature remain unavailable.

The optional `m39-low-battery-monitor.sh --observe` consumes this status and writes
`/run/m39-low-battery.json`. It cannot power off or change charging. Three distinct
low readings with USB absent produce `shutdown_recommended`; stale data/USB reset
the debounce. Candidate3.4V cutoff needs independent validation. Automatic
low-voltage shutdown is **disabled**. This observer is not low-battery recovery.

## Immediate validation sequence

1. Install/readback-test the release-budget candidate; verify boot, locked charging
   and encrypted handoff. Do not declare the release failure fixed from boot alone.
2. Complete a1770-second charging segment and clean transition without gauge faults;
   repeat on another boot and physical reconnect before calling it dependable.
3. Verify actual target cutoff/hold/recharge independently. Establish current/taper
   calibration before higher-voltage/full-charge work; CV detection alone is insufficient.
4. Validate low-battery shutdown/recovery and the remaining checklist regressions.

During long trials the user monitors. Check at completion, fault or explicit request;
no idle agent polling. Preserve watchdog/current/voltage bounds and fault shutdown.

## Recovery

Preserve encrypted data, private eMMC/LUKS backups, keys and calibration partitions.
Manual-only rescue: `artifacts/alpine-m39-source-battery-reporting-aux.partition.img`,
SHA256 `0f98501b68365bc85c63f89f46b0e4a959ad460c17418c91515d6a318e04b9a9`.
Flash only the reviewed boot partition with complete readback verification.
Historical research in `analysis/CHARGING.md` is not current status.
