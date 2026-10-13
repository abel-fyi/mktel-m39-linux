#!/bin/sh
# Supervised ceiling characterization: at most three existing bounded sessions.
# Never retries a fault, unplug, manual stop, or unverified cleanup.
set -eu
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
boot=$(cat /proc/sys/kernel/random/boot_id)
started=$(cut -d . -f 1 /proc/uptime)
segment=0
controller=''
phase=preparing
mkdir /run/m39-ceiling-test.lock || exit 1
status() {
 phase=$1
 printf '{"phase":"%s","boot_id":"%s","pid":%s,"segment":%s,"maximum_segments":3,"voltage_limit_mv":3900}\n' "$phase" "$boot" "$$" "$segment" > /run/m39-ceiling-test.json.tmp
 mv /run/m39-ceiling-test.json.tmp /run/m39-ceiling-test.json
}
active_phase() {
 case "$1" in preparing|charging) return 0;; *) return 1;; esac
}
terminal_action() {
 # Arguments are validated controller phase, stop reason, voltage and limit.
 case "$1:$2" in
  stopped:time_limit|stopped:interval_limit) echo next ;;
  stopped:voltage_limit)
   [ "$4" = 3900 ] && [ "$3" -ge 3900 ] && echo ceiling || echo fault ;;
  stopped:unplugged|stopped:stop_requested) echo cancelled ;;
  *) echo fault ;;
 esac
}
value() { sed -n "s/.*\"$2\":[[:space:]]*\"\{0,1\}\([^\",}]*\).*/\1/p" "$1"; }
cleanup() {
 result=$?
 trap - EXIT
 if [ "$(cat /proc/sys/kernel/random/boot_id)" = "$boot" ]; then
  m39-charge stop >> /run/m39-ceiling-test.log 2>&1 || result=1
 fi
 [ "$result" = 0 ] || status failed
 rmdir /run/m39-ceiling-test.lock
 exit "$result"
}
trap cleanup EXIT
trap 'status cancelled; exit 1' HUP INT TERM
status preparing
while [ "$segment" -lt 3 ]; do
 [ "$(cat /proc/sys/kernel/random/boot_id)" = "$boot" ]
 [ "$(( $(cut -d . -f 1 /proc/uptime) - started ))" -lt 5700 ]
 m39-charge stop
 m39-charge arm
 segment=$((segment+1))
 controller=''
 tries=0
 while [ -z "$controller" ]; do
  sleep 1
  tries=$((tries+1)); [ "$tries" -le 25 ]
  f=/run/m39-plug-status.json
  [ -r "$f" ] || continue
  [ "$(value "$f" boot_id)" = "$boot" ]
  if [ "$(value "$f" phase)" = charging ]; then controller=$(value "$f" controller_pid); fi
 done
 case "$controller" in ''|*[!0-9]*) exit 1;; esac
 status charging
 while :; do
  [ "$(cat /proc/sys/kernel/random/boot_id)" = "$boot" ]
  [ "$(( $(cut -d . -f 1 /proc/uptime) - started ))" -lt 5700 ]
  f=/run/m39-charge-status.json
  if [ -r "$f" ] && [ "$(value "$f" pid)" = "$controller" ]; then
   [ "$(value "$f" boot_id)" = "$boot" ]
   state=$(value "$f" phase)
   if ! active_phase "$state"; then
    [ "$(value "$f" charging_off_verified)" = true ]
    action=$(terminal_action "$state" "$(value "$f" stop_reason)" "$(value "$f" battery_mv)" "$(value "$f" voltage_limit_mv)")
    break
   fi
  fi
  kill -0 "$controller"
  sleep 5
 done
 case "$action" in
  ceiling) status voltage_ceiling_reached; exit 0 ;;
  cancelled) status cancelled; exit 0 ;;
  fault) exit 1 ;;
  next)
   if [ "$segment" -ge 3 ]; then status time_budget_exhausted; exit 0; fi
   status cooling_between_segments
   sleep 60
   # Explicit stop/unplug during the pause cancels the test; never replay it.
   [ ! -e /run/m39-charge-startup.disabled ]
   # A reconnect or another controller during the pause invalidates this run.
   [ "$(value /run/m39-charge-status.json pid)" = "$controller" ]
   [ "$(value /run/m39-charge-status.json phase)" = stopped ]
   [ "$(value /run/m39-charge-status.json charging_off_verified)" = true ]
   case "$(value /run/m39-charge-status.json stop_reason)" in time_limit|interval_limit) ;; *) exit 1;; esac
   [ "$(cat /sys/class/power_supply/usb/online)" = 1 ] || [ "$(cat /sys/class/power_supply/ac/online)" = 1 ]
   ;;
 esac
done
