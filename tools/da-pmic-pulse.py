#!/usr/bin/env python3
"""Bounded, supervised MT6328 charging diagnostic in download-agent mode.

Default is measurement/plan only. --pulse additionally requires a person
watching a cool battery. This is NOT an unattended charging implementation.
"""
import argparse
import json
import signal
import time
from da_pmic import Pmic, ROOT

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pulse', action='store_true')
parser.add_argument('--supervised-cool-battery', action='store_true')
parser.add_argument('--take-over-active', action='store_true',
                    help='Disable existing bootloader charging before the bounded test; leave it off afterward')
parser.add_argument('--stage-main-gate', action='store_true',
                    help='Test main control with DAC off before HWCV configuration; requires at least 3.20V')
parser.add_argument('--watchdog-test', action='store_true',
                    help='Observe up to eight seconds without refreshing watchdog, then disable charging')
parser.add_argument('--supervised-minute', action='store_true',
                    help='Observe up to 60 seconds with watchdog refresh; requires saved successful watchdog test')
parser.add_argument('--precharge', action='store_true',
                    help='Use minimum 70mA current and 3.00V lower diagnostic threshold')
args = parser.parse_args()
if args.pulse and not args.supervised_cool_battery:
    parser.error('Physical observer/cool-battery confirmation required')
if args.take_over_active and not args.pulse:
    parser.error('--take-over-active requires --pulse')
if args.stage_main_gate and not args.pulse:
    parser.error('--stage-main-gate requires --pulse')
if args.watchdog_test and not args.pulse:
    parser.error('--watchdog-test requires --pulse')
if args.supervised_minute:
    if not args.pulse or not args.stage_main_gate or args.watchdog_test:
        parser.error('--supervised-minute requires --pulse --stage-main-gate and excludes --watchdog-test')
    evidence = json.loads((ROOT / 'analysis/charger-watchdog-validated-result.json').read_text())
    expiry_rows = [s for s in evidence.get('samples', [])
                   if s.get('watchdog_status', 0) & 4 and not s.get('charger_control', 0x18) & 0x18]
    if not expiry_rows or not evidence.get('charging_off_verified') or evidence.get('error'):
        parser.error('Saved watchdog cutoff evidence is missing or unsuccessful')

pmic = Pmic()
result = {'mode': 'pulse' if args.pulse else 'plan', 'samples': [],
          'enabled': False, 'restored': False, 'flash_writes': False}
current_ma = 70 if args.precharge else 200
current_code = 15 if args.precharge else 14
minimum_mv = 3000 if args.precharge else 3200
observation_seconds = 8 if args.watchdog_test else 3
if args.supervised_minute:
    observation_seconds = 60
    minimum_mv = max(minimum_mv, 3200)
if args.stage_main_gate:
    minimum_mv = max(minimum_mv, 3200)
profile = [(0x0f62, 0x1f, 0x10), (0x0f66, 1, 1),
           (0x0f4e, 0x1f, 0), (0x0f50, 0x0f, current_code),
           (0x0f7a, 0x02, 0),
           (0x0f4c, 0x0a, 0x0a), (0x0f7a, 0x04, 0x04),
           (0x0f7a, 0x40, 0x40),
           (0x0f74, 0x77, 0x21), (0x0f76, 0x77, 0x14)]
saved = {}
controls_started = False

def guard(sample, diode_baseline):
    mv = sample['battery_mv']
    usb_mv = sample['charger_divider_mv'] * 369 // 39
    diode = sample['pmic_temp_diode_mv']
    if not minimum_mv <= mv < 3450:
        raise RuntimeError(f'Battery {mv}mV outside diagnostic range')
    if not 4500 <= usb_mv <= 5500:
        raise RuntimeError(f'USB estimate {usb_mv}mV outside range')
    if not 650 <= diode <= 800 or diode_baseline - diode > 5:
        raise RuntimeError('PMIC diode reading invalid or warming rapidly')
    if not pmic.read(0x0f54) & 1:
        raise RuntimeError('Hardware battery-overvoltage protection disabled')

def stop_signal(signum, frame):
    raise KeyboardInterrupt(f'Signal {signum}')

signal.signal(signal.SIGINT, stop_signal)
signal.signal(signal.SIGTERM, stop_signal)
try:
    before = pmic.sample()
    result['samples'].append({'phase': 'before', **before})
    baseline = before['pmic_temp_diode_mv']
    guard(before, baseline)
    initially_active = bool(pmic.read(0x0f48) & 0x18)
    result['initially_active'] = initially_active
    if initially_active and not args.take_over_active:
        raise RuntimeError('Charger already active; refusing test')
    saved = {address: pmic.read(address) for address, _, _ in profile}
    result['saved_registers'] = {hex(k): v for k, v in saved.items()}
    result['plan'] = {'current_ceiling_ma': current_ma, 'cv_ceiling_mv': 3775,
                      'minimum_battery_mv': minimum_mv,
                      'observation_seconds': observation_seconds, 'watchdog_configured_seconds': 4,
                      'watchdog_operation_validated': bool(args.supervised_minute),
                      'battery_temperature_verified': False}
    result['plan']['stage_main_gate'] = args.stage_main_gate
    print(json.dumps({'before': before, 'plan': result['plan']}, indent=2), flush=True)
    if args.pulse:
        pmic.allow_charger_controls = True
        controls_started = True
        if initially_active:
            pmic.charger_field(0x0f48, 0x18, 0)
            result['existing_charging_disabled'] = True
        for address, mask, bits in profile:
            # Original M39 LK (1aa62..1aa86) sets CSDAC_MODE after
            # CSDAC_EN/CHR_EN. It does not retain the value with charging off.
            if address == 0x0f7a and mask == 0x04:
                continue
            if args.stage_main_gate and address == 0x0f7a and mask == 0x40:
                continue
            pmic.charger_field(address, mask, bits)
            if address == 0x0f62:
                pmic.charger_field(0x0f62, 0x100, 0x100, action=True)
            if address == 0x0f66:
                pmic.charger_field(0x0f66, 2, 2, action=True)
        fresh = pmic.sample()
        guard(fresh, baseline)
        pmic.charger_field(0x0f66, 2, 2, action=True)
        pmic.charger_field(0x0f62, 0x100, 0x100, action=True)
        started = time.monotonic()
        deadline = started + observation_seconds
        if args.stage_main_gate:
            # Investigate control gating without setting CSDAC_EN. Do not
            # assume zero physical current: charger behavior is unvalidated.
            pmic.charger_field(0x0f48, 0x18, 0x10)
            result['main_gate_enabled'] = True
            pmic.charger_field(0x0f7a, 0x40, 0x40)
            pmic.charger_field(0x0f7a, 0x04, 0x04)
            result['samples'].append({'phase': 'main-gate', **pmic.sample()})
            guard(result['samples'][-1], baseline)
            if time.monotonic() >= deadline:
                raise RuntimeError('Staging consumed bounded observation window')
        pmic.charger_field(0x0f48, 0x18, 0x18)
        result['enabled'] = True
        pmic.charger_field(0x0f7a, 0x04, 0x04)
        last_watchdog_refresh = time.monotonic()
        while time.monotonic() < deadline:
            sample = pmic.sample()
            guard(sample, baseline)
            if pmic.read(0x0f62) & 0x1f != 0x10:
                raise RuntimeError('Watchdog configuration changed')
            row = {'phase': 'during', 'elapsed': time.monotonic() - started,
                   'charger_control': pmic.read(0x0f48),
                   'watchdog_status': pmic.read(0x0f66), **sample}
            result['samples'].append(row)
            print(json.dumps(row), flush=True)
            if args.supervised_minute:
                if row['watchdog_status'] & 4 or row['charger_control'] & 0x18 != 0x18:
                    raise RuntimeError('Charger stopped during supervised observation')
                if time.monotonic() - last_watchdog_refresh >= 1:
                    pmic.charger_field(0x0f62, 0x100, 0x100, action=True)
                    last_watchdog_refresh = time.monotonic()
            if args.watchdog_test and row['watchdog_status'] & 4:
                result['watchdog_expiry_observed_seconds'] = row['elapsed']
                break
            time.sleep(max(0, min(.2, deadline - time.monotonic())))
        if args.watchdog_test and 'watchdog_expiry_observed_seconds' not in result:
            raise RuntimeError('Watchdog expiry not observed within bounded test')
except BaseException as error:
    result['error'] = repr(error)
    print(f'Test stopped: {error}', flush=True)
finally:
    if controls_started:
        # Do not restore higher limits unless charging-off is confirmed first.
        try:
            pmic.charger_field(0x0f48, 0x18, 0)
            result['charging_off_verified'] = not pmic.read(0x0f48) & 0x18
            if not result['charging_off_verified']:
                raise RuntimeError('Cannot confirm charging disabled')
            failures = []
            for address, mask, _ in reversed(profile):
                if address == 0x0f7a and mask == 0x04:
                    # Disabled hardware clears this mode bit; never enable
                    # charging just to restore its formerly active value.
                    result['off_mode_bit'] = pmic.read(address) & mask
                    continue
                try:
                    pmic.charger_field(address, mask, saved[address] & mask)
                except BaseException as error:
                    failures.append(f'{address:#x}: {error}')
            result['restored'] = not failures
            if failures:
                result['restore_errors'] = failures
            result['samples'].append({'phase': 'after', **pmic.sample()})
        except BaseException as error:
            result['cleanup_error'] = repr(error)
            print('Charging-off/restoration unverified: disconnect power and remove battery.', flush=True)
    result['pmic_writes'] = pmic.writes
    (ROOT / 'analysis/da-pmic-pulse-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ['samples', 'pmic_writes']}, indent=2), flush=True)
    pmic.close()
if 'error' in result or 'cleanup_error' in result or result.get('restore_errors'):
    raise SystemExit(1)
