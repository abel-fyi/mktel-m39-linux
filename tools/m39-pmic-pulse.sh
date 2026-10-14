#!/bin/sh
# Engineering diagnostic only. Not a battery-charging service.
# Default mode reads hardware and prints the plan; --pulse requires supervision.
# Register definitions: MT6328 vendor upmu_hw.h / charging_hw_pmic.c.
set -eu
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
access=/sys/devices/platform/mt-pmic/pmic_access
power=/sys/class/power_supply/battery
stop_file=${M39_STOP_FILE:-}
case "$stop_file" in ''|/run/m39-plug-charge-*.stop) ;; *) echo 'Invalid stop-request path'; exit 2;; esac
restore_backlight=${M39_RESTORE_BACKLIGHT:-}
case "$restore_backlight" in ''|0|255) ;; *) echo 'Invalid backlight restoration value'; exit 2;; esac
if [ -n "$restore_backlight" ]; then
    [ -r /run/m39-backlight-validated ] &&
    [ "$(cat /run/m39-backlight-validated)" = "$(cat /proc/sys/kernel/random/boot_id)" ] || {
        echo 'Backlight control has not been validated on this boot'; exit 1;
    }
fi
owner_path=/sys/module/charging_hw_pmic/parameters/m39_owner_seconds
write_owner() (
    command_file=/run/m39-owner-command.$$
    trap 'rm -f "$command_file"' EXIT
    trap 'exit 1' HUP INT TERM
    printf '%s\n' "$1" > "$command_file" || exit 1
    cat "$command_file" > "$owner_path"
)
requires_owner=0
case "$(uname -r)" in *m39-diagnostic*) requires_owner=1 ;; esac
pmic_thermal=''
for zone in /sys/class/thermal/thermal_zone*; do
    [ "$(cat "$zone/type" 2>/dev/null)" = mtktspmic ] || continue
    pmic_thermal=$zone
    break
done
mode=${1:---plan}
current_ma=${2:-200}
case "$current_ma" in
    200) current_code=14 ;;
    300) current_code=13 ;;
    *) echo 'Diagnostic current must be 200 or 300 mA'; exit 2 ;;
esac
case "$mode" in --plan|--plan-battery-boot|--pulse|--watchdog-test|--watchdog-test-battery-boot|--watchdog-test-3900|--supervised-minute|--supervised-minute-battery-boot|--supervised-five-minutes|--supervised-recharge|--supervised-battery-boot|--supervised-recharge-3900) ;; *) echo 'Unknown diagnostic mode'; exit 2;; esac
supervised_run=0
run_seconds=60
maximum_mv=3450
plan_mode=0
cv_code=0
case "$mode" in
    --watchdog-test-battery-boot) mode=--watchdog-test; maximum_mv=3600 ;;
    --watchdog-test-3900) mode=--watchdog-test; maximum_mv=3900; cv_code=3 ;;
    --plan) plan_mode=1 ;;
    --plan-battery-boot) plan_mode=1; maximum_mv=3600 ;;
    --supervised-minute) supervised_run=1 ;;
    --supervised-minute-battery-boot) mode=--supervised-minute; supervised_run=1; maximum_mv=3600 ;;
    --supervised-five-minutes) supervised_run=1; run_seconds=300 ;;
    --supervised-recharge) supervised_run=1; run_seconds=900 ;;
    --supervised-battery-boot) supervised_run=1; run_seconds=1800; maximum_mv=3600 ;;
    --supervised-recharge-3900) supervised_run=1; run_seconds=1770; maximum_mv=3900; cv_code=3 ;;
esac
uptime_seconds() {
    read system_uptime remaining < /proc/uptime
    echo "${system_uptime%%.*}"
}
uptime_decimal() {
    read diagnostic_uptime diagnostic_idle < /proc/uptime
    echo "$diagnostic_uptime"
}
status_active=0
stop_reason=running
write_status() {
    [ "$status_active" -eq 1 ] || return 0
    status_phase=$1
    status_off=$2
    status_uptime=$(uptime_seconds)
    status_boot=$(cat /proc/sys/kernel/random/boot_id)
    printf '{"phase":"%s","pid":%s,"boot_id":"%s","uptime_seconds":%s,"current_setting_ma":%s,"battery_mv":%s,"fg_signed_raw":%s,"charging_off_verified":%s,"voltage_limit_mv":%s,"duration_limit_seconds":%s,"stop_reason":"%s"}\n' \
        "$status_phase" "$$" "$status_boot" "$status_uptime" "$current_ma" "${voltage:-0}" "${fg_direction:-0}" "$status_off" "${maximum_mv:-3450}" "${run_seconds:-0}" "${stop_reason:-unknown}" \
        > "/run/m39-charge-status.json.tmp.$$" || return 1
    mv "/run/m39-charge-status.json.tmp.$$" /run/m39-charge-status.json
}
fail() {
    [ "${stop_reason:-running}" != running ] || stop_reason=fault
    echo "ABORT: $*" >&2
    exit 1
}
number() {
    value=$(cat "$1") || fail "Cannot read $1"
    case "$value" in ''|*[!0-9]*) fail "Invalid reading from $1";; esac
    echo "$value"
}
readreg_raw() {
    case "$1" in 0200|028a|0ca4|0cb2|0e94|0eb0|0e8a|0e2e|0e32|0e04|0e06|0e08|0f48|0f4c|0f4e|0f50|0f54|0f62|0f66|0f74|0f76|0f7a) ;; *) fail 'Unexpected register';; esac
    # Exactly five bytes selects a READ in the reviewed sysfs handler.
    printf '%s\n' "$1" > /run/m39-pmic-read-request || fail 'Cannot buffer read request'
    cat /run/m39-pmic-read-request > "$access" || fail 'PMIC read selection failed'
    number "$access"
}

readreg() {
    if [ "${M39_TRACE_IO:-0}" != 1 ]; then
        readreg_raw "$@"
        return
    fi
    io_started=$(uptime_seconds)
    printf 'readreg %s started=%s\n' "$1" "$io_started" > /run/m39-charge-last-io
    if readreg_raw "$@"; then io_result=0; else io_result=$?; fi
    io_finished=$(uptime_seconds)
    if [ "$((io_finished - io_started))" -ge 1 ]; then
        echo "SLOW_IO operation=readreg register=$1 start=$io_started end=$io_finished result=$io_result" >&2
    fi
    printf 'readreg %s completed=%s result=%s\n' "$1" "$io_finished" "$io_result" > /run/m39-charge-last-io
    return "$io_result"
}

field() {
    addr=$1 mask=$2 bits=$3
    old=$(readreg "$addr") || return 1
    new=$(( (old & ~mask) | (bits & mask) ))
    writereg "$addr" "$new" || return 1
    actual=$(readreg "$addr") || return 1
    [ "$((actual & mask))" -eq "$((bits & mask))" ] || {
        echo "ABORT: readback mismatch at $addr expected=$((bits & mask)) actual=$((actual & mask)) raw=$actual mask=$mask before=$old" >&2; return 1;
    }
}
writereg() {
    # Buffer the complete ten-byte request. Direct shell printf can split
    # writes, which this vendor handler rejects. Verified cat -> sysfs works.
    printf '%s %04x\n' "$1" "$2" > /run/m39-pmic-write-request || return 1
    [ "$(wc -c < /run/m39-pmic-write-request)" -eq 10 ] || return 1
    cat /run/m39-pmic-write-request > "$access" || {
        echo "ABORT: PMIC write failed at $1" >&2; return 1;
    }
}
sample() (
    # Native transaction avoids dozens of fork/execs within the four-second WDT.
    if [ -x /usr/local/libexec/m39/m39-adc-sample ]; then
        exec /usr/local/libexec/m39/m39-adc-sample
    fi
    adc_clock1=$(readreg 028a) || exit 1
    adc_clock2=$(readreg 0e94) || exit 1
    adc_clock3=$(readreg 0eb0) || exit 1
    restore_adc() {
        trap - EXIT INT TERM HUP
        failed=0
        field 028a 256 "$adc_clock1" || failed=1
        field 0e94 32768 "$adc_clock2" || failed=1
        field 0eb0 128 "$adc_clock3" || failed=1
        [ "$failed" -eq 0 ]
    }
    trap 'restore_adc || exit 1' EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    field 028a 256 256 || exit 1
    field 0e94 32768 32768 || exit 1
    field 0eb0 128 128 || exit 1
    # CH0 battery, CH1 sense, CH2 USB divider, CH3 BATON, CH4 PMIC diode.
    writereg 0e8a 31 || exit 1
    adc_values=''
    for adc_address in 0e2e 0e32 0e04 0e06 0e08; do
        adc_tries=0
        while :; do
            adc_value=$(readreg "$adc_address") || exit 1
            [ "$((adc_value & 32768))" -ne 0 ] && break
            adc_tries=$((adc_tries + 1))
            [ "$adc_tries" -lt 30 ] || fail "ADC not ready at $adc_address"
            sleep 0.01
        done
        adc_values="$adc_values $adc_value"
    done
    set -- $adc_values
    echo "$(( ($1 & 32767) * 5400 / 32768 )) $(( ($2 & 32767) * 5400 / 32768 )) $(( ($3 & 4095) * 1800 / 4096 * 369 / 39 )) $(( ($5 & 4095) * 1800 / 4096 )) $(( ($4 & 4095) * 1800 / 4096 ))"
)
fuel_current() (
    [ -x /run/m39-fg-sample ] || fail 'Native fuel-gauge helper missing'
    # Fast, bounded transaction; never falls back to the contended shell
    # reader or treats a failed/stale acquisition as a valid current sample.
    exec /run/m39-fg-sample
)
verify_charge_profile() {
    regulation_now=$(readreg 0f4c) || fail 'Regulation register unreadable'
    cv_now=$(readreg 0f4e) || fail 'CV register unreadable'
    current_now=$(readreg 0f50) || fail 'Current register unreadable'
    voltage_mode_now=$(readreg 0f7a) || fail 'Voltage mode register unreadable'
    [ "$((regulation_now & 10))" -eq 10 ] || { stop_reason=regulation_disabled; fail 'Voltage/current regulation disabled'; }
    [ "$((cv_now & 31))" -eq "$cv_code" ] || { stop_reason=power_profile_changed; fail 'CV limit changed'; }
    [ "$((current_now & 15))" -eq "$current_code" ] || { stop_reason=power_profile_changed; fail 'Current limit changed'; }
    [ "$((voltage_mode_now & 70))" -eq 68 ] || { stop_reason=power_profile_changed; fail 'Voltage-control mode changed'; }
}
guard() {
    if [ -n "$stop_file" ] && [ -e "$stop_file" ]; then
        stop_reason=stop_requested
        echo 'Controlled stop requested; leaving the charging loop.'
        exit 0
    fi
    guard_start=$(uptime_decimal)
    if [ "$requires_owner" -eq 1 ] && [ "$plan_mode" -eq 0 ]; then
        [ -r "$owner_path" ] || fail 'Source kernel lacks exclusive charger ownership'
        owner_remaining=$(number "$owner_path")
        [ "$owner_remaining" -gt 0 ] || fail 'Exclusive charger lease missing or expired'
    fi
    sampled=$(sample) || fail 'Fresh ADC measurement or clock restoration failed'
    set -- $sampled
    [ "$#" -eq 5 ] || fail 'Invalid ADC sample'
    voltage=$1 sense_voltage=$2 vbus=$3 diode_voltage=$4 baton_voltage=$5
    [ -n "$pmic_thermal" ] || fail 'PMIC thermal sensor missing'
    pmic_temp=$(number "$pmic_thermal/temp")
    [ "$(cat "$pmic_thermal/type")" = mtktspmic ] || fail 'Wrong thermal sensor'
    [ "$voltage" -ge 3200 ] || fail "Battery voltage $voltage outside test range"
    if [ "$voltage" -ge "$maximum_mv" ]; then
        stop_reason=voltage_limit
        if [ "$status_active" -eq 1 ]; then
            echo "Battery voltage $voltage reached diagnostic ceiling $maximum_mv; stopping."
            exit 0
        fi
        fail "Battery voltage $voltage reached diagnostic ceiling $maximum_mv"
    fi
    if [ "$vbus" -lt 4500 ] || [ "$vbus" -gt 5500 ]; then
        stop_reason=input_voltage_changed
        fail "USB voltage $vbus outside test range"
    fi
    [ "$pmic_temp" -ge 10000 ] && [ "$pmic_temp" -lt 40000 ] || fail "PMIC temperature $pmic_temp outside test range"
    [ "$diode_voltage" -ge 650 ] && [ "$diode_voltage" -le 800 ] || fail 'PMIC diode outside diagnostic range'
    [ "$(( $(readreg 0f54) & 1 ))" -eq 1 ] || fail 'Hardware battery overvoltage protection disabled'
    fg_sampled=$(fuel_current) || fail 'Fuel gauge measurement or cleanup failed'
    set -- $fg_sampled
    [ "$#" -eq 2 ] || fail 'Invalid fuel gauge sample'
    fg_direction=$2
    echo "Battery=${voltage}mV Sense=${sense_voltage}mV USB=${vbus}mV PMIC=${pmic_temp}mC Diode=${diode_voltage}mV FGraw=$1 FGsigned=$2 BATON=${baton_voltage}mV GuardStart=${guard_start} GuardEnd=$(uptime_decimal)"
}
guard
chip=$(readreg 0200)
echo "PMIC HWCID=$chip"
[ "$((chip >> 8))" -eq 40 ] || fail 'PMIC identity is not verified MT6328 family'
saved_f48=$(readreg 0f48)
[ "$((saved_f48 & 24))" -eq 0 ] || fail 'Charger already active'
saved_f4c=$(readreg 0f4c)
saved_f4e=$(readreg 0f4e)
saved_f50=$(readreg 0f50)
saved_f62=$(readreg 0f62)
saved_f66=$(readreg 0f66)
saved_f7a=$(readreg 0f7a)
saved_f74=$(readreg 0f74)
saved_f76=$(readreg 0f76)
echo "PLAN: ${current_ma}mA nominal current setting; CV code=$cv_code (0=3.775V, 3=3.9V); mode=$mode."
echo "Abort at ${maximum_mv}mV; four-second watchdog requires this boot's validation marker."
echo 'Battery temperature input is UNVALIDATED; requires an observer and cool battery.'
[ "$plan_mode" -eq 0 ] || exit 0
[ "${M39_SUPERVISED:-0}" = 1 ] || fail 'Supervised test acknowledgement missing'
if [ "$supervised_run" -eq 1 ]; then
    [ -f /run/m39-watchdog-validated ] || fail 'Linux watchdog cutoff evidence missing'
    [ "$(cat /run/m39-watchdog-validated)" = "$(uname -r)" ] || fail 'Watchdog evidence kernel mismatch'
fi
mkdir /run/m39-pmic-pulse.lock || fail 'Another test is active'
status_active=1
cleanup() {
    trap - EXIT INT TERM HUP
    set +e
    # Independent display restoration is allowed only after this boot's test.
    if [ -n "${restore_backlight:-}" ]; then
        printf '%s\n' "$restore_backlight" > /sys/class/leds/lcd-backlight/brightness ||
            echo 'Backlight restoration failed' >&2
    fi
    # Turn charging off BEFORE restoring the prior limits/configuration.
    if ! field 0f48 24 0; then
        echo 'Charging-off unverified: retaining conservative limits; do not continue.' >&2
        write_status off_unverified false
        rmdir /run/m39-pmic-pulse.lock
        return 1
    fi
    restore_failed=0
    restore_profile=1
    if [ "${requires_owner:-0}" -eq 1 ]; then
        if cleanup_sample=$(sample); then
            set -- $cleanup_sample
            if [ "$#" -eq 5 ]; then
                if [ "$3" -lt 1000 ]; then
                    case "${stop_reason:-unknown}" in
                        stop_requested|charger_stopped|input_voltage_changed|regulation_disabled|power_profile_changed)
                            stop_reason=unplugged
                            test_exit=0
                            ;;
                    esac
                    restore_profile=0
                    echo "USB input absent (${3}mV); charging verified off, leaving standby profile unchanged."
                fi
            else
                restore_profile=0
                restore_failed=1
                echo 'Cleanup power state invalid; retaining conservative settings.' >&2
            fi
        else
            restore_profile=0
            restore_failed=1
            echo 'Cleanup power measurement failed; retaining conservative settings.' >&2
        fi
    fi
    if [ "$restore_profile" -eq 1 ]; then
        field 0f4c 10 "$saved_f4c" || restore_failed=1
        # CSDAC_MODE clears with charger off; never enable to restore this bit.
        field 0f7a 66 "$saved_f7a" || restore_failed=1
        field 0f74 119 "$saved_f74" || restore_failed=1
        field 0f76 119 "$saved_f76" || restore_failed=1
        field 0f4e 31 "$saved_f4e" || restore_failed=1
        field 0f50 15 "$saved_f50" || restore_failed=1
        field 0f62 31 "$saved_f62" || restore_failed=1
        field 0f66 1 "$saved_f66" || restore_failed=1
    fi
    if [ "${requires_owner:-0}" -eq 1 ]; then
        write_owner 0 || restore_failed=1
    fi
    rmdir /run/m39-pmic-pulse.lock
    if [ "$restore_failed" -ne 0 ]; then
        write_status off_restore_failed true
        echo 'Charging disabled; some prior settings could not be restored.' >&2
        return 1
    fi
    if [ "${test_exit:-0}" -eq 0 ]; then
        write_status stopped true || return 1
    else
        write_status aborted true || return 1
    fi
    if [ "$restore_profile" -eq 1 ]; then
        echo 'Pulse finished; charging disabled and prior settings restored.'
    else
        echo 'Pulse finished; charging disabled, standby profile retained until next validated connection.'
    fi
    if [ "$mode" = --watchdog-test ] && [ "${watchdog_observed:-0}" -eq 1 ]; then
        uname -r > /run/m39-watchdog-validated
    fi
}
trap 'test_exit=$?; cleanup || exit 1' EXIT
trap 'stop_reason=interrupted; exit 130' INT
trap 'stop_reason=interrupted; exit 143' TERM
trap 'stop_reason=interrupted; exit 129' HUP
write_status preparing false
# Establish conservative limits and independent hardware cutoff before enabling.
field 0f62 31 16
old=$(readreg 0f62); writereg 0f62 "$((old | 256))"
field 0f66 1 1
old=$(readreg 0f66); writereg 0f66 "$((old | 2))"
field 0f4e 31 "$cv_code"
field 0f50 15 "$current_code"
field 0f7a 2 0
field 0f4c 10 10
field 0f74 119 33
field 0f76 119 20
# Watchdog reset and flag acknowledge are self-clearing action bits.
old=$(readreg 0f62); writereg 0f62 "$((old | 256))"
old=$(readreg 0f66); writereg 0f66 "$((old | 3))"
observation_start=$(uptime_seconds)
guard
old=$(readreg 0f62); writereg 0f62 "$((old | 256))"
old=$(readreg 0f66); writereg 0f66 "$((old | 3))"
# CHR_EN gates HWCV/MODE: configure them with the main gate on and
# current-DAC enable off. This exact staging passed the supervised DA test.
field 0f48 24 16
field 0f7a 64 64
field 0f7a 4 4
[ "$(( $(readreg 0f4c) & 10 ))" -eq 10 ] || fail 'Voltage/current regulation disabled'
[ "$(( $(readreg 0f4e) & 31 ))" -eq "$cv_code" ] || fail 'CV limit changed'
[ "$(( $(readreg 0f50) & 15 ))" -eq "$current_code" ] || fail 'Current limit changed'
[ "$(( $(readreg 0f7a) & 70 ))" -eq 68 ] || fail 'Voltage control/mode not ready'
field 0f48 24 24
echo 'Charger pulse enabled.'
count=0
intervals=2
[ "$mode" != --watchdog-test ] || intervals=6
if [ "$supervised_run" -eq 1 ]; then
    intervals=$run_seconds
fi
watchdog_observed=0
nonpositive_samples=0
while [ "$count" -lt "$intervals" ]; do
    if [ "$supervised_run" -eq 1 ] && [ "$(( $(uptime_seconds) - observation_start ))" -ge "$run_seconds" ]; then
        stop_reason=time_limit
        break
    fi
    sleep 1
    if [ "$supervised_run" -eq 1 ]; then
        if [ -n "$stop_file" ] && [ -e "$stop_file" ]; then
            stop_reason=stop_requested
            echo 'Controlled stop requested before watchdog refresh.'
            break
        fi
        if [ "$requires_owner" -eq 1 ]; then
            [ "$(number "$owner_path")" -gt 0 ] || fail 'Exclusive charger lease expired'
        fi
        [ "$(( $(readreg 0f48) & 24 ))" -eq 24 ] || { stop_reason=charger_stopped; fail 'Charger stopped before sampling'; }
        [ "$(( $(readreg 0f66) & 4 ))" -eq 0 ] || fail 'Watchdog expired before sampling'
        [ "$(( $(readreg 0f62) & 31 ))" -eq 16 ] || fail 'Four-second watchdog profile changed'
        verify_charge_profile
        old=$(readreg 0f62); writereg 0f62 "$((old | 256))"
    fi
    guard
    charger_now=$(readreg 0f48)
    watchdog_now=$(readreg 0f66)
    write_status charging false
    echo "charger_control=$charger_now watchdog=$watchdog_now uptime=$(cut -d ' ' -f 1 /proc/uptime)"
    if [ "$mode" = --watchdog-test ] && [ "$((watchdog_now & 4))" -ne 0 ]; then
        [ "$((charger_now & 24))" -eq 0 ] || fail 'Watchdog flag set but charger still enabled'
        watchdog_observed=1
        stop_reason=watchdog_test_complete
        echo 'Linux watchdog cutoff observed: flag set and charger enable bits cleared.'
        break
    fi
    [ "$(( $(readreg 0f62) & 16 ))" -eq 16 ] || fail 'Watchdog was disabled by another driver'
    [ "$((charger_now & 24))" -eq 24 ] || { stop_reason=charger_stopped; fail 'Charger stopped'; }
    [ "$((watchdog_now & 4))" -eq 0 ] || fail 'Watchdog expired'
    if [ "$supervised_run" -eq 1 ]; then
        # One load transient is not sustained loss of charging. Keep all voltage,
        # USB, thermal and watchdog guards active during this bounded debounce.
        if [ "$fg_direction" -gt 0 ]; then
            nonpositive_samples=0
        else
            nonpositive_samples=$((nonpositive_samples + 1))
            echo "Net charging transient: consecutive_nonpositive=$nonpositive_samples"
            [ "$nonpositive_samples" -lt 3 ] || {
                stop_reason=net_discharge
                fail 'No net battery charging for three consecutive fresh samples'
            }
        fi
    fi
    if [ "$supervised_run" -eq 1 ]; then
        verify_charge_profile
        old=$(readreg 0f62); writereg 0f62 "$((old | 256))"
    fi
    count=$((count + 1))
done
[ "$stop_reason" != running ] || stop_reason=interval_limit
[ "$mode" != --watchdog-test ] || [ "$watchdog_observed" -eq 1 ] || fail 'Watchdog cutoff not observed'
