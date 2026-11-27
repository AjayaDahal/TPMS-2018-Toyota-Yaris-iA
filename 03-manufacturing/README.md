# 03 — Manufacturing & JLCPCB Production (TPMS Monitor Panel)

v1 TPMS panel (`production/`):
- `production/tpms_panel_gerbers_jlcpcb.zip` — Ready-to-order JLCPCB Gerber & drill package
- `production/tpms_panel_bom.csv` — Complete component bill of materials
- `production/gerbers/` — Individual copper, mask, silkscreen, and drill layers

v2 carrier PCB, rev A (`v2_carrier/`, written by [build_carrier.py](../01-hardware/v2/carrier/build_carrier.py); order steps in the [carrier README](../01-hardware/v2/carrier/README.md#order-it-at-jlcpcb)):
- `v2_carrier/tpms_v2_carrier_gerbers_jlcpcb.zip` — 2-layer Gerbers, drill files and drill maps: upload this to JLCPCB
- `v2_carrier/tpms_v2_carrier_bom_jlcpcb.csv` and `v2_carrier/tpms_v2_carrier_cpl_jlcpcb.csv` — the Economic PCBA files (under-$59 hybrid: 167 placements, 51 BOM lines)
- `v2_carrier/tpms_v2_carrier_hand_solder_and_dnp.csv` — the 10 chunky SMD power parts + 5 THT connectors you solder yourself, and the empty rework pads
- `v2_carrier/gerbers/` — the same Gerber and drill files, unzipped
