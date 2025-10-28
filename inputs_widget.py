"""
inputs_widget.py

Simple Inputs-only page. Mirrors the exact values shown beside sensor dots by
using DataManager.get_sensor_value for currently mapped roles and known center
outlet sensors. No calculations here; just list live inputs.
"""

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit
from PyQt6.QtWidgets import QPushButton
from component_schemas import SCHEMAS


class InputsWidget(QWidget):
    """Live inputs page that reflects mapping/unmapping instantly."""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._refresh)

        layout = QVBoxLayout(self)

        title = QLabel("Inputs")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.subtitle = QLabel("Click Refresh to update inputs.")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle)

        # Manual refresh button
        self.refresh_btn = QPushButton("Refresh Inputs")
        self.refresh_btn.setFont(QFont("Arial", 12))
        self.refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(self.refresh_btn)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont("Courier", 10))
        layout.addWidget(self.text)

        # Intentionally no live subscriptions; updates happen only on button click

        # Initial state: do not auto-refresh

    def update_ui(self):
        # No-op for manual refresh mode
        return

    def _refresh(self):
        try:
            lines: List[str] = []
            dm = self.data_manager
            roles: Dict[str, str] = dm.diagram_model.get('sensor_roles', {}) or {}
            components: Dict[str, Dict] = dm.diagram_model.get('components', {}) or {}

            def enumerate_ports(comp_type: str, props: Dict) -> List[str]:
                ports: List[str] = []
                schema = SCHEMAS.get(comp_type, {})
                # Static ports
                for p in schema.get('ports', []) or []:
                    name = p.get('name')
                    if name:
                        ports.append(name)
                # Dynamic ports
                for dyn_key in ('dynamic_ports', 'dynamic_ports_2'):
                    dyn = schema.get(dyn_key)
                    if not dyn:
                        continue
                    prefix = dyn.get('prefix')
                    count_prop = dyn.get('count_property')
                    if not prefix or not count_prop:
                        continue
                    count = int((props.get(count_prop) or 0))
                    for i in range(1, count + 1):
                        ports.append(f"{prefix}{i}")
                return ports

            def port_label(component_type: str, props: Dict, port_name: str) -> str:
                label = props.get('circuit_label')
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
                if component_type == 'Condenser':
                    if port_name == 'inlet':
                        return "Condenser Inlet"
                    if port_name == 'outlet':
                        return "Condenser Outlet"
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

            def format_sensor(sensor_name: Optional[str]) -> str:
                if not sensor_name:
                    return ""
                num = dm.get_sensor_number(sensor_name)
                val = self._val(sensor_name)
                num_str = f"#{num}" if num is not None else ""
                if val is None:
                    return num_str
                try:
                    if isinstance(val, (int, float)):
                        return f"{num_str} {val:.1f}".strip()
                except Exception:
                    pass
                return f"{num_str} {val}".strip()

            type_order = {
                'Compressor': 1,
                'Condenser': 2,
                'Evaporator': 3,
                'TXV': 4,
                'Distributor': 5,
                'Junction': 6,
                'SensorBulb': 7,
                'Fan': 8,
                'AirSensorArray': 9,
                'ShelvingGrid': 10,
            }

            def comp_sort_key(item):
                ctype = item[1].get('type', '')
                return (type_order.get(ctype, 999), item[0])

            for comp_id, comp in sorted(components.items(), key=comp_sort_key):
                ctype = comp.get('type')
                props = comp.get('properties', {}) or {}
                port_names = enumerate_ports(ctype, props)
                if not port_names:
                    continue
                header_side = props.get('circuit_label')
                header = f"{header_side + ' ' if header_side else ''}{ctype} ({comp_id})".strip()
                lines.append(header)
                lines.append("-" * 40)
                for p in port_names:
                    role_key_primary = f"{ctype}.{comp_id}.{p}"
                    role_key_fallback = f"{comp_id}.{p}"
                    mapped_sensor = roles.get(role_key_primary)
                    if not mapped_sensor:
                        mapped_sensor = roles.get(role_key_fallback)
                    display_val = format_sensor(mapped_sensor)
                    label = port_label(ctype, props, p)
                    if display_val:
                        lines.append(f"{label}: {display_val}")
                    else:
                        lines.append(f"{label}:")
                lines.append("")

            self.text.setPlainText("\n".join(lines))
            self.subtitle.setText("Inputs refreshed")
        except Exception as e:
            self.text.setPlainText(f"Error: {e}")
            self.subtitle.setText("Error")

    def _val(self, sensor_name: Optional[str]) -> Optional[float]:
        try:
            if not sensor_name:
                return None
            return self.data_manager.get_sensor_value(sensor_name)
        except Exception:
            return None

    def _fmt(self, label: str, name: Optional[str], val: Optional[float], unit: str) -> str:
        if name and val is not None:
            if isinstance(val, (int, float)):
                try:
                    return f"{label}: {name} = {val:.1f}{unit}"
                except Exception:
                    return f"{label}: {name} = {val}{unit}"
            return f"{label}: {name} = {val}{unit}"
        if name:
            return f"{label}: {name} = N/A"
        return f"{label}: [MISSING]"


