# BL-25BI research — 2026-10-13

## Result that changes the working hypothesis

NTC-equipped BL-25BI/25BI-compatible variants are explicitly advertised.
The exact MKTEL-supplied pack is not identified. A fixed-ID resistor remains
one possible explanation of the unchanged reading; it is not established.
9.90kOhm alone is also compatible with a nominal10kOhm NTC near25C.
No independently measured before/after temperature pair was obtained.
Do not repeat warming/resistance requests: user explicitly rejected more of
those tests. Do not declare the sensor absent or calibrate it from one point.

## Evidence and provenance

1. Itel-hosted declaration for it9220 specifies BL-25BI,3.7V2500mAh/9.25Wh,
   maximum4.2V. Strong source for that listed pack's ratings; no pinout/curve.
   https://www.itel-life.com/fileadmin/assets/img/User_Manul/20240812/it9220_Declaration_of_conformity.pdf
2. Itel-branded February2024 accessories price list explicitly advertises
   BL-25BI with NTC support. Third-party Scribd upload of a brand document;
   not independently authenticated through an Itel-hosted copy.
   https://www.scribd.com/document/708289353/February-Pricelist
3. Zhongshan Tianmao Battery's own manufacturer listing has a compatibility
   table row BP826/25BI(withNTC), cellcodeP624475ARG,2500mAh. This is direct
   supplier evidence of an NTC-equipped variant, not the user's supplier.
   No resistance/temperature curve, pin mapping or cutoffs are specified.
   https://tmbbattery.en.made-in-china.com/product/dQgrwuWMrBhk/China-Rechargeable-Lithium-Ion-Battery-with-Wire-for-3c-Digital-Customizable.html
4. Mirrored service/material report repeatedly labels BL25BI2500mAh NTC NBIS.
   Upload provenance is unverified. Corroborating lead only; don't decode NBIS
   or assign part-code25001981 from flattened table ordering without proof.
   https://www.scribd.com/document/775007640/Itel-1-August-to-30-September
5. MediaTek technical brief identifies MT6328BATON pinP2 as battery NTC input,
   and TREF pinP13 as reference output. It establishes chip capability,
   not M39 board wiring or sensor presence inside this specific pack.
   https://www.nikom.biz/pic_info/A101016/MT6328.PDF
6. Vishay NTCLE100 datasheet has10kOhm-at25C parts with2/3/5percent tolerances.
   This is an EXAMPLE showing9.90kOhm is not a sensor-absence proof. It is
   not an identification of the battery's thermistor or its beta value.
   https://www.vishay.com/docs/29049/ntcle100.pdf

## Observations on the user's pack

Label: BL-25BI,3.7V2500mAh,4.2V maximum. No identifiable maker reported.
User-provided S/N: ZJ2024088888. Exact searches found no relevant indexed
manufacturer/decoder match. Do not infer a date, maker or authenticity from
ZJ/202408/8888. No serial-code mapping was established.
Detached-battery DC: centre-to-minus0.00V; plus-to-centre3.46V. Supports a
negative-referenced middle contact. It does not identify its internal component.
Detached-battery resistance middle-to-minus repeatedly9.90kOhm. Touch-based
warming observations did not provide a quantified sensor temperature change.

## Concrete kernel configuration mismatch to investigate

Actual compiled dependency file references mt6735/mach/mt_battery_meter_table.h.
That header sets BAT_NTC_10=0,BAT_NTC_47=1,RBAT_PULL_UP_R=61900,
RBAT_PULL_UP_VOLT=1800. The conversion in battery_meter.c computes
R = Rp * V / (Vbias - V). At406mV this yields18028Ohm, exactly matching earlier
source-kernel output. That is not the independently measured9900Ohm contact.

If all measurements are comparable and bias really1.8V, the simple-divider
model implies Rp approximately34.0kOhm;33kOhm is a candidate, not measured.
If Rp were16.9kOhm, an approximately1.10V bias could fit the same point.
One point does not distinguish gain/reference/pull-up/wiring/temperature errors.
The datasheet advertises nominalTREF1.8V, not a measurement of this board.
Do not change runtime calibration or restore temperature reporting on this basis.
Calculation artifact: bl25bi-profile-mismatch.json.

## Device-tree and circuit-model follow-up

The current base DT has a `/bus/bat_meter` node, but it contains only
compatible/phandle properties. The surviving original merged-board DTS also
has no rbat_pull_up_r, rbat_pull_up_volt or batt_temperature_table overrides.
The driver's DT parser therefore has no board-specific values from these
artifacts to replace the header defaults. This is evidence about the examined
artifacts, not proof of the original factory calibration or physical circuit.

The earlier simple-divider inference is not unique. With a 16.9kOhm pull-up
and 1.8V reference, 406mV corresponds to an effective resistance of about
4.92kOhm. A roughly 9.79kOhm board shunt in parallel with a 9.90kOhm contact
would fit that same point. No such M39 shunt has been discovered or measured.
This is another arithmetic explanation, not permission to adopt that profile.
The source itself supports optional RBAT_PULL_DOWN_R compensation in its
voltage-to-resistance conversion; the examined profile header does not define
that macro. These alternatives prevent identifying pull-up or sensor type
from one resistance/ADC pair alone.

## Claims not established

## Reference-board schematic checked visually

Xunlong Orange Pi 4G-IOT V1.1 schematic, sheet 14, shows battery PAD1
connected to VBATREF through R1=16.9kOhm and to BAT_ON through a separate
R1406=1kOhm series resistor. PAD2 returns through R1408=0.01Ohm to ground
with CS_N/CS_P sense connections. Sheet 5 identifies MT6328 and its TREF
pin; sheet 14 uses a separate external charger U6. This is an actual
reference-board wiring example, not the M39 wiring or its charge settings.
No parallel 10kOhm shunt appears in that battery-pad network.

For an ideal high-impedance ADC and 1.8V bias, 9.90kOhm against 16.9kOhm
would give about 665mV, not the observed 406mV. A series 1kOhm resistor
alone would not account for that difference without input loading or other
circuit effects. Thus simply selecting the donor's 10k profile is still
unsupported. The M39 pull-up, excitation, input loading and connection
remain to be identified.

Source (manufacturer-authored schematic mirrored by distributor):
https://download.kamami.pl/p570325-ORANGE_PI-4G%20IOT-V1.1_schematic_180711.pdf
Saved PDF: orangepi-4g-iot-schematic.pdf; visual crop:
orangepi-battery-network.png. Lightweight PDF rendering dependencies
pypdfium2 and Pillow were installed only in the host project's virtualenv.

Additional lead: Azumi A40LT manufacturer schematic, FCC attachment2744719,
lists a 16.9kOhm pull-up and NC_R/10k R2102. Its text extraction does not
establish R2102 wiring or population; local PDF download returned HTTP403.
Do not treat that uninspected optional component as a discovered M39 shunt.
https://device.report/m/06d1a9452e53bd8fd1f79db5d630627989ad0ac1d172dcfaa5a1be1c6648f81a

### Remaining unproven claims

## ADC and reference-control audit

Inspected vendor pmic_auxadc.c and the actual diagnostic m39-pmic-pulse.sh:
both use channel3 BATON, 12-bit output scaled as raw*1800/4096. The helper
reads channel3 at0x0e06, reorders its output after the PMIC diode channel,
and the shell caller labels the reordered value BATON. No channel swap or
obvious 12/15-bit scaling discrepancy was found in these paths. This checks
software consistency, not physical ADC calibration or input loading.

Vendor pmic.c declares VTREF with a fixed1.8V voltage table. upmu_hw.h maps
TREF enable/control/stability/status to0x0a44, battery presence/detection
controls to0x0f56, and high-temperature controls/status to0x0f9e. No software
selectable1.1V TREF voltage was found in those definitions. The source's
commented0x0a44 write is not an executed initialization. Physical TREF and
M39 board excitation still need measurement or authoritative board evidence.

Next read-only evidence: capture0x0a44,0x0f56,0x0f9e and the AUXADC input
selection register alongside current boot identification. No speculative
enable-bit changes are justified by this audit. At the host USB inventory
check the phone was absent; reconnection requested, no reader left running.

## Live sensing-control read after reconnection

Boot UUID0ddc886e-fe94-4b85-943c-aa92ba3552d8. No userspace charging
controller in the process inventory; owner lease0. Hardware register read
selectors only were used (four hex digits plus newline), not configuration
writes. Evidence: logs/battery-sensing-registers.txt and precheck log.

- TREF0x0a44=49418 (0xc10a): requested enable bit1=1, software-control
  bit3=1, stability-delay field=1, stable status bit14=1, enabled status
  bit15=1. The reference is digitally reported enabled/stable, not measured
  with a voltmeter. This weakens the disabled-reference hypothesis.
- BATON0x0f56=1: presence-enable bit0=1; TDET bit2 and software TDET bit8=0.
- High-temperature0x0f9e=0: enable/status/control fields read0.
- AUXADC selection0x0eb2=0: mapped alternate input/temperature-detection
  selection bits read0. Register names alone do not establish analog loading.
- Public raw BATON report407mV; battery3472mV; charger5118mV.
- Additional read: charger gates0x0f48=99 (0x63), CHR_EN bit4=0 and
  CSDAC_EN bit3=0, confirming charging is off in this boot. Analog mux
  control0x0f68=4 has VSEN mux/external-BATON/VSEN-enable bits8/9/11=0.
  Evidence: logs/battery-sensing-registers-extra.txt.

No charger configuration, thermal calibration or firmware was changed.
These live controls narrow the reference-state explanation but still do not
identify a sensor, resistor network or reliable cell-temperature conversion.

## Surviving LK ADC initialization recovered

Expanded offline candidate scan to ARM immediates and PC-relative literal
loads as well as Thumb. Found one raw-register candidate at0xb8b4; the old
flag-ID-only scan did not include this raw-address path. Artifacts:
lk-battery-reference-candidates.json and lk-tref-candidate.disassembly.txt.

At0xb89c a routine accepts channel0..15;0xb8b0 loads value0x010a and0xb8b4
loads register0x0a44, then calls0xb730. That helper supplies mask0xffff,
shift0 and branches to the verified masked PMIC writer0xb6bc. The writer
reads via wrapper0x5678 with operation0, applies the mask, and calls the
wrapper with operation1. The ADC routine subsequently writes request
register0x0e8a with1<<channel. This supports identifying the candidate as
actual TREF initialization within the surviving LK ADC routine.

Live0xc10a agrees with programmed0x010a for the relevant low control bits;
the additional0xc000 consists of the enabled/stable status bits. This is
consistent with the surviving LK reference setup, not a software-disabled
reference or discovered alternative voltage. No binary or runtime settings
were changed. Firmware provenance remains uncertain after the historical
cross-device flash; this is not proof of factory M39 calibration.

- Actual middle-contact function, thermistor R25/beta/curve and placement.
- Internal PCM part numbers, thermal cutoff or independent thermal protection.
- Real battery capacity/health, permitted charge current for this supplied pack.
- A universal BL-25BI pinout or serial decoding scheme.
- Full unattended charging safety, completion or calibrated percentage.

Some replacement listings reuse inconsistent dimensions/capacities/charge
ratings. The TruePower listing reviewed is visibly generic/inconsistent and
is not a basis for changing current or voltage limits. Reseller claims of
thermal protection are not component-level evidence for the user's pack.

## Next productive evidence

Identify a maker-specific BL-25BI datasheet or M39 board circuit/calibration,
then correlate with the actual pack. Request R25,tolerance,beta/curve,third-pin
connection and PCM/thermal cutoffs if manufacturer documentation becomes
available. No outreach has been sent. Keep charging development separate
from unproven sensor assumptions; existing engineering limits stay unchanged.
