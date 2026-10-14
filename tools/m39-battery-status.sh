#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Public diagnostic status. Never writes PMIC registers or invents SOC/full.
set -eu
umask 077
runtime=${M39_STATUS_RUNTIME:-/run}
boot_file=${M39_STATUS_BOOT:-/proc/sys/kernel/random/boot_id}
uptime_file=${M39_STATUS_UPTIME:-/proc/uptime}
proc_root=${M39_STATUS_PROC:-/proc}
boot=$(cat "$boot_file")
read up rest < "$uptime_file"
now=${up%%.*}
snapshot="$runtime/m39-status-snapshot.$$"
trap 'rm -f "$snapshot"' EXIT
field() { sed -n "s/.*\"$1\":[[:space:]]*\"\{0,1\}\([^\",}]*\).*/\1/p" "$snapshot"; }
status=unknown
voltage=null
current=null
age=null
reason=no_current_record
input_present=null
policy_phase=null
canonical_unsigned() {
 case "$1" in ''|*[!0-9]*|0[0-9]*) return 1;; *) return 0;; esac
}
if [ -r "$runtime/m39-charge-status.json" ]; then
 cp "$runtime/m39-charge-status.json" "$snapshot"
 if [ "$(field boot_id)" = "$boot" ]; then
  phase=$(field phase)
  pid=$(field pid)
  stamp=$(field uptime_seconds)
  mv=$(field battery_mv)
  fg=$(field fg_signed_raw)
  case "$stamp:$mv:$pid" in *[!0-9:]*|:*|*::*) reason=invalid_record;;
  *)
   if canonical_unsigned "$stamp" && canonical_unsigned "$mv" &&
      canonical_unsigned "$pid" && [ "$now" -ge "$stamp" ]; then
    age=$((now-stamp))
    reason=$(field stop_reason)
    # Completed OFF verification is a historical fact, not a full-battery claim.
    if [ "$(field charging_off_verified)" = true ] && [ ! -r "$proc_root/$pid/stat" ]; then
     status=not_charging
    fi
    if [ "$age" -le 3 ] && [ "$mv" -ge 2700 ] && [ "$mv" -le 4300 ]; then
     voltage=$mv
     case "$fg" in -*) digits=${fg#-};; *) digits=$fg;; esac
     if canonical_unsigned "$digits"; then current=$fg; fi
     if [ "$phase" = charging ] && [ -r "$proc_root/$pid/stat" ] &&
        tr '\000' ' ' < "$proc_root/$pid/cmdline" | grep -Fq m39-pmic-pulse.sh &&
        [ "$(field charging_off_verified)" = false ] && [ "$current" != null ]; then
      if [ "$current" -gt 0 ]; then
       status=charging
       # This fresh controller sample passed the USB-voltage guard before
       # publishing charging. No new hardware read is needed here.
       input_present=true
      else status=unknown; fi
     fi
    elif [ "$status" = unknown ]; then reason=stale_record; fi
   else reason=invalid_record; fi ;;
  esac
 else reason=different_boot; fi
fi
# Idle voltage comes from the broker's existing ADC read, never another
# hardware transaction. Require fresh sampling and a matching live process
# birth time; a broker loop heartbeat is not a new battery measurement.
if [ -r "$runtime/m39-broker.json" ]; then
 cp "$runtime/m39-broker.json" "$snapshot"
 bp=$(field pid); birth=$(field pid_start_ticks); stamp=$(field sample_uptime_seconds)
 bm=$(field battery_mv); usb=$(field usb_mv); phase=$(field phase)
 if [ "$(field boot_id)" = "$boot" ] && canonical_unsigned "$bp" &&
    canonical_unsigned "$birth" && [ -r "$proc_root/$bp/stat" ] &&
    [ "$(awk '{print $22}' "$proc_root/$bp/stat")" = "$birth" ] &&
    tr '\000' ' ' < "$proc_root/$bp/cmdline" | grep -Fq m39-charge-broker.sh; then
  case "$phase" in idle|low_voltage|target_hold|resting|preparing|charging)
   heartbeat=$(field uptime_seconds)
   if canonical_unsigned "$heartbeat" && [ "$heartbeat" -le "$now" ] &&
      [ "$((now-heartbeat))" -le 5 ]; then policy_phase=$phase; fi ;;
  esac
  if canonical_unsigned "$stamp" && canonical_unsigned "$bm" &&
     canonical_unsigned "$usb" && [ "$stamp" -le "$now" ] &&
     [ "$((now-stamp))" -le 5 ] && [ "$bm" -ge 2700 ] && [ "$bm" -le 4300 ]; then
   if [ "$voltage" = null ]; then voltage=$bm; age=$((now-stamp)); fi
   if [ "$input_present" = null ]; then
    if [ "$usb" -lt 1000 ]; then input_present=false
    elif [ "$usb" -ge 4500 ] && [ "$usb" -le 5500 ]; then input_present=true; fi
   fi
  fi
 fi
fi
# All output strings come from reviewed controller enums, never credentials.
case "$reason" in *[!a-z_]*|'') reason=invalid_record;; esac
printf '{"status":"%s","voltage_mv":%s,"fg_signed_raw":%s,"sample_age_seconds":%s,"input_present":%s,"policy_phase":%s,"percentage":null,"full":null,"cell_temperature":null,"reason":"%s"}\n' "$status" "$voltage" "$current" "$age" "$input_present" "$(if [ "$policy_phase" = null ]; then echo null; else printf '"%s"' "$policy_phase"; fi)" "$reason"
