#!/bin/sh
# GPL-2.0-only. Pure policy decisions; no hardware writes.
# Target remains 3.9V until higher-voltage behavior is independently verified.
m39_policy_decide() {
    state=$1 connected=$2 voltage=$3 age=$4 terminal=$5 off_verified=$6
    case "$state" in idle|charging|target_hold|fault) ;; *) echo fault; return;; esac
    case "$connected:$off_verified" in 0:0|0:1|1:0|1:1) ;; *) echo fault; return;; esac
    case "$voltage:$age" in *[!0-9:]*|:*|*:) echo fault; return;; esac
    [ "$age" -le 5 ] && [ "$voltage" -ge 2700 ] && [ "$voltage" -le 4300 ] || { echo fault; return; }
    # Faults are latched. A separate fresh validation must explicitly clear them.
    [ "$state" != fault ] || { echo fault; return; }
    case "$terminal" in
        none) ;;
        time_limit|interval_limit|voltage_limit)
            [ "$off_verified" = 1 ] || { echo fault; return; } ;;
        unplugged|stop_requested)
            [ "$off_verified" = 1 ] || { echo fault; return; }
            echo idle; return ;;
        *) echo fault; return ;;
    esac
    if [ "$connected" = 0 ]; then echo idle; return; fi
    # Leaving charge to the existing bootloader/precharge path at low voltage.
    if [ "$voltage" -lt 3200 ]; then echo low_voltage; return; fi
    if [ "$terminal" = voltage_limit ] && [ "$voltage" -lt 3900 ]; then
        echo fault; return
    fi
    if [ "$voltage" -ge 3900 ]; then echo target_hold; return; fi
    if [ "$state" = target_hold ] && [ "$voltage" -gt 3750 ]; then
        echo target_hold; return
    fi
    # The caller must verify charger-off and acquire a fresh bounded lease
    # before starting a new controller. Never extend an active lease here.
    if [ "$state" != charging ] || [ "$terminal" != none ]; then
        [ "$off_verified" = 1 ] || { echo fault; return; }
        echo start_bounded; return
    fi
    echo charging
}
