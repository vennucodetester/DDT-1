import csv
import pandas as pd
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
                             QFileDialog, QLineEdit, QFrame, QMessageBox, QScrollArea,
                             QDialog, QDialogButtonBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont
from mapping_dialog import MappingDialog


class ComparisonWidget(QWidget):
    """Widget for comparing base CSV with up to 2 other CSV files."""
    
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        
        # Store comparison data
        self.comparison_files = {
            1: {
                'file_path': None,
                'label': 'Comparison 1',
                'csv_data': None,
                'sensor_list': [],
                'sensor_mapping': {},  # base_sensor -> comparison_sensor
            },
            2: {
                'file_path': None,
                'label': 'Comparison 2',
                'csv_data': None,
                'sensor_list': [],
                'sensor_mapping': {},
            }
        }
        
        self.setupUi()
        
    def setupUi(self):
        """Set up the comparison UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Title and instructions
        title_label = QLabel("CSV Comparison View")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)
        
        instructions = QLabel(
            "Compare the base CSV (loaded in sensor panel) with up to 2 other CSV files. "
            "Values shown use the current aggregation method from the Diagram tab."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; padding: 5px;")
        main_layout.addWidget(instructions)
        
        # Load buttons layout
        buttons_layout = QHBoxLayout()
        
        self.load_comp1_btn = QPushButton("Load Comparison 1")
        self.load_comp1_btn.clicked.connect(lambda: self.load_comparison_csv(1))
        buttons_layout.addWidget(self.load_comp1_btn)
        
        self.load_comp2_btn = QPushButton("Load Comparison 2")
        self.load_comp2_btn.clicked.connect(lambda: self.load_comparison_csv(2))
        buttons_layout.addWidget(self.load_comp2_btn)
        
        self.clear_all_btn = QPushButton("Clear All Comparisons")
        self.clear_all_btn.clicked.connect(self.clear_all_comparisons)
        buttons_layout.addWidget(self.clear_all_btn)
        
        self.export_btn = QPushButton("Export Comparison")
        self.export_btn.clicked.connect(self.export_comparison)
        buttons_layout.addWidget(self.export_btn)
        
        buttons_layout.addStretch()
        main_layout.addLayout(buttons_layout)

        # Base search and group controls
        controls_layout = QHBoxLayout()
        self.base_search_input = QLineEdit()
        self.base_search_input.setPlaceholderText("Search base sensors...")
        self.base_search_input.textChanged.connect(self.on_search_changed)
        controls_layout.addWidget(QLabel("Filter:"))
        controls_layout.addWidget(self.base_search_input, 1)
        
        self.expand_all_btn = QPushButton("Expand All")
        self.expand_all_btn.clicked.connect(self.expand_all_groups)
        controls_layout.addWidget(self.expand_all_btn)
        
        self.collapse_all_btn = QPushButton("Collapse All")
        self.collapse_all_btn.clicked.connect(self.collapse_all_groups)
        controls_layout.addWidget(self.collapse_all_btn)
        
        main_layout.addLayout(controls_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)
        
        # Comparison table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        main_layout.addWidget(self.table)
        self.table.cellClicked.connect(self.on_table_cell_clicked)
        
        # Status label
        self.status_label = QLabel("Load a CSV file to begin comparison")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        main_layout.addWidget(self.status_label)
        
        # Internal state for grouping/collapse and search
        self.group_collapse_states = {}
        self.group_to_row_indexes = {}
        self.search_text = ""
        
    def filter_data_like_manager(self, df):
        """Apply the DataManager's current time-range filter to a comparison DataFrame if possible.
        Falls back to the original df on any error."""
        try:
            if df is None or df.empty:
                return df
            # If manager uses 'Timestamp' and the df has it, filter similarly
            if hasattr(self.data_manager, 'time_range') and 'Timestamp' in df.columns:
                # replicate get_filtered_data logic minimally
                if getattr(self.data_manager, 'time_range', 'All Data') == 'All Data':
                    return df
                if getattr(self.data_manager, 'time_range', '') == 'Custom' and hasattr(self.data_manager, 'custom_time_range'):
                    ctr = getattr(self.data_manager, 'custom_time_range', None)
                    if ctr and 'start' in ctr and 'end' in ctr:
                        f = df.copy()
                        f['Timestamp'] = pd.to_datetime(f['Timestamp'], errors='coerce')
                        start_time = pd.to_datetime(ctr['start'], errors='coerce')
                        end_time = pd.to_datetime(ctr['end'], errors='coerce')
                        return f[(f['Timestamp'] >= start_time) & (f['Timestamp'] <= end_time)]
                    return df
                # Hour-window ranges
                time_ranges = {
                    '1 Hour': 1,
                    '3 Hours': 3,
                    '8 Hours': 8,
                    '16 Hours': 16
                }
                hours = time_ranges.get(getattr(self.data_manager, 'time_range', 'All Data'))
                if hours is None:
                    return df
                f = df.copy()
                f['Timestamp'] = pd.to_datetime(f['Timestamp'], errors='coerce')
                last_ts = f['Timestamp'].max()
                cutoff = last_ts - pd.Timedelta(hours=hours)
                filtered = f[f['Timestamp'] >= cutoff]
                return filtered if not filtered.empty else df
            return df
        except Exception:
            return df
        
    def load_comparison_csv(self, slot_number):
        """Load a CSV file for comparison."""
        # Check if base CSV is loaded
        if self.data_manager.csv_data is None or len(self.data_manager.csv_data) == 0:
            QMessageBox.warning(
                self,
                "No Base CSV",
                "Please load a base CSV file in the sensor panel first."
            )
            return
        
        # Open file dialog
        file_name, _ = QFileDialog.getOpenFileName(
            self, 
            f"Open Comparison CSV {slot_number}", 
            "", 
            "CSV Files (*.csv)"
        )
        
        if not file_name:
            return
        
        # Ask for label
        label = self.get_comparison_label(slot_number)
        if label is None:  # User cancelled
            return
        
        # Load CSV data
        csv_data, sensor_list = self.parse_csv(file_name)
        if csv_data is None:
            return
        
        # Store basic info
        self.comparison_files[slot_number]['file_path'] = file_name
        self.comparison_files[slot_number]['label'] = label
        self.comparison_files[slot_number]['csv_data'] = csv_data
        self.comparison_files[slot_number]['sensor_list'] = sensor_list
        
        # Show mapping dialog
        base_sensors = self.data_manager.get_sensor_list()
        comparison_sensors = sensor_list
        
        # Show mapping dialog (similar to config vs CSV mapping)
        mapping_dialog = MappingDialog(
            orphaned_sensors=base_sensors,  # Base sensors on left
            new_sensors=comparison_sensors,  # Comparison sensors on right
            matched_sensors=[],
            parent=self
        )
        mapping_dialog.setWindowTitle(f"Map Base CSV to {label}")
        
        # Accept on any truthy exec() (PyQt6 returns int)
        if mapping_dialog.exec():
            # Get mappings: base_sensor -> comparison_sensor
            mappings = mapping_dialog.get_mappings()
            self.comparison_files[slot_number]['sensor_mapping'] = mappings
            
            # Update button text
            if slot_number == 1:
                self.load_comp1_btn.setText(f"Change Comparison 1: {label}")
            else:
                self.load_comp2_btn.setText(f"Change Comparison 2: {label}")
            
            # Update the comparison table
            self.update_comparison_table()
            
            self.status_label.setText(f"Loaded {label} successfully")
        else:
            # User cancelled mapping, clear the loaded data
            self.comparison_files[slot_number]['file_path'] = None
            self.comparison_files[slot_number]['csv_data'] = None
            self.comparison_files[slot_number]['sensor_list'] = []
            self.comparison_files[slot_number]['sensor_mapping'] = {}
    
    def get_comparison_label(self, slot_number):
        """Show dialog to get custom label for comparison."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Label Comparison {slot_number}")
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        label = QLabel("Enter a label for this comparison:")
        layout.addWidget(label)
        
        line_edit = QLineEdit()
        line_edit.setText(f"Comparison {slot_number}")
        line_edit.selectAll()
        layout.addWidget(line_edit)
        
        # Examples
        examples = QLabel("Examples: TXV Change test, TXV 2 Change test, After Repair, etc.")
        examples.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(examples)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return line_edit.text().strip() or f"Comparison {slot_number}"
        return None
    
    def parse_csv(self, file_path):
        """Parse CSV file and return data and sensor list (using pandas like data_manager)."""
        try:
            # Use pandas to read CSV, just like data_manager does
            csv_data = pd.read_csv(file_path)
            
            if csv_data.empty:
                QMessageBox.warning(
                    self,
                    "Invalid CSV",
                    "CSV file is empty or has no data rows."
                )
                return None, []
            
            # Get sensor list (all columns except the first one, which is DateTime)
            sensor_list = csv_data.columns.tolist()[1:]
            
            if len(sensor_list) == 0:
                QMessageBox.warning(
                    self,
                    "Invalid CSV",
                    "No sensor columns found in CSV file."
                )
                return None, []
            
            return csv_data, sensor_list
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading CSV",
                f"Failed to load CSV file:\n{str(e)}"
            )
            return None, []
    
    def update_comparison_table(self):
        """Update the comparison table with current data."""
        # Get base sensors in sensor panel order
        base_sensors = self.data_manager.get_sensor_list()
        
        if not base_sensors:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return
        
        # Determine columns: Base + loaded comparisons
        columns = ['Base CSV']
        active_comparisons = []
        
        for slot in [1, 2]:
            df = self.comparison_files[slot]['csv_data']
            if df is not None and not getattr(df, 'empty', False):
                columns.append(self.comparison_files[slot]['label'])
                active_comparisons.append(slot)
        
        # Build grouped row model based on DataManager groups and search filter
        row_model = self.build_row_model(base_sensors)

        # Set up table
        self.table.clear()
        self.table.setRowCount(len(row_model))
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # Get current aggregation method
        aggregation = self.data_manager.value_aggregation

        # Get filtered base data according to DataManager's current time range
        base_filtered = self.data_manager.get_filtered_data() if hasattr(self.data_manager, 'get_filtered_data') else self.data_manager.csv_data
        
        # Populate table
        self.group_to_row_indexes = {}
        current_row = 0
        for entry in row_model:
            if entry['type'] == 'group_header':
                group_name = entry['group']
                # Create a spanning header row
                header_item = QTableWidgetItem(f"{group_name}")
                header_item.setFlags(header_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                header_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                font = header_item.font()
                font.setBold(True)
                header_item.setFont(font)
                header_item.setBackground(QBrush(QColor(230, 230, 230)))
                header_item.setData(Qt.ItemDataRole.UserRole, {'is_group': True, 'group': group_name})
                self.table.setItem(current_row, 0, header_item)
                # Span across all comparison columns
                if self.table.columnCount() > 1:
                    self.table.setSpan(current_row, 0, 1, self.table.columnCount())
                self.table.setRowHeight(current_row, 28)
                current_row += 1
                continue

            # Sensor row
            base_sensor = entry['sensor']
            group_name = entry['group']
            # Track rows per group for collapse/expand
            self.group_to_row_indexes.setdefault(group_name, []).append(current_row)
            # Base CSV value
            base_value = self.get_aggregated_value_from_data(
                base_filtered,
                base_sensor,
                aggregation
            )
            
            # Create base cell
            base_item = QTableWidgetItem(f"{base_sensor}\n{base_value}")
            base_item.setFlags(base_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            base_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Style base column
            base_item.setBackground(QBrush(QColor(230, 240, 255)))
            font = base_item.font()
            font.setBold(True)
            base_item.setFont(font)
            
            self.table.setItem(current_row, 0, base_item)
            
            # Comparison values
            for col_idx, slot in enumerate(active_comparisons, start=1):
                comp_data = self.comparison_files[slot]
                mapping = comp_data['sensor_mapping']
                
                # Find mapped sensor
                comparison_sensor = mapping.get(base_sensor)
                
                if comparison_sensor:
                    comp_value = self.get_aggregated_value_from_data(
                        self.filter_data_like_manager(comp_data['csv_data']),
                        comparison_sensor,
                        aggregation
                    )
                    
                    # Calculate difference
                    try:
                        base_val_float = float(base_value.split()[0])
                        comp_val_float = float(comp_value.split()[0])
                        diff = comp_val_float - base_val_float
                        diff_str = f"({diff:+.2f})"
                        
                        # Color code based on difference
                        comp_item = QTableWidgetItem(
                            f"{comparison_sensor}\n{comp_value}\n{diff_str}"
                        )
                        
                        if abs(diff) < 0.01:
                            comp_item.setBackground(QBrush(QColor(240, 255, 240)))  # Light green
                        elif abs(diff) < 1.0:
                            comp_item.setBackground(QBrush(QColor(255, 255, 230)))  # Light yellow
                        else:
                            comp_item.setBackground(QBrush(QColor(255, 240, 240)))  # Light red
                    except:
                        comp_item = QTableWidgetItem(
                            f"{comparison_sensor}\n{comp_value}"
                        )
                        comp_item.setBackground(QBrush(QColor(250, 250, 250)))
                else:
                    comp_item = QTableWidgetItem("Not Mapped")
                    comp_item.setBackground(QBrush(QColor(220, 220, 220)))
                    comp_item.setForeground(QBrush(QColor(150, 150, 150)))
                
                comp_item.setFlags(comp_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                comp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(current_row, col_idx, comp_item)

            # Apply collapsed state visibility
            if self.group_collapse_states.get(group_name, False):
                self.table.setRowHidden(current_row, True)

            current_row += 1
        
        # Adjust column widths
        header = self.table.horizontalHeader()
        for i in range(len(columns)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        
        # Adjust row heights
        # Set a reasonable default height for sensor rows (group headers already set)
        for r in range(self.table.rowCount()):
            if self.table.rowSpan(r, 0) <= 1:  # not a spanning group header
                self.table.setRowHeight(r, 80)

    def build_row_model(self, base_sensors):
        """Constructs a list of rows including group headers and sensor rows, respecting search filter.
        Returns a list of dicts: {type:'group_header', group:name} or {type:'sensor', sensor:name, group:name}
        """
        # Determine groups
        groups = self.data_manager.sensor_groups or {}
        base_set = set(base_sensors)
        # Build ungrouped list
        grouped_sensors = set()
        for _, members in groups.items():
            for s in members:
                if s in base_set:
                    grouped_sensors.add(s)
        ungrouped = [s for s in base_sensors if s not in grouped_sensors]

        # Preserve base order within each group
        def order_sensors_for_group(member_list):
            member_set = set(member_list)
            return [s for s in base_sensors if s in member_set]

        # Apply search filter function
        st = (self.search_text or '').strip().lower()
        def matches(s):
            return (not st) or (st in s.lower())

        row_model = []
        # Iterate groups in insertion order
        for group_name, members in groups.items():
            ordered = order_sensors_for_group(members)
            # Filter sensors
            filtered = [s for s in ordered if matches(s)]
            if not filtered:
                continue
            row_model.append({'type': 'group_header', 'group': group_name})
            for s in filtered:
                row_model.append({'type': 'sensor', 'sensor': s, 'group': group_name})

        # Add ungrouped at end
        if ungrouped:
            filtered_ug = [s for s in ungrouped if matches(s)]
            if filtered_ug:
                row_model.append({'type': 'group_header', 'group': 'Ungrouped'})
                for s in filtered_ug:
                    row_model.append({'type': 'sensor', 'sensor': s, 'group': 'Ungrouped'})

        # If no groups at all and no search, make a flat list under a single header
        if not row_model and base_sensors:
            flat = [s for s in base_sensors if matches(s)]
            if flat:
                row_model.append({'type': 'group_header', 'group': 'Sensors'})
                for s in flat:
                    row_model.append({'type': 'sensor', 'sensor': s, 'group': 'Sensors'})
        return row_model

    def on_table_cell_clicked(self, row, column):
        """Toggle group collapse when a header row is clicked."""
        item = self.table.item(row, 0)
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return
        if data.get('is_group'):
            group = data.get('group')
            current = self.group_collapse_states.get(group, False)
            self.group_collapse_states[group] = not current
            # Show or hide rows for this group
            for r in self.group_to_row_indexes.get(group, []):
                self.table.setRowHidden(r, not current)  # inverse because we just toggled

    def expand_all_groups(self):
        self.group_collapse_states = {g: False for g in self.group_to_row_indexes.keys()}
        for rows in self.group_to_row_indexes.values():
            for r in rows:
                self.table.setRowHidden(r, False)

    def collapse_all_groups(self):
        self.group_collapse_states = {g: True for g in self.group_to_row_indexes.keys()}
        for rows in self.group_to_row_indexes.values():
            for r in rows:
                self.table.setRowHidden(r, True)

    def on_search_changed(self, text):
        self.search_text = text
        self.update_comparison_table()
    
    def get_aggregated_value_from_data(self, csv_data, sensor_name, aggregation):
        """Get aggregated value for a sensor from CSV data (pandas DataFrame)."""
        if csv_data is None or csv_data.empty:
            return "N/A"
        
        # Check if sensor exists in the DataFrame
        if sensor_name not in csv_data.columns:
            return "N/A"
        
        # Get the sensor column, dropping NaN values
        sensor_series = csv_data[sensor_name].dropna()
        
        if len(sensor_series) == 0:
            return "N/A"
        
        # Apply aggregation - normalize manager's labels (Average/Maximum/Minimum)
        try:
            agg = (aggregation or '').strip().lower()
            if agg in ('avg', 'mean', 'average'):
                result = sensor_series.mean()
            elif agg in ('min', 'minimum'):
                result = sensor_series.min()
            elif agg in ('max', 'maximum'):
                result = sensor_series.max()
            elif agg in ('last', 'latest'):
                result = sensor_series.iloc[-1]
            else:
                # Fallback to the DataManager's semantics if it's one of those strings
                dm_agg = getattr(self.data_manager, 'value_aggregation', 'Average')
                dm_agg_l = (dm_agg or '').strip().lower()
                if dm_agg_l in ('maximum', 'max'):
                    result = sensor_series.max()
                elif dm_agg_l in ('minimum', 'min'):
                    result = sensor_series.min()
                else:
                    result = sensor_series.mean()
            
            return f"{result:.2f}"
        except Exception as e:
            return "N/A"
    
    def clear_all_comparisons(self):
        """Clear all comparison data."""
        reply = QMessageBox.question(
            self,
            "Clear All Comparisons",
            "Are you sure you want to clear all comparison data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for slot in [1, 2]:
                self.comparison_files[slot] = {
                    'file_path': None,
                    'label': f'Comparison {slot}',
                    'csv_data': None,
                    'sensor_list': [],
                    'sensor_mapping': {},
                }
            
            self.load_comp1_btn.setText("Load Comparison 1")
            self.load_comp2_btn.setText("Load Comparison 2")
            
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.status_label.setText("All comparisons cleared")
    
    def export_comparison(self):
        """Export comparison data to CSV."""
        if not self.comparison_files[1]['csv_data'] and not self.comparison_files[2]['csv_data']:
            QMessageBox.warning(
                self,
                "No Comparison Data",
                "Please load at least one comparison CSV first."
            )
            return
        
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export Comparison",
            "",
            "CSV Files (*.csv)"
        )
        
        if not file_name:
            return
        
        try:
            base_sensors = self.data_manager.get_sensor_list()
            aggregation = self.data_manager.value_aggregation
            
            with open(file_name, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                header = ['Base Sensor', 'Base Value']
                for slot in [1, 2]:
                    if self.comparison_files[slot]['csv_data']:
                        label = self.comparison_files[slot]['label']
                        header.extend([f'{label} Sensor', f'{label} Value', f'{label} Difference'])
                
                writer.writerow(header)
                
                # Write data
                for base_sensor in base_sensors:
                    row = [base_sensor]
                    
                    # Base value
                    base_value = self.get_aggregated_value_from_data(
                        self.data_manager.csv_data,
                        base_sensor,
                        aggregation
                    )
                    row.append(base_value)
                    
                    # Comparison values
                    for slot in [1, 2]:
                        if self.comparison_files[slot]['csv_data']:
                            comp_data = self.comparison_files[slot]
                            mapping = comp_data['sensor_mapping']
                            comparison_sensor = mapping.get(base_sensor, '')
                            
                            if comparison_sensor:
                                comp_value = self.get_aggregated_value_from_data(
                                    comp_data['csv_data'],
                                    comparison_sensor,
                                    aggregation
                                )
                                
                                # Calculate difference
                                try:
                                    base_val_float = float(base_value)
                                    comp_val_float = float(comp_value)
                                    diff = comp_val_float - base_val_float
                                    row.extend([comparison_sensor, comp_value, f"{diff:.2f}"])
                                except:
                                    row.extend([comparison_sensor, comp_value, 'N/A'])
                            else:
                                row.extend(['', '', ''])
                
                    writer.writerow(row)
            
            QMessageBox.information(
                self,
                "Export Successful",
                f"Comparison exported to:\n{file_name}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export comparison:\n{str(e)}"
            )
    
    def update_ui(self):
        """Update UI when data changes."""
        # Always refresh; at minimum show the Base CSV column in current order
        self.update_comparison_table()

