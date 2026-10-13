# Updated evidence — read first

See [BL25BI-RESEARCH.md](BL25BI-RESEARCH.md). Later lookup found explicitNTC
support in an Itel-branded catalog and a manufacturer's25BIcompatibility table.
Thus the earlier fixed-ID hypothesis below is NOT a confirmed identification.
Actual pack function remainsunknown. The compiled kernel's47k/61.9k profile
also disagrees with the measuredcontact/simple-divider evidence. No runtime
calibration or protection limits have been changed on those assumptions.

# Battery sensor audit — 2026-10-13

## Established

The battery middle-to-minus contact measured approximately9.90kOhm and did
not change detectably after repeated gentle palm warming. Live BATON ADC was
approximately406–409mV despite visible PMIC-die warming. These observations
support a fixed-ID-resistor hypothesis but do not prove it: actual cell/sensor
temperature change was not independently measured.

The source MT6328 charging_hw_init explicitly disables RG_BATON_HT_EN.
Historical live reads show0f9e=0, so that high-temperature path was disabled.
Do not enable it blindly: its threshold/calibration and contact suitability
have not been established. Its name does not prove protection of this cell.

The original LK flag descriptor table was independently recovered from its
actual Thumb setter, at file offset0x3b34c, with12-byte entries. Nineteen
validated descriptors cover TREF0a44/BATON0f56/high-temperature0f9e controls.
A direct Thumb-immediate candidate scan found no uses of those IDs; this does
NOT exclude computed flags, ARM code, preloader setup, or hardware behavior.
Reproduce with .venv/bin/python tools/audit-lk-battery-controls.py.
Evidence: lk-battery-control-audit.json and earlier live input logs.

The originalLK low-voltage charger loop0x1aad4..0x1abe4 checks battery voltage,
charger presence/input voltage and charging current. It exits around3450mV.
No cell-temperature check was established in this loop. This is a boot
threshold loop, not evidence for a normal long-running charging policy.

## Public documentation

Itel manufacturer declaration for it9220 identifies BL-25BI as3.7V2500mAh,
maximum charge4.2V. It does not document third-contact identity/NTC curve.
https://www.itel-life.com/fileadmin/assets/img/User_Manul/20240812/it9220_Declaration_of_conformity.pdf
Matching model text does not establish authenticity or internal construction
of the battery supplied with this MKTEL phone.

## Implications

Do not fit an NTC curve to a fixed resistance merely to make a displayed
number look plausible. Keep converted kernel battery temperature explicitly
unvalidated. PMIC temperature is a chip measurement, not cell temperature.
Software alone has not established a reliable cell-temperature input.
Normal unattended/full charging therefore remains unvalidated. Further
hardware evidence would require documented battery-contact construction or
an independently measured, repeatable sensor response. Current opt-in bounded
charging remains separate from production plug-to-charge policy.
