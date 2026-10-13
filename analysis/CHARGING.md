# M39 charging investigation — 2026-10-12

The integrated MT6328 charger can now be enabled, observed and disabled from
both the download agent and the running Alpine 3.18.79 kernel. This is a tested
engineering interface, not finished automatic charge management.

The working binary kernel selects a nonresponding BQ24157 external charger.
Its recovered symbols contain no integrated-PMIC charger fallback. No firmware,
partition or persistent startup changes were made during these latest tests.

## Control sequence that resolved the readback failures

`CHR_EN` must be enabled with `CSDAC_EN` still off before configuring and
checking `HWCV_EN` and `CSDAC_MODE`. Both fields failed to retain writes when
CHR_EN was off. Staging the main gate made both retain their values. Then the
current DAC can be enabled. Do not assume that staging guarantees zero physical
current: automatic charger behavior remains incompletely characterized.

The tests first set the nominal 200 mA current code and 3.775 V CV code, enable
CV/current sensing, verify overvoltage protection, configure the four-second
watchdog and use a fresh-ADC software cutoff at 3.45 V. They require physical
supervision with a cool battery. ADC clocks are restored after every sample.

The PMIC sysfs interface needs complete five-byte read selectors and ten-byte
write requests. Buffering requests and copying them into sysfs avoids split
writes that the vendor handler rejects. `InstatVolt` was cached: use direct
AUXADC conversion requests for the diagnostic cutoff.

## Evidence

- DA watchdog expired at approximately 4.23 seconds without refresh: f66 became
  5 (watchdog output set), f48 became 99 (both enable bits cleared), and battery
  voltage dropped. `charger-watchdog-validated-result.json` preserves evidence.
- Linux reproduced that hardware cutoff; `../logs/charger-linux-watchdog-test.txt`
  records flag 5, control 99, exit 0 and verified cleanup.
- A supervised Linux minute refreshed the watchdog, retained the conservative
  configuration and completed with cleanup/exit 0. The first six charging
  samples averaged 3.338 V; the last six averaged 3.344 V. Sense readings were
  consistently above battery readings. The later off-charge reading was
  3.297 V, so significant retained charge gain has NOT been established.
  See `../logs/charger-linux-supervised-minute.txt` and
  `../logs/charger-linux-after-minute.txt`.

## Tools and current limits

`../tools/da-pmic-pulse.py` and `../tools/m39-pmic-pulse.sh` default to a diagnostic
plan, never automatic charging. The native script supports short pulse,
watchdog validation and a supervised minute. The minute requires a watchdog
validation marker under /run for the current kernel. /run is temporary.

Battery temperature sensing is still unverified. The PMIC temperature sensor
is not a battery sensor. Full-charge CV behavior, termination, real net charge
rate, battery health, unplugged operation and safe automatic startup remain
unvalidated. Do not configure unattended charging from these test scripts.

The original bootloader can also precharge a low battery on the wall charger;
that observation does not demonstrate full-charge regulation or termination.

## Net charge direction — subsequent tests

The later signed fuel-gauge measurements changed the interpretation of the
200 mA tests: the charger supplied current, but the battery still showed slight
net discharge. With charging off the raw signed reading was about -700; at the
nominal 200 mA setting it was about -55. At the nominal 300 mA setting it became
+222/+225. A full minute at 300 mA retained positive readings in every sample
(range +205 to +252), with a stable USB supply and PMIC temperature below 30 C.
Thus 300 mA has demonstrated net charging under this diagnostic workload.

These are raw signed counts, not calibrated milliamps. The read protocol was
verified against the actual running kernel disassembly: FGADC_CON0 (ca4), upper
byte command 0200, latch-ready bit10, current field 773 mapped to cb2, clear0800
then0000. Values above32767 decode as raw-65535 (discharge). The script requests
and releases the measurement latch and preserves the low control byte; it
refuses an already-busy gauge. No gauge reset or charge-counter reset is used.

The native diagnostic now accepts nominal 200 or300 mA, plus a supervised
five-minute mode with the same conservative cutoff and watchdog. Further host
edits require positive fuel-gauge direction during extended runs; they are not
yet uploaded while the earlier five-minute script is executing. No startup
service or full-charge policy has been installed.

## Five-minute net-charging verification

The five-minute 300 mA run completed with exit 0 and verified charger-off/profile
restoration. All 170 charging samples had positive signed gauge readings
(+194..+556). The first six charging samples averaged 3.286 V and the last six
3.321 V. With charging off under the running Linux workload, voltage was
3.223 V before and 3.264 V after. USB stayed at least 5.033 V; PMIC temperature
was about31 C at completion. This demonstrates net charging under the tested
workload, not full-charge behavior or calibrated battery capacity.

Evidence: `charger-five-minute-summary.json` and
`../logs/charger-linux-300ma-five-minutes.txt`. The updated script with a
positive-net-current check for extended runs was uploaded AFTER this completed
run. Nominal300 remains the maximum supported native diagnostic setting.
The USB configuration advertises500mA; do not assume arbitrary higher input
current is available. No permanent charging service is installed.

## Native fuel-gauge reader reliability change

The previous extended recharge stopped after approximately12.5minutes because
its shell-operated fuel-gauge latch timed out. Charger-off and profile
restoration were verified. The kernel also controls that latch; interference
is plausible, but the old log does not establish the cause. The user later
measured3.36V with the battery removed.

`../tools/m39-fg-sample.c` replaces the multi-process shell gauge transaction.
The helper is a3.3KB freestanding AArch64 executable, built by
`../tools/build-m39-fg.py` with the existing AOSP compiler. It writes only gauge
measurement request/release commands. It never resets the charge counter,
changes calibration, controls charging, or accepts a stale sample after a
failed request. An already-busy gauge is left untouched. A lost ready flag is
rejected; acquisition can retry up to three times within a30ms window, with
bounded release cleanup. Blocking sysfs I/O is not a hard real-time guarantee,
and no exclusive lock against the kernel is claimed.

Six host fault-injection checks cover contention, permanent busy/timeout,
failed I/O/release, identity mismatch and preservation of configuration. Fifty
consecutive samples passed on the phone. A native watchdog test then showed
negative gauge direction with charging off, positive direction at300mA, and
negative direction again when the watchdog automatically cleared the enables.
The controller now requires this helper and retains its existing fail-closed
policy. An extended hardware run is still in progress; do not claim the
intermittent issue fully resolved until longer validation completes.

## Native-reader extended run outcome

The next run reached the conservative3.45V software cutoff after about9.85
minutes. All344 charging samples had positive signed current and no gauge
acquisition timeout was reported. Cleanup verified charging-off and restored
settings. Fresh off-charge voltage afterward was3.376V, versus3.341V before.
This is a successful bounded recharge; it does not demonstrate a full charge,
battery capacity/health, or eliminate every intermittent measurement race.

The older failure happened around12.5minutes, so this shorter cutoff-limited
run is not a duration-matched reliability test. Source fault injection and
this hardware result support the change without proving indefinite operation.
Evidence: `charger-native-helper-recharge-summary.json` and
`../logs/charger-native-helper-phone-recharge.log`.

Next physical check: battery disconnected from phone, middle-to-minus resistance
before and after five minutes of gentle palm warming. No calibration change or
fake fixed temperature is justified until the pin behavior is established.

## USB-dependent shutdown investigation

The actual3.18.79 binary charger command table was recovered: command17 maps to
`charging_set_power_off`, which calls `kernel_power_off`. The binary's
`do_chrdet_int_task` checks its stored platform boot mode against8/9 before
issuing that shutdown command on its charger-removal path. This is stronger
than relying on the older reference kernel alone. Runtime boot mode is still
needed before attributing this phone's particular unplug event to that path.

`../tools/m39-boot-state.sh` reads the numeric boot-mode attribute or the
bootloader's atag metadata. It never writes boot mode. The charging-mode USB
console patch changes only local USB decisions; it does not globally change
boot mode or remove shutdown protection.

The next supervised experiment uses the same nominal300mA setting and
configured3.775V hardware CV value, with a3.60V software cutoff and a30minute
limit. This explicit mode is for gaining enough charge for a battery-only boot
test, not full charging or unattended startup. Previous modes retain their
3.45V cutoff. Temperature sensing remains unverified.

## Normal boot and remaining automatic-charging blockers

Battery-only cold boot succeeded and the user confirmed five minutes of stable
Alpine operation. Reconnecting USB revealed boot mode 0 (normal), independently
confirming this was not a charging-mode startup. The fresh gauge still showed
net discharge: USB reconnection alone does not enable the integrated charger.
Two additional 30-minute bounded runs completed with verified charger-off;
latest off-charge voltage was 3.470 V. No full-charge or capacity claim follows.

Read-only normal-mode inventory (logs/normal-boot-thermal-inventory.txt) exposes
battery, CPU, PA, PMIC and connectivity zones. Battery remains 44 C from the
same contact conversion; CPU/PMIC readings are not battery temperatures.
PA/connectivity readings were invalid. No independent exposed cell sensor was
found. Original M39 overlay has no battery calibration override; merged battery
nodes have no pull-up/thermistor properties. Thus no discovered DT calibration
can simply replace the donor's conversion. Fixed identification resistance
remains plausible, not proven.

The donor power_supply uevent falsely reports Charging/Good despite real PMIC
gates being off and fresh gauge current negative. Percentage, current calibration
and health labels remain unvalidated. tools/m39-power-status.sh avoids those
claims, reads actual enable/watchdog bits and the reviewed native gauge helper,
and labels cached voltage explicitly. Uploaded and hardware-tested successfully;
logs/normal-boot-power-status.txt records both gates off and signed raw -656.
It never writes charger configuration, enables charging, or installs a service.

The previously built correct-charger source kernel remains unbooted. A header
comparison now confirms matching ARM64 text offset (524288) and flags (0), so
those header fields do not explain its earlier failed boot. Evidence:
kernel-boot-header-comparison.json. Retrying source bring-up needs usable early
boot evidence and a verified rollback; no new kernel flash was done here.

No automatic or full-charge service is installed. Remaining work is correct
charger integration, cell temperature sensing/calibration, CV/termination and
battery-health validation. Do not invent a constant cell temperature or equate
PMIC temperature with cell temperature to bypass these uncertainties.

## Source-kernel bring-up succeeded

The diagnostic markers identified mrdump_mini_init as the failing initializer.
Recovered printk RAM confirmed an ARM64 alignment fault in strncmp reading the
reserved crash-dump header. remap_lowmem used pgprot_noncached, which this
architecture maps as Device-nGnRnE. The fix uses normal noncached RAM via
pgprot_writecombine and checks allocation failure before dereferencing the
header. Crash-dump support remains present. The legacy Kbuild saved-command
hash escaping also needed correction; shared-header regeneration still caused
this round's broader rebuild. KBUILD_NOCMDDEP=1 was used with unchanged compiler
flags; source/header dependency checks were retained.

The written image and full boot partition readback match SHA256
2fc1bf9061054c66ca8b69abd460173643e07b125fc920207d6f6d80b5d9ea51.
User saw green marker followed by Alpine. USB verifies
3.18.19-m39-diagnostic+ #4 and boot ID915198f5-36a2-47ab-913b-b14afe728991.
The source integrated MT6328 driver now runs. Charging remains deliberately
inhibited: f48=99, main/current-DAC gates off, fresh FGraw -678, cached3461mV.
Evidence logs/source-mrdumpfix-first-boot.txt and source-mrdumpfix-live-pmic.txt.

Remaining donor defaults MUST be corrected before enabling charging:
- Actual included mt6735/mach/mt_charging.h unconditionally defines
  HIGH_BATTERY_VOLTAGE_SUPPORT; low5 f4e=22 configures4.35V, unsuitable for
  the user's labelled4.2V cell. HardwareOV f54=7. Gates currently OFF.
- CONFIG_MTK_DISABLE_POWER_ON_OFF_VOLTAGE_LIMITATION=y causes the actual included
  mt_battery_meter.h to define FIXED_TBAT_25. Live250 means hardcoded25C,
  not a repaired sensor. Do not use it as thermal evidence.
- Source battery thread continues writing its profile while gates are OFF.
  Do not run the earlier userspace recharge controller concurrently: the
  kernel can overwrite its conservative limits. Fix/coordinate the source
  policy first and keep the independent watchdog and cutoffs.

New bootability does not validate cell temperature, full charging, termination,
capacity or health. No GPT/preloader/other partition writes were performed.

## Corrected limits and bounded charger ownership verified

Source kernel #7 boot af45d6cf-e30a-4f67-b81b-32dee81c464b now runs.
Image SHA2560df499bf60d14a55957712c1011b7cdde6eecb2a9adbcc310065762213429f0e
was fully readback verified. Hardware f4e low5=3 means3.9V CV, f50=13 means
nominal300mA, f54=5 selects4.3V OV with protection enabled. Fake fixed25C is
removed; converted470 is still unvalidated and not an actual temperature claim.

The root-only kernel m39_owner_seconds parameter grants exclusive access to
reviewed userspace diagnostics for at most1800s. The lease itself never enables
charging. It rejects active-lease extension and grants only from OFF with the
reviewed PMIC/profile. Kernel driver profile/enable/watchdog mutations are
serialized and inhibited during ownership; reset/power-off paths remain active.
Expiry clears both charger gates; ownership remains inhibited/retries if OFF
cannot be verified. Scheduling is not hard real-time. Independent hardware
watchdog still applies. No startup/autonomous charging service is installed.

Hardware checks: OFF-only3slease expired, duplicategrant rejected; fresh Linux
watchdog300test showed positive current then cut both gates and negative current
without refresh; one-minute recharge completed positive/stable and released
ownership; active12slease expired while charging, kernel reported OFFverified1,
controller rejected expiredlease and verified cleanup. That expected abort was
intentional, not a failed charger. Evidence logs/charge-owner-expiry-test.txt,
source-charge-owner-watchdog.txt, source-charge-owner-minute.txt,
source-charge-owner-active-expiry.txt.

NOW ACTIVE supervised recharge toward3.9V: controller6743, bootaf45d6cf..., initial
OFF3326mV, ON3385mV FG+198. Currentnominal300, CVcode3/hardware3.9V, software
cutoff3900, controllerlimit1770s inside1800skernellease. Four-second hardwareWD,
fresh voltage/USB/PMIC checks, positive net gauge and fail-closed cleanup.
Watcher logs/source-charge-3900-watch.txt and logs/charger-recharge-status.json.
KeepUSBconnected and observe. Full-charge/termination/cell sensing/health remain
unvalidated. Do NOT claim this is unattended charging or calibrated capacity.

## Backlight drain investigation, prepared during charging

The M39 overlay supplies led_mode2 (GPIO callback mode) with numeric data1 for
LCD/keypad/button LEDs. This source driver treats data as a function pointer,
so writing brightness on the current kernel can invoke address1. No brightness
write was attempted. Cached255 does not establish actual PWM brightness.

Verified LK backup SHA41780ba85a06f8e428d23309d2ade5e3b1063fcdd47914d2d83439a502081290
contains LCD descriptor callback41e001bd, keyboard41e00195, button41e0016d.
Thumb disassembly proves LCDGPIO69, keyboard42, button5; nonzero=on, zero=off.
GPIO69 directionregister10211020 bit5 andoutput10211120 bit5 exactly match
source gpio_cfg.h DIR/DATAOUT mappings. Backlight is binary, not PWM dimming.

Prepared tools/prepare-m39-backlight.py: known callbacks enabled only by explicit
m39,verified-lk-gpio DT markers matching exactLED/pin pairs. Callback refuses
unexpected mux/direction, preservespinconfiguration, writesoutput andchecks
readback. Invalid low/numeric callback values are rejected. MarkedbaseDTB
boot-base-m39-backlight.dtb merges original overlay successfully, properties
persist. No DTBO orotherpartitionwrites. Buildsource-backlight-final-build.txt
completed; objectincludescorrectunsigned64bitcallbackaddressguard.

Packaged alpine-m39-source-backlight.partition.img (NOTFLASHED); SHA:
c886cb2dcbd45c94511506e7d0ff1d0c5db8fe63d8063bb8e07258ead165dd0f
Uses existing source charger ownership/limits unchanged. Next after userreports
charge stop: checkOFF/lease0/savecurrentlog, theninstall/readback/boot newimage.
Announce screen-off test before writingbrightness; timedrestore and FGcomparison
will verify physical control and drain reduction. Charginground4 remainsmanaged
byexistingcontroller; userrequested rootNOTpollchargingwatcher, respectthat.

HAL FG calls are not serialized against the diagnostic latch; possible contention
is an investigation lead, not established cause of round2. Hostcontroller now
adds GuardStart/GuardEnd to identify slow sampling beforeWDcutoff. Updatedhost
script testedsyntax/cleanup3tests, NOTuploaded overrunningcontroller. No safety
checks weakened. Temperature sensing/unattended charging remainunfinished.

BACKLIGHT FIX LIVE VERIFIED kernel#10 boot058887b2-8d7e-4fd2-a4de-02431f2ca7a8.
Software-onlyupload/write/fullreadback/reboot pathSUCCESS nohumanreset needed.
NewkernelGPIOon smoke result0; timed15sofftest userconfirmedblackthenreturn.
KernelGPIO69request0/1 bothresult0 andsamebootID throughout: NO reboot.
FGsteadyONavg-571.25 raw; OFFavg-317.0 raw, ~44.5% lowerdischarge signal.
Excludefirsttransitionreadperphase; uncalibratedrawcounts, notclaimedmA/capacity.
Evidence logs/backlight-direct-power-test.txt, analysis/backlight-direct-power-summary.json.
Currentbacklight restored255/on; chargingOFF/lease0. Rootcancontrolscreen/reboot
andupdateBOOTfromRAMroot withstronghash/blocklayoutchecks, physicalDAfallback
onlyforunbootable/unresponsivekernel. NoGPT/storagechanges.
Next controlledchargewithbacklightoff toverifyincreasednetcharge, freshthisboot
WDmarker needed. Updatedhostcontroller timingfields notyetuploadedonnewboot.
Usecurrent#10 rollback artifactsource-backlight-direct SHAf265...; old#7 fallback
stillavailable. Drivernormalautocharge/temperature/terminationunfinished.

SCREENOFF RECHARGE ACTIVE kernel#10 boot058887b2-8d7e-4fd2-a4de-02431f2ca7a8.
FreshWD300testonthisboot passed exit0/off/lease0; newnativecontrolleruploaded.
NativeoptionalM39_RESTORE_BACKLIGHT=255 validatedonlywithbootID marker/run/
m39-backlight-validated; cleanuprestoresbacklight evenabort. No chargelimit
changes, 3cleanupchecks+syntaxpass. Actualrestorationoncompletedrunstillpending.
PID1070 lease1800/controller1770/CV3.9/max3900/current300; initialOFF3440.
ChargingscreenON FG198/216 mean207; screenOFF FG477/470/486/472/464 mean473.8,
~2.29x netcharging signal atsamecurrentlimit. NotcalibratedmA. GPIO69offresult0.
ScreenwillstayOFF duringrun, LinuxUSBstillalive, restore255atcleanup. Background
watch89921 logs/backlight-off-recharge-watch.txt; usermonitors, rootDO NOTpoll.
Next userreportsstop: stop/off+lease0+screenrestored verify, save/hashlog andfresh
OFFvoltage. Newhosttimingfieldsuploaded; everyguard~0.46s, loop~1.6s duringtest.
Documentationcomparisonanalysis/backlight-off-charge-comparison.json. No more
physicalresetneededfornormalsoftwareupdates; current#10liveupdate proven.
Noautochargeservice/temperaturevalidation/fullterminationdoneyet. Keepbattery
priority; noLinuxstorageworkuntiluserasks. 3.9targetnotprerequisiteforprogress.

SCREENOFF recharge1070 COMPLETED1770sec EXIT0, watcher89921ended0. OFFverified,
lease0, brightness255 restoredautomatically. LastON3554 FG+486; freshOFF3472
vsinitial3440 (+32mV), butOFFsampleuptime2210 taken224sAFTERstop1986 withscreenON.
Do notcomparevoltagegain directlyascalibratedchargeamount orinferhealth.
Log198095B downloadedverified SHA
269f177dcb7570742bdd37aab705c1d5336817aba14209917e2720b3fcdee4d9.
Summaryanalysis/backlight-off-recharge-summary.json. Current#10 boot058887b2,
USBconnected, screenON, noactivecharge/lease/watch. Nofault/rebootduringtest.
UserdoesNOTwantwaitingfor3.9; continuebatteryengineering/power/plugbehavior,
notjustrepeat30mincharging. NormalselfagentliveBOOTupdate+reboot proven.
Temperature/calibratedcurrent/capacity/charge termination/normalautocharger
unfinished. Don'tstartLinuxstoragework. Hosttimingdiagnosticsnowtestedactive.

PLUG/UNPLUG HARDWARETEST PASSED currentboot058887b2-8d7e-4fd2-a4de-02431f2ca7a8.
UserconfirmedAlpineSTAYSONduringUSBunplug10s; reconnectlistener confirmsSAME
bootUUID/service11549/session2 newchild16909, activepositive216/235 rawcurrent,
ON3520/USB5043/PMIC31.263C/gates123/WD1. Normalmode0 softwareboot supports
batterycontinuity withoutchangingglobalbootmetadata/shutdownpolicies.
Prooflogs/plug-service-hardware-reconnect.txt and disconnect-cleanup.txt.
Plugtestservice remainsARMEDtemporaryRAM/currentboot only, activechargechild16909.
It stops onpowerloss/end/cutoff andwon'tauto-repeatwhileplugged. Sessionlimit
1770/lease1800 CV3.9/current300 unchanged. NOpersistentbootautocharger installed.
Afterreboot service+arm+helpersdisappear; needreinstall/arm untiltemppolicyvalid.
Nohostwatcheractive; usermonitorsonrequest, rootdoNOTpoll charging. Nextfocus
thermal/termination/calibratedcurrent and dependable integration; keepcharge
runningduringindependentwork, don'twaitfor3.9 orswitchtostoragewithoutuserask.
Rootcanstopservice kill-TERM11549 (cleanupstopschild/releaseslease). Current
installedkernel#10 artifactsource-backlight-direct SHAf26571239aa6d412926ab62fe8517f989dd2c8d7e4c0c023aafcb20629600e9d.

IMPORTANT PLUGTEST QUALIFICATION: previouschild11562 unpluglog reportsreadback
mismatch f74/f4e/f50 duringprofile-restoration, then"Charging disabled; someprior
settingscouldnotberestored". Do NOTclaimperfectcleanup. NativeOFFverifiedbefore
restoration, lease released0; nextsession16909 successfullyrequiredreviewed
3.9V/current<=300/OV/gatesOFF tograntlease, positivechargingconfirmed. Functional
sameboot/reconnectPASS, cleanuprobustnessunfinished. PossibleTERMin-flightADC
subprocess/sysfsselector race vsregisterretentionwithoutVBUS; causeunproven.
Next implementcooperativestoprequest/graceperiod (avoidkillingnativewhilechild
ADCtransactionsstillrunning), preserveOFF-first guards anddon'tignoreprofile
mismatches. Nochangesyet toactiveservice/controller; keepchargingduringofflinework.

Cleanupdiagnosiscontinued: cooperativeactualunplug STILLrestorationerrorsf4e,
f50,f62 thoughOFFverified/newsessionpassesprofiles. NotjustTERMrace; causeunknown.
RootfoundPMICsysfs ignoresparse/transportret and returnsbytecountalways. Prepared
sourcefix tools/prepare-pmic-access-errors.py: propagateparsefailure/EIOnegative,
onlypublishsuccessfulread (no stalecache acceptedafterfailure). Actualhandler
hostmocktest tools/test_pmic_access_errors.py passedread/writefailure+badinput.
Addednativefield mismatch diagnostics expected/actual/raw/mask/before.
Kernel#11 BUILT+liveBOOTwrite FULLreadbackverified SHA
53ddffd156c2a5d1f499b432cc339296a2455febfa1d3d82370da5c8bb3dcff6.
Software reboot successful NEWboot6e49e4e2-996d-4bdf-a501-1c0615ce97b9 MODE0.
No physicalresetneeded/noGPTwrites. CurrentPMICprofile/CV/currentboundsunchanged.
Captured TRUEwatchdogstop beforeupdate inoldservicecharge: guard3872.85->3876.34
(3.49sec), plus1secsleep exceeds4s; hardwaref4899/f665, FG-623, ABORTChargerStopped.
Log54420B downloadedverified SHA73f5b3353052da17cdecd0793cd7878b0e8c4eef6ae3251bb0d207bb122103a6.
This establishescauseofTHATstop, notretroactiveproofround2. Nativecontrollernow
refreshesWDafterlease/gates/4secprofile/CV/current/modechecksBEFOREfreshADC,
keepsallpostmeasurementchecks/positiveFG requirement and4sWDCUTOFF unchanged.
HostinjectedfaultchecksverifyNOKICKwhenlease/gate/WD/timer/CV/current/modeinvalid
orstoprequested; cleanup3checks+syntaxpass. FreshWDhardwaretest on#11RUNNING
logs/pmic-errors-kernel-watchdog.txt; helper/controller/serviceuploadedverified.
No servicecurrentlyrunning/chargingonlyshortWDtest. Needtestexit0/OFF/lease0 then
armnewbootUUIDandstartservice, repeatphysicalunplug10/reconnecttodetailedreadback
cause. No temperature/termination/productionautochargeclaim. Usernearstanding,
nohostwatcher/polling. CurrentkernelflashCLIartifacts/live-update-pmic-access-errors.sh.

Actualunplugregisterdiagnostics showfieldsrevertstandby andwritesnotretained:
f74expected2 actual34 before34; f4eexpected3 actual13 raw205 before205 (4.2V
standby), f50expected13 actual15 before15 (70mA standby). No transporterror.
Cooperative stopdidnoteliminatethis. Current#11 typedAPI ensuresrealIOerrors
propagated, userwillingtest. Nativecleanupchanged: verifygatesOFF FIRST;
sourcekernelonlyfreshADC+clock-restorationchecked; ifVBUS<1000 leaveinactive
standbyprofile alone (no pointlesscharger-onlyrestoration). Poweredinput still
restoresall savedfields; unknown/failedpower measurement reportsfailure and
retainssettings. Lease release stillOFFverified; NEWleasealwaysrequireskernel
3.9V/current<=300/OV4.3/gatesOFF beforestart so standby4.2 cannotbeusedfortest.
ExplicitADCread/write/clockerrorsnowexit1 evenconditionalcaller/errexitdisabled.
Tests6cleanup scenarios andactualADChelperfaults(clock/enable/request/read/
restore) passed; shellsyntaxpass. tools/test_m39_adc_errors.py saved.
Oldservice1074 stoppedcooperativelyonpoweredinput; uploadednewcontrolleronly
whennotexecuting. Newservice15785 child15799 chargingpositive197 ON3523,
boot6e49e4e2 source#11; CV/current/WD/timelimits unchanged. Listener waits
logs/standby-cleanup-hardware-test.txt forunplug10/reconnect andoldsession1tail.
Don'tclaimhardwarefixpasseduntilinspect. No sourcekernelwrites/reboots thisstep.
CurrentBOOTSHA53ddffd... archived/liveupdateverified. Nohostchargewatcher/poll.

STANDBY CLEANUP HARDWARE PASS logs/standby-cleanup-hardware-test.txt. Oldchild15799
cooperative stopbeforeWDrefresh; freshUSB37mV, OFFverified, retainedstandbyprofile,
finished WITHOUTrestorationerrors. Sameboot6e49e4e2, service15785session2child26104
reconnectautomaticallypositive214 ON3521/gates123/WD1. No reboot/firmwarewrites
thisstep. User5%tokensremaining; newCURRENT-STATE.md concisehandoff created.
Activeboundedservice independentofchat, nohostwatcher/poll, nohalf-finishedflash.
Stilltemporary/currentboot/supervised; temperature/termination/calibration health
unfinished. Do notclaimfullyfixedbattery. Continuebatteryworknotstorage.

## Resumed session: bounded reliability result

Session2 completed1770s with clean OFF/restoration, no reported watchdog fault.
Archived verified log logs/source-charge-clean-session2.log and summary
analysis/source-charge-clean-session2-summary.json. Actual premeasurement
refresh fault fixture now saved tools/test_m39_watchdog_refresh.py: nine cases
passed (valid refresh and rejection of lease/gates/WD/timer/CV/current/mode/stop).
User physically reconnected; session3 controller19961 active, sameboot6e49,
3500mV positive224 raw, PMIC31.263C. No firmware modification this round.
OriginalLK loop0x1aad4..0x1abe4 shows low-voltage entry/exit near3450mV,
charger presence, input overvoltage/current checks. No cell-temperature check
established in that function; absence of temperature strings does not prove
absence of thermal checks in callees/hardware. Strings archived
analysis/lk-battery-strings.json. Temperature remains unresolved.

Sensor audit saved analysis/BATTERY-SENSOR-AUDIT.md and reproducible LKflag
recovery tools/audit-lk-battery-controls.py. No hardware/charging changes.
Source+historicalread show BATON_HTdisabled; do not blindlyenable it. Manufacturer
BL-25BIdocument confirmslabelratingsbutnotNTC/contact construction. No software
proof ofworkingcellthermometry found. Remain explicit about unresolvedhardware
evidence; do notfabricatetemperature orclaimnormalunattendedchargingvalidated.

## Stop-reason staging

Donor switch_charging.c charging_full_check rejects full below4100mV,
so it cannot establish completion at our3900mV diagnostic CV. No donor
full/recharge policy was enabled. Native controller now emits stop_reason
(running,time_limit,voltage_limit,stop_requested/unplugged,interrupted,
interval_limit,watchdog_test_complete,fault). Ceiling remains fail-closed
exit1 and cannot be confused with calibrated100% capacity. ADC/lowvoltage/
thermal faults remain faults. Cleanup phase/offverified remains independent.
Tests7guard scenarios,6cleanup,9WDfaults andADCfaultchecks passed.
NewcontrollerSHA e5e4582f31d640f4057281dadd980c2fea0cf5de7672656487daf986c89219ce
uploadedverified /run/m39-pmic-pulse.next.sh, notoverwrittenactivecontroller.
Standaloneinstaller /run/install-charge-controller-when-idle.sh waitschild19961
exit(up to1800s), checksboot6e49/OFFverified/lease0/nochildlock/targetSHA, briefly
freezesidle service15785 toexclude reconnectspawnrace, replacesRAMcontroller,
resumesservicewithconnectionlatchunchanged. NOchargingretry/firmwarewrites.
Runtime status /run/m39-controller-install.status initiallywaiting_for_controller_exit.
Do notclaiminstalleduntilstatusinstalled +actualcontrollerhashverified.
Currenthealthycharge continues. Installfailure reportsnot_installed andresumes
service; nochargecontrolwrite. Nextnewphysicalsessionwilluseupdatedscript.

## Source12 and persistent opt-in helper bundle

Source MT6328 completion getter previouslyreturnedOKwithoutwritingdata.
prepare-m39-charge-status.py now explicitlyoutputsFALSE/UNSUPPORTED; hostCtest
compilesactualgetter/callerwithfaultinjection. switch_charging.c callerhardening
wasalsoprepared, but THISbuild useslinear_charging.c (switchpolicyunselected).
Thus4100mVfullcheck finding applies toswitchpolicy, notcurrentactivealgorithm.
Linearpolicyreliesoncachedcurrent/timers; neitherisadoptedforoursupervisor.
Nativeautomaticcharge inhibitionretained. Buildsuccesssource12, baseline61warnings.

Bundled /usr/local/sbin/m39-charge [status|arm|stop] andhelpersininitramfs.
Noautoarming/startupchanged: original529archiveentriesincludinginit arebyte/
metadataidentical. Freshbootrequiresarm,whichperformsa200mA/3.9VhardwareWD
cutofftestunder60slease thenstartsbounded300mAplugserviceonlyonverifiedsuccess.
Thiscommand eliminateshosthelperuploadsaftereveryreboot; notproductioncharging.

Hardwarecaught directBusyBoxprintf60-to-ownersysfs returningexit1 DESPITE
installing60slease; exactwritefragmentationnottraced. Bufferedregularfile+cat
claim/release bothreturned0, verified60then0. AllownerwritesinCLI/controller/
servicechangedto bufferedcat. Initialfailedarm NEVERenabledcharger; noWDtest
logwascreated; leaseexpired/released. Noerrorignoredorautomaticretryloopadded.
Actualarm/stoptestpassedafterhotRAMfix:200mA WDflag5/gates99 after4s; cleanup
OFFverified/lease0. 200mA pulse reduceddischarge(-725->-81->-722), notnetcharge;
subsequent300mAsupervisedrunpositive199/210. CLIstopcooperative/OFFverified
reportedstop_requested andservice_stopped, exit0. Logs source-charge-tools-*.txt.

Finalbootbundlepersisted/16MiBfullreadbackverified: artifact
alpine-m39-source-charge-tools-buffered.partition.img
SHA4fdb42988992f457944de0318cb94a46fdde57d668d4f5fc025d1e2d55fcb446.
Secondsoftware-onlyreboot successfulboot1fe92e37-5256-4a3e-bb3e-0fae6bbfb680
normalmode0/source12. Installedhelperhashesmatchpackagemetadatawithoutuploads.
Freshperbootarmtestnowrunning; inspectlogs/source-charge-tools-buffered-persistent-arm.txt
oncecomplete. NoGPT/preloader/storagewrites. Source getterunsupportednotfakefull.

Stopreasonwatcherclassification nowusesexplicitreason, requiresOFFverified,
rejectscleanupfailure/contradictoryvoltage; backwardcompatibleolderlogs.
test_m39_charge_outcome.py passed. HostwatcherNOTstarted/rootdoesNOTpollcharge.
PendingoldidleinstallerwasRAMonly/lostonsuccessfulreboot; nopendingoldjob.

PersistentarmhardwarePASSboot1fe92:WDcutoffflag5/gates99/OFFcleanupverified,
ARMexit0. Newservice1056/controller1074/session1positive205at3504mV. Nohelper
uploadrequiredafterreboot. Hostreadonlyreconnectlistenerwaiting
logs/source12-helper-reconnect-test.txt; nohostchargewatcher. Nextuserphysical
unplug5/reconnect testmustconfirmAlpinestayson/sameboot/cleanupreasonunplugged.

SOURCE12RECONNECT hardwarePASS userreportsAlpinestayedvisible, sameboot1fe92,
service1056session2child5380 positive197at3512mV. OFF/standbycleanupverified
withoutrestoreerrors. QUALIFICATION: gatecheckbeatservice-stopflag during
unplug, logABORTChargerStoppedBeforeSampling; notwrongchargeenable, butreason
classificationcanreportfaultfornormalphysicalpowerloss. Do notclaimperfect
reasonhandling; pendinglabelraceimprovement. Newoptionalidle-screenprototype
compiled tools/m39-screen-idle.c +boundedwrapper; monitorsONLYverifiedmtk-kpd
event1 withoutEVGRAB, brightness0after10s/wake255onkeypress, exits/restores255
after120s. NoPMIC/chargeconfigwrites, noauto-start. Hosttransitiontestpassed.
Protohardwaretestnotyetstarted; runtimefilesuploaded /run only.

## Idle screen hardware validation and command packaging

Userconfirmed centreOKwokeAlpine. Nativeprototype logDARK->WAKE->DARK, same
boot1fe92, healthychargepositive479 at3536mV whilebacklight0. Thisrawsnapshot
isnotcalibratedmA/charging-speed proof. Prototypeexitedat120s/restored255.
Onlymtk-kpd/event1 ismonitored; ACCDET/event0 andhwmdata/event2 ignored.
NoEVGRAB/keyconsumption, PMICwrite, system-suspend, framebuffer/LCDregisterwrite.

Newconfigparser accepts5..600sidle and0..86400slifetime; defaults10/120 without
explicitconfig. /usr/local/sbin/m39-screen [on [seconds]|off|status] testedon60/
off/restore255. Defaulton60, optionalnotautostart. Nativeworker detectsparent
death andrestores255/exits. ActualhardwareSIGKILLsupervisortest showed0->255
within3s, workererror/restorelog, CLIstalelockcleanup exit0. Nochargecontrols
changed. Operatorstop/errorrestorealsoverified. Hostparser/transitiontestpassed.

New image alpine-m39-source-charge-screen-tools.partition.img built/validated,
SHAfbbb0ff7c83a03bb0912e40eeaf2370bc7cf25f09809d72c027bf585aaa2ed13.
Samealreadybootedkernel12; bundles6helpers, preservesoriginal529archiveentries
andinit unchanged. Helpers NOTautoarmed/autostart. UploadBOOTcandidateinprogress,
exact-current-boot update script artifacts/live-update-charge-screen-tools.sh
prepared but NOTyet executed. CurrentliveBOOThashstill4fdb4298... untilfull
readbackverified. Usernoactionneededforupdate/software-reboot. Thermal/full
termination/unattendedcharging remainunfinished.

CHARGE+SCREENbundle full16MiBBOOTreadbackverified SHA
fbbb0ff7c83a03bb0912e40eeaf2370bc7cf25f09809d72c027bf585aaa2ed13.
SoftwarebootPASSnewUUID89b421b4-ba2a-41ef-99f8-b9ec3f684eea normal0/#12.
Screenhelper/CLIhashesmatchmetadata AFTERreboot;6helperspersist/noautostart.
Freshread-onlyplanbaseline Battery3437mV/FG-728/PMIC30.679C, chargerOFF/lease0,
screenON. AgentneedsmeterGROSScrosscheck batteryremoved(nextphysicalstep).
Loadremoval meansvoltagecomparisonisnotprecisecalibration; do notadjustADC
gain basedsolelyonthisdifferentload/relaxationmeasurement. LatestbootNOTarmed
yet becauseactualbattery-outmeasurementnext. Afterreturnbattery/reconnect,
agentarm+screenon60 frombundledcommands, nohostuploadsneeded.

Usermeterbatteryremoved3.43V vsfreshADC3437mV underdisplayON/chargeOFF.
Grossagreement7mV; thisdoesNOTestablishprecisegaincalibration becauseload/
timechanged. NoADCscaleadjustmentmade, nohealth/fullcharge/temperatureclaim.
PrepareUSBreaderforbatteryreinstallation/reconnect andresume boundedservice.

## Source14 honest battery-reporting ABI verified

M39-only getter recognizesexacttag /odm/led@6 gpio69. STATUS/HEALTH=Unknown,
PRESENT/CAPACITY/batt_temp/TemperatureR/BatteryAverageCurrent unavailable
(-ENODATA). AuxiliarySMBproperties also unavailable (hardwaretestcaughtlegacy
phantom50% aftersource13; source14corrects). Rawvoltage/ADC/chemistryretained.
Hosttestcompilesactualgetter+detector, checksotherboardsunchanged/node-refbalance
andinternaldataunchanged. PublicreportingONLY; nointernalcharge/thermalchanges.
Kernelpower_supply_sysfs explicitlyskipsENODATAinudevevents; notanerror.
Actualhardwareueventverified allinvalidfieldsabsent, voltage3468mV retained.

CurrentBOOTsource14SHA0f98501b68365bc85c63f89f46b0e4a959ad460c17418c91515d6a318e04b9a9
artifactalpine-m39-source-battery-reporting-aux.partition.img, fullreadback/boot
verified UUIDf6f32551-dd95-40e4-9a23-c6b77122cb12 normal0. NoGPT/preloaderwrites.
Kernelbuiltincrementally, baseline61warnings. Sixpersistenthelpersunchanged.
Currentbootchargingnotarmedforbattery-only90stest. m39-screen on60started.
Independentlogger /run/m39-battery-log.sh waitsUSBremoval then90s samplesfresh
ADC/FG/brightness; onlyADCrequest/clockwrites, NEVERchargerconfig. Derived
fromreviewedhelpersbytools/build-battery-log.py; writefaulttestallowedADC and
rejectedalltestedchargerregisters. Pulse-lockexcludesarmingduringmeasurement.
Nochargerserviceactive/lease0 prerequisite. Minimum3300mV stop, noauto-retry.
Usernextactionunplug90s/centreOK/reconnect; logs /run/m39-battery-only.log.
Afterreconnect, inspectloggerdone/boot/voltage/currentdirection, thenarmand
resumecharge(withfreshhardwareWDtest) onlyafterloggerlockgone. Nohostcharge
watcher/modelpolling. Pendingloggerrequiresactualphysicalunplug; noflashpending.

USERPRIORITYREASSERTED: finishbattery100% beforeotherLinux/driverwork. Additional
90sdischargebenchmarkcancelled aslowvaluegivenexistingunplug/wake/powerproof.
LoggerTERMcleanupremovedpulse-lock; noADCmeasurementstarted/nochargeconfig
changed. Source14freshWDarmPASS; service1914/controller1931/session1 positive469
at3514mV, bootf6f32551normal0. Idle60sactive/off. Nohostwatcher/flash/buildpending.

SurvivingpreloaderPICstringxrefresolved: WaitForBatteryinserted caller0xdbc0;
batterycheck0xe9b0 prints"ignore bat check !" andunconditionallyreturns1.
Chargehelperoffsets0xea02/04/06 arebx-lr stubs. Presence-waitloopbypassed.
Disassembly/report analysis/preloader-battery-stubs.*. ThispreloaderisNOTproof
ofworkingfactoryprotection/sensorabsence; provenanceunverified afteroldROMflash.
Temperatureinput remainscriticalpathforfullyvalidatednormalcharging; nofuture
claimof100%functional/unattendedcharging without actualsensor/policy evidence.
Askedtypeofexistingwaterthermometer toseeifindependenttemperaturemeasurement
ispossible, notanotherrepeated"battery cool/areyouthere" prompt. Noheating
measurementrequesteduntilthermometercapabilityknown. Workonchargecompletion/
restart+protectioninputs whilehealthyboundedchargecontinues.

UseraskswhethermiddlecontactcouldbeNTCtoPOSratherthanNEG. TopologyNOT
established; performisolatedbatteryDCvoltagechecks BOTHreferencepairs before
anyohmstest. Ohmmeasurementacrossenergizedpairisinvalid. Chargingstoppedvia
CLIforactualphysicalmeasurement; inspectlogs/battery-contact-reference-stop.txt.
Metal-rodwaterthermometeravailable, butdonotwarm/repeatRuntilreferenceknown.

Researchcorrection:NTC-supportedBL25BIvariants documented. Actualpackunknown;
9.9k constant notproof ofID alone. Compiled47k/61.9k profile confirmed; exact
Rconversion18.028k at406mV matchesoldsourcecache. CandidateRp34k inferredonly.
Seeanalysis/BL25BI-RESEARCH.md forsources/limits. Activeexplicitresearchgoal.
UserserialZJ2024088888unmapped; no more repeatedthermal/resistance requests.
Currentboot aafc4e66...armPASSservice1014/controller1038 chargepositive205.
Researchchangedauthoritativedocumentation, notcode/firmware/charginglimits.
# Latest controller change: regulation-enable checks

The controller now requires both CV_EN and CS_EN (register0x0f4c,
mask0x000a) before enabling current and before watchdog refresh. Post-sample
limit/mode checks now precede the refresh too. Host fault injection verifies
disabled regulation or changed limits prevents a kick; cleanup and stop-reason
tests pass. Temperature sensing remains explicitly deferred.

Installed in RAM on boot0ddc886e-fe94-4b85-943c-aa92ba3552d8 after verifying
no active controller/service and lease0. Controller SHA-256:
7a1aaf2e5cfba75ff07fbf9a3b917af119841033f2315c8c2ee0278414520c1f.
The fresh hardware watchdog-cutoff test passed and arming completed.
Evidence: local logs/controller-regulation-{precheck,upload,arm,start}.txt.
This update is not yet in the flashed boot image and disappears on reboot.
Engineering limits remain300mA nominal/3900mV/1770seconds per session.
