#!/usr/bin/env python3
"""Make unsupported MT6328 charge-completion queries fail closed."""
from pathlib import Path

root = Path(__file__).resolve().parent / 'mt6735-kernel'
driver = root / 'drivers/misc/mediatek/power/mt6735/charging_hw_pmic.c'
old = '''static unsigned int charging_get_charging_status(void *data)
{
	unsigned int status = STATUS_OK;
	return status;
}'''
new = '''static unsigned int charging_get_charging_status(void *data)
{
	/* This backend has no validated charge-completion detector. Never leave
	 * the caller's boolean uninitialized or mistake CV mode for full. */
	*(kal_bool *)data = KAL_FALSE;
	return STATUS_UNSUPPORTED;
}'''
text = driver.read_text()
if new not in text:
    assert text.count(old) == 1, 'Unexpected PMIC completion handler'
    driver.write_text(text.replace(old, new))

policy = root / 'drivers/power/mediatek/switch_charging.c'
old = '''static unsigned int charging_full_check(void)
{
	unsigned int status;

	battery_charging_control(CHARGING_CMD_GET_CHARGING_STATUS, &status);'''
new = '''static unsigned int charging_full_check(void)
{
	unsigned int status = KAL_FALSE;

	if (battery_charging_control(CHARGING_CMD_GET_CHARGING_STATUS, &status)) {
		/* Unsupported/failed hardware queries are never completion evidence. */
		g_full_check_count = 0;
		return KAL_FALSE;
	}'''
text = policy.read_text()
if new not in text:
    assert text.count(old) == 1, 'Unexpected full-check caller'
    policy.write_text(text.replace(old, new))
print('Prepared fail-closed completion queries; no full-charge detector invented.')
