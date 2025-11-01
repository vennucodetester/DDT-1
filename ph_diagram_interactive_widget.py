"""
Interactive P-h Diagram Widget for R290

Displays an interactive P-h diagram with circuit-specific cycles using Matplotlib.
Receives data from CalculationsWidget and plots saturation lines + cycle paths.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QCheckBox, QGroupBox, QMessageBox,
                             QTableWidget, QTableWidgetItem, QFileDialog)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import numpy as np
import pandas as pd
from ph_diagram_generator import PhDiagramGenerator


class PhDiagramInteractiveWidget(QWidget):
    """
    Widget for interactive P-h diagram visualization.
    Displays saturation dome, cycle paths, and state points.
    """
    
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.generator = PhDiagramGenerator('R290')
        
        self.current_data = None
        self.sat_data = None
        self.cycle_data = None
        self.cycle_paths = None
        
        # Interactive cursor state
        self.interactive_enabled = False
        self.cursor_annotation = None
        self.crosshair_v = None
        self.crosshair_h = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Create the UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # ==================== Title ====================
        title = QLabel("Interactive P-h Diagram (R290)")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title.setFont(title_font)
        main_layout.addWidget(title)
        
        # ==================== Control Panel ====================
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)
        
        # ==================== Matplotlib Canvas ====================
        self.figure = Figure(figsize=(14, 8), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas, 1)
        
        # ==================== Status Bar ====================
        self.status_label = QLabel("Ready. Load filtered data from Calculations tab.")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        main_layout.addWidget(self.status_label)
    

    def _create_control_panel(self):
        """Create the control panel with toggles and buttons."""
        panel = QGroupBox("Display Options")
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(15)
        
        # ========== Circuit Toggles ==========
        circuits_group = QGroupBox("Circuits")
        circuits_layout = QHBoxLayout()
        circuits_layout.setContentsMargins(5, 5, 5, 5)
        
        self.check_lh = QCheckBox("Left Hand (LH)")
        self.check_lh.setChecked(True)
        self.check_lh.stateChanged.connect(self.on_options_changed)
        circuits_layout.addWidget(self.check_lh)
        
        self.check_ctr = QCheckBox("Center (CTR)")
        self.check_ctr.setChecked(True)
        self.check_ctr.stateChanged.connect(self.on_options_changed)
        circuits_layout.addWidget(self.check_ctr)
        
        self.check_rh = QCheckBox("Right Hand (RH)")
        self.check_rh.setChecked(True)
        self.check_rh.stateChanged.connect(self.on_options_changed)
        circuits_layout.addWidget(self.check_rh)
        
        circuits_group.setLayout(circuits_layout)
        layout.addWidget(circuits_group)
        
        # ========== Display Options ==========
        options_group = QGroupBox("Display")
        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(5, 5, 5, 5)
        
        self.check_grid = QCheckBox("Show Grid")
        self.check_grid.setChecked(True)
        self.check_grid.stateChanged.connect(self.on_options_changed)
        options_layout.addWidget(self.check_grid)
        
        self.check_labels = QCheckBox("Show Labels")
        self.check_labels.setChecked(True)
        self.check_labels.stateChanged.connect(self.on_options_changed)
        options_layout.addWidget(self.check_labels)
        
        self.check_interactive = QCheckBox("Interactive Cursor")
        self.check_interactive.setChecked(False)
        self.check_interactive.stateChanged.connect(self.on_interactive_toggled)
        options_layout.addWidget(self.check_interactive)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # ========== Action Buttons ==========
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(self.on_options_changed)
        layout.addWidget(self.btn_refresh)
        
        self.btn_export = QPushButton("💾 Export as PNG")
        self.btn_export.clicked.connect(self.on_export_diagram)
        layout.addWidget(self.btn_export)

        self.btn_info = QPushButton("ℹ️ Column Info")
        self.btn_info.clicked.connect(self.on_show_column_info)
        self.btn_info.setToolTip("Show which columns are being plotted for each cycle point")
        layout.addWidget(self.btn_info)

        layout.addStretch()
        panel.setLayout(layout)
        return panel
    
    def load_filtered_data(self, filtered_df, circuit_data=None):
        """
        Load filtered data from Calculations tab and prepare for plotting.

        Args:
            filtered_df: DataFrame with calculated columns
            circuit_data: Optional (not used in this version)
        """
        # REMOVED BLOCKING: P-h diagram only needs calculated data, not rated inputs
        # Goal-2C graceful degradation allows calculations to run with defaults
        # P-h diagram should draw whenever calculation data is available

        if filtered_df is None or filtered_df.empty:
            self.status_label.setText("❌ No data to display. Filter data in Calculations tab first.")
            self.status_label.setStyleSheet("color: red;")
            return
        
        try:
            self.current_data = filtered_df
            
            # Generate saturation data
            self.sat_data = self.generator.generate_saturation_data()
            
            # Rebuilt workflow: compute averaged points and module paths
            self.avg_points = self.generator.build_averaged_points(filtered_df)
            self.module_paths = self.generator.get_paths_from_points(self.avg_points)
            
            self.status_label.setText("✓ Data loaded successfully. Rendering diagram...")
            self.status_label.setStyleSheet("color: green;")
            
            # Draw the diagram
            self.on_options_changed()
            
        except Exception as e:
            self.status_label.setText(f"❌ Error loading data: {str(e)}")
            self.status_label.setStyleSheet("color: red;")
            print(f"[PH DIAGRAM] Load error: {e}")
            import traceback
            traceback.print_exc()
    
    def on_options_changed(self):
        """Handle changes to display options and redraw diagram."""
        if self.sat_data is None or self.avg_points is None or self.module_paths is None:
            self.status_label.setText("❌ No data loaded.")
            self.status_label.setStyleSheet("color: red;")
            return
        
        try:
            # Get toggle states
            show_lh = self.check_lh.isChecked()
            show_ctr = self.check_ctr.isChecked()
            show_rh = self.check_rh.isChecked()
            show_grid = self.check_grid.isChecked()
            show_labels = self.check_labels.isChecked()
            
            # Clear figure
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            self.figure.patch.set_facecolor('white')
            ax.set_facecolor('#f8f9fa')
            
            # ==================== Plot Saturation Dome ====================
            h_liquid = self.sat_data['h_liquid']
            h_vapor = self.sat_data['h_vapor']
            pressures = self.sat_data['pressures']
            
            # Fill between liquid and vapor lines (two-phase region)
            ax.fill_betweenx(pressures, h_liquid, h_vapor, alpha=0.08, color='gray', label='Two-phase region')
            
            # Saturation lines
            ax.plot(h_liquid, pressures, 'k-', linewidth=2.5, label='Saturated liquid (Q=0)')
            ax.plot(h_vapor, pressures, 'k-', linewidth=2.5, label='Saturated vapor (Q=1)')
            
            # ==================== Plot Cycle Paths ====================
            # Use new averaged paths workflow
            # Plot each module's averaged polyline
            circuit_list = []
            if show_lh:
                circuit_list.append(('LH', '#3b82f6'))
            if show_ctr:
                circuit_list.append(('CTR', '#16a34a'))
            if show_rh:
                circuit_list.append(('RH', '#a855f7'))

            import logging
            logger = logging.getLogger(__name__)
            for circuit_name, color in circuit_list:
                path = self.module_paths.get(circuit_name, [])
                if len(path) >= 2:
                    h_path = [pt['h'] for pt in path]
                    p_path = [pt['P'] for pt in path]
                    ax.plot(h_path, p_path, '-', color=color, linewidth=2.5,
                            label=f'{circuit_name} Module', zorder=4)
                    logger.info(f"[PH AVG] Path.{circuit_name} plotted -> {list(zip([round(x,3) for x in h_path],[round(y,3) for y in p_path]))}")

            # Compression path (2b -> 3b), shown as dashed dark line
            comp_path = self.module_paths.get('compression', [])
            if len(comp_path) == 2:
                ax.plot([comp_path[0]['h'], comp_path[1]['h']],
                        [comp_path[0]['P'], comp_path[1]['P']],
                        '--', color='#374151', linewidth=2.0, label='Compression (2b→3b)', zorder=3)
                logger.info(f"[PH AVG] Path.Compression plotted -> [(x={comp_path[0]['h']:.3f}, y={comp_path[0]['P']:.3f}), (x={comp_path[1]['h']:.3f}, y={comp_path[1]['P']:.3f})]")
            
            # ==================== Plot State Points ====================
            # For labeling, flatten module points
            all_points = []
            for circuit_name, color in [('LH','#3b82f6'),('CTR','#16a34a'),('RH','#a855f7')]:
                if ((circuit_name=='LH' and show_lh) or
                    (circuit_name=='CTR' and show_ctr) or
                    (circuit_name=='RH' and show_rh)):
                    for key in ['T3b','T4b','T1b','T2b']:
                        pt = self.avg_points.get(circuit_name, {}).get(key)
                        if pt and not (np.isnan(pt['h']) or np.isnan(pt['P'])):
                            all_points.append({'id': f'{key}_{circuit_name}', 'h': pt['h'], 'P': pt['P'], 'desc': key, 'color': color})
            
            # Debug: Print all point IDs to understand structure (can be removed later)
            # print("\n[DEBUG] All point IDs in data:")
            # for pt in all_points:
            #     print(f"  ID: {pt['id']}, h={pt['h']:.1f}, P={pt['P']:.1f}, desc={pt['desc']}")
            
            # Collect points to label - one per corner, choosing representative position
            corner_positions = {}  # {corner_num: (h, P)}
            corner_labels = {
                '1': '1: Evap Inlet',
                '2': '2: Evap Outlet', 
                '3': '3: Comp Outlet',
                '4': '4: Cond Outlet'
            }
            
            for point in all_points:
                # Determine if point should be visible based on circuit toggles
                point_id = point['id']
                should_show = False
                
                # Circuit-specific points have format like '1_LH', '2a_RH', '4b_CTR'
                if '_LH' in point_id and show_lh:
                    should_show = True
                elif '_CTR' in point_id and show_ctr:
                    should_show = True
                elif '_RH' in point_id and show_rh:
                    should_show = True
                elif '_' not in point_id:
                    pass
                
                if should_show:
                    ax.plot(point['h'], point['P'], 'o', color=point['color'], 
                           markersize=8, markeredgecolor='white', markeredgewidth=1.5, 
                           zorder=10)
                    
                    # Track position for labeling - only store FIRST occurrence of each corner
                    base_id = point_id.split('_')[0]
                    
                    # Map specific point IDs to corner numbers (one label per corner only)
                    # Corner 1: Evap Inlet - use circuit-specific "1" points (left side, bottom, low h)
                    if base_id == '1' and '1' not in corner_positions:
                        corner_positions['1'] = (point['h'], point['P'])
                    # Corner 2: Evap Outlet - use "2a" points (right side, bottom, high h)
                    elif base_id == '2a' and '2' not in corner_positions:
                        corner_positions['2'] = (point['h'], point['P'])
                    # Corner 3: Comp Outlet - use ONLY "3a" (top left, after compression)
                    elif base_id == '3a' and '3' not in corner_positions:
                        corner_positions['3'] = (point['h'], point['P'])
                    # Corner 4: Cond Outlet - use ONLY "4b" points (top right, low h, before TXV)
                    elif base_id == '4b' and '4' not in corner_positions:
                        corner_positions['4'] = (point['h'], point['P'])
            
            # Add labels after all points are plotted - label the four keys once per module
            if show_labels and corner_positions:
                for corner_num, (h, P) in corner_positions.items():
                    label_text = corner_labels.get(corner_num, corner_num)
                    ax.annotate(label_text, xy=(h, P), 
                               xytext=(10, 10), textcoords='offset points', 
                               fontsize=9, fontweight='bold', 
                               color='#1f2937', alpha=0.9,
                               bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7, edgecolor='none'))
            
            # ==================== Formatting ====================
            ax.set_xlabel('Enthalpy (h) [kJ/kg]', fontsize=12, fontweight='bold')
            ax.set_ylabel('Pressure (P) [kPa]', fontsize=12, fontweight='bold')
            ax.set_title('P-h Diagram for R290 Refrigeration Cycle', fontsize=13, fontweight='bold', pad=15)
            
            # Set axis limits
            h_min, h_max = h_liquid.min() - 20, h_vapor.max() + 30
            p_min, p_max = pressures.min() * 0.8, pressures.max() * 1.2
            
            ax.set_xlim(h_min, h_max)
            ax.set_ylim(p_min, p_max)
            ax.set_yscale('log')
            
            # Grid
            if show_grid:
                ax.grid(True, which='both', alpha=0.3, linestyle='-', linewidth=0.5)
                ax.grid(True, which='minor', alpha=0.1, linestyle=':', linewidth=0.3)
            
            # Legend
            handles, labels = ax.get_legend_handles_labels()
            ax.legend(handles, labels, loc='best', fontsize=10, framealpha=0.95)
            
            self.figure.tight_layout()
            self.canvas.draw()
            
            circuits_shown = ', '.join([c[0] for c in circuit_list])
            self.status_label.setText(f"✓ Diagram rendered. Circuits: {circuits_shown}")
            self.status_label.setStyleSheet("color: green;")
            
        except Exception as e:
            self.status_label.setText(f"❌ Error rendering diagram: {str(e)}")
            self.status_label.setStyleSheet("color: red;")
            print(f"[PH DIAGRAM] Render error: {e}")
            import traceback
            traceback.print_exc()
    
    def on_interactive_toggled(self):
        """Toggle interactive cursor mode on/off."""
        self.interactive_enabled = self.check_interactive.isChecked()
        
        if self.interactive_enabled:
            # Connect mouse motion event
            self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
            self.status_label.setText("✓ Interactive cursor enabled. Hover over diagram.")
            self.status_label.setStyleSheet("color: green;")
        else:
            # Remove crosshair and annotation if they exist
            if self.cursor_annotation:
                self.cursor_annotation.remove()
                self.cursor_annotation = None
            if self.crosshair_v:
                self.crosshair_v.remove()
                self.crosshair_v = None
            if self.crosshair_h:
                self.crosshair_h.remove()
                self.crosshair_h = None
            self.canvas.draw_idle()
            self.status_label.setText("✓ Interactive cursor disabled.")
            self.status_label.setStyleSheet("color: gray;")
    
    def on_mouse_move(self, event):
        """Handle mouse movement for interactive cursor."""
        if not self.interactive_enabled or not event.inaxes:
            return
        
        # Get cursor position in data coordinates
        h_cursor = event.xdata  # enthalpy
        p_cursor = event.ydata  # pressure
        
        if h_cursor is None or p_cursor is None:
            return
        
        # Get the axes
        ax = self.figure.axes[0] if self.figure.axes else None
        if not ax:
            return
        
        # Remove old crosshair and annotation
        if self.cursor_annotation:
            self.cursor_annotation.remove()
        if self.crosshair_v:
            self.crosshair_v.remove()
        if self.crosshair_h:
            self.crosshair_h.remove()
        
        # Draw crosshair
        self.crosshair_v = ax.axvline(h_cursor, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
        self.crosshair_h = ax.axhline(p_cursor, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
        
        # Calculate properties at cursor position
        tooltip_text = self.get_properties_at_point(h_cursor, p_cursor)
        
        # Create annotation (tooltip)
        self.cursor_annotation = ax.annotate(
            tooltip_text,
            xy=(h_cursor, p_cursor),
            xytext=(20, 20),
            textcoords='offset points',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.9, edgecolor='gray'),
            fontsize=8,
            verticalalignment='bottom',
            horizontalalignment='left',
            zorder=100
        )
        
        self.canvas.draw_idle()
    
    def get_properties_at_point(self, h_kJkg, P_kPa):
        """Calculate and format thermodynamic properties at given point."""
        try:
            # Convert to SI units for CoolProp
            h_Jkg = h_kJkg * 1000
            P_Pa = P_kPa * 1000
            
            # Calculate properties using CoolProp
            from CoolProp.CoolProp import PropsSI
            
            T_K = PropsSI('T', 'H', h_Jkg, 'P', P_Pa, 'R290')
            T_C = T_K - 273.15
            T_F = T_C * 9/5 + 32
            
            # Try to get quality (vapor fraction)
            try:
                quality = PropsSI('Q', 'H', h_Jkg, 'P', P_Pa, 'R290')
                if quality < 0:
                    phase = "Subcooled Liquid"
                elif quality > 1:
                    phase = "Superheated Vapor"
                else:
                    phase = f"Two-Phase (Q={quality*100:.1f}%)"
            except:
                phase = "Unknown Phase"
                quality = None
            
            # Get context (location/component identification)
            context = self.identify_location_context(h_kJkg, P_kPa, quality)
            
            # Format tooltip text
            lines = [
                f"P: {P_kPa:.1f} kPa ({P_kPa*0.145:.1f} psia)",
                f"h: {h_kJkg:.1f} kJ/kg",
                f"T: {T_C:.1f}°C ({T_F:.1f}°F)",
                f"Phase: {phase}"
            ]
            
            # Add context if available
            if context:
                lines.append("─" * 30)
                lines.append(context)
            
            return '\n'.join(lines)
            
        except Exception as e:
            return f"P: {P_kPa:.1f} kPa\nh: {h_kJkg:.1f} kJ/kg\n(Properties unavailable)"
    
    def identify_location_context(self, h_kJkg, P_kPa, quality):
        """Identify which component or process the cursor position represents."""
        if not self.cycle_data:
            return None
        
        common = self.cycle_data.get('common_points', {})
        circuits = self.cycle_data.get('circuit_points', {})
        
        # Get pressure levels
        P_suc = self.cycle_data.get('P_suc_pa', 0) / 1000  # kPa
        P_cond = self.cycle_data.get('P_cond_pa', 0) / 1000  # kPa
        
        if P_suc == 0 or P_cond == 0:
            return None
        
        # Tolerance for pressure matching (±10%)
        pressure_tolerance = 0.1
        
        # Determine pressure zone
        at_low_pressure = abs(P_kPa - P_suc) / P_suc < pressure_tolerance
        at_high_pressure = abs(P_kPa - P_cond) / P_cond < pressure_tolerance
        
        # Check proximity to specific state points
        nearest_point = self.find_nearest_cycle_point(h_kJkg, P_kPa)
        if nearest_point:
            return nearest_point
        
        # General region identification based on pressure and phase
        if at_high_pressure:
            if quality is not None and 0 <= quality <= 1:
                return "📍 Condenser Interior\n⚙️  Refrigerant condensing, rejecting heat"
            elif quality is not None and quality > 1:
                return "📍 Compressor Discharge / Condenser Inlet\n⚙️  Hot gas entering condenser"
            elif quality is not None and quality < 0:
                return "📍 Liquid Line / Condenser Outlet\n⚙️  Subcooled liquid before expansion"
        
        elif at_low_pressure:
            if quality is not None and 0 <= quality <= 1:
                return "📍 Evaporator Interior\n⚙️  Refrigerant boiling, absorbing heat"
            elif quality is not None and quality > 1:
                return "📍 Suction Line / Evaporator Outlet\n⚙️  Superheated vapor before compressor"
            elif quality is not None and quality < 0:
                return "📍 After Expansion Valve\n⚙️  Cold two-phase mixture entering evaporator"
        
        else:
            # Between pressures - likely compression or expansion
            if h_kJkg < 300:
                return "📍 Expansion Process Region\n⚙️  TXV throttling (4b→1)"
            else:
                return "📍 Compression Process Region\n⚙️  Gas being compressed (2b→3a)"
        
        return None
    
    def find_nearest_cycle_point(self, h_kJkg, P_kPa, threshold=30):
        """Find if cursor is near any cycle point and return description."""
        if not self.cycle_data:
            return None
        
        common = self.cycle_data.get('common_points', {})
        circuits = self.cycle_data.get('circuit_points', {})
        
        min_distance = float('inf')
        nearest_info = None
        
        # Check common points
        point_descriptions = {
            '2b': ('📍 Point 2b: Compressor Inlet', '⚙️  Mixed suction gas from all circuits'),
            '3a': ('📍 Point 3a: Compressor Outlet', '⚙️  Hot discharge gas, highest temperature'),
            '3b': ('📍 Point 3b: Condenser Inlet', '⚙️  Entering condenser for cooling'),
            '4a': ('📍 Point 4a: Condenser Outlet', '⚙️  Subcooled liquid ready for distribution')
        }
        
        for point_id, point_data in common.items():
            h_point = point_data.get('h', 0)
            P_point = point_data.get('P', 0)
            
            # Calculate Euclidean distance (normalized)
            h_diff = (h_kJkg - h_point)
            P_diff = (P_kPa - P_point) / 10  # Scale pressure to similar magnitude as enthalpy
            distance = (h_diff**2 + P_diff**2)**0.5
            
            if distance < threshold and distance < min_distance:
                min_distance = distance
                if point_id in point_descriptions:
                    nearest_info = '\n'.join(point_descriptions[point_id])
        
        # Check circuit-specific points (only for first circuit to avoid duplication)
        circuit_descriptions = {
            '1': ('📍 Point 1: Evaporator Inlet', '⚙️  After TXV expansion, two-phase mixture'),
            '2a': ('📍 Point 2a: Evaporator Outlet', '⚙️  Superheated vapor leaving evaporator'),
            '4b': ('📍 Point 4b: TXV Inlet', '⚙️  Subcooled liquid before expansion')
        }
        
        for circuit_name in ['LH', 'CTR', 'RH']:
            if circuit_name not in circuits:
                continue
            
            for point_id, point_data in circuits[circuit_name].items():
                h_point = point_data.get('h', 0)
                P_point = point_data.get('P', 0)
                
                h_diff = (h_kJkg - h_point)
                P_diff = (P_kPa - P_point) / 10
                distance = (h_diff**2 + P_diff**2)**0.5
                
                if distance < threshold and distance < min_distance:
                    min_distance = distance
                    if point_id in circuit_descriptions:
                        desc = circuit_descriptions[point_id]
                        nearest_info = f'{desc[0]} ({circuit_name})\n{desc[1]}'
            
            # Only check one circuit to avoid repetition
            break
        
        return nearest_info
    
    def on_export_diagram(self):
        """Export diagram as PNG."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export P-h Diagram",
            "ph_diagram.png",
            "PNG Images (*.png);;PDF Files (*.pdf);;SVG Files (*.svg)"
        )

        if file_path:
            try:
                self.figure.savefig(file_path, dpi=300, bbox_inches='tight', facecolor='white')
                QMessageBox.information(self, "Success", f"Diagram exported to:\n{file_path}")
                self.status_label.setText(f"✓ Exported to {file_path}")
                self.status_label.setStyleSheet("color: green;")
                print(f"[PH DIAGRAM] Exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")
                self.status_label.setText(f"❌ Export failed")
                self.status_label.setStyleSheet("color: red;")

    def on_show_column_info(self):
        """Display information about which columns are plotted for each cycle point."""
        info_text = """
<h2 style='color: #1f2937;'>P-h Diagram Column Mapping</h2>
<p style='color: #6b7280;'>This shows which Excel columns from Calculations-DDT.xlsx are used to plot each state point and cycle line in the P-h diagram.</p>

<hr>

<h3 style='color: #3b82f6;'>Pressure Levels (Horizontal Lines)</h3>
<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>
<tr style='background-color: #f3f4f6;'>
    <td><b>Pressure Level</b></td>
    <td><b>Excel Column</b></td>
    <td><b>Fallback (old name)</b></td>
</tr>
<tr>
    <td>Suction Pressure (Low)</td>
    <td><code>P_suction</code></td>
    <td><code>Press.suc</code></td>
</tr>
<tr>
    <td>Discharge Pressure (High)</td>
    <td><code>P_disch</code></td>
    <td><code>Press disch</code></td>
</tr>
</table>

<hr>

<h3 style='color: #16a34a;'>Common State Points (Black Dots)</h3>
<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>
<tr style='background-color: #f3f4f6;'>
    <td><b>Point</b></td>
    <td><b>Description</b></td>
    <td><b>Excel Column(s)</b></td>
    <td><b>Fallback (old)</b></td>
</tr>
<tr>
    <td><b>2b</b></td>
    <td>Compressor Inlet (Suction Line)</td>
    <td><code>T_2b</code> + <code>P_suction</code></td>
    <td><code>Comp.in</code></td>
</tr>
<tr>
    <td><b>3a</b></td>
    <td>Compressor Outlet (Discharge Line)</td>
    <td><code>T_3a</code> + <code>P_disch</code></td>
    <td><code>T comp outlet</code></td>
</tr>
<tr>
    <td><b>3b</b></td>
    <td>Condenser Inlet</td>
    <td><code>T_3b</code> + <code>P_disch</code></td>
    <td><code>T cond inlet</code></td>
</tr>
<tr>
    <td><b>4a</b></td>
    <td>Condenser Outlet (Subcooled)</td>
    <td><code>T_4a</code> + <code>P_disch</code></td>
    <td><code>T cond. Outlet</code></td>
</tr>
</table>

<hr>

<h3 style='color: #a855f7;'>Circuit-Specific Points (Colored Dots)</h3>
<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>
<tr style='background-color: #f3f4f6;'>
    <td><b>Point</b></td>
    <td><b>Description</b></td>
    <td><b>Excel Columns</b></td>
    <td><b>Circuits</b></td>
</tr>
<tr>
    <td><b>1</b></td>
    <td>Evaporator Inlet (TXV Outlet)</td>
    <td><code>h_4b_{circuit}</code> (isenthalpic) + <code>P_suction</code></td>
    <td>LH, CTR, RH</td>
</tr>
<tr>
    <td><b>2a</b></td>
    <td>Evaporator Outlet (TXV Bulb)</td>
    <td><code>H_coil lh</code>, <code>H_coil ctr</code>, <code>H_coil rh</code> + <code>P_suction</code></td>
    <td>LH, CTR, RH</td>
</tr>
<tr>
    <td><b>4b</b></td>
    <td>TXV Inlet (Subcooled Liquid)</td>
    <td><code>H_txv.lh</code>, <code>H_txv.ctr</code>, <code>H_txv.rh</code> + <code>P_disch</code></td>
    <td>LH, CTR, RH</td>
</tr>
</table>

<hr>

<h3 style='color: #ef4444;'>Cycle Paths (Lines Connecting Points)</h3>
<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>
<tr style='background-color: #f3f4f6;'>
    <td><b>Process</b></td>
    <td><b>Path</b></td>
    <td><b>Line Style</b></td>
    <td><b>Description</b></td>
</tr>
<tr>
    <td>Compression</td>
    <td>2b → 3a</td>
    <td>Solid Black (Heavy)</td>
    <td>Common to all circuits (single compressor)</td>
</tr>
<tr>
    <td>Condensation</td>
    <td>3a → 4b</td>
    <td>Solid Colored</td>
    <td>Per-circuit (high pressure side)</td>
</tr>
<tr>
    <td>Expansion</td>
    <td>4b → 1</td>
    <td>Solid Colored</td>
    <td>Per-circuit (TXV throttling)</td>
</tr>
<tr>
    <td>Evaporation</td>
    <td>1 → 2a</td>
    <td>Solid Colored</td>
    <td>Per-circuit (low pressure side)</td>
</tr>
<tr>
    <td>Mixing</td>
    <td>2a → 2b</td>
    <td>Dashed Colored</td>
    <td>Circuit convergence to common suction</td>
</tr>
</table>

<hr>

<h3 style='color: #f59e0b;'>Color Legend</h3>
<ul>
<li><b style='color: #3b82f6;'>■ Blue</b> - Left Hand Circuit (LH)</li>
<li><b style='color: #16a34a;'>■ Green</b> - Center Circuit (CTR)</li>
<li><b style='color: #a855f7;'>■ Purple</b> - Right Hand Circuit (RH)</li>
<li><b style='color: #111827;'>■ Black</b> - Common Points (shared by all circuits)</li>
</ul>

<hr>

<h3 style='color: #6b7280;'>Notes</h3>
<ul>
<li>All temperatures are converted from Fahrenheit to Kelvin before CoolProp calculations</li>
<li>Pressures are converted from PSIG to Pa for CoolProp, then to kPa for plotting</li>
<li>Enthalpies are calculated using CoolProp with T and P inputs</li>
<li>Point 1 uses isenthalpic expansion (h_1 = h_4b) per thermodynamic theory</li>
<li>Backward compatibility: Falls back to old column names if new names not found</li>
</ul>
"""

        # Create a message box with scrollable text
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("P-h Diagram Column Mapping")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(info_text)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setIcon(QMessageBox.Icon.Information)

        # Make the dialog larger to accommodate the table
        msg_box.setStyleSheet("QLabel{min-width: 700px; min-height: 500px;}")

        msg_box.exec()
