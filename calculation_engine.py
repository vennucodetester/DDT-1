"""
calculation_engine.py

Pure calculation logic for refrigeration cycle P-h points and performance metrics.
Decoupled from any UI; takes normalized inputs and returns structured results.

Assumptions:
- Pressures provided in Pascals (absolute)
- Temperatures provided in Kelvin
- Default refrigerant: R410A
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd

try:
    import CoolProp.CoolProp as CP
except Exception:  # pragma: no cover - CoolProp may not be available in some environments
    CP = None  # type: ignore


# --- Helper Functions for Unit Conversion ---
def f_to_k(temp_f: float) -> float:
    """Converts Fahrenheit to Kelvin."""
    return (temp_f + 459.67) * 5.0 / 9.0

def psig_to_pa(pressure_psig: float) -> float:
    """Converts PSIG (gauge) to Pascals (absolute)."""
    return (pressure_psig + 14.7) * 6894.76

def cm3_to_m3(volume_cm3: float) -> float:
    """Converts cubic centimeters to cubic meters."""
    return volume_cm3 / 1_000_000

def rpm_to_rps(speed_rpm: float) -> float:
    """Converts revolutions per minute to revolutions per second."""
    return speed_rpm / 60.0


def aggregate_values(values: List[float], method: str) -> Optional[float]:
    """
    Aggregate a list of numbers using the provided method.

    method: 'Average' | 'Maximum' | 'Minimum' | 'Last'
    Returns None if values is empty.
    """
    if not values:
        return None
    m = (method or "").strip().lower()
    if m in ("avg", "mean", "average", ""):
        return sum(values) / len(values)
    if m in ("max", "maximum"):
        return max(values)
    if m in ("min", "minimum"):
        return min(values)
    # default: last
    return values[-1]


def _compute_single_coil(
    suction_pressure_pa: float,
    discharge_pressure_pa: float,
    outlet_temp_k: Optional[float],
    refrigerant: str,
) -> Dict:
    """
    Compute P-h points and metrics for a single coil.

    Returns a dict with keys: usedTempK, tSatK, superheatF, p1..p4 (dicts),
    refrigerationEffectKJkg, compressorWorkKJkg, heatRejectedKJkg, cop.
    """
    if CP is None:
        return {
            "error": "CoolProp not available",
        }

    # Point 1: Evaporator outlet
    if outlet_temp_k is None:
        h1 = CP.PropsSI("H", "P", suction_pressure_pa, "Q", 1, refrigerant)
        s1 = CP.PropsSI("S", "P", suction_pressure_pa, "Q", 1, refrigerant)
        t1 = CP.PropsSI("T", "P", suction_pressure_pa, "Q", 1, refrigerant)
    else:
        h1 = CP.PropsSI("H", "P", suction_pressure_pa, "T", outlet_temp_k, refrigerant)
        s1 = CP.PropsSI("S", "P", suction_pressure_pa, "T", outlet_temp_k, refrigerant)
        t1 = outlet_temp_k

    # Saturation at suction
    t_sat = CP.PropsSI("T", "P", suction_pressure_pa, "Q", 1, refrigerant)
    superheat_f = (t1 - t_sat) * 9.0 / 5.0

    # Point 2: Compressor outlet (isentropic)
    h2 = CP.PropsSI("H", "P", discharge_pressure_pa, "S", s1, refrigerant)
    t2 = CP.PropsSI("T", "P", discharge_pressure_pa, "S", s1, refrigerant)

    # Point 3: Condenser outlet (saturated liquid)
    h3 = CP.PropsSI("H", "P", discharge_pressure_pa, "Q", 0, refrigerant)
    t3 = CP.PropsSI("T", "P", discharge_pressure_pa, "Q", 0, refrigerant)

    # Point 4: TXV outlet (isenthalpic)
    h4 = h3
    t4 = CP.PropsSI("T", "P", suction_pressure_pa, "H", h4, refrigerant)

    refrigeration_effect = (h1 - h4) / 1000.0
    compressor_work = (h2 - h1) / 1000.0
    heat_rejected = (h2 - h3) / 1000.0
    cop = (refrigeration_effect / compressor_work) if compressor_work > 0 else 0.0

    def pt(h: float, t: float, p: float) -> Dict[str, float]:
        return {"h_kJkg": h / 1000.0, "t_K": t, "p_kPa": p / 1000.0}

    return {
        "usedTempK": t1,
        "tSatK": t_sat,
        "superheatF": superheat_f,
        "p1": pt(h1, t1, suction_pressure_pa),
        "p2": pt(h2, t2, discharge_pressure_pa),
        "p3": pt(h3, t3, discharge_pressure_pa),
        "p4": pt(h4, t4, suction_pressure_pa),
        "refrigerationEffectKJkg": refrigeration_effect,
        "compressorWorkKJkg": compressor_work,
        "heatRejectedKJkg": heat_rejected,
        "cop": cop,
    }


def compute_cycle(
    suction_pressure_pa: Optional[float],
    discharge_pressure_pa: Optional[float],
    coil_outlet_temps_k: Dict[str, List[float]],
    aggregation_method: str = "Average",
    refrigerant: str = "R410A",
) -> Dict:
    """
    Compute the refrigeration cycle for Left/Center/Right coils.

    coil_outlet_temps_k: { "left": [..], "center": [..], "right": [..] }
    Returns a dict with overall status and per-coil results.
    """
    result: Dict[str, object] = {
        "ok": False,
        "errors": [],
        "pressures": {
            "suctionPa": suction_pressure_pa,
            "dischargePa": discharge_pressure_pa,
        },
        "coils": {},
        "refrigerant": refrigerant,
        "aggregation": aggregation_method,
    }

    # Validate pressures
    if suction_pressure_pa is None:
        result["errors"].append("Missing suction pressure")
    if discharge_pressure_pa is None:
        result["errors"].append("Missing discharge pressure")
    if result["errors"]:
        return result

    try:
        coils = {"left": [], "center": [], "right": []}
        for coil_name in coils.keys():
            raw_values = [v for v in (coil_outlet_temps_k.get(coil_name) or []) if v is not None]
            agg_temp_k = aggregate_values(raw_values, aggregation_method)
            coils[coil_name] = {
                "inputsK": raw_values,
                "effectiveTempK": agg_temp_k,
            }

        result["coils"] = {
            name: {
                **coils[name],
                "calc": _compute_single_coil(suction_pressure_pa, discharge_pressure_pa, coils[name]["effectiveTempK"], refrigerant),
            }
            for name in ("left", "center", "right")
        }
        result["ok"] = True
        return result
    except Exception as e:  # Keep engine robust; the UI can display the error
        result["errors"].append(str(e))
        return result


def compute_8_point_cycle(
    suction_pressure_pa: float,
    liquid_pressure_pa: float,
    temperatures_k: Dict[str, Optional[float]],
    refrigerant: str = "R290"
) -> Dict:
    """
    Compute all 8 state points per plan.txt methodology.
    
    Args:
        suction_pressure_pa: Low-side pressure (Pa absolute)
        liquid_pressure_pa: High-side pressure (Pa absolute)
        temperatures_k: Dict with keys T_2a, T_2b, T_3a, T_3b, T_4a, T_4b (all optional)
        refrigerant: Refrigerant type (default R290)
    
    Returns:
        Dict with state points, superheat, subcooling, vapor quality, etc.
    """
    
    if CP is None:
        return {"error": "CoolProp not available"}
    
    result = {
        "refrigerant": refrigerant,
        "pressures": {
            "suction_pa": suction_pressure_pa,
            "liquid_pa": liquid_pressure_pa,
            "suction_kPa": suction_pressure_pa / 1000,
            "liquid_kPa": liquid_pressure_pa / 1000
        },
        "states": {},
        "performance": {},
        "errors": []
    }
    
    try:
        # --- HIGH-PRESSURE SIDE ---
        
        # State 3a: Compressor Outlet
        T_3a = temperatures_k.get('T_3a')
        if T_3a:
            h_3a = CP.PropsSI('H', 'P', liquid_pressure_pa, 'T', T_3a, refrigerant)
            rho_3a = CP.PropsSI('D', 'P', liquid_pressure_pa, 'T', T_3a, refrigerant)
            s_3a = CP.PropsSI('S', 'P', liquid_pressure_pa, 'T', T_3a, refrigerant)
            T_sat_3a = CP.PropsSI('T', 'P', liquid_pressure_pa, 'Q', 1, refrigerant)
            superheat_3a = (T_3a - T_sat_3a) * 9/5  # Convert to °F
            
            result["states"]["3a"] = {
                "label": "Compressor Outlet",
                "T_K": T_3a,
                "T_F": T_3a * 9/5 - 459.67,
                "P_Pa": liquid_pressure_pa,
                "P_kPa": liquid_pressure_pa / 1000,
                "h_kJkg": h_3a / 1000,
                "rho_kgm3": rho_3a,
                "s_kJkgK": s_3a / 1000,
                "T_sat_K": T_sat_3a,
                "T_sat_F": T_sat_3a * 9/5 - 459.67,
                "superheat_F": superheat_3a
            }
        
        # State 3b: Condenser Inlet
        T_3b = temperatures_k.get('T_3b')
        if T_3b:
            h_3b = CP.PropsSI('H', 'P', liquid_pressure_pa, 'T', T_3b, refrigerant)
            rho_3b = CP.PropsSI('D', 'P', liquid_pressure_pa, 'T', T_3b, refrigerant)
            s_3b = CP.PropsSI('S', 'P', liquid_pressure_pa, 'T', T_3b, refrigerant)
            T_sat_3b = CP.PropsSI('T', 'P', liquid_pressure_pa, 'Q', 1, refrigerant)
            superheat_3b = (T_3b - T_sat_3b) * 9/5
            
            result["states"]["3b"] = {
                "label": "Condenser Inlet",
                "T_K": T_3b,
                "T_F": T_3b * 9/5 - 459.67,
                "P_Pa": liquid_pressure_pa,
                "P_kPa": liquid_pressure_pa / 1000,
                "h_kJkg": h_3b / 1000,
                "rho_kgm3": rho_3b,
                "s_kJkgK": s_3b / 1000,
                "T_sat_K": T_sat_3b,
                "T_sat_F": T_sat_3b * 9/5 - 459.67,
                "superheat_F": superheat_3b
            }
        
        # State 4a: Condenser Outlet
        T_4a = temperatures_k.get('T_4a')
        if T_4a:
            h_4a = CP.PropsSI('H', 'P', liquid_pressure_pa, 'T', T_4a, refrigerant)
            rho_4a = CP.PropsSI('D', 'P', liquid_pressure_pa, 'T', T_4a, refrigerant)
            s_4a = CP.PropsSI('S', 'P', liquid_pressure_pa, 'T', T_4a, refrigerant)
            T_sat_4a = CP.PropsSI('T', 'P', liquid_pressure_pa, 'Q', 0, refrigerant)
            subcooling_4a = (T_sat_4a - T_4a) * 9/5  # Convert to °F
            
            result["states"]["4a"] = {
                "label": "Condenser Outlet",
                "T_K": T_4a,
                "T_F": T_4a * 9/5 - 459.67,
                "P_Pa": liquid_pressure_pa,
                "P_kPa": liquid_pressure_pa / 1000,
                "h_kJkg": h_4a / 1000,
                "rho_kgm3": rho_4a,
                "s_kJkgK": s_4a / 1000,
                "T_sat_K": T_sat_4a,
                "T_sat_F": T_sat_4a * 9/5 - 459.67,
                "subcooling_F": subcooling_4a
            }
        
        # State 4b: TXV Inlet
        T_4b = temperatures_k.get('T_4b')
        h_4b = None
        if T_4b:
            h_4b = CP.PropsSI('H', 'P', liquid_pressure_pa, 'T', T_4b, refrigerant)
            rho_4b = CP.PropsSI('D', 'P', liquid_pressure_pa, 'T', T_4b, refrigerant)
            s_4b = CP.PropsSI('S', 'P', liquid_pressure_pa, 'T', T_4b, refrigerant)
            T_sat_4b = CP.PropsSI('T', 'P', liquid_pressure_pa, 'Q', 0, refrigerant)
            subcooling_4b = (T_sat_4b - T_4b) * 9/5
            
            result["states"]["4b"] = {
                "label": "TXV Inlet",
                "T_K": T_4b,
                "T_F": T_4b * 9/5 - 459.67,
                "P_Pa": liquid_pressure_pa,
                "P_kPa": liquid_pressure_pa / 1000,
                "h_kJkg": h_4b / 1000,
                "rho_kgm3": rho_4b,
                "s_kJkgK": s_4b / 1000,
                "T_sat_K": T_sat_4b,
                "T_sat_F": T_sat_4b * 9/5 - 459.67,
                "subcooling_F": subcooling_4b
            }
        
        # --- LOW-PRESSURE SIDE ---
        
        # State 1: Evaporator Inlet (isenthalpic expansion from 4b)
        if h_4b:
            h_1 = h_4b  # Isenthalpic expansion
            T_1 = CP.PropsSI('T', 'P', suction_pressure_pa, 'H', h_1, refrigerant)
            rho_1 = CP.PropsSI('D', 'P', suction_pressure_pa, 'H', h_1, refrigerant)
            s_1 = CP.PropsSI('S', 'P', suction_pressure_pa, 'H', h_1, refrigerant)
            quality_1 = CP.PropsSI('Q', 'P', suction_pressure_pa, 'H', h_1, refrigerant)
            T_sat_1 = CP.PropsSI('T', 'P', suction_pressure_pa, 'Q', 1, refrigerant)
            
            result["states"]["1"] = {
                "label": "Evaporator Inlet (After TXV)",
                "T_K": T_1,
                "T_F": T_1 * 9/5 - 459.67,
                "P_Pa": suction_pressure_pa,
                "P_kPa": suction_pressure_pa / 1000,
                "h_kJkg": h_1 / 1000,
                "rho_kgm3": rho_1,
                "s_kJkgK": s_1 / 1000,
                "T_sat_K": T_sat_1,
                "T_sat_F": T_sat_1 * 9/5 - 459.67,
                "vapor_quality": quality_1,
                "quality_percent": quality_1 * 100
            }
        
        # State 2a: Evaporator Outlet
        T_2a = temperatures_k.get('T_2a')
        h_2a = None
        s_2a = None
        if T_2a:
            h_2a = CP.PropsSI('H', 'P', suction_pressure_pa, 'T', T_2a, refrigerant)
            rho_2a = CP.PropsSI('D', 'P', suction_pressure_pa, 'T', T_2a, refrigerant)
            s_2a = CP.PropsSI('S', 'P', suction_pressure_pa, 'T', T_2a, refrigerant)
            T_sat_2a = CP.PropsSI('T', 'P', suction_pressure_pa, 'Q', 1, refrigerant)
            superheat_2a = (T_2a - T_sat_2a) * 9/5
            
            result["states"]["2a"] = {
                "label": "Evaporator Outlet",
                "T_K": T_2a,
                "T_F": T_2a * 9/5 - 459.67,
                "P_Pa": suction_pressure_pa,
                "P_kPa": suction_pressure_pa / 1000,
                "h_kJkg": h_2a / 1000,
                "rho_kgm3": rho_2a,
                "s_kJkgK": s_2a / 1000,
                "T_sat_K": T_sat_2a,
                "T_sat_F": T_sat_2a * 9/5 - 459.67,
                "superheat_F": superheat_2a
            }
        
        # State 2b: Compressor Inlet
        T_2b = temperatures_k.get('T_2b')
        h_2b = None
        s_2b = None
        rho_2b = None
        if T_2b:
            h_2b = CP.PropsSI('H', 'P', suction_pressure_pa, 'T', T_2b, refrigerant)
            rho_2b = CP.PropsSI('D', 'P', suction_pressure_pa, 'T', T_2b, refrigerant)
            s_2b = CP.PropsSI('S', 'P', suction_pressure_pa, 'T', T_2b, refrigerant)
            T_sat_2b = CP.PropsSI('T', 'P', suction_pressure_pa, 'Q', 1, refrigerant)
            superheat_2b = (T_2b - T_sat_2b) * 9/5
            
            result["states"]["2b"] = {
                "label": "Compressor Inlet",
                "T_K": T_2b,
                "T_F": T_2b * 9/5 - 459.67,
                "P_Pa": suction_pressure_pa,
                "P_kPa": suction_pressure_pa / 1000,
                "h_kJkg": h_2b / 1000,
                "rho_kgm3": rho_2b,
                "s_kJkgK": s_2b / 1000,
                "T_sat_K": T_sat_2b,
                "T_sat_F": T_sat_2b * 9/5 - 459.67,
                "superheat_F": superheat_2b
            }
        
        # --- PERFORMANCE CALCULATIONS ---
        
        # Use 2b and 4b for cycle calculations (compressor inlet/outlet)
        if h_2b and h_4b:
            refrigeration_effect = (h_2b - h_4b) / 1000  # kJ/kg
            
            # Isentropic compression from 2b to 3a (if we have s_2b)
            if s_2b:
                h_3a_isentropic = CP.PropsSI('H', 'P', liquid_pressure_pa, 'S', s_2b, refrigerant)
                compressor_work = (h_3a_isentropic - h_2b) / 1000  # kJ/kg
            else:
                compressor_work = None
            
            # Heat rejection (3a to 4a) - if we have both
            if T_3a and T_4a:
                h_3a_actual = CP.PropsSI('H', 'P', liquid_pressure_pa, 'T', T_3a, refrigerant)
                h_4a_actual = CP.PropsSI('H', 'P', liquid_pressure_pa, 'T', T_4a, refrigerant)
                heat_rejected = (h_3a_actual - h_4a_actual) / 1000  # kJ/kg
            else:
                heat_rejected = None
            
            cop = refrigeration_effect / compressor_work if compressor_work and compressor_work > 0 else None
            
            result["performance"] = {
                "refrigeration_effect_kJkg": refrigeration_effect,
                "compressor_work_kJkg": compressor_work,
                "heat_rejected_kJkg": heat_rejected,
                "cop": cop
            }
        
        # Store density for mass flow calculations
        if rho_2b:
            result["density_compressor_inlet_kgm3"] = rho_2b
        
        return result
        
    except Exception as e:
        result["errors"].append(f"Calculation error: {str(e)}")
        return result


def calculate_mass_flow_rate(
    density_kgm3: float,
    displacement_cm3: float,
    speed_rpm: float,
    volumetric_efficiency: float = 0.85
) -> Dict:
    """
    Calculate mass flow rate using compressor displacement method.
    
    Args:
        density_kgm3: Refrigerant density at compressor inlet (kg/m³)
        displacement_cm3: Compressor displacement (cm³/rev)
        speed_rpm: Compressor speed (RPM)
        volumetric_efficiency: Volumetric efficiency (0-1)
    
    Returns:
        Dict with mass flow rates in various units
    """
    
    # Convert units
    displacement_m3 = displacement_cm3 / 1_000_000  # cm³ to m³
    speed_rps = speed_rpm / 60  # RPM to rev/sec
    speed_rph = speed_rpm * 60  # RPM to rev/hour
    
    # Calculate theoretical mass flow
    m_dot_theoretical_kgs = density_kgm3 * displacement_m3 * speed_rps
    m_dot_theoretical_kgh = density_kgm3 * displacement_m3 * speed_rph
    
    # Apply volumetric efficiency
    m_dot_actual_kgs = m_dot_theoretical_kgs * volumetric_efficiency
    m_dot_actual_kgh = m_dot_theoretical_kgh * volumetric_efficiency
    
    # Convert to lbs/hr for comparison with plan.txt
    m_dot_actual_lbhr = m_dot_actual_kgh * 2.20462
    
    return {
        "theoretical_kgs": m_dot_theoretical_kgs,
        "theoretical_kgh": m_dot_theoretical_kgh,
        "actual_kgs": m_dot_actual_kgs,
        "actual_kgh": m_dot_actual_kgh,
        "actual_lbhr": m_dot_actual_lbhr,
        "volumetric_efficiency": volumetric_efficiency,
        "inputs": {
            "density_kgm3": density_kgm3,
            "displacement_cm3": displacement_cm3,
            "displacement_m3": displacement_m3,
            "speed_rpm": speed_rpm,
            "speed_rps": speed_rps,
            "speed_rph": speed_rph
        }
    }


def calculate_system_performance(
    state_points: Dict,
    mass_flow_kgs: float
) -> Dict:
    """
    Calculate complete system performance metrics.

    Args:
        state_points: Dict from compute_8_point_cycle()
        mass_flow_kgs: Mass flow rate (kg/s)

    Returns:
        Dict with all performance metrics
    """

    states = state_points.get("states", {})
    perf = state_points.get("performance", {})

    # Get enthalpies (in J/kg, convert from kJ/kg)
    h_2b = states.get("2b", {}).get("h_kJkg", 0) * 1000
    h_3a = states.get("3a", {}).get("h_kJkg", 0) * 1000
    h_4a = states.get("4a", {}).get("h_kJkg", 0) * 1000
    h_4b = states.get("4b", {}).get("h_kJkg", 0) * 1000

    result = {}

    # Cooling Capacity (Watts)
    if h_2b and h_4b:
        cooling_capacity_w = mass_flow_kgs * (h_2b - h_4b)
        cooling_capacity_btu_hr = cooling_capacity_w * 3.41214
        cooling_capacity_tons = cooling_capacity_btu_hr / 12000

        result["cooling_capacity"] = {
            "watts": cooling_capacity_w,
            "btu_hr": cooling_capacity_btu_hr,
            "tons": cooling_capacity_tons
        }

    # Compressor Power (Watts) - use isentropic work from performance
    compressor_work_kJkg = perf.get("compressor_work_kJkg")
    if compressor_work_kJkg:
        compressor_power_w = mass_flow_kgs * compressor_work_kJkg * 1000
        compressor_power_hp = compressor_power_w / 745.7

        result["compressor_power"] = {
            "watts": compressor_power_w,
            "horsepower": compressor_power_hp
        }

    # Heat Rejection (Watts)
    if h_3a and h_4a:
        heat_rejection_w = mass_flow_kgs * (h_3a - h_4a)
        heat_rejection_btu_hr = heat_rejection_w * 3.41214

        result["heat_rejection"] = {
            "watts": heat_rejection_w,
            "btu_hr": heat_rejection_btu_hr
        }

    # COP and EER
    cop = perf.get("cop")
    if cop:
        result["efficiency"] = {"cop": cop}

        # Calculate EER if we have cooling capacity
        if "cooling_capacity" in result and "compressor_power" in result:
            eer = result["cooling_capacity"]["btu_hr"] / result["compressor_power"]["watts"]
            result["efficiency"]["eer"] = eer

    return result


# =========================================================================
# NEW UNIFIED CALCULATION ENGINE (from goal.md)
# Implements the two-step calculation process from Calculations-DDT.txt
# =========================================================================

def hz_to_rph(hz: float) -> float:
    """Convert Hz to revolutions per hour."""
    return hz * 3600.0


def ft3_to_m3(ft3: float) -> float:
    """Convert cubic feet to cubic meters."""
    if ft3 is None:
        return 0.0
    return ft3 * 0.0283168


def calculate_volumetric_efficiency(rated_inputs: Dict, refrigerant: str = 'R290') -> Dict:
    """
    Performs the "Step 1" calculation from Calculations-DDT.txt / goal.md
    to find the constant volumetric efficiency (eta_vol).

    This is a one-time calculation based on user manual inputs (rated values).

    Goal-2C: Implements graceful degradation - returns default eta_vol (0.85)
    with warnings if rated inputs are missing.

    Args:
        rated_inputs: Dict with keys:
            - m_dot_rated_lbhr: Rated mass flow rate (lbm/hr)
            - hz_rated: Rated compressor speed (Hz)
            - disp_ft3: Compressor displacement (ft³)
            - rated_evap_temp_f: Rated evaporator temperature (°F)
            - rated_return_gas_temp_f: Rated return gas temperature (°F)
        refrigerant: Refrigerant name (default 'R290')

    Returns:
        Dict with:
        - eta_vol: float (calculated or default 0.85)
        - method: 'calculated' | 'default'
        - warnings: list of warning messages (empty if calculated)
        - (other intermediate values if calculated successfully)
    """
    if CP is None:
        return {'error': 'CoolProp not available'}

    # 1. Get User Inputs
    m_dot_rated_lb_hr = rated_inputs.get('m_dot_rated_lbhr', 0)
    rated_evap_f = rated_inputs.get('rated_evap_temp_f', 0)
    rated_return_f = rated_inputs.get('rated_return_gas_temp_f', 0)
    rated_disp_ft3 = rated_inputs.get('disp_ft3', 0)
    rated_hz = rated_inputs.get('hz_rated', 0)

    # Check if all required inputs are present
    missing = []
    if not m_dot_rated_lb_hr or m_dot_rated_lb_hr == 0:
        missing.append('Rated Mass Flow Rate')
    if not rated_hz or rated_hz == 0:
        missing.append('Rated Compressor Speed')
    if not rated_disp_ft3 or rated_disp_ft3 == 0:
        missing.append('Compressor Displacement')
    if not rated_evap_f or rated_evap_f == 0:
        missing.append('Rated Evaporator Temperature')
    if not rated_return_f or rated_return_f == 0:
        missing.append('Rated Return Gas Temperature')

    # GRACEFUL DEGRADATION: Use default if inputs missing
    if missing:
        return {
            'eta_vol': 0.85,
            'method': 'default',
            'warnings': [
                f"Missing rated inputs: {', '.join(missing)}",
                "Using default volumetric efficiency (0.85)",
                "Mass flow and cooling capacity calculations will be approximate"
            ]
        }

    # Try to calculate
    try:
        # 2. Calculate Theoretical Mass Flow (m_dot_th)
        # Get saturation pressure at rated evaporator temperature
        rated_evap_k = f_to_k(rated_evap_f)
        P_rated_sat = CP.PropsSI('P', 'T', rated_evap_k, 'Q', 0, refrigerant)

        # Get density at rated return gas temperature and saturation pressure
        rated_return_k = f_to_k(rated_return_f)
        dens_rated_kg_m3 = CP.PropsSI('D', 'T', rated_return_k, 'P', P_rated_sat, refrigerant)
        dens_rated_lb_ft3 = dens_rated_kg_m3 * 0.062428  # Convert to lb/ft³

        # Calculate RPH (revolutions per hour)
        rph = hz_to_rph(rated_hz)

        # Theoretical mass flow
        m_dot_th_lb_hr = dens_rated_lb_ft3 * rph * rated_disp_ft3

        # 3. Calculate Volumetric Efficiency
        if m_dot_th_lb_hr == 0:
            # GRACEFUL DEGRADATION: Calculation failed, use default
            return {
                'eta_vol': 0.85,
                'method': 'default',
                'warnings': [
                    "Theoretical mass flow is zero - cannot calculate eta_vol",
                    "Using default volumetric efficiency (0.85)"
                ]
            }

        eta_vol = m_dot_rated_lb_hr / m_dot_th_lb_hr

        return {
            'eta_vol': eta_vol,
            'method': 'calculated',
            'warnings': [],
            'm_dot_rated_lb_hr': m_dot_rated_lb_hr,
            'm_dot_th_lb_hr': m_dot_th_lb_hr,
            'dens_rated_lb_ft3': dens_rated_lb_ft3,
            'dens_rated_kg_m3': dens_rated_kg_m3,
            'P_rated_sat_pa': P_rated_sat,
            'rph': rph,
        }
    except Exception as e:
        # GRACEFUL DEGRADATION: Exception occurred, use default
        return {
            'eta_vol': 0.85,
            'method': 'default',
            'warnings': [
                f"Error calculating eta_vol: {str(e)}",
                "Using default volumetric efficiency (0.85)"
            ]
        }


def calculate_row_performance(
    row: pd.Series,
    sensor_map: Dict[str, str],
    comp_specs: Dict,
    refrigerant: str = 'R290'
) -> pd.Series:
    """
    Performs the "Step 2" calculation from Calculations-DDT.txt
    on a single row of data.

    COMPLETE REWRITE to produce ALL 54 columns matching Calculations-DDT.xlsx EXACTLY.
    Also adds P-h diagram specific columns for plotting.

    Args:
        row: Single row from DataFrame (pandas Series)
        sensor_map: Dict mapping internal role keys to CSV column names
        comp_specs: Dict with 'gpm_water' key
        refrigerant: Refrigerant name (default 'R290')

    Returns:
        pandas Series with all 54 calculated values PLUS P-h diagram columns
    """
    if CP is None:
        return pd.Series({'error': 'CoolProp not available'})

    results = {}

    try:
        # Helper function to safely get values from the row
        def get_val(key):
            col_name_or_list = sensor_map.get(key)
            if col_name_or_list is None:
                return None
            
            # If it's a list (for averaging), compute average
            if isinstance(col_name_or_list, list):
                values = []
                for col_name in col_name_or_list:
                    val = row.get(col_name)
                    if val is not None:
                        values.append(val)
                if not values:
                    return None
                return sum(values) / len(values)
            
            # Otherwise it's a single column name
            return row.get(col_name_or_list)

        # ===== 1. GET ALL SENSOR VALUES (INCLUDING 8 MISSING ONES) =====
        # Pressures
        p_suc_psig = get_val('P_suc')
        p_disch_psig = get_val('P_disch')

        # LH circuit (8 sensors total: inlet + outlet for each coil)
        t_1a_lh_f = get_val('T_1a-lh')  # TXV outlet / Evap inlet LH
        t_1b_lh_f = get_val('_avg_T_1b-lh') if '_avg_T_1b-lh' in sensor_map else get_val('T_1b-lh')  # Coil inlet LH (averaged)
        t_2a_lh_f = get_val('_avg_T_2a-LH') if '_avg_T_2a-LH' in sensor_map else get_val('T_2a-LH')  # Evap outlet LH (averaged)
        t_4b_lh_f = get_val('T_4b-lh')  # TXV inlet LH

        # CTR circuit
        t_1a_ctr_f = get_val('T_1a-ctr')  # TXV outlet / Evap inlet CTR
        t_1b_ctr_f = get_val('_avg_T_1b-ctr') if '_avg_T_1b-ctr' in sensor_map else get_val('T_1b-ctr')  # Coil inlet CTR (averaged)
        t_2a_ctr_f = get_val('_avg_T_2a-ctr') if '_avg_T_2a-ctr' in sensor_map else get_val('T_2a-ctr')  # Evap outlet CTR (averaged)
        t_4b_ctr_f = get_val('T_4b-ctr')  # TXV inlet CTR

        # RH circuit
        t_1a_rh_f = get_val('T_1a-rh')  # TXV outlet / Evap inlet RH
        t_1c_rh_f = get_val('_avg_T_1c-rh') if '_avg_T_1c-rh' in sensor_map else get_val('T_1c-rh')  # Coil inlet RH (averaged)
        t_2a_rh_f = get_val('_avg_T_2a-RH') if '_avg_T_2a-RH' in sensor_map else get_val('T_2a-RH')  # Evap outlet RH (averaged)
        t_4b_rh_f = get_val('T_4b-rh')  # TXV inlet RH

        # Compressor and Condenser
        t_2b_f = get_val('T_2b')  # Compressor inlet
        t_3a_f = get_val('T_3a')  # Compressor outlet
        t_3b_f = get_val('T_3b')  # Condenser inlet
        t_4a_f = get_val('T_4a')  # Condenser outlet
        # Condenser water temps: support both legacy ('Cond.water.*') and Excel names ('T_water*')
        t_water_out_f = get_val('Cond.water.out')
        t_water_in_f = get_val('Cond.water.in')
        t_waterin_f = get_val('T_waterin')
        t_waterout_f = get_val('T_waterout')
        # Prefer Excel names; if missing, fall back to legacy keys
        if t_waterin_f is None:
            t_waterin_f = t_water_in_f
        if t_waterout_f is None:
            t_waterout_f = t_water_out_f

        # Validate critical pressure values
        if p_suc_psig is None or p_disch_psig is None:
            return pd.Series({'error': 'Missing pressure sensors - Please map suction and discharge pressure sensors in the Diagram tab'})

        # ===== 2. CONVERT UNITS (PSIG → Pa, °F → K) =====
        p_suc_pa = psig_to_pa(p_suc_psig)
        p_disch_pa = psig_to_pa(p_disch_psig)

        # Get saturation temperatures
        t_sat_suc_k = CP.PropsSI('T', 'P', p_suc_pa, 'Q', 0, refrigerant)
        t_sat_disch_k = CP.PropsSI('T', 'P', p_disch_pa, 'Q', 0, refrigerant)

        # Store intermediate enthalpy values for P-h diagram
        h_2a_lh, h_2a_ctr, h_2a_rh = None, None, None
        h_2b, h_3a, h_3b, h_4a = None, None, None, None
        h_4b_lh, h_4b_ctr, h_4b_rh = None, None, None
        rho_2b = None

        # ===== 3. AT LH COIL (Columns 1-8) =====
        # Sensor data first (columns 1-3)
        if t_1a_lh_f is not None:
            results['T_1a-lh'] = t_1a_lh_f
        if t_1b_lh_f is not None:
            results['T_1b-lh'] = t_1b_lh_f
        if t_2a_lh_f is not None:
            results['T_2a-LH'] = t_2a_lh_f
            # Calculate properties at evap outlet (columns 4-8)
            t_2a_lh_k = f_to_k(t_2a_lh_f)
            h_2a_lh = CP.PropsSI('H', 'T', t_2a_lh_k, 'P', p_suc_pa, refrigerant)
            s_2a_lh = CP.PropsSI('S', 'T', t_2a_lh_k, 'P', p_suc_pa, refrigerant)
            d_2a_lh = CP.PropsSI('D', 'T', t_2a_lh_k, 'P', p_suc_pa, refrigerant)
            sh_lh = t_2a_lh_k - t_sat_suc_k

            results['T_sat.lh'] = (t_sat_suc_k - 273.15) * 9/5 + 32
            results['S.H_lh coil'] = sh_lh * 9/5
            results['D_coil lh'] = d_2a_lh
            results['H_coil lh'] = h_2a_lh / 1000
            results['S_coil lh'] = s_2a_lh / 1000

        # ===== 4. AT CTR COIL (Columns 9-16) =====
        if t_1a_ctr_f is not None:
            results['T_1a-ctr'] = t_1a_ctr_f
        if t_1b_ctr_f is not None:
            results['T_1b-ctr'] = t_1b_ctr_f
        if t_2a_ctr_f is not None:
            results['T_2a-ctr'] = t_2a_ctr_f
            t_2a_ctr_k = f_to_k(t_2a_ctr_f)
            h_2a_ctr = CP.PropsSI('H', 'T', t_2a_ctr_k, 'P', p_suc_pa, refrigerant)
            s_2a_ctr = CP.PropsSI('S', 'T', t_2a_ctr_k, 'P', p_suc_pa, refrigerant)
            d_2a_ctr = CP.PropsSI('D', 'T', t_2a_ctr_k, 'P', p_suc_pa, refrigerant)
            sh_ctr = t_2a_ctr_k - t_sat_suc_k

            results['T_sat.ctr'] = (t_sat_suc_k - 273.15) * 9/5 + 32
            results['S.H_ctr coil'] = sh_ctr * 9/5
            results['D_coil ctr'] = d_2a_ctr
            results['H_coil ctr'] = h_2a_ctr / 1000
            results['S_coil ctr'] = s_2a_ctr / 1000

        # ===== 5. AT RH COIL (Columns 17-24) =====
        if t_1a_rh_f is not None:
            results['T_1a-rh'] = t_1a_rh_f
        if t_1c_rh_f is not None:
            results['T_1c-rh'] = t_1c_rh_f
        if t_2a_rh_f is not None:
            results['T_2a-RH'] = t_2a_rh_f
            t_2a_rh_k = f_to_k(t_2a_rh_f)
            h_2a_rh = CP.PropsSI('H', 'T', t_2a_rh_k, 'P', p_suc_pa, refrigerant)
            s_2a_rh = CP.PropsSI('S', 'T', t_2a_rh_k, 'P', p_suc_pa, refrigerant)
            d_2a_rh = CP.PropsSI('D', 'T', t_2a_rh_k, 'P', p_suc_pa, refrigerant)
            sh_rh = t_2a_rh_k - t_sat_suc_k

            results['T_sat.rh'] = (t_sat_suc_k - 273.15) * 9/5 + 32
            results['S.H_rh coil'] = sh_rh * 9/5
            results['D_coil rh'] = d_2a_rh
            results['H_coil rh'] = h_2a_rh / 1000
            results['S_coil rh'] = s_2a_rh / 1000

        # ===== 6. AT COMPRESSOR INLET (Columns 25-31) =====
        # Excel column names: P_suction, T_2b, T_sat.comp.in, S.H_total, D_comp.in, H_comp.in, S_comp.in
        results['P_suction'] = p_suc_psig
        if t_2b_f is not None:
            results['T_2b'] = t_2b_f
            t_2b_k = f_to_k(t_2b_f)
            h_2b = CP.PropsSI('H', 'T', t_2b_k, 'P', p_suc_pa, refrigerant)
            s_2b = CP.PropsSI('S', 'T', t_2b_k, 'P', p_suc_pa, refrigerant)
            rho_2b = CP.PropsSI('D', 'T', t_2b_k, 'P', p_suc_pa, refrigerant)
            sh_total = t_2b_k - t_sat_suc_k

            results['T_sat.comp.in'] = (t_sat_suc_k - 273.15) * 9/5 + 32
            results['S.H_total'] = sh_total * 9/5
            results['D_comp.in'] = rho_2b
            results['H_comp.in'] = h_2b / 1000
            results['S_comp.in'] = s_2b / 1000

        # ===== 7. COMP OUTLET (Columns 32-33) =====
        # Excel column names: T_3a, rpm
        if t_3a_f is not None:
            results['T_3a'] = t_3a_f
            # Calculate enthalpy for P-h diagram (MISSING IN OLD CODE)
            t_3a_k = f_to_k(t_3a_f)
            h_3a = CP.PropsSI('H', 'T', t_3a_k, 'P', p_disch_pa, refrigerant)
        # RPM column removed - no longer needed with water-side calculations

        # ===== 8. AT CONDENSER (Columns 34-40) =====
        # Excel column names: T_3b, P_disch, T_4a, T_sat.cond, S.C, T_waterin, T_waterout
        if t_3b_f is not None:
            results['T_3b'] = t_3b_f
            # Calculate enthalpy for P-h diagram (MISSING IN OLD CODE)
            t_3b_k = f_to_k(t_3b_f)
            h_3b = CP.PropsSI('H', 'T', t_3b_k, 'P', p_disch_pa, refrigerant)

        results['P_disch'] = p_disch_psig

        if t_4a_f is not None:
            results['T_4a'] = t_4a_f
            t_4a_k = f_to_k(t_4a_f)
            # Calculate enthalpy for P-h diagram (MISSING IN OLD CODE)
            h_4a = CP.PropsSI('H', 'T', t_4a_k, 'P', p_disch_pa, refrigerant)
            subcool_cond = t_sat_disch_k - t_4a_k
            results['T_sat.cond'] = (t_sat_disch_k - 273.15) * 9/5 + 32
            results['S.C'] = subcool_cond * 9/5

        # Water temps
        if t_waterin_f is not None:
            results['T_waterin'] = t_waterin_f
        if t_waterout_f is not None:
            results['T_waterout'] = t_waterout_f

        # ===== 9. AT TXV LH (Columns 41-44) =====
        # Excel column names: T_4b-lh, T_sat.txv.lh, S.C-txv.lh, H_txv.lh
        if t_4b_lh_f is not None:
            results['T_4b-lh'] = t_4b_lh_f
            t_4b_lh_k = f_to_k(t_4b_lh_f)
            h_4b_lh = CP.PropsSI('H', 'T', t_4b_lh_k, 'P', p_disch_pa, refrigerant)
            subcool_lh = t_sat_disch_k - t_4b_lh_k

            results['T_sat.txv.lh'] = (t_sat_disch_k - 273.15) * 9/5 + 32
            results['S.C-txv.lh'] = subcool_lh * 9/5
            results['H_txv.lh'] = h_4b_lh / 1000

        # ===== 10. AT TXV CTR (Columns 45-48) =====
        if t_4b_ctr_f is not None:
            results['T_4b-ctr'] = t_4b_ctr_f
            t_4b_ctr_k = f_to_k(t_4b_ctr_f)
            h_4b_ctr = CP.PropsSI('H', 'T', t_4b_ctr_k, 'P', p_disch_pa, refrigerant)
            subcool_ctr = t_sat_disch_k - t_4b_ctr_k

            results['T_sat.txv.ctr'] = (t_sat_disch_k - 273.15) * 9/5 + 32
            results['S.C-txv.ctr'] = subcool_ctr * 9/5
            results['H_txv.ctr'] = h_4b_ctr / 1000

        # ===== 11. AT TXV RH (Columns 49-52) =====
        # Note: Excel has typo "T_4b-lh" for column 49, should be T_4b-rh
        if t_4b_rh_f is not None:
            results['T_4b-rh'] = t_4b_rh_f  # Using correct name not typo
            t_4b_rh_k = f_to_k(t_4b_rh_f)
            h_4b_rh = CP.PropsSI('H', 'T', t_4b_rh_k, 'P', p_disch_pa, refrigerant)
            subcool_rh = t_sat_disch_k - t_4b_rh_k

            results['T_sat.txv.rh'] = (t_sat_disch_k - 273.15) * 9/5 + 32
            results['S.C-txv.rh'] = subcool_rh * 9/5
            results['H_txv.rh'] = h_4b_rh / 1000

        # ===== 12. TOTAL (Columns 53-54) =====
        # Excel column names: m_dot, qc
        # Water-side mass flow calculation
        gpm_water = comp_specs.get('gpm_water')
        
        if gpm_water and t_waterin_f is not None and t_waterout_f is not None:
            # Calculate water temperature delta
            delta_t_water_f = t_waterout_f - t_waterin_f
            
            # Get condenser enthalpy change (refrigerant side)
            if h_3a and h_4a:
                # Convert J/kg to BTU/lb: J/kg * 0.0004299 = BTU/lb
                h_3a_btulb = h_3a * 0.0004299
                h_4a_btulb = h_4a * 0.0004299
                delta_h_condenser_btulb = h_3a_btulb - h_4a_btulb
                
                if delta_h_condenser_btulb > 0:
                    # Water-side heat rejection (BTU/hr)
                    # Q_water = 500.4 * GPM * delta_T
                    q_water_btuhr = 500.4 * gpm_water * delta_t_water_f
                    
                    # Mass flow rate (lb/hr) from energy balance
                    mass_flow_lbhr = q_water_btuhr / delta_h_condenser_btulb
                    
                    results['m_dot'] = mass_flow_lbhr
                    
                    # Calculate cooling capacity
                    if h_2b:
                        h_4b_values = []
                        if h_4b_lh is not None:
                            h_4b_values.append(h_4b_lh)
                        if h_4b_ctr is not None:
                            h_4b_values.append(h_4b_ctr)
                        if h_4b_rh is not None:
                            h_4b_values.append(h_4b_rh)
                        
                        if h_4b_values:
                            h_4b_avg = sum(h_4b_values) / len(h_4b_values)
                            
                            # Convert to BTU/lb
                            h_2b_btulb = h_2b * 0.0004299
                            h_4b_avg_btulb = h_4b_avg * 0.0004299
                            delta_h_evap_btulb = h_2b_btulb - h_4b_avg_btulb
                            
                            # Cooling capacity (BTU/hr)
                            cooling_cap_btuhr = mass_flow_lbhr * delta_h_evap_btulb
                            
                            results['qc'] = cooling_cap_btuhr

        # ===== 13. P-H DIAGRAM SPECIFIC COLUMNS =====
        # These columns allow ph_diagram_generator.py to find the data it needs
        # without renaming existing columns
        if h_2b is not None:
            results['h_2b'] = h_2b / 1000  # kJ/kg
        if h_3a is not None:
            results['h_3a'] = h_3a / 1000
        if h_3b is not None:
            results['h_3b'] = h_3b / 1000
        if h_4a is not None:
            results['h_4a'] = h_4a / 1000
        if h_2a_lh is not None:
            results['h_2a_LH'] = h_2a_lh / 1000
        if h_2a_ctr is not None:
            results['h_2a_CTR'] = h_2a_ctr / 1000
        if h_2a_rh is not None:
            results['h_2a_RH'] = h_2a_rh / 1000
        if h_4b_lh is not None:
            results['h_4b_LH'] = h_4b_lh / 1000
        if h_4b_ctr is not None:
            results['h_4b_CTR'] = h_4b_ctr / 1000
        if h_4b_rh is not None:
            results['h_4b_RH'] = h_4b_rh / 1000

        # P-h diagram also needs pressures in Pa
        results['P_suc'] = p_suc_pa
        results['P_cond'] = p_disch_pa

        return pd.Series(results)

    except Exception as e:
        print(f"Error processing row: {e}")
        import traceback
        traceback.print_exc()
        return pd.Series({'error': str(e)})


def calculate_performance_from_compressor(
    dataframe: pd.DataFrame,
    mappings: Dict[str, str],
    compressor_specs: Dict[str, float],
    refrigerant: str
) -> Dict:
    """
    Calculates system performance on a time-step basis using compressor displacement.
    
    This is a vectorized implementation that operates on entire columns for efficiency.

    Args:
        dataframe: The raw sensor data as a pandas DataFrame.
        mappings: A dictionary mapping roles (e.g., 'Suction Pressure') to column names.
        compressor_specs: A dict with 'displacement_cm3', 'speed_rpm', 'vol_eff'.
        refrigerant: The refrigerant name string (e.g., 'R410A').

    Returns:
        A dictionary containing the results, including the enriched DataFrame
        and any errors encountered.
    """
    if CP is None:
        return {"ok": False, "error": "CoolProp library not found.", "dataframe": None}
    
    # --- 1. Identify required sensor columns from mappings ---
    # Create a reverse mapping for easier lookup.
    role_to_column = {v: k for k, v in mappings.items()}
    required_roles = [
        "Suction Pressure", "Suction Temperature",
        "Liquid Line Pressure", "Liquid Line Temperature"
    ]
    
    # Check if all necessary sensors have been mapped by the user.
    missing_roles = [role for role in required_roles if role not in role_to_column]
    if missing_roles:
        return {"ok": False, "error": f"Missing sensor mappings for: {', '.join(missing_roles)}", "dataframe": None}

    # Make a copy to avoid modifying the original DataFrame in the DataManager.
    df = dataframe.copy()
    
    try:
        # --- 2. Vectorized Unit Conversion ---
        # Educational Note: Instead of a 'for' loop, we apply the conversion
        # to the entire column at once. This is significantly faster.
        df['Suction P (Pa)'] = psig_to_pa(df[role_to_column["Suction Pressure"]])
        df['Suction T (K)'] = f_to_k(df[role_to_column["Suction Temperature"]])
        df['Liquid P (Pa)'] = psig_to_pa(df[role_to_column["Liquid Line Pressure"]])
        df['Liquid T (K)'] = f_to_k(df[role_to_column["Liquid Line Temperature"]])

        # --- 3. Get Thermodynamic Properties using CoolProp ---
        # Educational Note: CoolProp calculations must be done row-by-row.
        # We use pandas '.apply()' method, which is the most efficient way to
        # perform such row-wise operations.

        def get_suction_props(row):
            try:
                # State is defined by Pressure (P) and Temperature (T)
                h = CP.PropsSI('H', 'P', row['Suction P (Pa)'], 'T', row['Suction T (K)'], refrigerant)
                d = CP.PropsSI('D', 'P', row['Suction P (Pa)'], 'T', row['Suction T (K)'], refrigerant)
                return h, d # Enthalpy (J/kg), Density (kg/m^3)
            except ValueError:
                return None, None

        def get_liquid_props(row):
            try:
                # State is defined by Pressure (P) and Temperature (T)
                h = CP.PropsSI('H', 'P', row['Liquid P (Pa)'], 'T', row['Liquid T (K)'], refrigerant)
                return h # Enthalpy (J/kg)
            except ValueError:
                return None

        df[['Suction Enthalpy (J/kg)', 'Density (kg/m^3)']] = df.apply(get_suction_props, axis=1, result_type='expand')
        df['Evap Inlet Enthalpy (J/kg)'] = df.apply(get_liquid_props, axis=1)

        # Drop rows where CoolProp failed to prevent calculation errors
        df.dropna(subset=['Suction Enthalpy (J/kg)', 'Density (kg/m^3)', 'Evap Inlet Enthalpy (J/kg)'], inplace=True)
        if df.empty:
             return {"ok": False, "error": "Could not calculate thermodynamic properties. Check sensor data quality.", "dataframe": None}

        # --- 4. Calculate Mass Flow Rate (m_dot) ---
        # Educational Note: This is another vectorized calculation. We get the compressor
        # specs and convert their units once, then apply the formula to the entire 'Density' column.
        disp_m3 = cm3_to_m3(compressor_specs['displacement_cm3'])
        speed_rps = rpm_to_rps(compressor_specs['speed_rpm'])
        vol_eff = compressor_specs['vol_eff']

        # Formula: m_dot = Displacement * Speed * Density * Volumetric_Efficiency
        df['Mass Flow (kg/s)'] = disp_m3 * speed_rps * df['Density (kg/m^3)'] * vol_eff

        # --- 5. Calculate Cooling Capacity (Q_c) ---
        # Educational Note: The cooling capacity is the change in energy (enthalpy)
        # across the evaporator, multiplied by how much refrigerant is flowing (mass flow rate).
        # Formula: Q_c = m_dot * (h_suction - h_liquid_line)
        df['Cooling Capacity (W)'] = df['Mass Flow (kg/s)'] * (df['Suction Enthalpy (J/kg)'] - df['Evap Inlet Enthalpy (J/kg)'])

        return {"ok": True, "error": None, "dataframe": df}

    except KeyError as e:
        return {"ok": False, "error": f"A mapped column is missing from the data: {e}", "dataframe": None}
    except Exception as e:
        return {"ok": False, "error": f"An unexpected error occurred: {e}", "dataframe": None}


