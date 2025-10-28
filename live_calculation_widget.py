"""
live_calculation_widget.py

Live-updating calculations page. Listens to DataManager changes and recomputes
results using calculation_engine. Designed to be independent of older widgets.
"""

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit

from calculation_engine import compute_cycle, calculate_performance_from_compressor


def f_to_k(temp_f: float) -> float:
    return (temp_f + 459.67) * 5.0 / 9.0


def psig_to_pa(pressure_psig: float) -> float:
    return (pressure_psig + 14.7) * 6894.76


class LiveCalculationWidget(QWidget):
    """A live, reactive calculations page."""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)  # ms
        self._debounce_timer.timeout.connect(self._recompute)
        
        # Store performance calculation results
        self.perf_results = None
        self.coil_results = None

        layout = QVBoxLayout(self)

        title = QLabel("Live Calculations")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.status_label = QLabel("Live (listening for changes)...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont("Courier", 10))
        layout.addWidget(self.text)

        # Connect to DataManager signals for reactivity
        try:
            self.data_manager.data_changed.connect(self.update_ui)
            self.data_manager.diagram_model_changed.connect(self.update_ui)
        except Exception:
            pass

        self.update_ui()

    # Public API compatible with app update pattern
    def update_ui(self):
        # Debounce rapid bursts
        self._debounce_timer.start()

    # Internal recompute
    def _recompute(self):
        try:
            self.status_label.setText("Recomputing…")
            
            # Get dataframe from data manager
            df = self.data_manager.get_current_dataframe()
            if df is None or df.empty:
                self.text.setPlainText("Load a CSV file to begin calculations.")
                self.status_label.setText("No data")
                return

            # Resolve required sensors
            suction_sensor = self.data_manager.get_mapped_sensor_for_role('suction_pressure')
            discharge_sensor = self.data_manager.get_mapped_sensor_for_role('discharge_pressure')

            # Try custom sensor fallbacks by type
            if not suction_sensor:
                custom = self.data_manager.diagram_model.get('custom_sensors', {})
                roles = self.data_manager.diagram_model.get('sensor_roles', {})
                for sid, sdata in custom.items():
                    if sdata.get('type') == 'suction_pressure' and sid in roles:
                        suction_sensor = roles.get(sid)
                        break
            if not discharge_sensor:
                custom = self.data_manager.diagram_model.get('custom_sensors', {})
                roles = self.data_manager.diagram_model.get('sensor_roles', {})
                for sid, sdata in custom.items():
                    if sdata.get('type') == 'discharge_pressure' and sid in roles:
                        discharge_sensor = roles.get(sid)
                        break

            suction_psig = self._get_value_safe(suction_sensor)
            discharge_psig = self._get_value_safe(discharge_sensor)

            # Coils: allow multiple inputs; center may have many named sensors
            coils_f: Dict[str, List[float]] = {"left": [], "center": [], "right": []}

            # Left
            left_sensor = self.data_manager.get_mapped_sensor_for_role('left_coil_outlet')
            left_val = self._get_value_safe(left_sensor)
            if left_val is not None:
                coils_f['left'].append(left_val)

            # Right
            right_sensor = self.data_manager.get_mapped_sensor_for_role('right_coil_outlet')
            right_val = self._get_value_safe(right_sensor)
            if right_val is not None:
                coils_f['right'].append(right_val)

            # Center: CTR Coil Outlet 1..6, and also scan mapped names containing that pattern
            roles_snapshot = list(self.data_manager.diagram_model.get('sensor_roles', {}).items())
            for i in range(1, 7):
                name = f'CTR Coil Outlet {i}'
                v = self._get_value_safe(name)
                if v is not None:
                    coils_f['center'].append(v)
            if not coils_f['center']:
                for _, sn in roles_snapshot:
                    if isinstance(sn, str) and 'CTR Coil Outlet' in sn:
                        v = self._get_value_safe(sn)
                        if v is not None:
                            coils_f['center'].append(v)

            # Convert units
            suction_pa = psig_to_pa(suction_psig) if suction_psig is not None else None
            discharge_pa = psig_to_pa(discharge_psig) if discharge_psig is not None else None
            coils_k = {k: [f_to_k(x) for x in vals] for k, vals in coils_f.items()}

            # Aggregation from DataManager setting
            agg = getattr(self.data_manager, 'value_aggregation', 'Average')

            # Compute coil superheat calculations
            self.coil_results = compute_cycle(
                suction_pressure_pa=suction_pa,
                discharge_pressure_pa=discharge_pa,
                coil_outlet_temps_k=coils_k,
                aggregation_method=agg,
                refrigerant='R410A',
            )

            # --- NEW: Extract compressor specs from diagram and compute performance ---
            compressor_specs = self._extract_compressor_specs()
            if compressor_specs:
                # Build mappings dict for the new calculation function
                # It expects role names like "Suction Pressure", "Liquid Line Pressure", etc.
                sensor_roles = self.data_manager.diagram_model.get('sensor_roles', {})
                mappings = {}
                
                # Map sensor roles to actual sensor names
                for role_key, sensor_name in sensor_roles.items():
                    if 'compressor' in role_key.lower() and 'inlet' in role_key.lower():
                        mappings['Suction Temperature'] = sensor_name
                    elif 'compressor' in role_key.lower() and 'outlet' in role_key.lower():
                        mappings['Discharge Temperature'] = sensor_name
                
                # Add pressure sensors
                if suction_sensor:
                    mappings['Suction Pressure'] = suction_sensor
                if discharge_sensor:
                    mappings['Discharge Pressure'] = discharge_sensor
                
                # Try to find liquid line sensors
                for role_key, sensor_name in sensor_roles.items():
                    if 'liquid' in role_key.lower() and 'temperature' in role_key.lower():
                        mappings['Liquid Line Temperature'] = sensor_name
                    elif 'liquid' in role_key.lower() and 'pressure' in role_key.lower():
                        mappings['Liquid Line Pressure'] = sensor_name
                    # Also check for TXV inlet as liquid line
                    elif 'txv' in role_key.lower() and 'inlet' in role_key.lower():
                        if 'Liquid Line Temperature' not in mappings:
                            mappings['Liquid Line Temperature'] = sensor_name
                
                # Call the new performance calculation
                self.perf_results = calculate_performance_from_compressor(
                    dataframe=df,
                    mappings=mappings,
                    compressor_specs=compressor_specs,
                    refrigerant=self.data_manager.refrigerant
                )
            else:
                self.perf_results = None

            # Render both results
            self._render_result(self.coil_results, suction_sensor, discharge_sensor, coils_f)
            self.status_label.setText("Live (updated)")
        except Exception as e:
            self.text.setPlainText(f"Error: {e}")
            self.status_label.setText("Error")

    def _extract_compressor_specs(self) -> Optional[Dict[str, float]]:
        """Extract compressor specifications from the first compressor in the diagram."""
        try:
            components = self.data_manager.diagram_model.get('components', {})
            for comp_id, comp_data in components.items():
                if comp_data.get('type') == 'Compressor':
                    props = comp_data.get('properties', {})
                    return {
                        'displacement_cm3': props.get('displacement_cm3', 10.5),
                        'speed_rpm': props.get('speed_rpm', 3500.0),
                        'vol_eff': props.get('vol_eff', 0.85)
                    }
            return None
        except Exception:
            return None

    def _get_value_safe(self, sensor_name: Optional[str]) -> Optional[float]:
        try:
            if not sensor_name:
                return None
            return self.data_manager.get_sensor_value(sensor_name)
        except Exception:
            return None

    def _render_result(self, result: Dict, suction_sensor: Optional[str], discharge_sensor: Optional[str], coils_f: Dict[str, List[float]]):
        lines: List[str] = []
        
        # --- NEW: Display Performance Calculation Results First ---
        if self.perf_results:
            lines.append("=" * 60)
            lines.append(" PERFORMANCE (from Compressor Displacement)")
            lines.append("=" * 60)
            lines.append("")
            
            if not self.perf_results.get("ok"):
                lines.append(f"ERROR: {self.perf_results.get('error', 'Unknown error')}")
            else:
                results_df = self.perf_results.get("dataframe")
                if results_df is not None and not results_df.empty:
                    avg_mass_flow = results_df['Mass Flow (kg/s)'].mean()
                    avg_capacity_w = results_df['Cooling Capacity (W)'].mean()
                    avg_capacity_btu = avg_capacity_w * 3.41214  # W to BTU/hr
                    
                    lines.append(f"Avg. Mass Flow Rate : {avg_mass_flow:.4f} kg/s")
                    lines.append(f"Avg. Cooling Capacity: {avg_capacity_w:,.1f} W")
                    lines.append(f"Avg. Cooling Capacity: {avg_capacity_btu:,.0f} BTU/hr")
                    lines.append("")
                    
                    # Show compressor specs used
                    compressor_specs = self._extract_compressor_specs()
                    if compressor_specs:
                        lines.append("Compressor Specifications:")
                        lines.append(f"  Displacement: {compressor_specs['displacement_cm3']:.2f} cm³")
                        lines.append(f"  Speed: {compressor_specs['speed_rpm']:.0f} RPM")
                        lines.append(f"  Volumetric Efficiency: {compressor_specs['vol_eff']:.2f}")
                        lines.append("")
        else:
            lines.append("=" * 60)
            lines.append(" PERFORMANCE CALCULATION")
            lines.append("=" * 60)
            lines.append("No compressor found in diagram or missing sensor mappings.")
            lines.append("Required sensors: Suction Pressure, Suction Temperature,")
            lines.append("                  Liquid Line Pressure, Liquid Line Temperature")
            lines.append("")
        
        lines.append("")
        lines.append("=" * 60)
        lines.append(" COIL SUPERHEAT ANALYSIS")
        lines.append("=" * 60)
        lines.append("")
        
        lines.append("REQUIRED SENSORS")
        lines.append("-" * 40)
        if suction_sensor:
            lines.append(f"Suction Pressure: {suction_sensor}")
        else:
            lines.append("Suction Pressure: [MISSING]")
        if discharge_sensor:
            lines.append(f"Discharge Pressure: {discharge_sensor}")
        else:
            lines.append("Discharge Pressure: [MISSING]")
        lines.append("")

        # Coil sensors list
        lines.append("COIL INPUTS (°F)")
        lines.append("-" * 40)
        lines.append(f"Left:   {', '.join(f'{v:.1f}' for v in coils_f['left']) if coils_f['left'] else 'None'}")
        lines.append(f"Center: {', '.join(f'{v:.1f}' for v in coils_f['center']) if coils_f['center'] else 'None'}")
        lines.append(f"Right:  {', '.join(f'{v:.1f}' for v in coils_f['right']) if coils_f['right'] else 'None'}")
        lines.append("")

        if not result.get('ok'):
            lines.append("Cannot compute yet:")
            for err in result.get('errors', []):
                lines.append(f"- {err}")
            self.text.setPlainText("\n".join(lines))
            return

        coils = result.get('coils', {})
        for name in ("left", "center", "right"):
            c = coils.get(name, {})
            calc = c.get('calc', {})
            lines.append("=" * 60)
            lines.append(f"{name.upper()} COIL")
            lines.append("=" * 60)
            if 'error' in calc:
                lines.append(f"Error: {calc['error']}")
                lines.append("")
                continue
            used = calc.get('usedTempK')
            t_sat = calc.get('tSatK')
            superheat_f = calc.get('superheatF')
            lines.append(f"Used Temp: {used*9/5-459.67:.1f}°F" if used is not None else "Used Temp: N/A")
            lines.append(f"Sat Temp:  {t_sat*9/5-459.67:.1f}°F" if t_sat is not None else "Sat Temp:  N/A")
            lines.append(f"Superheat: {superheat_f:.1f}°F" if superheat_f is not None else "Superheat: N/A")
            lines.append("")

            p1, p2, p3, p4 = calc.get('p1'), calc.get('p2'), calc.get('p3'), calc.get('p4')
            lines.append("P-h POINTS (h kJ/kg, p kPa)")
            def fmtp(pt):
                if not pt:
                    return "N/A"
                return f"({pt['h_kJkg']:.1f}, {pt['p_kPa']:.1f})"
            lines.append(f"P1: {fmtp(p1)}  P2: {fmtp(p2)}  P3: {fmtp(p3)}  P4: {fmtp(p4)}")
            lines.append("")

            lines.append("CYCLE PERFORMANCE")
            lines.append(f"Refrig. Effect: {calc.get('refrigerationEffectKJkg', 0):.2f} kJ/kg")
            lines.append(f"Compressor Work: {calc.get('compressorWorkKJkg', 0):.2f} kJ/kg")
            lines.append(f"Heat Rejected: {calc.get('heatRejectedKJkg', 0):.2f} kJ/kg")
            lines.append(f"COP: {calc.get('cop', 0):.2f}")
            lines.append("")

        self.text.setPlainText("\n".join(lines))


