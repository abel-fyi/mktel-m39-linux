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
      if [ "$current" -gt 0 ]; then status=charging; else status=unknown; fi
     fi
    elif [ "$status" = unknown ]; then reason=stale_record; fi
   else reason=invalid_record; fi ;;
  esac
 else reason=different_boot; fi
fi
# All output strings come from reviewed controller enums, never credentials.
case "$reason" in *[!a-z_]*|'') reason=invalid_record;; esac
printf '{"status":"%s","voltage_mv":%s,"fg_signed_raw":%s,"sample_age_seconds":%s,"percentage":null,"full":null,"cell_temperature":null,"reason":"%s"}\n' "$status" "$voltage" "$current" "$age" "$reason"
