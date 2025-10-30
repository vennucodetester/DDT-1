"""
calculation_orchestrator.py

Orchestrates the complete 8-point cycle calculation using port_resolver and calculation_engine.
This module bridges the diagram model with the calculation engine.
"""

from typing import Dict, Optional, List
import pandas as pd
from port_resolver import resolve_mapped_sensor, get_sensor_value
from calculation_engine import (
    compute_8_point_cycle,
    calculate_mass_flow_rate,
    calculate_system_performance,
    calculate_volumetric_efficiency,
    calculate_row_performance,
    f_to_k,
    psig_to_pa,
    ft3_to_m3
)


def gather_temperatures_from_ports(data_manager) -> Dict[str, Optional[float]]:
    """
    Gather all required temperature measurements from mapped ports.
    
    Returns dict with keys: T_2a, T_2b, T_3a, T_3b, T_4a, T_4b (in Kelvin)
    Each value can be None if sensor not mapped or no data available.
    """
    model = data_manager.diagram_model
    components = model.get('components', {})
    
    temps = {}
    
    # Find Compressor for T_2b (inlet) and T_3a (outlet)
    for comp_id, comp in components.items():
        if comp.get('type') == 'Compressor':
            # T_2b: Compressor Inlet
            sensor = resolve_mapped_sensor(model, 'Compressor', comp_id, 'inlet')
            val = get_sensor_value(data_manager, sensor)
            if val is not None:
                temps['T_2b'] = f_to_k(val)  # Convert °F to K
            
            # T_3a: Compressor Outlet
            sensor = resolve_mapped_sensor(model, 'Compressor', comp_id, 'outlet')
            val = get_sensor_value(data_manager, sensor)
            if val is not None:
                temps['T_3a'] = f_to_k(val)
            
            break  # Assume single compressor
    
    # Find Condenser for T_3b (inlet) and T_4a (outlet)
    for comp_id, comp in components.items():
        if comp.get('type') == 'Condenser':
            # T_3b: Condenser Inlet (optional)
            sensor = resolve_mapped_sensor(model, 'Condenser', comp_id, 'inlet')
            val = get_sensor_value(data_manager, sensor)
            if val is not None:
                temps['T_3b'] = f_to_k(val)
            
            # T_4a: Condenser Outlet
            sensor = resolve_mapped_sensor(model, 'Condenser', comp_id, 'outlet')
            val = get_sensor_value(data_manager, sensor)
            if val is not None:
                temps['T_4a'] = f_to_k(val)
            
            break  # Assume single condenser
    
    # Find TXVs for T_4b (inlet) - average all TXVs
    txv_temps = []
    for comp_id, comp in components.items():
        if comp.get('type') == 'TXV':
            sensor = resolve_mapped_sensor(model, 'TXV', comp_id, 'inlet')
            val = get_sensor_value(data_manager, sensor)
            if val is not None:
                txv_temps.append(f_to_k(val))
    
    if txv_temps:
        temps['T_4b'] = sum(txv_temps) / len(txv_temps)  # Average
    
    # Find Evaporators for T_2a (outlet) - average all outlets
    evap_temps = []
    for comp_id, comp in components.items():
        if comp.get('type') == 'Evaporator':
            props = comp.get('properties', {})
            circuits = props.get('circuits', 1)
            
            # Average all outlet circuits for this evaporator
            for i in range(1, circuits + 1):
                sensor = resolve_mapped_sensor(model, 'Evaporator', comp_id, f'outlet_circuit_{i}')
                val = get_sensor_value(data_manager, sensor)
                if val is not None:
                    evap_temps.append(f_to_k(val))
    
    if evap_temps:
        temps['T_2a'] = sum(evap_temps) / len(evap_temps)  # Average
    
    return temps


def gather_pressures_from_ports(data_manager) -> Dict[str, Optional[float]]:
    """
    Gather pressure measurements from compressor ports.
    
    Returns dict with keys: suction_pa, liquid_pa (in Pascals absolute)
    """
    model = data_manager.diagram_model
    components = model.get('components', {})
    
    pressures = {}
    
    # Find Compressor for SP and DP
    for comp_id, comp in components.items():
        if comp.get('type') == 'Compressor':
            # Suction Pressure (SP)
            sensor = resolve_mapped_sensor(model, 'Compressor', comp_id, 'SP')
            val = get_sensor_value(data_manager, sensor)
            if val is not None:
                pressures['suction_pa'] = psig_to_pa(val)  # Convert PSIG to Pa
            
            # Discharge/Liquid Pressure (DP)
            sensor = resolve_mapped_sensor(model, 'Compressor', comp_id, 'DP')
            val = get_sensor_value(data_manager, sensor)
            if val is not None:
                pressures['liquid_pa'] = psig_to_pa(val)
            
            break  # Assume single compressor
    
    return pressures


def gather_compressor_specs(data_manager) -> Dict[str, Optional[float]]:
    """
    Gather compressor specifications from diagram and ports.
    
    Returns dict with keys: displacement_cm3, speed_rpm, vol_eff
    """
    model = data_manager.diagram_model
    components = model.get('components', {})
    
    specs = {}
    
    # Find Compressor
    for comp_id, comp in components.items():
        if comp.get('type') == 'Compressor':
            props = comp.get('properties', {})
            
            # Get displacement and vol_eff from properties
            specs['displacement_cm3'] = props.get('displacement_cm3')
            specs['vol_eff'] = props.get('vol_eff', 0.85)
            
            # Get RPM from mapped sensor
            sensor = resolve_mapped_sensor(model, 'Compressor', comp_id, 'RPM')
            val = get_sensor_value(data_manager, sensor)
            if val is not None:
                specs['speed_rpm'] = val
            else:
                # Fallback to property if sensor not mapped
                specs['speed_rpm'] = props.get('speed_rpm')
            
            break  # Assume single compressor
    
    return specs


def calculate_full_system(data_manager) -> Dict:
    """
    Perform complete 8-point cycle calculation with mass flow and performance metrics.
    
    This is the main entry point for calculations.
    
    Returns:
        Dict with all calculation results including:
        - state_points: 8-point cycle results
        - mass_flow: mass flow rate results
        - performance: system performance metrics
        - on_time: ON-time filtering stats
        - errors: list of any errors encountered
    """
    
    result = {
        "ok": False,
        "errors": [],
        "state_points": None,
        "mass_flow": None,
        "performance": None,
        "on_time": {
            "percentage": 0.0,
            "on_rows": 0,
            "total_rows": 0
        }
    }
    
    # Get refrigerant
    refrigerant = data_manager.refrigerant
    
    # Gather ON-time stats
    result["on_time"] = {
        "percentage": data_manager.on_time_percentage,
        "on_rows": data_manager.on_time_row_count,
        "total_rows": data_manager.total_row_count,
        "threshold_psig": data_manager.on_time_threshold_psig,
        "filtering_enabled": data_manager.on_time_filtering_enabled
    }
    
    # Gather pressures
    pressures = gather_pressures_from_ports(data_manager)
    suction_pa = pressures.get('suction_pa')
    liquid_pa = pressures.get('liquid_pa')
    
    if not suction_pa:
        result["errors"].append("Missing suction pressure - map Compressor.SP port")
    if not liquid_pa:
        result["errors"].append("Missing liquid pressure - map Compressor.DP port")
    
    if result["errors"]:
        return result
    
    # Gather temperatures
    temps_k = gather_temperatures_from_ports(data_manager)
    
    # Check for critical temperatures
    if not temps_k.get('T_2b'):
        result["errors"].append("Missing compressor inlet temp (T_2b) - map Compressor.inlet port")
    if not temps_k.get('T_3a'):
        result["errors"].append("Missing compressor outlet temp (T_3a) - map Compressor.outlet port")
    if not temps_k.get('T_4b'):
        result["errors"].append("Missing TXV inlet temp (T_4b) - map TXV.inlet port(s)")
    if not temps_k.get('T_2a'):
        result["errors"].append("Missing evaporator outlet temp (T_2a) - map Evaporator.outlet_circuit_N port(s)")
    
    # Compute 8-point cycle
    state_points = compute_8_point_cycle(
        suction_pressure_pa=suction_pa,
        liquid_pressure_pa=liquid_pa,
        temperatures_k=temps_k,
        refrigerant=refrigerant
    )
    
    result["state_points"] = state_points
    
    # Check for errors in state point calculation
    if state_points.get("errors"):
        result["errors"].extend(state_points["errors"])
    
    # Gather compressor specs
    comp_specs = gather_compressor_specs(data_manager)
    displacement = comp_specs.get('displacement_cm3')
    speed_rpm = comp_specs.get('speed_rpm')
    vol_eff = comp_specs.get('vol_eff', 0.85)
    
    if not displacement:
        result["errors"].append("Missing compressor displacement - set in Compressor properties")
    if not speed_rpm:
        result["errors"].append("Missing compressor speed - map Compressor.RPM port or set in properties")
    
    # Calculate mass flow rate
    density = state_points.get('density_compressor_inlet_kgm3')
    if density and displacement and speed_rpm:
        mass_flow = calculate_mass_flow_rate(
            density_kgm3=density,
            displacement_cm3=displacement,
            speed_rpm=speed_rpm,
            volumetric_efficiency=vol_eff
        )
        result["mass_flow"] = mass_flow
        
        # Calculate system performance
        mass_flow_kgs = mass_flow['actual_kgs']
        performance = calculate_system_performance(
            state_points=state_points,
            mass_flow_kgs=mass_flow_kgs
        )
        result["performance"] = performance
    else:
        if not density:
            result["errors"].append("Cannot calculate mass flow - missing density (need T_2b)")
    
    # Mark as successful if we got state points
    if state_points and not state_points.get("error"):
        result["ok"] = True
    
    return result


def calculate_per_circuit(data_manager, circuit_label: str) -> Dict:
    """
    Calculate 8-point cycle for a specific circuit (Left, Center, or Right).
    
    Args:
        data_manager: DataManager instance
        circuit_label: "Left", "Center", or "Right"
    
    Returns:
        Dict with calculation results for that circuit
    """
    
    model = data_manager.diagram_model
    components = model.get('components', {})
    refrigerant = data_manager.refrigerant
    
    result = {
        "ok": False,
        "circuit": circuit_label,
        "errors": [],
        "state_points": None
    }
    
    # Gather pressures (same for all circuits)
    pressures = gather_pressures_from_ports(data_manager)
    suction_pa = pressures.get('suction_pa')
    liquid_pa = pressures.get('liquid_pa')
    
    if not suction_pa or not liquid_pa:
        result["errors"].append("Missing pressures")
        return result
    
    # Gather temperatures for this specific circuit
    temps_k = {}
    
    # Compressor temps (same for all circuits)
    for comp_id, comp in components.items():
        if comp.get('type') == 'Compressor':
            sensor = resolve_mapped_sensor(model, 'Compressor', comp_id, 'inlet')
            val = get_sensor_value(data_manager, sensor)
            if val is not None:
                temps_k['T_2b'] = f_to_k(val)
            
            sensor = resolve_mapped_sensor(model, 'Compressor', comp_id, 'outlet')
            val = get_sensor_value(data_manager, sensor)
            if val is not None:
                temps_k['T_3a'] = f_to_k(val)
            break
    
    # Condenser temps (same for all circuits)
    for comp_id, comp in components.items():
        if comp.get('type') == 'Condenser':
            sensor = resolve_mapped_sensor(model, 'Condenser', comp_id, 'outlet')
            val = get_sensor_value(data_manager, sensor)
            if val is not None:
                temps_k['T_4a'] = f_to_k(val)
            break
    
    # TXV inlet for this circuit
    for comp_id, comp in components.items():
        if comp.get('type') == 'TXV':
            props = comp.get('properties', {})
            if props.get('circuit_label') == circuit_label:
                sensor = resolve_mapped_sensor(model, 'TXV', comp_id, 'inlet')
                val = get_sensor_value(data_manager, sensor)
                if val is not None:
                    temps_k['T_4b'] = f_to_k(val)
                break
    
    # Evaporator outlet for this circuit (average all outlets)
    evap_temps = []
    for comp_id, comp in components.items():
        if comp.get('type') == 'Evaporator':
            props = comp.get('properties', {})
            if props.get('circuit_label') == circuit_label:
                circuits = props.get('circuits', 1)
                for i in range(1, circuits + 1):
                    sensor = resolve_mapped_sensor(model, 'Evaporator', comp_id, f'outlet_circuit_{i}')
                    val = get_sensor_value(data_manager, sensor)
                    if val is not None:
                        evap_temps.append(f_to_k(val))
    
    if evap_temps:
        temps_k['T_2a'] = sum(evap_temps) / len(evap_temps)
    
    # Compute 8-point cycle for this circuit
    state_points = compute_8_point_cycle(
        suction_pressure_pa=suction_pa,
        liquid_pressure_pa=liquid_pa,
        temperatures_k=temps_k,
        refrigerant=refrigerant
    )
    
    result["state_points"] = state_points

    if state_points.get("errors"):
        result["errors"].extend(state_points["errors"])
    else:
        result["ok"] = True

    return result


# =========================================================================
# NEW UNIFIED BATCH PROCESSING ENGINE (from goal.md Step 3)
# This replaces coolprop_calculator.py entirely
# =========================================================================

# Master list of all sensor roles needed for the new calculation
# Maps internal role keys to (ComponentType, PortName, {optional property filters})
# UPDATED: Added 8 missing sensor roles (T_1a/T_1b for circuits + water temps)
REQUIRED_SENSOR_ROLES = {
    # Pressures
    'P_suc': [('Compressor', 'SP')],
    'P_disch': [('Compressor', 'DP')],
    'RPM': [('Compressor', 'RPM')],

    # Compressor and Condenser temps
    'T_2b': [('Compressor', 'inlet')],
    'T_3a': [('Compressor', 'outlet')],
    'T_3b': [('Condenser', 'inlet')],
    'T_4a': [('Condenser', 'outlet')],

    # Condenser water temps (ADDED - were missing)
    'T_waterin': [('Condenser', 'water_inlet')],
    'T_waterout': [('Condenser', 'water_outlet')],

    # LH circuit
    # CRITICAL: T_1a and T_1b represent DIFFERENT physical points
    # T_1a = TXV outlet / Distributor outlet
    # T_1b = Coil inlet (after distributor circuits split)
    # If only one inlet sensor exists, prefer T_1a (primary measurement point)
    'T_1a-lh': [
        ('Distributor', 'outlet_1', {'circuit_label': 'Left'}),  # Prefer distributor outlet if available
        ('Evaporator', 'inlet_circuit_1', {'circuit_label': 'Left'})  # Fallback to evaporator inlet
    ],
    'T_1b-lh': [
        ('Evaporator', 'inlet_circuit_2', {'circuit_label': 'Left'}),  # Try different circuit inlet
        # DO NOT map to inlet_circuit_1 - would cause duplicate with T_1a-lh
    ],
    'T_2a-LH': [('Evaporator', 'outlet_circuit_1', {'circuit_label': 'Left'})],
    'T_4b-lh': [('TXV', 'inlet', {'circuit_label': 'Left'})],

    # CTR circuit
    'T_1a-ctr': [
        ('Distributor', 'outlet_1', {'circuit_label': 'Center'}),
        ('Evaporator', 'inlet_circuit_1', {'circuit_label': 'Center'})
    ],
    'T_1b-ctr': [
        ('Evaporator', 'inlet_circuit_2', {'circuit_label': 'Center'}),
    ],
    'T_2a-ctr': [('Evaporator', 'outlet_circuit_1', {'circuit_label': 'Center'})],
    'T_4b-ctr': [('TXV', 'inlet', {'circuit_label': 'Center'})],

    # RH circuit
    'T_1a-rh': [
        ('Distributor', 'outlet_1', {'circuit_label': 'Right'}),
        ('Evaporator', 'inlet_circuit_1', {'circuit_label': 'Right'})
    ],
    'T_1c-rh': [
        ('Evaporator', 'inlet_circuit_2', {'circuit_label': 'Right'}),
    ],
    'T_2a-RH': [('Evaporator', 'outlet_circuit_1', {'circuit_label': 'Right'})],
    'T_4b-rh': [('TXV', 'inlet', {'circuit_label': 'Right'})],

    # Condenser water temperatures (optional display fields)
    'Cond.water.out': [('Condenser', 'water_out_temp')],
    'Cond.water.in': [('Condenser', 'water_in_temp')],
}


def _find_sensor_for_role(model: Dict, role_def: tuple) -> Optional[str]:
    """
    Helper to find the first mapped sensor for a given role definition.

    Args:
        model: Diagram model dict
        role_def: Tuple of (ComponentType, PortName) or (ComponentType, PortName, {props})

    Returns:
        Sensor name (CSV column name) or None
    """
    components = model.get('components', {})

    role_comp_type = role_def[0]
    role_port = role_def[1]
    role_props = role_def[2] if len(role_def) > 2 else {}

    # CRITICAL: Track all matching components to detect ambiguous mappings
    matching_components = []

    for comp_id, comp in components.items():
        comp_type = comp.get('type')
        props = comp.get('properties', {})

        # Check component type
        if comp_type != role_comp_type:
            continue

        # Check if properties match (e.g., circuit_label)
        props_match = True
        if role_props:
            for key, val in role_props.items():
                if props.get(key) != val:
                    props_match = False
                    break

        if props_match:
            matching_components.append((comp_id, comp))

    # CRITICAL FIX: Warn if multiple components match the same role
    # This could cause ambiguous mappings and duplicate values
    if len(matching_components) > 1:
        comp_ids = [comp_id for comp_id, _ in matching_components]
        print(f"[MAPPING] WARNING: Multiple components match role {role_def[0]}.{role_def[1]} with props {role_props}: {comp_ids}")
        print(f"[MAPPING] Using first match: {comp_ids[0]}")

    # Find the first component with a mapped sensor
    for comp_id, comp in matching_components:
        sensor = resolve_mapped_sensor(model, role_comp_type, comp_id, role_port)
        if sensor:
            return sensor

    return None


def run_batch_processing(
    data_manager,
    input_dataframe: pd.DataFrame
) -> pd.DataFrame:
    """
    The NEW main entry point for the "Calculations" tab.

    This function implements the complete two-step calculation process from goal.md:
    - Step 1: Calculate volumetric efficiency from rated inputs (one-time)
    - Step 2: Apply row-by-row performance calculations (for each timestamp)

    This replaces coolprop_calculator.py entirely with a flexible, port-mapping-based system.

    Args:
        data_manager: DataManager instance with diagram_model and rated_inputs
        input_dataframe: Raw CSV data (or filtered data)

    Returns:
        DataFrame with all calculated columns matching Calculations-DDT.xlsx structure
    """
    print(f"[BATCH PROCESSING] Starting batch processing on {len(input_dataframe)} rows...")

    # === STEP 1: GET RATED INPUTS AND CALCULATE ETA_VOL ===
    rated_inputs = data_manager.rated_inputs
    refrigerant = data_manager.refrigerant or 'R290'

    eta_vol_results = calculate_volumetric_efficiency(rated_inputs, refrigerant)

    # Goal-2C: Handle CoolProp errors (fatal)
    if 'error' in eta_vol_results:
        print(f"[BATCH PROCESSING] ERROR in Step 1 (eta_vol): {eta_vol_results['error']}")
        print("[BATCH PROCESSING] Please ensure CoolProp is installed.")
        return pd.DataFrame({'error': [eta_vol_results['error']]})

    # Goal-2C: Handle graceful degradation warnings (non-fatal)
    eta_vol = eta_vol_results.get('eta_vol', 0.85)
    method = eta_vol_results.get('method', 'calculated')
    warnings = eta_vol_results.get('warnings', [])

    if method == 'default':
        print(f"[BATCH PROCESSING] WARNING: Using default eta_vol = {eta_vol:.4f}")
        for warning in warnings:
            print(f"[BATCH PROCESSING] WARNING: {warning}")
    else:
        print(f"[BATCH PROCESSING] Step 1 complete: eta_vol = {eta_vol:.4f} (calculated from rated inputs)")

    # === STEP 2: GET COMPRESSOR SPECS ===
    # Convert displacement from user input (ft³) to m³ for the engine
    # Handle None values: if key exists but value is None, treat as missing (default to 0)
    rated_disp_ft3 = rated_inputs.get('disp_ft3') or 0
    
    comp_specs = {
        'displacement_m3': ft3_to_m3(rated_disp_ft3)
    }
    print(f"[BATCH PROCESSING] Compressor displacement: {rated_disp_ft3} ft^3 = {comp_specs['displacement_m3']:.6f} m^3")

    # === STEP 3: BUILD THE SENSOR NAME MAP ===
    diagram_model = data_manager.diagram_model
    sensor_map = {}

    # VERSION MARKER - If you see this, the new code is running!
    print("[BATCH PROCESSING] ========================================")
    print("[BATCH PROCESSING] CODE VERSION: 2025-10-30-FIX-v3")
    print("[BATCH PROCESSING] Duplicate prevention logic: ACTIVE")
    print("[BATCH PROCESSING] ========================================")

    # CRITICAL: Validate against actual input columns to avoid ghost/adjacent values
    # Create set for fast lookup and ensure we're using exact column names
    input_columns = set(input_dataframe.columns.tolist() if input_dataframe is not None else [])

    print(f"[BATCH PROCESSING] Available DataFrame columns ({len(input_columns)}): {sorted(input_columns)[:10]}{'...' if len(input_columns) > 10 else ''}")

    unmapped_roles = []
    duplicate_prevention = {}  # Track which sensor is mapped to which role to prevent duplicates

    for key, role_defs in REQUIRED_SENSOR_ROLES.items():
        found = False

        # DEBUG: Log T_1b roles to verify correct configuration
        if 'T_1b' in key or 'T_1c' in key:
            print(f"[BATCH PROCESSING] DEBUG: Processing {key} with {len(role_defs)} role definitions")

        for role_def in role_defs:
            sensor_name = _find_sensor_for_role(diagram_model, role_def)

            # DEBUG: Log what sensor T_1b resolves to
            if ('T_1b' in key or 'T_1c' in key) and sensor_name:
                print(f"[BATCH PROCESSING] DEBUG: {key} resolved to sensor '{sensor_name}' via {role_def}")

            # CRITICAL: Triple validation to prevent any possibility of ghost values
            if sensor_name:
                # Check 1: Sensor name is not None
                if sensor_name in input_columns:
                    # Check 2: Column actually exists in DataFrame

                    # Check 3: PREVENT DUPLICATE MAPPINGS - critical fix for ghost values!
                    # Multiple roles should NEVER map to the same sensor column
                    if sensor_name in duplicate_prevention:
                        existing_role = duplicate_prevention[sensor_name]
                        print(f"[BATCH PROCESSING] CRITICAL: Skipping duplicate mapping!")
                        print(f"                   Role '{key}' wants sensor '{sensor_name}'")
                        print(f"                   But '{existing_role}' already claimed it")
                        print(f"                   → '{key}' will show as unmapped (prevents ghost values)")
                        # Continue to next role_def to try fallback options
                        continue

                    # Check 4: This role hasn't been mapped yet
                    if key not in sensor_map:
                        sensor_map[key] = sensor_name
                        duplicate_prevention[sensor_name] = key  # Mark this sensor as claimed
                        found = True
                        break  # Found valid mapping
                    else:
                        print(f"[BATCH PROCESSING] WARNING: Duplicate mapping for '{key}' - using first match")
                        found = True
                        break
                else:
                    print(f"[BATCH PROCESSING] WARNING: Sensor '{sensor_name}' for role '{key}' not found in DataFrame columns")

        if not found:
            unmapped_roles.append(key)

    if unmapped_roles:
        print(f"[BATCH PROCESSING] WARNING: {len(unmapped_roles)} unmapped roles: {unmapped_roles[:5]}{'...' if len(unmapped_roles) > 5 else ''}")

    print(f"[BATCH PROCESSING] Sensor map built with {len(sensor_map)} valid mappings (validated against DataFrame columns)")

    # Verify no duplicate values in sensor_map (multiple roles mapping to same column)
    sensor_values = list(sensor_map.values())
    if len(sensor_values) != len(set(sensor_values)):
        print("[BATCH PROCESSING] WARNING: Multiple roles mapping to same sensor column - this may indicate configuration error")
        from collections import Counter
        duplicates = [item for item, count in Counter(sensor_values).items() if count > 1]
        print(f"[BATCH PROCESSING] Duplicate sensor columns: {duplicates}")

    # === STEP 4: RUN STEP 2 (ROW-BY-ROW PROCESSING) ===
    print(f"[BATCH PROCESSING] Starting row-by-row calculation...")

    results_df = input_dataframe.apply(
        calculate_row_performance,
        axis=1,
        sensor_map=sensor_map,
        eta_vol=eta_vol,
        comp_specs=comp_specs,
        refrigerant=refrigerant
    )

    print(f"[BATCH PROCESSING] Row-by-row calculation complete!")
    print(f"[BATCH PROCESSING] Output DataFrame has {len(results_df)} rows and {len(results_df.columns)} columns")
    print(f"[BATCH PROCESSING] Output columns: {list(results_df.columns)}")

    return results_df

