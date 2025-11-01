"""
ph_data_builder.py

Build 12 averaged state points (4 per module × 3 modules) from the
entire Calculations dataframe for plotting on a P–h diagram (R290).

Points per module (averaged across full columns):
 - T1b: Coil inlet temperature at suction pressure (low side)
 - T2b: Compressor inlet temperature at suction pressure (low side)
 - T3b: Condenser inlet temperature at discharge pressure (high side)
 - T4b: TXV inlet temperature at discharge pressure (high side)

Returns enthalpy h in kJ/kg and pressure P in kPa for each point.
"""

from typing import Dict, Any
import numpy as np
import pandas as pd
import logging

try:
    from CoolProp.CoolProp import PropsSI
except Exception:
    PropsSI = None

logger = logging.getLogger(__name__)


MODULE_KEYS = {
    'LH': {
        'T1b': 'T_1b-lh',
        'T4b': 'T_4b-lh',
    },
    'CTR': {
        'T1b': 'T_1b-ctr',
        'T4b': 'T_4b-ctr',
    },
    'RH': {
        'T1b': 'T_1c-rh',  # In current dataset right-hand coil inlet is 1c
        'T4b': 'T_4b-rh',
    },
}


def _to_float_series(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series([], dtype=float)
    return pd.to_numeric(s, errors='coerce')


def _avg(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns:
        return np.nan
    ser = _to_float_series(df[col])
    if ser.dropna().empty:
        return np.nan
    return float(ser.dropna().mean())


def _psig_to_pa(psig: float) -> float:
    if psig is None or np.isnan(psig):
        return np.nan
    return (psig + 14.696) * 6894.76


def _f_to_k(temp_f: float) -> float:
    if temp_f is None or np.isnan(temp_f):
        return np.nan
    return (temp_f + 459.67) * 5.0 / 9.0


def _enthalpy_kj_kg(temp_f: float, P_pa: float, refrigerant: str) -> float:
    if PropsSI is None:
        return np.nan
    T_K = _f_to_k(temp_f)
    if np.isnan(T_K) or np.isnan(P_pa) or P_pa <= 0:
        return np.nan
    try:
        return float(PropsSI('H', 'T', T_K, 'P', P_pa, refrigerant) / 1000.0)
    except Exception:
        return np.nan


def compute_averaged_points(df: pd.DataFrame, refrigerant: str = 'R290') -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Compute averaged P–h points for LH/CTR/RH modules.

    Returns:
        {
          'LH': { 'T1b': {'h': .., 'P': ..}, 'T2b': {...}, 'T3b': {...}, 'T4b': {...} },
          'CTR': { ... },
          'RH': { ... }
        }
    """
    if df is None or df.empty:
        return {'LH': {}, 'CTR': {}, 'RH': {}}

    # Pressures: prefer Pa columns if present; else convert from psig
    P_suc_pa = np.nan
    P_cond_pa = np.nan

    if 'P_suc' in df.columns:
        P_suc_pa = _avg(df, 'P_suc')
    if 'P_cond' in df.columns:
        P_cond_pa = _avg(df, 'P_cond')

    if np.isnan(P_suc_pa):
        psig = _avg(df, 'P_suction') if 'P_suction' in df.columns else np.nan
        if np.isnan(psig):
            psig = _avg(df, 'Press.suc') if 'Press.suc' in df.columns else np.nan
        P_suc_pa = _psig_to_pa(psig)

    if np.isnan(P_cond_pa):
        psig = _avg(df, 'P_disch') if 'P_disch' in df.columns else np.nan
        if np.isnan(psig):
            psig = _avg(df, 'Press disch') if 'Press disch' in df.columns else np.nan
        P_cond_pa = _psig_to_pa(psig)

    # Common temps
    T2b_f = _avg(df, 'T_2b') if 'T_2b' in df.columns else np.nan
    T3b_f = _avg(df, 'T_3b') if 'T_3b' in df.columns else np.nan

    # Build module dict
    out: Dict[str, Dict[str, Dict[str, float]]] = {'LH': {}, 'CTR': {}, 'RH': {}}

    for module in ['LH', 'CTR', 'RH']:
        keys = MODULE_KEYS[module]
        T1b_col = keys['T1b']
        T4b_col = keys['T4b']

        T1b_f = _avg(df, T1b_col)
        T4b_f = _avg(df, T4b_col)

        # Enthalpies
        # Per latest requirement: point 1b keeps the same enthalpy (x) as T4b,
        # but uses suction pressure for y. So x = h(T4b@Pcond), y = Psuc.
        # We first compute h_T4b at Pcond, then reuse that value for 1b.x
        h_T2b = _enthalpy_kj_kg(T2b_f, P_suc_pa, refrigerant)
        h_T3b = _enthalpy_kj_kg(T3b_f, P_cond_pa, refrigerant)
        h_T4b = _enthalpy_kj_kg(T4b_f, P_cond_pa, refrigerant)
        h_T1b = h_T4b

        out[module]['T1b'] = {'h': h_T1b, 'P': (P_suc_pa / 1000.0 if not np.isnan(P_suc_pa) else np.nan)}
        out[module]['T2b'] = {'h': h_T2b, 'P': (P_suc_pa / 1000.0 if not np.isnan(P_suc_pa) else np.nan)}
        out[module]['T3b'] = {'h': h_T3b, 'P': (P_cond_pa / 1000.0 if not np.isnan(P_cond_pa) else np.nan)}
        out[module]['T4b'] = {'h': h_T4b, 'P': (P_cond_pa / 1000.0 if not np.isnan(P_cond_pa) else np.nan)}

        # Detailed point logs with sensor labels (x=h, y=P)
        if not (np.isnan(out[module]['T3b']['h']) or np.isnan(out[module]['T3b']['P'])):
            logger.info(f"[PH AVG] {module}.T3b from ['T_3b'] -> (x={out[module]['T3b']['h']:.3f} kJ/kg, y={out[module]['T3b']['P']:.3f} kPa)")
        if not (np.isnan(out[module]['T4b']['h']) or np.isnan(out[module]['T4b']['P'])):
            logger.info(f"[PH AVG] {module}.T4b from ['{T4b_col}'] -> (x={out[module]['T4b']['h']:.3f} kJ/kg, y={out[module]['T4b']['P']:.3f} kPa)")
        if not (np.isnan(out[module]['T1b']['h']) or np.isnan(out[module]['T1b']['P'])):
            logger.info(f"[PH AVG] {module}.T1b (x=T4b, y@Psuc) from ['{T4b_col}'] -> (x={out[module]['T1b']['h']:.3f} kJ/kg, y={out[module]['T1b']['P']:.3f} kPa)")
        if not (np.isnan(out[module]['T2b']['h']) or np.isnan(out[module]['T2b']['P'])):
            logger.info(f"[PH AVG] {module}.T2b from ['T_2b'] -> (x={out[module]['T2b']['h']:.3f} kJ/kg, y={out[module]['T2b']['P']:.3f} kPa)")

    # Log summary
    common_count = sum(1 for m in out.values() for pt in m.values() if not (np.isnan(pt.get('h', np.nan)) or np.isnan(pt.get('P', np.nan))))
    lh_count = sum(1 for pt in out['LH'].values() if not (np.isnan(pt.get('h', np.nan)) or np.isnan(pt.get('P', np.nan))))
    ctr_count = sum(1 for pt in out['CTR'].values() if not (np.isnan(pt.get('h', np.nan)) or np.isnan(pt.get('P', np.nan))))
    rh_count = sum(1 for pt in out['RH'].values() if not (np.isnan(pt.get('h', np.nan)) or np.isnan(pt.get('P', np.nan))))
    logger.info(f"[PH AVG] Points built: common={lh_count+ctr_count+rh_count} total, LH={lh_count}, CTR={ctr_count}, RH={rh_count}")

    return out


