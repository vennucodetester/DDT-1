"""
inputs_widget.py

Displays live sensor inputs AND provides UI for entering rated (manual) inputs
needed for volumetric efficiency calculation (Step 1 from Calculations-DDT.txt).
"""

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
                              QPushButton, QDoubleSpinBox, QGroupBox, QFormLayout,
                              QMessageBox)
from component_schemas import SCHEMAS


class InputsWidget(QWidget):
    """
    Inputs page with two sections:
    1. Live sensor values (read-only)
    2. Rated inputs form (user-editable, for Step 1 calculation)
    """

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._refresh_sensor_values)

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Inputs")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # === SECTION 1: RATED INPUTS (USER MANUAL INPUT) ===
        rated_inputs_group = self._create_rated_inputs_section()
        layout.addWidget(rated_inputs_group)

        # === SECTION 2: LIVE SENSOR VALUES ===
        sensor_values_group = self._create_sensor_values_section()
        layout.addWidget(sensor_values_group)

        # Load rated inputs from data manager on initialization
        self._load_rated_inputs()

    def _create_rated_inputs_section(self):
        """Create the rated inputs form (Step 1 requirements)."""
        group = QGroupBox("Rated Inputs (User Manual Input for Step 1)")
        group.setFont(QFont("Arial", 11, QFont.Weight.Bold))

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # Create input widgets for each rated value
        # Based on Calculations-DDT.txt Step 1 requirements

        self.m_dot_rated_spinbox = QDoubleSpinBox()
        self.m_dot_rated_spinbox.setRange(0, 10000)
        self.m_dot_rated_spinbox.setDecimals(2)
        self.m_dot_rated_spinbox.setSuffix(" lbm/hr")
        self.m_dot_rated_spinbox.setToolTip("Rated mass flow rate from compressor datasheet")
        form_layout.addRow("Rated Mass Flow (m_dot_rated):", self.m_dot_rated_spinbox)

        self.hz_rated_spinbox = QDoubleSpinBox()
        self.hz_rated_spinbox.setRange(0, 200)
        self.hz_rated_spinbox.setDecimals(1)
        self.hz_rated_spinbox.setSuffix(" Hz")
        self.hz_rated_spinbox.setToolTip("Rated compressor speed from datasheet")
        form_layout.addRow("Rated Speed (hz_rated):", self.hz_rated_spinbox)

        self.disp_ft3_spinbox = QDoubleSpinBox()
        self.disp_ft3_spinbox.setRange(0, 100)
        self.disp_ft3_spinbox.setDecimals(4)
        self.disp_ft3_spinbox.setSuffix(" ft³")
        self.disp_ft3_spinbox.setToolTip("Compressor displacement from datasheet")
        form_layout.addRow("Compressor Displacement (disp_ft3):", self.disp_ft3_spinbox)

        self.rated_evap_temp_spinbox = QDoubleSpinBox()
        self.rated_evap_temp_spinbox.setRange(-100, 100)
        self.rated_evap_temp_spinbox.setDecimals(1)
        self.rated_evap_temp_spinbox.setSuffix(" °F")
        self.rated_evap_temp_spinbox.setToolTip("Rated evaporator temperature from datasheet")
        form_layout.addRow("Rated Evap Temp:", self.rated_evap_temp_spinbox)

        self.rated_return_gas_temp_spinbox = QDoubleSpinBox()
        self.rated_return_gas_temp_spinbox.setRange(-100, 100)
        self.rated_return_gas_temp_spinbox.setDecimals(1)
        self.rated_return_gas_temp_spinbox.setSuffix(" °F")
        self.rated_return_gas_temp_spinbox.setToolTip("Rated return gas temperature from datasheet")
        form_layout.addRow("Rated Return Gas Temp:", self.rated_return_gas_temp_spinbox)

        # Save button
        button_layout = QHBoxLayout()
        self.save_rated_button = QPushButton("Save Rated Inputs")
        self.save_rated_button.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.save_rated_button.clicked.connect(self._save_rated_inputs)
        button_layout.addWidget(self.save_rated_button)
        button_layout.addStretch()

        form_layout.addRow("", button_layout)

        group.setLayout(form_layout)
        return group

    def _create_sensor_values_section(self):
        """Create the live sensor values display."""
        group = QGroupBox("Live Sensor Values")
        group.setFont(QFont("Arial", 11, QFont.Weight.Bold))

        layout = QVBoxLayout()

        self.subtitle = QLabel("Click Refresh to update sensor inputs.")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle)

        # Manual refresh button
        self.refresh_btn = QPushButton("Refresh Sensor Values")
        self.refresh_btn.setFont(QFont("Arial", 10))
        self.refresh_btn.clicked.connect(self._refresh_sensor_values)
        layout.addWidget(self.refresh_btn)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont("Courier", 9))
        layout.addWidget(self.text)

        group.setLayout(layout)
        return group

    def _load_rated_inputs(self):
        """Load rated inputs from data manager into UI."""
        rated = self.data_manager.rated_inputs

        if rated.get('m_dot_rated_lbhr') is not None:
            self.m_dot_rated_spinbox.setValue(rated['m_dot_rated_lbhr'])
        if rated.get('hz_rated') is not None:
            self.hz_rated_spinbox.setValue(rated['hz_rated'])
        if rated.get('disp_ft3') is not None:
            self.disp_ft3_spinbox.setValue(rated['disp_ft3'])
        if rated.get('rated_evap_temp_f') is not None:
            self.rated_evap_temp_spinbox.setValue(rated['rated_evap_temp_f'])
        if rated.get('rated_return_gas_temp_f') is not None:
            self.rated_return_gas_temp_spinbox.setValue(rated['rated_return_gas_temp_f'])

    def _save_rated_inputs(self):
        """Save rated inputs from UI to data manager."""
        self.data_manager.rated_inputs = {
            'm_dot_rated_lbhr': self.m_dot_rated_spinbox.value(),
            'hz_rated': self.hz_rated_spinbox.value(),
            'disp_ft3': self.disp_ft3_spinbox.value(),
            'rated_evap_temp_f': self.rated_evap_temp_spinbox.value(),
            'rated_return_gas_temp_f': self.rated_return_gas_temp_spinbox.value(),
        }

        QMessageBox.information(
            self,
            "Rated Inputs Saved",
            "Rated inputs have been saved successfully.\n\n"
            "These values will be used for volumetric efficiency calculation (Step 1)."
        )

        print(f"[INPUTS] Rated inputs saved: {self.data_manager.rated_inputs}")

    def update_ui(self):
        """Called when tab is shown - refresh sensor values."""
        self._refresh_sensor_values()

    def _refresh_sensor_values(self):
        """Refresh the live sensor values display."""
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
            self.subtitle.setText("Sensor values refreshed")
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
