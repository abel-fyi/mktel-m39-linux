"""Classify diagnostic completion without inferring capacity or cell health."""
import re

def classify(state, log_tail=''):
    if state.get('charging_off_verified') is not True:
        return 'stopped_with_error'
    if state.get('phase') not in ('stopped', 'aborted'):
        return 'stopped_with_error'
    reason = state.get('stop_reason')
    if reason == 'voltage_limit':
        if state.get('battery_mv', 0) >= state.get('voltage_limit_mv', 3450):
            return 'voltage_cutoff_reached'
        return 'stopped_with_error'
    if state['phase'] == 'stopped':
        outcomes = {'time_limit': 'bounded_run_completed',
                    'interval_limit': 'bounded_run_completed',
                    'stop_requested': 'controlled_stop',
                    'unplugged': 'disconnected_charging_off',
                    'watchdog_test_complete': 'watchdog_cutoff_verified'}
        if reason in outcomes:
            return outcomes[reason]
    if reason is not None:
        return 'stopped_with_error'
    # Compatibility with the older controller, which had no explicit reason.
    cutoff = re.search(r'ABORT: Battery voltage (\d+) outside test range', log_tail)
    if cutoff and int(cutoff[1]) >= state.get('voltage_limit_mv', 3450):
        return 'voltage_cutoff_reached'
    if state['phase'] == 'stopped':
        return 'bounded_run_completed'
    return 'stopped_with_error'
