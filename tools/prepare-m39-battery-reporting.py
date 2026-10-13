#!/usr/bin/env python3
"""Suppress unvalidated estimates in the M39 public power_supply interface."""
from pathlib import Path

path = Path(__file__).resolve().parent / 'mt6735-kernel/drivers/power/mediatek/battery_common.c'
text = path.read_text()
helper = '''/* The diagnostic M39 DT is explicitly tagged by its verified LCD GPIO.
 * This changes public reporting only, never internal charging/thermal policy. */
static bool m39_battery_estimates_unvalidated(void)
{
#ifdef CONFIG_OF
	struct device_node *node = of_find_node_by_path("/odm/led@6");
	u32 gpio;
	bool matched = node &&
		!of_property_read_u32(node, "m39,verified-lk-gpio", &gpio) && gpio == 69;
	of_node_put(node);
	return matched;
#else
	return false;
#endif
}

'''
signature = 'static int battery_get_property(struct power_supply *psy,'
if helper not in text:
    assert text.count(signature) == 1
    text = text.replace(signature, helper + signature)
needle = '''	struct battery_data *data = container_of(psy, struct battery_data, psy);

	switch (psp) {'''
replacement = '''	struct battery_data *data = container_of(psy, struct battery_data, psy);

	if (m39_battery_estimates_unvalidated()) {
		switch (psp) {
		case POWER_SUPPLY_PROP_STATUS:
			val->intval = POWER_SUPPLY_STATUS_UNKNOWN;
			return 0;
		case POWER_SUPPLY_PROP_HEALTH:
			val->intval = POWER_SUPPLY_HEALTH_UNKNOWN;
			return 0;
		case POWER_SUPPLY_PROP_PRESENT:
		case POWER_SUPPLY_PROP_CAPACITY:
		case POWER_SUPPLY_PROP_batt_temp:
		case POWER_SUPPLY_PROP_TemperatureR:
		case POWER_SUPPLY_PROP_BatteryAverageCurrent:
		case POWER_SUPPLY_PROP_status_smb:
		case POWER_SUPPLY_PROP_capacity_smb:
		case POWER_SUPPLY_PROP_present_smb:
			/* No cell thermometry, calibrated gauge or valid detector yet. */
			return -ENODATA;
		default:
			break; /* Retain voltage/raw ADC diagnostics and chemistry. */
		}
	}

	switch (psp) {'''
start = text.index(signature)
before, function = text[:start], text[start:]
legacy = '\t\tcase POWER_SUPPLY_PROP_BatteryAverageCurrent:\n\t\t\t/* No cell thermometry'
if legacy in function:
    function = function.replace(legacy,
        '\t\tcase POWER_SUPPLY_PROP_BatteryAverageCurrent:\n'
        '\t\tcase POWER_SUPPLY_PROP_status_smb:\n'
        '\t\tcase POWER_SUPPLY_PROP_capacity_smb:\n'
        '\t\tcase POWER_SUPPLY_PROP_present_smb:\n'
        '\t\t\t/* No cell thermometry')
if replacement not in function:
    assert function.count(needle) == 1
    function = function.replace(needle, replacement)
path.write_text(before + function)
print('Prepared M39-only unknown/unavailable reporting; charging and thermal algorithms unchanged.')
