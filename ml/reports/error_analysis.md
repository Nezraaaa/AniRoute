# Error analysis (auto-generated)

Split: `test` · operating confidence 0.14 · IoU 0.5. Regenerate with `python ml/evaluate.py test`.

## Missed objects by size (fraction of the image area: small < 0.5%, medium < 5%)

| Size | Objects | Missed | Miss rate |
| --- | --- | --- | --- |
| small | 16 | 14 | 88% |
| medium | 148 | 119 | 80% |
| large | 100 | 45 | 45% |

## Missed objects by lighting (dark = LAB lightness mean < 95)

| Lighting | Objects | Missed | Miss rate |
| --- | --- | --- | --- |
| normal | 254 | 172 | 68% |
| dark | 10 | 6 | 60% |

## False alarms by predicted class

- Severe road damage: 84
- Pothole: 34

## Class confusions (true → predicted)

- pothole → severe_road_damage: 1
- severe_road_damage → pothole: 2

## Team interpretation

_Look through `ml/reports/error_gallery/` and write 3–5 sentences here on why the model fails (for example faded cracks, wet asphalt that looks like a pothole, motion blur, shadows). This section is kept when the file is regenerated only if you copy it into docs/EVALUATION.md._
