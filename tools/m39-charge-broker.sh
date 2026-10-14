#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Bounded experimental automatic target/recharge broker, usable by boot startup.
set -eu
case "${1:-}" in --run|--startup) ;; *) echo 'Use --run or --startup for bounded 3.9V policy.'; exit 2;; esac
invocation=$1
runtime=${M39_BROKER_RUNTIME:-/run}
command=${M39_BROKER_COMMAND:-/usr/local/sbin/m39-charge}
adc=${M39_BROKER_ADC:-/usr/local/libexec/m39/m39-adc-sample}
policy=${M39_BROKER_POLICY:-/usr/local/libexec/m39/m39-charge-policy.sh}
boot_file=${M39_BROKER_BOOT:-/proc/sys/kernel/random/boot_id}
uptime_file=${M39_BROKER_UPTIME:-/proc/uptime}
owner_file=${M39_BROKER_OWNER:-/sys/module/charging_hw_pmic/parameters/m39_owner_seconds}
proc_root=${M39_BROKER_PROC:-/proc}
pause=${M39_BROKER_SLEEP:-sleep}
. "$policy"
boot=$(cat "$boot_file")
clock() { read up rest < "$uptime_file"; echo "${up%%.*}"; }
started=$(clock)
state=idle
controller=''
controller_start=''
phase=initializing
reason=none
last_event=''
[ ! -d "$runtime/m39-ceiling-test.lock" ]
[ ! -d "$runtime/m39-charge-startup.lock" ]
mkdir "$runtime/m39-broker.lock" || exit 1
snapshot="$runtime/m39-broker-snapshot.$$"
field() { sed -n "s/.*\"$1\":[[:space:]]*\"\{0,1\}\([^\",}]*\).*/\1/p" "$snapshot"; }
status() {
 phase=$1
 printf '{"phase":"%s","pid":%s,"boot_id":"%s","uptime_seconds":%s,"controller_pid":"%s","target_mv":3900,"recharge_mv":3750,"reason":"%s"}\n' "$phase" "$$" "$boot" "$(clock)" "$controller" "$reason" > "$runtime/m39-broker.json.tmp"
 mv "$runtime/m39-broker.json.tmp" "$runtime/m39-broker.json"
 event="$phase:$controller:$reason"
 if [ "$event" != "$last_event" ]; then
  cat "$runtime/m39-broker.json"
  last_event=$event
 fi
}
stop_controller() {
 M39_STOP_INTERNAL=1 "$command" stop || return 1
 [ "$(cat "$owner_file")" = 0 ] || return 1
 controller=''
 controller_start=''
}
cleanup() {
 rc=$?
 trap - EXIT
 if [ "$(cat "$boot_file")" = "$boot" ]; then stop_controller || rc=1; fi
 [ "$rc" = 0 ] || { : > "$runtime/m39-broker.fault"; reason=guard_or_controller_failure; status fault; }
 rm -f "$snapshot"
 rmdir "$runtime/m39-broker.lock"
 exit "$rc"
}
trap cleanup EXIT
trap 'reason=signal; status cancelled; exit 0' HUP INT TERM
# This explicit invocation may clear an earlier manual stop once, never later.
if [ "$invocation" = --run ]; then
 rm -f "$runtime/m39-charge-startup.disabled"
 rm -f "$runtime/m39-broker.fault"
else
 [ ! -e "$runtime/m39-charge-startup.disabled" ] || { reason=operator_stop; status cancelled; exit 0; }
 [ ! -e "$runtime/m39-broker.fault" ] || exit 1
fi
stop_controller
status idle
while :; do
 [ "$(cat "$boot_file")" = "$boot" ]
 if [ -e "$runtime/m39-charge-startup.disabled" ]; then reason=operator_stop; status cancelled; exit 0; fi
 if [ "$(( $(clock) - started ))" -ge 11400 ]; then reason=run_budget; status budget_exhausted; exit 0; fi
 if [ -n "$controller" ]; then
  cp "$runtime/m39-charge-status.json" "$snapshot"
  [ "$(field boot_id)" = "$boot" ] && [ "$(field pid)" = "$controller" ] || exit 1
  stamp=$(field uptime_seconds)
  case "$stamp" in ''|*[!0-9]*) exit 1;; esac
  age=$(( $(clock) - stamp ))
  [ "$age" -ge 0 ] && [ "$age" -le 5 ] || exit 1
  if [ -r "$proc_root/$controller/stat" ]; then
   [ "$(awk '{print $22}' "$proc_root/$controller/stat")" = "$controller_start" ]
  fi
  terminal_phase=$(field phase)
  case "$terminal_phase" in
   preparing|charging)
    [ -r "$proc_root/$controller/stat" ]
    status "$terminal_phase"
    "$pause" 2
    continue ;;
   stopped)
    [ "$(field charging_off_verified)" = true ]
    [ "$(field voltage_limit_mv)" = 3900 ]
    action=$(m39_policy_decide charging 1 "$(field battery_mv)" 0 "$(field stop_reason)" 1)
    case "$action" in
     target_hold) stop_controller; state=target_hold; reason=target_reached; status target_hold ;;
     start_bounded) stop_controller; state=idle; reason=segment_complete; status resting; "$pause" 60 ;;
     idle)
      reason=$(field stop_reason)
      if [ "$reason" = unplugged ]; then
          stop_controller; state=idle; status idle
      else status cancelled; exit 0; fi ;;
     *) exit 1 ;;
    esac ;;
   *) exit 1 ;;
  esac
 fi
 # No second ADC reader is started while a controller is active.
 [ "$(cat "$owner_file")" = 0 ]
 before=$(clock)
 values=$("$adc")
 [ "$(( $(clock) - before ))" -le 2 ]
 set -- $values
 [ "$#" = 5 ]
 for v in "$@"; do case "$v" in ''|*[!0-9]*) exit 1;; esac; done
 voltage=$1
 if [ "$3" -lt 1000 ]; then connected=0
 elif [ "$3" -ge 4500 ] && [ "$3" -le 5500 ]; then connected=1
 else exit 1; fi
 action=$(m39_policy_decide "$state" "$connected" "$voltage" 0 none 1)
 case "$action" in
  idle|low_voltage|target_hold) state=$action; status "$action"; "$pause" 5 ;;
  start_bounded)
   [ ! -e "$runtime/m39-charge-startup.disabled" ]
   # The old service is stopped and ownership released. Its last JSON may
   # still say charging: do not mistake that controller for the new child.
   rm -f "$runtime/m39-plug-status.json"
   M39_STARTUP=1 "$command" arm
   until_time=$(( $(clock) + 25 ))
   while :; do
    [ "$(clock)" -le "$until_time" ]
    if [ ! -r "$runtime/m39-plug-status.json" ]; then "$pause" 1; continue; fi
    cp "$runtime/m39-plug-status.json" "$snapshot"
    [ "$(field boot_id)" = "$boot" ]
    if [ "$(field phase)" = charging ]; then controller=$(field controller_pid); break; fi
    "$pause" 1
   done
   case "$controller" in ''|*[!0-9]*) exit 1;; esac
   controller_start=$(awk '{print $22}' "$proc_root/$controller/stat")
   # Wait for the new child's first record; arm's watchdog test has another PID.
   while :; do
    [ "$(clock)" -le "$until_time" ]
    cp "$runtime/m39-charge-status.json" "$snapshot"
    [ "$(field pid)" != "$controller" ] || break
    "$pause" 1
   done
   state=charging ;;
  *) exit 1 ;;
 esac
done
