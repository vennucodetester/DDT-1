"""
Simple P-h Diagram Calculation Widget
Shows step-by-step calculations for Left, Center, and Right coils
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTextEdit, QScrollArea, QFrame, QGroupBox,
                             QCheckBox, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import CoolProp.CoolProp as CP
from port_resolver import list_all_ports
import pandas as pd
from datetime import datetime
from pathlib import Path

class SimpleCalculationWidget(QWidget):
    """Simple calculation widget showing step-by-step P-h diagram calculations."""
    
    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.needs_refresh = False  # Flag to track if calculations need refresh
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("P-h Diagram Calculations")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Calculate button
        calc_button = QPushButton("Calculate P-h Diagram Points")
        calc_button.setFont(QFont("Arial", 12))
        calc_button.clicked.connect(self.calculate_ph_points)
        layout.addWidget(calc_button)

        # Manual inputs/ports buttons
        inputs_btn = QPushButton("Show Calculation Inputs")
        inputs_btn.setFont(QFont("Arial", 12))
        inputs_btn.clicked.connect(self.show_calc_inputs)
        layout.addWidget(inputs_btn)

        ports_btn = QPushButton("Show All Ports (Debug)")
        ports_btn.setFont(QFont("Arial", 12))
        ports_btn.clicked.connect(self.show_all_ports)
        layout.addWidget(ports_btn)
        
        # Export section
        export_frame = QFrame()
        export_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        export_layout = QHBoxLayout(export_frame)
        
        # Checkbox for ON-time only
        self.on_time_only_checkbox = QCheckBox("Export ON-time data only")
        self.on_time_only_checkbox.setChecked(True)
        self.on_time_only_checkbox.setFont(QFont("Arial", 10))
        export_layout.addWidget(self.on_time_only_checkbox)
        
        # Export button
        export_btn = QPushButton("📊 Export Calculation Results to CSV")
        export_btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        export_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        export_btn.clicked.connect(self.export_calculations)
        export_layout.addWidget(export_btn)
        
        layout.addWidget(export_frame)
        
        # Results area
        self.results_text = QTextEdit()
        self.results_text.setFont(QFont("Courier", 10))
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)
        
        # Initial message
        self.results_text.setPlainText("Click 'Calculate P-h Diagram Points' to see step-by-step calculations for each coil.")
        
    def update_ui(self):
        """Update the UI when data changes (e.g., when sensor mappings change)."""
        print("[PH CALC] update_ui() called - setting needs_refresh = True")
        # Set flag that calculations need refresh
        self.needs_refresh = True
        # Clear the results and show a message indicating that calculations need to be refreshed
        self.results_text.setPlainText("Data has been updated. Click 'Calculate P-h Diagram Points' to see updated calculations with the new sensor mappings.")
        print("[PH CALC] UI updated with refresh message")

    def resolve_calc_inputs(self):
        """Gather calculation inputs directly from ports via port_resolver.

        Returns dict with keys: suction_psig, discharge_psig, left_out_f, center_out_f, right_out_f
        Values may be None if not mapped.
        """
        ports = list_all_ports(self.data_manager)
        suction_psig = None
        discharge_psig = None
        # Group evaporator outlet values by circuit label
        left_vals = []
        center_vals = []
        right_vals = []

        for p in ports:
            if p.get('type') == 'Compressor':
                if p.get('port') == 'inlet' and p.get('value') is not None:
                    suction_psig = p.get('value')
                if p.get('port') == 'outlet' and p.get('value') is not None:
                    discharge_psig = p.get('value')
            elif p.get('type') == 'Evaporator' and isinstance(p.get('port'), str) and p.get('port').startswith('outlet_circuit_'):
                val = p.get('value')
                if val is None:
                    continue
                label = (p.get('properties') or {}).get('circuit_label')
                if label == 'Left':
                    left_vals.append(val)
                elif label == 'Center':
                    center_vals.append(val)
                elif label == 'Right':
                    right_vals.append(val)

        def avg_or_none(values):
            return sum(values) / len(values) if values else None

        return {
            'suction_psig': suction_psig,
            'discharge_psig': discharge_psig,
            'left_out_f': avg_or_none(left_vals),
            'center_out_f': avg_or_none(center_vals),
            'right_out_f': avg_or_none(right_vals),
        }

    def calculate_ph_points(self):
        """Calculate P-h diagram points for all three coils."""
        try:
            print("[PH] calculate_ph_points() invoked - button click received")
            # Clear the needs refresh flag since we're calculating now
            self.needs_refresh = False
            
            # Use the stored data manager
            if not self.data_manager:
                self.results_text.setPlainText("Error: No data manager available")
                return
            # Resolve inputs from ports (same source as Show Calculation Inputs)
            inputs = self.resolve_calc_inputs()
            suction_pressure_psig = inputs.get('suction_psig')
            discharge_pressure_psig = inputs.get('discharge_psig')
            left_outlet_temp = inputs.get('left_out_f')
            center_outlet_temp = inputs.get('center_out_f')
            right_outlet_temp = inputs.get('right_out_f')
            print(f"[PH] inputs via ports -> suction={suction_pressure_psig}, discharge={discharge_pressure_psig}, L={left_outlet_temp}, C={center_outlet_temp}, R={right_outlet_temp}")

            # Heuristics: if left/right roles are unmapped, attempt to infer from mapped sensor names
            # Removed: we now rely solely on ports
            
            # Start building results
            results = []
            results.append("=" * 80)
            results.append("P-h DIAGRAM CALCULATIONS - STEP BY STEP")
            results.append("=" * 80)
            results.append("")
            
            # Show comprehensive sensor status report
            results.append("REQUIRED SENSORS FOR P-h CALCULATIONS:")
            results.append("=" * 80)
            results.append("")
            
            # Pressure Sensors
            results.append("PRESSURE SENSORS:")
            results.append("-" * 40)
            
            # Suction/Discharge via ports only
            if suction_pressure_psig is not None:
                results.append(f"✓ Suction Pressure: {suction_pressure_psig:.1f} psig")
            else:
                results.append("✗ Suction Pressure: [MISSING]")
            if discharge_pressure_psig is not None:
                results.append(f"✓ Discharge Pressure: {discharge_pressure_psig:.1f} psig")
            else:
                results.append("✗ Discharge Pressure: [MISSING]")
            
            results.append("")
            
            # Coil Outlet Temperatures
            results.append("COIL OUTLET TEMPERATURES:")
            results.append("-" * 40)
            
            # Left/Center/Right Coil Outlet Temps via ports only (averaged per side)
            if left_outlet_temp is not None:
                results.append(f"✓ Left Coil Outlet: {left_outlet_temp:.1f}°F")
            else:
                results.append("✗ Left Coil Outlet: [MISSING]")
            
            # Center Coil Outlet Temp (multiple sensors)
            if center_outlet_temp is not None:
                results.append(f"✓ Center Coil Outlet: {center_outlet_temp:.1f}°F")
            else:
                results.append("✗ Center Coil Outlet: [MISSING]")
            
            # Right Coil Outlet Temp
            if right_outlet_temp is not None:
                results.append(f"✓ Right Coil Outlet: {right_outlet_temp:.1f}°F")
            else:
                results.append("✗ Right Coil Outlet: [MISSING]")
            
            # Mapping Instructions
            results.append("MAPPING INSTRUCTIONS:")
            results.append("-" * 40)
            
            missing_sensors = []
            if suction_pressure_psig is None:
                missing_sensors.append("Suction Pressure")
            if discharge_pressure_psig is None:
                missing_sensors.append("Discharge Pressure")
            if left_outlet_temp is None:
                missing_sensors.append("Left Coil Outlet")
            if center_outlet_temp is None:
                missing_sensors.append("Center Coil Outlet")
            if right_outlet_temp is None:
                missing_sensors.append("Right Coil Outlet")
            
            if missing_sensors:
                results.append("To complete pH calculations, you need to map:")
                for sensor in missing_sensors:
                    if sensor == "Left Coil Outlet":
                        results.append(f"- Map a sensor to 'left_coil_outlet' role for left coil temperature")
                    elif sensor == "Right Coil Outlet":
                        results.append(f"- Map a sensor to 'right_coil_outlet' role for right coil temperature")
                    elif sensor == "Center Coil Outlet":
                        results.append(f"- Map CTR Coil Outlet sensors (1-6) for center coil temperature")
                    elif sensor == "Suction Pressure":
                        results.append(f"- Create a custom suction pressure sensor or map to 'suction_pressure' role")
                    elif sensor == "Discharge Pressure":
                        results.append(f"- Create a custom discharge pressure sensor or map to 'discharge_pressure' role")
            else:
                results.append("✓ All required sensors are mapped and ready for calculations!")
            
            results.append("")
            results.append("")
            
            # Convert pressures to absolute
            suction_pressure_pa = (suction_pressure_psig + 14.7) * 6894.76
            discharge_pressure_pa = (discharge_pressure_psig + 14.7) * 6894.76
            
            results.append("CONVERTED PRESSURES:")
            results.append("-" * 40)
            results.append(f"Suction Pressure: {suction_pressure_pa/1000:.1f} kPa")
            results.append(f"Discharge Pressure: {discharge_pressure_pa/1000:.1f} kPa")
            results.append("")
            
            # Calculate for each coil
            coil_data = {
                'left': left_outlet_temp,
                'center': center_outlet_temp,
                'right': right_outlet_temp
            }
            
            for coil_name, outlet_temp_f in coil_data.items():
                results.append("=" * 60)
                results.append(f"{coil_name.upper()} COIL CALCULATION")
                results.append("=" * 60)
                results.append("")
                
                if outlet_temp_f is None:
                    results.append("No outlet temperature data - using saturated vapor assumption")
                    # Point 1: Saturated vapor
                    h1 = CP.PropsSI('H', 'P', suction_pressure_pa, 'Q', 1, 'R410A')
                    s1 = CP.PropsSI('S', 'P', suction_pressure_pa, 'Q', 1, 'R410A')
                    t1 = CP.PropsSI('T', 'P', suction_pressure_pa, 'Q', 1, 'R410A')
                else:
                    results.append(f"Using actual outlet temperature: {outlet_temp_f:.1f}°F")
                    # Point 1: Actual outlet temperature
                    outlet_temp_k = (outlet_temp_f + 459.67) * 5/9
                    h1 = CP.PropsSI('H', 'P', suction_pressure_pa, 'T', outlet_temp_k, 'R410A')
                    s1 = CP.PropsSI('S', 'P', suction_pressure_pa, 'T', outlet_temp_k, 'R410A')
                    t1 = outlet_temp_k
                
                # Calculate saturation temperature
                t_sat = CP.PropsSI('T', 'P', suction_pressure_pa, 'Q', 1, 'R410A')
                superheat = (t1 - t_sat) * 9/5
                
                results.append("")
                results.append("POINT 1 - EVAPORATOR OUTLET:")
                results.append(f"  Temperature: {t1-273.15:.1f}°C ({t1*9/5-459.67:.1f}°F)")
                results.append(f"  Saturation Temp: {t_sat-273.15:.1f}°C ({t_sat*9/5-459.67:.1f}°F)")
                results.append(f"  Superheat: {superheat:.1f}°F")
                results.append(f"  Enthalpy: {h1/1000:.2f} kJ/kg")
                results.append(f"  Pressure: {suction_pressure_pa/1000:.1f} kPa")
                results.append("")
                
                # Point 2: Compressor Outlet (Isentropic compression)
                h2 = CP.PropsSI('H', 'P', discharge_pressure_pa, 'S', s1, 'R410A')
                t2 = CP.PropsSI('T', 'P', discharge_pressure_pa, 'S', s1, 'R410A')
                
                results.append("POINT 2 - COMPRESSOR OUTLET:")
                results.append(f"  Temperature: {t2-273.15:.1f}°C ({t2*9/5-459.67:.1f}°F)")
                results.append(f"  Enthalpy: {h2/1000:.2f} kJ/kg")
                results.append(f"  Pressure: {discharge_pressure_pa/1000:.1f} kPa")
                results.append("")
                
                # Point 3: Condenser Outlet (Saturated liquid)
                h3 = CP.PropsSI('H', 'P', discharge_pressure_pa, 'Q', 0, 'R410A')
                t3 = CP.PropsSI('T', 'P', discharge_pressure_pa, 'Q', 0, 'R410A')
                
                results.append("POINT 3 - CONDENSER OUTLET:")
                results.append(f"  Temperature: {t3-273.15:.1f}°C ({t3*9/5-459.67:.1f}°F)")
                results.append(f"  Enthalpy: {h3/1000:.2f} kJ/kg")
                results.append(f"  Pressure: {discharge_pressure_pa/1000:.1f} kPa")
                results.append("")
                
                # Point 4: TXV Outlet (Isenthalpic expansion)
                h4 = h3  # Isenthalpic
                t4 = CP.PropsSI('T', 'P', suction_pressure_pa, 'H', h4, 'R410A')
                
                results.append("POINT 4 - TXV OUTLET:")
                results.append(f"  Temperature: {t4-273.15:.1f}°C ({t4*9/5-459.67:.1f}°F)")
                results.append(f"  Enthalpy: {h4/1000:.2f} kJ/kg")
                results.append(f"  Pressure: {suction_pressure_pa/1000:.1f} kPa")
                results.append("")
                
                # Calculate cycle performance
                refrigeration_effect = (h1 - h4) / 1000
                compressor_work = (h2 - h1) / 1000
                heat_rejected = (h2 - h3) / 1000
                cop = refrigeration_effect / compressor_work if compressor_work > 0 else 0
                
                results.append("CYCLE PERFORMANCE:")
                results.append(f"  Refrigeration Effect: {refrigeration_effect:.2f} kJ/kg")
                results.append(f"  Compressor Work: {compressor_work:.2f} kJ/kg")
                results.append(f"  Heat Rejected: {heat_rejected:.2f} kJ/kg")
                results.append(f"  COP: {cop:.2f}")
                results.append("")
                
                # P-h diagram coordinates
                results.append("P-h DIAGRAM COORDINATES:")
                results.append(f"  P1: ({h1/1000:.1f} kJ/kg, {suction_pressure_pa/1000:.1f} kPa)")
                results.append(f"  P2: ({h2/1000:.1f} kJ/kg, {discharge_pressure_pa/1000:.1f} kPa)")
                results.append(f"  P3: ({h3/1000:.1f} kJ/kg, {discharge_pressure_pa/1000:.1f} kPa)")
                results.append(f"  P4: ({h4/1000:.1f} kJ/kg, {suction_pressure_pa/1000:.1f} kPa)")
                results.append("")
            
            # Display results
            print("[PH] calculate_ph_points() completed successfully - updating UI")
            self.results_text.setPlainText("\n".join(results))
            
        except Exception as e:
            print(f"[PH] calculate_ph_points() exception: {e}")
            self.results_text.setPlainText(f"Error in calculations: {e}")

    def show_calc_inputs(self):
        try:
            ports = list_all_ports(self.data_manager)
            # Filter to calculation necessities: compressor inlet/outlet; evaporator outlets; optional TXV bulb
            lines = []
            lines.append("CALCULATION INPUTS")
            lines.append("-" * 40)
            # Compressor pressures
            for p in ports:
                if p['type'] == 'Compressor' and p['port'] in ('inlet', 'outlet'):
                    sensor_num = f"#{p['sensorNumber']}" if p['sensorNumber'] else ""
                    val = p['value']
                    val_str = (f"{val:.1f}" if isinstance(val, (int, float)) else (str(val) if val is not None else ""))
                    lines.append(f"{p['label']}: {sensor_num} {val_str}".strip())
            # Evaporator outlets
            for p in ports:
                if p['type'] == 'Evaporator' and p['port'].startswith('outlet_circuit_'):
                    sensor_num = f"#{p['sensorNumber']}" if p['sensorNumber'] else ""
                    val = p['value']
                    val_str = (f"{val:.1f}" if isinstance(val, (int, float)) else (str(val) if val is not None else ""))
                    lines.append(f"{p['label']}: {sensor_num} {val_str}".strip())
            # Optional: TXV bulb temperatures (if needed later)
            # for p in ports:
            #     if p['type'] == 'TXV' and p['port'] == 'bulb':
            #         sensor_num = f"#{p['sensorNumber']}" if p['sensorNumber'] else ""
            #         val = p['value']
            #         val_str = (f"{val:.1f}" if isinstance(val, (int, float)) else (str(val) if val is not None else ""))
            #         lines.append(f"{p['label']}: {sensor_num} {val_str}".strip())

            self.results_text.setPlainText("\n".join(lines))
        except Exception as e:
            self.results_text.setPlainText(f"Error showing inputs: {e}")
    
    def export_calculations(self):
        """Export all calculation results to a CSV file."""
        try:
            # Check if we have data
            if self.data_manager.csv_data is None or self.data_manager.csv_data.empty:
                QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
                return
            
            # Check if we have a configuration
            if not self.data_manager.diagram_model:
                QMessageBox.warning(self, "No Configuration", "Please load a configuration file first.")
                return
            
            # Get data based on checkbox
            on_time_only = self.on_time_only_checkbox.isChecked()
            
            if on_time_only:
                df = self.data_manager.get_on_time_filtered_data()
                data_type = "ON-time"
            else:
                df = self.data_manager.get_filtered_data()
                data_type = "All"
            
            if df is None or df.empty:
                QMessageBox.warning(self, "No Data", f"No {data_type} data available.")
                return
            
            # Show progress message
            QMessageBox.information(
                self,
                "Calculating...",
                f"Calculating state points for {len(df)} rows.\n\n"
                f"This may take a moment. Please wait..."
            )
            
            # Import calculation functions
            from calculation_orchestrator import calculate_full_system
            
            # Run calculations
            results = calculate_full_system(self.data_manager)
            
            if not results or 'state_points' not in results:
                QMessageBox.warning(self, "Calculation Error", "Could not calculate state points.")
                return
            
            # Build output DataFrame
            output_rows = []
            state_points = results['state_points']
            n_rows = len(df)
            
            for i in range(n_rows):
                row = {
                    'Row_Number': i + 1,
                    'Compressor_State': 'ON' if on_time_only else 'UNKNOWN'
                }
                
                # Add timestamp if available
                if 'Timestamp' in df.columns:
                    row['Timestamp'] = df.iloc[i]['Timestamp']
                
                # Add all 8 state points
                for point_name in ['point_1', 'point_2a', 'point_2b', 'point_3a', 
                                   'point_3b', 'point_4a', 'point_4b', 'point_5']:
                    if point_name in state_points:
                        point_data = state_points[point_name]
                        prefix = point_name.replace('_', '').upper()
                        
                        # Temperature (F)
                        row[f'{prefix}_T_F'] = point_data['T'][i] if i < len(point_data['T']) else None
                        
                        # Pressure (psia)
                        row[f'{prefix}_P_psia'] = point_data['P'][i] if i < len(point_data['P']) else None
                        
                        # Enthalpy (Btu/lb)
                        row[f'{prefix}_h_Btu_lb'] = point_data['h'][i] if i < len(point_data['h']) else None
                        
                        # Entropy (Btu/lb-R)
                        row[f'{prefix}_s_Btu_lbR'] = point_data['s'][i] if i < len(point_data['s']) else None
                        
                        # Quality (0-1 or None)
                        quality_list = point_data.get('quality', [None] * len(point_data['P']))
                        row[f'{prefix}_quality'] = quality_list[i] if i < len(quality_list) else None
                
                # Add performance metrics
                row['Superheat_F'] = results.get('superheat', [None]*n_rows)[i]
                row['Subcooling_F'] = results.get('subcooling', [None]*n_rows)[i]
                row['Mass_Flow_Rate_lb_hr'] = results.get('mass_flow_rate', [None]*n_rows)[i]
                row['Cooling_Capacity_Btu_hr'] = results.get('cooling_capacity', [None]*n_rows)[i]
                row['Compressor_Power_Btu_hr'] = results.get('compressor_power', [None]*n_rows)[i]
                row['Heat_Rejection_Btu_hr'] = results.get('heat_rejection', [None]*n_rows)[i]
                row['COP'] = results.get('cop', [None]*n_rows)[i]
                row['EER'] = results.get('eer', [None]*n_rows)[i]
                
                output_rows.append(row)
            
            # Create DataFrame
            output_df = pd.DataFrame(output_rows)
            
            # Ask user where to save
            default_filename = f"calculation_results_{data_type.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Calculation Results",
                default_filename,
                "CSV Files (*.csv)"
            )
            
            if not file_path:
                return  # User cancelled
            
            # Save to CSV
            output_df.to_csv(file_path, index=False)
            
            # Show success message
            QMessageBox.information(
                self,
                "Export Successful",
                f"✅ Calculation results exported successfully!\n\n"
                f"File: {Path(file_path).name}\n"
                f"Location: {Path(file_path).parent}\n\n"
                f"Rows: {len(output_df):,}\n"
                f"Columns: {len(output_df.columns)}\n"
                f"Data Type: {data_type}\n\n"
                f"You can now open this file in Excel to verify calculations."
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"An error occurred during export:\n\n{str(e)}\n\n"
                f"Please check the console for details."
            )
            import traceback
            traceback.print_exc()
    
    def show_all_ports(self):
        """Show all ports for debugging."""
        try:
            ports = list_all_ports(self.data_manager)
            lines = []
            lines.append("ALL PORTS (DEBUG)")
            lines.append("-" * 40)
            for p in ports:
                sensor_num = f"#{p['sensorNumber']}" if p['sensorNumber'] else ""
                val = p['value']
                val_str = (f"{val:.1f}" if isinstance(val, (int, float)) else (str(val) if val is not None else ""))
                lines.append(f"{p['type']} {p['componentId']} {p['port']} | {p['label']}: {sensor_num} {val_str}".strip())
            self.results_text.setPlainText("\n".join(lines))
        except Exception as e:
            self.results_text.setPlainText(f"Error listing ports: {e}")
