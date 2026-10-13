from m39_charge_outcome import classify

base = dict(phase='stopped', charging_off_verified=True,
            battery_mv=3900, voltage_limit_mv=3900)
for reason, outcome in [('time_limit', 'bounded_run_completed'),
                        ('interval_limit', 'bounded_run_completed'),
                        ('voltage_limit', 'voltage_cutoff_reached'),
                        ('stop_requested', 'controlled_stop'),
                        ('unplugged', 'disconnected_charging_off'),
                        ('watchdog_test_complete', 'watchdog_cutoff_verified'),
                        ('fault', 'stopped_with_error')]:
    assert classify(dict(base, stop_reason=reason)) == outcome
    assert classify(dict(base, stop_reason=reason, charging_off_verified=False)) == 'stopped_with_error'
    assert classify(dict(base, stop_reason=reason, phase='off_restore_failed')) == 'stopped_with_error'
assert classify(dict(base, stop_reason='voltage_limit', phase='aborted')) == 'voltage_cutoff_reached'
assert classify(dict(base, stop_reason='voltage_limit', battery_mv=3800)) == 'stopped_with_error'
assert classify(dict(base, stop_reason='fault'), 'ABORT: Battery voltage 3900 outside test range') == 'stopped_with_error'
assert classify(dict(base, phase='aborted'), 'ABORT: Battery voltage 3900 outside test range') == 'voltage_cutoff_reached'
assert classify(base) == 'bounded_run_completed'
print('PASS: explicit completion/unplug/fault reasons, inconsistent cutoff rejection, cleanup failure and legacy compatibility.')
