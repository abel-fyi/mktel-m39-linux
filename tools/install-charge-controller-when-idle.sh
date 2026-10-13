#!/bin/sh
# Replace a staged RAM-only controller after its current process has exited.
# Never controls charging, restarts the service, or writes persistent storage.
set -eu
pid=$1
expected_boot=$2
expected_hash=$3
service_pid=$4
case "$pid" in ''|*[!0-9]*) exit 2;; esac
case "$service_pid" in ''|*[!0-9]*) exit 2;; esac
case "$expected_hash" in ''|*[!0-9a-f]*) exit 2;; esac
[ "${#expected_hash}" -eq 64 ] || exit 2
candidate=/run/m39-pmic-pulse.next.sh
status=/run/m39-controller-install.status
check_boot() { [ "$(cat /proc/sys/kernel/random/boot_id)" = "$expected_boot" ]; }
check_boot
service_start=$(awk '{print $22}' "/proc/$service_pid/stat")
frozen=0
finished=0
cleanup() {
    if [ "$frozen" = 1 ]; then kill -CONT "$service_pid" 2>/dev/null || :; fi
    [ "$finished" = 1 ] || echo not_installed > "$status"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
printf 'waiting_for_controller_exit\n' > "$status"
ticks=0
while kill -0 "$pid" 2>/dev/null; do
    check_boot
    ticks=$((ticks + 1))
    [ "$ticks" -lt 900 ] || { echo timed_out > "$status"; exit 1; }
    sleep 2
done
# Fail closed on a new session, retained lease, missing cleanup evidence,
# stale boot, or modified candidate. No automatic charging retries.
check_boot
[ "$(awk '{print $22}' "/proc/$service_pid/stat")" = "$service_start" ]
# Freeze only the idle service briefly to exclude a reconnect/spawn race.
# Its existing connection latch survives CONT; no session is restarted.
kill -STOP "$service_pid"
frozen=1
[ ! -d /run/m39-pmic-pulse.lock ]
[ "$(cat /sys/module/charging_hw_pmic/parameters/m39_owner_seconds)" = 0 ]
grep -q '"charging_off_verified":true' /run/m39-charge-status.json
grep -q "\"pid\":$pid," /run/m39-charge-status.json
actual=$(sha256sum "$candidate")
[ "${actual%% *}" = "$expected_hash" ]
sh -n "$candidate"
chmod 755 "$candidate"
mv "$candidate" /run/m39-pmic-pulse.sh
kill -CONT "$service_pid"
frozen=0
finished=1
echo installed > "$status"
echo 'Installed controller while idle; charging service and limits unchanged.'
