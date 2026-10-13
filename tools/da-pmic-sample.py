#!/usr/bin/env python3
"""Sample MT6328 battery ADC without Linux or charger-control writes."""
import json
from da_pmic import Pmic, ROOT

pmic = Pmic()
try:
    result = {'samples': [pmic.sample() for _ in range(3)],
              'charger_control': pmic.read(0x0f48),
              'adc_measurement_writes': pmic.writes,
              'charger_register_writes': False, 'flash_writes': False}
    (ROOT / 'analysis/da-pmic-samples.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
finally:
    pmic.close()
