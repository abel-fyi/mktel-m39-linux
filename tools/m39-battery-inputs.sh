#!/bin/sh
# Read reviewed battery-input controls and cached kernel reports; no PMIC
# configuration, ADC request, charger enable, or storage writes.
set -eu
access=/sys/devices/platform/mt-pmic/pmic_access
selector=/run/m39-battery-input-read
for addr in 0200 0a44 0f56 0f9c 0f9e; do
    printf '%s\n' "$addr" > "$selector"
    cat "$selector" > "$access"
    value=$(cat "$access")
    case "$value" in ''|*[!0-9]*) echo 'Invalid PMIC response' >&2; exit 1;; esac
    printf '%s=%s\n' "$addr" "$value"
    case "$addr" in
        0200) [ "$((value >> 8))" -eq 40 ] || exit 1 ;;
        0a44) printf 'TREF_enable=%s TREF_hardware_control=%s\n' "$(( (value >> 1) & 1 ))" "$(( (value >> 3) & 1 ))" ;;
        0f56) printf 'BATON_enable=%s detection_enable=%s\n' "$((value & 1))" "$(( (value >> 2) & 1 ))" ;;
        0f9c) printf 'environment_detector_enable=%s\n' "$(( (value >> 1) & 1 ))" ;;
        0f9e) printf 'BATON_HT_enable=%s BATON_HT_active=%s BATON_high=%s\n' "$((value & 1))" "$(( (value >> 5) & 1 ))" "$(( (value >> 6) & 1 ))" ;;
    esac
done
for name in batt_temp TemperatureR TempBattVoltage present; do
    printf 'cached_%s=' "$name"
    if ! cat "/sys/class/power_supply/battery/$name" 2>/dev/null; then
        echo 'unavailable: this input/estimate is not validated'
    fi
done
