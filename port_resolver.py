"""
port_resolver.py

Utilities to enumerate component ports and resolve their mapped sensors and
current values, using diagram model as the single source of truth.

Role key resolution order:
1) "{TypeName}.{componentId}.{portName}"
2) "{componentId}.{portName}"
"""

from typing import Dict, List, Optional, Tuple, Any
from component_schemas import SCHEMAS


def enumerate_ports_for_component(component_type: str, component_props: Dict[str, Any]) -> List[str]:
    ports: List[str] = []
    schema = SCHEMAS.get(component_type, {})

    # Static ports
    for p in schema.get('ports', []) or []:
        name = p.get('name')
        if name:
            ports.append(name)

    # Dynamic ports (support _2 key in schema)
    for dyn_key in ('dynamic_ports', 'dynamic_ports_2'):
        dyn = schema.get(dyn_key)
        if not dyn:
            continue
        prefix = dyn.get('prefix')
        count_prop = dyn.get('count_property')
        if not prefix or not count_prop:
            continue
        count = int((component_props.get(count_prop) or 0))
        for i in range(1, count + 1):
            ports.append(f"{prefix}{i}")

    return ports


def resolve_mapped_sensor(diagram_model: Dict[str, Any], component_type: str, component_id: str, port_name: str) -> Optional[str]:
    roles: Dict[str, str] = diagram_model.get('sensor_roles', {}) or {}
    primary = f"{component_type}.{component_id}.{port_name}"
    fallback = f"{component_id}.{port_name}"
    return roles.get(primary) or roles.get(fallback)


def get_sensor_number(dm, sensor_name: Optional[str]) -> Optional[int]:
    if not sensor_name:
        return None
    try:
        return dm.get_sensor_number(sensor_name)
    except Exception:
        return None


def get_sensor_value(dm, sensor_name: Optional[str]) -> Optional[float]:
    if not sensor_name:
        return None
    try:
        return dm.get_sensor_value(sensor_name)
    except Exception:
        return None


def format_port_label(component_type: str, component_props: Dict[str, Any], port_name: str) -> str:
    label = component_props.get('circuit_label')
    side = f"{label} " if label else ""
    if component_type == 'Evaporator':
        if port_name.startswith('inlet_circuit_'):
            idx = port_name.split('_')[-1]
            return f"{side}Evap Inlet {idx}".strip()
        if port_name.startswith('outlet_circuit_'):
            idx = port_name.split('_')[-1]
            return f"{side}Evap Outlet {idx}".strip()
    if component_type == 'Distributor':
        if port_name == 'inlet':
            return f"{side}Distributor Inlet".strip()
        if port_name.startswith('outlet_'):
            idx = port_name.split('_')[-1]
            return f"{side}Distributor Outlet {idx}".strip()
    if component_type == 'TXV':
        if port_name == 'inlet':
            return f"TXV {side}Inlet".replace('  ', ' ').strip()
        if port_name == 'outlet':
            return f"TXV {side}Outlet".replace('  ', ' ').strip()
        if port_name == 'bulb':
            return f"TXV {side}Bulb".replace('  ', ' ').strip()
    if component_type == 'Compressor':
        if port_name == 'inlet':
            return "Compressor Inlet"
        if port_name == 'outlet':
            return "Compressor Outlet"
        if port_name == 'SP':
            return "Suction Pressure"
        if port_name == 'DP':
            return "Discharge Pressure"
        if port_name == 'RPM':
            return "Compressor RPM"
    if component_type == 'Condenser':
        if port_name == 'inlet':
            return "Condenser Inlet"
        if port_name == 'outlet':
            return "Condenser Outlet"
        if port_name == 'air_in_temp':
            return "Condenser Air Inlet Temp"
        if port_name == 'air_out_temp':
            return "Condenser Air Outlet Temp"
        if port_name == 'water_in_temp':
            return "Condenser Water Inlet Temp"
        if port_name == 'water_out_temp':
            return "Condenser Water Outlet Temp"
    if component_type == 'Junction':
        if port_name.startswith('inlet_'):
            idx = port_name.split('_')[-1]
            return f"{side}Junction Inlet {idx}".strip()
        if port_name.startswith('outlet_'):
            idx = port_name.split('_')[-1]
            return f"{side}Junction Outlet {idx}".strip()
        if port_name == 'sensor':
            return f"{side}Junction Sensor".strip()
    if component_type == 'SensorBulb' and port_name == 'measurement':
        return f"Sensor Bulb {side}Measurement".replace('  ', ' ').strip()
    return f"{side}{port_name}".strip()


def list_all_ports(dm) -> List[Dict[str, Any]]:
    """Return a list of port dicts with resolved sensor and value.

    Each dict: { componentId, type, properties, port, label, roleKeyPrimary,
                 roleKeyFallback, sensor, sensorNumber, value }
    """
    out: List[Dict[str, Any]] = []
    model = dm.diagram_model
    components: Dict[str, Dict] = model.get('components', {}) or {}

    for comp_id, comp in components.items():
        ctype = comp.get('type')
        props = comp.get('properties', {}) or {}
        for port in enumerate_ports_for_component(ctype, props):
            sensor = resolve_mapped_sensor(model, ctype, comp_id, port)
            out.append({
                'componentId': comp_id,
                'type': ctype,
                'properties': props,
                'port': port,
                'label': format_port_label(ctype, props, port),
                'roleKeyPrimary': f"{ctype}.{comp_id}.{port}",
                'roleKeyFallback': f"{comp_id}.{port}",
                'sensor': sensor,
                'sensorNumber': get_sensor_number(dm, sensor),
                'value': get_sensor_value(dm, sensor),
            })
    return out


def get_pressures_from_compressor(dm) -> Dict[str, Optional[float]]:
    """Return suction and discharge pressures based on compressor ports (if mapped)."""
    model = dm.diagram_model
    components: Dict[str, Dict] = model.get('components', {}) or {}
    suction_val: Optional[float] = None
    discharge_val: Optional[float] = None
    for comp_id, comp in components.items():
        if comp.get('type') != 'Compressor':
            continue
        for port in ('inlet', 'outlet'):
            sensor = resolve_mapped_sensor(model, 'Compressor', comp_id, port)
            val = get_sensor_value(dm, sensor)
            if port == 'inlet' and val is not None:
                suction_val = val
            if port == 'outlet' and val is not None:
                discharge_val = val
    return {'suction': suction_val, 'discharge': discharge_val}


def get_evaporator_outlet_temps(dm) -> Dict[str, List[float]]:
    """Return outlet temps grouped by evaporator circuit_label (Left/Center/Right)."""
    model = dm.diagram_model
    components: Dict[str, Dict] = model.get('components', {}) or {}
    groups: Dict[str, List[float]] = {'Left': [], 'Center': [], 'Right': []}
    for comp_id, comp in components.items():
        if comp.get('type') != 'Evaporator':
            continue
        props = comp.get('properties', {}) or {}
        label = props.get('circuit_label') or ''
        for port in enumerate_ports_for_component('Evaporator', props):
            if not port.startswith('outlet_circuit_'):
                continue
            sensor = resolve_mapped_sensor(model, 'Evaporator', comp_id, port)
            val = get_sensor_value(dm, sensor)
            if val is not None and label in groups:
                groups[label].append(val)
    return groups


