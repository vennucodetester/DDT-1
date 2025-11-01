"""
calculation_orchestrator.py

Orchestrates the complete 8-point cycle calculation using port_resolver and calculation_engine.
This module bridges the diagram model with the calculation engine.
"""

from typing import Dict, Optional, List
import pandas as pd
from port_resolver import resolve_mapped_sensor, get_sensor_value
from calculation_engine import (
    calculate_row_performance,
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

    # LH circuit (FIXED: T_1a maps to TXV outlet, T_1b averages ALL coil inlets)
    'T_1a-lh': [('TXV', 'outlet', {'circuit_label': 'Left'})],
    'T_1b-lh': [('Evaporator', 'inlet_circuit_1', {'circuit_label': 'Left'})],  # Will be averaged across all circuits
    'T_2a-LH': [('Evaporator', 'outlet_circuit_1', {'circuit_label': 'Left'})],  # Will be averaged across all circuits
    'T_4b-lh': [('TXV', 'inlet', {'circuit_label': 'Left'})],

    # CTR circuit (FIXED: T_1a maps to TXV outlet, T_1b averages ALL coil inlets)
    'T_1a-ctr': [('TXV', 'outlet', {'circuit_label': 'Center'})],
    'T_1b-ctr': [('Evaporator', 'inlet_circuit_1', {'circuit_label': 'Center'})],  # Will be averaged across all circuits
    'T_2a-ctr': [('Evaporator', 'outlet_circuit_1', {'circuit_label': 'Center'})],  # Will be averaged across all circuits
    'T_4b-ctr': [('TXV', 'inlet', {'circuit_label': 'Center'})],

    # RH circuit (FIXED: T_1a maps to TXV outlet, T_1c averages ALL coil inlets)
    'T_1a-rh': [('TXV', 'outlet', {'circuit_label': 'Right'})],
    'T_1c-rh': [('Evaporator', 'inlet_circuit_1', {'circuit_label': 'Right'})],  # Will be averaged across all circuits
    'T_2a-RH': [('Evaporator', 'outlet_circuit_1', {'circuit_label': 'Right'})],  # Will be averaged across all circuits
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
            # Found matching component, resolve the sensor
            sensor = resolve_mapped_sensor(model, comp_type, comp_id, role_port)
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

    # === STEP 1: GET RATED INPUTS AND SYSTEM SPECS ===
    rated_inputs = data_manager.rated_inputs
    refrigerant = data_manager.refrigerant or 'R290'

    # === GET SYSTEM SPECS ===
    comp_specs = {
        'gpm_water': rated_inputs.get('gpm_water')
    }
    print(f"[BATCH PROCESSING] Water flow rate: {comp_specs.get('gpm_water', 'Not set')} GPM")

    # === STEP 3: BUILD THE SENSOR NAME MAP ===
    diagram_model = data_manager.diagram_model
    sensor_map = {}

    # Validate against actual input columns to avoid ghost/adjacent values
    input_columns = set(input_dataframe.columns if input_dataframe is not None else [])

    for key, role_defs in REQUIRED_SENSOR_ROLES.items():
        for role_def in role_defs:
            sensor_name = _find_sensor_for_role(diagram_model, role_def)
            # Only accept mappings that exist in the current input dataframe
            if sensor_name and sensor_name in input_columns:
                sensor_map[key] = sensor_name
                break  # Found it

        if key not in sensor_map:
            print(f"[BATCH PROCESSING] WARNING: No sensor mapped for required role '{key}' (or column missing in input data)")
    
    # Special handling for T_1b, T_2a (coil inlets/outlets that need averaging)
    # Find ALL mapped circuits for Left, Center, Right evaporators
    components = diagram_model.get('components', {})
    circuit_avg_keys = {}  # Will contain lists of sensor names to average
    
    for side in ['Left', 'Center', 'Right']:
        # Find the evaporator for this side
        evap_id = None
        for comp_id, comp in components.items():
            if comp.get('type') == 'Evaporator' and comp.get('properties', {}).get('circuit_label') == side:
                evap_id = comp_id
                break
        
        if evap_id:
            # Check how many circuits this evaporator has
            circuits = comp.get('properties', {}).get('circuits', 1)
            
            # Collect all inlet circuit sensors for T_1b
            inlet_sensors = []
            outlet_sensors = []
            for i in range(1, circuits + 1):
                inlet_port = f'inlet_circuit_{i}'
                outlet_port = f'outlet_circuit_{i}'
                from port_resolver import resolve_mapped_sensor
                inlet_sensor = resolve_mapped_sensor(diagram_model, 'Evaporator', evap_id, inlet_port)
                outlet_sensor = resolve_mapped_sensor(diagram_model, 'Evaporator', evap_id, outlet_port)
                
                if inlet_sensor and inlet_sensor in input_columns:
                    inlet_sensors.append(inlet_sensor)
                if outlet_sensor and outlet_sensor in input_columns:
                    outlet_sensors.append(outlet_sensor)
            
            # Store for averaging (will be processed in calculate_row_performance)
            if side == 'Left':
                if inlet_sensors:
                    sensor_map[f'_avg_T_1b-lh'] = inlet_sensors
                if outlet_sensors:
                    sensor_map[f'_avg_T_2a-LH'] = outlet_sensors
            elif side == 'Center':
                if inlet_sensors:
                    sensor_map[f'_avg_T_1b-ctr'] = inlet_sensors
                if outlet_sensors:
                    sensor_map[f'_avg_T_2a-ctr'] = outlet_sensors
            elif side == 'Right':
                if inlet_sensors:
                    sensor_map[f'_avg_T_1c-rh'] = inlet_sensors
                if outlet_sensors:
                    sensor_map[f'_avg_T_2a-RH'] = outlet_sensors

    print(f"[BATCH PROCESSING] Sensor map built with {len(sensor_map)} valid mappings (validated against DataFrame columns)")
    print(f"[BATCH PROCESSING] Sensor map: {sensor_map}")

    # === STEP 4: RUN STEP 2 (ROW-BY-ROW PROCESSING) ===
    print(f"[BATCH PROCESSING] Starting row-by-row calculation...")

    results_df = input_dataframe.apply(
        calculate_row_performance,
        axis=1,
        sensor_map=sensor_map,
        comp_specs=comp_specs,
        refrigerant=refrigerant
    )

    print(f"[BATCH PROCESSING] Row-by-row calculation complete!")
    print(f"[BATCH PROCESSING] Output DataFrame has {len(results_df)} rows and {len(results_df.columns)} columns")
    print(f"[BATCH PROCESSING] Output columns: {list(results_df.columns)}")

    return results_df

