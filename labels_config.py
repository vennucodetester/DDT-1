"""
Header Labels Configuration for Calculations Tab
================================================

Edit this file to change the Calculations tab headers without touching code.

How to update (easy steps):
1) MAIN_SECTIONS controls the top row group titles and their column spans.
2) SUB_SECTIONS controls the second row labels (one string per column, left→right).
3) COLUMN_NAMES controls the third row raw data keys (must match DataFrame columns).

Tips:
- To rename a header, simply change the string in SUB_SECTIONS.
- To add/remove a column, update all three lists consistently.
- Keep the number of items in SUB_SECTIONS equal to the total span in MAIN_SECTIONS.
- Keep COLUMN_NAMES length equal to SUB_SECTIONS length.

For coil groups (LH/CTR/RH), the first two columns are:
- TXV out (T_1a-*)
- Coil in (T_1b-* for LH/CTR, T_1c-rh for RH)

This fixes the previous issue where both first two labels showed as "TXV out".
"""

# Row 1: Main section headers (text, span)
MAIN_SECTIONS = [
    ("AT LH coil", 8),
    ("AT CTR coil", 8),
    ("AT RH coil", 8),
    ("At compressor inlet", 7),
    ("Comp outlet", 2),
    ("At Condenser", 7),
    ("At TXV LH", 4),
    ("At TXV CTR", 4),
    ("At TXV RH", 4),
    ("TOTAL", 2),
]

# Row 2: Sub-section headers (descriptive labels for each column)
# IMPORTANT: Keep this list length equal to sum of spans in MAIN_SECTIONS (54)
SUB_SECTIONS = [
    # AT LH coil (8)
    "TXV out", "Coil in", "Coil out", "T sat", "Superheat", "Density", "Enthalpy", "Entropy",
    # AT CTR coil (8)
    "TXV out", "Coil in", "Coil out", "T sat", "Superheat", "Density", "Enthalpy", "Entropy",
    # AT RH coil (8)
    "TXV out", "Coil in", "Coil out", "T sat", "Superheat", "Density", "Enthalpy", "Entropy",
    # At compressor inlet (7)
    "Pressure", "Temp", "T sat", "Superheat", "Density", "Enthalpy", "Entropy",
    # Comp outlet (2)
    "Temp", "RPM",
    # At Condenser (7)
    "Inlet", "Pressure", "Outlet", "T sat", "Subcool", "Water in", "Water out",
    # At TXV LH (4)
    "Temp", "T sat", "Subcool", "Enthalpy",
    # At TXV CTR (4)
    "Temp", "T sat", "Subcool", "Enthalpy",
    # At TXV RH (4)
    "Temp", "T sat", "Subcool", "Enthalpy",
    # TOTAL (2)
    "Mass flow", "Capacity",
]

# Row 3: Actual DataFrame column keys (must match processed_df columns)
# Keep this list length equal to SUB_SECTIONS length.
COLUMN_NAMES = [
    # LH Coil (8)
    "T_1a-lh", "T_1b-lh", "T_2a-LH", "T_sat.lh", "S.H_lh coil", "D_coil lh", "H_coil lh", "S_coil lh",
    # CTR Coil (8)
    "T_1a-ctr", "T_1b-ctr", "T_2a-ctr", "T_sat.ctr", "S.H_ctr coil", "D_coil ctr", "H_coil ctr", "S_coil ctr",
    # RH Coil (8)
    "T_1a-rh", "T_1c-rh", "T_2a-RH", "T_sat.rh", "S.H_rh coil", "D_coil rh", "H_coil rh", "S_coil rh",
    # Compressor Inlet (7)
    "P_suction", "T_2b", "T_sat.comp.in", "S.H_total", "D_comp.in", "H_comp.in", "S_comp.in",
    # Comp Outlet (2)
    "T_3a", "rpm",
    # Condenser (7)
    "T_3b", "P_disch", "T_4a", "T_sat.cond", "S.C", "T_waterin", "T_waterout",
    # TXV LH (4)
    "T_4b-lh", "T_sat.txv.lh", "S.C-txv.lh", "H_txv.lh",
    # TXV CTR (4)
    "T_4b-ctr", "T_sat.txv.ctr", "S.C-txv.ctr", "H_txv.ctr",
    # TXV RH (4)
    "T_4b-rh", "T_sat.txv.rh", "S.C-txv.rh", "H_txv.rh",
    # TOTAL (2)
    "m_dot", "qc",
]


