#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Candidate discharge policy. Threshold needs hardware validation before use.
m39_low_battery_decide() {
    voltage=$1 input=$2 age=$3 samples=$4
    for value in "$voltage" "$age" "$samples"; do
        case "$value" in ''|*[!0-9]*|0[0-9]*) echo unavailable; return;; esac
        [ "${#value}" -le 6 ] || { echo unavailable; return; }
    done
    [ "$age" -le 5 ] && [ "$voltage" -ge 2700 ] && [ "$voltage" -le 4300 ] || {
        echo unavailable; return;
    }
    case "$input" in true) echo powered; return;; false) ;; *) echo unavailable; return;; esac
    # 3.4V is a conservative development candidate above the observed low-
    # voltage boot problems. It is not a calibrated state-of-charge estimate.
    if [ "$voltage" -gt 3400 ]; then echo healthy
    elif [ "$samples" -lt 3 ]; then echo low_pending
    else echo shutdown_recommended; fi
}
