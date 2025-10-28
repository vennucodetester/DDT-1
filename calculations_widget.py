"""
Calculations Widget
Provides pressure threshold filtering, thermodynamic calculations, and data export functionality.
Uses CoolProp to calculate state point properties and system performance metrics.
This widget operates independently from the Graph tab filtering.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QDoubleSpinBox, QTableWidget, 
                             QTableWidgetItem, QFileDialog, QMessageBox,
                             QHeaderView, QSpinBox, QComboBox, QApplication)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import pandas as pd
from coolprop_calculator import ThermodynamicCalculator, get_calculation_output_columns


class CalculationsWidget(QWidget):
    """
    Widget for pressure threshold-based data filtering and CSV export.
    Independent from Graph tab filtering.
    """
    
    # Signal emitted when filtered data is ready
    filtered_data_ready = pyqtSignal(object, object)  # (filtered_df, circuit_data)
    
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.threshold_data = None
        self.calculated_data = None
        self.calculator = ThermodynamicCalculator()
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        """Create the UI layout and components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # ==================== Control Panel ====================
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)
        
        # ==================== Data Display Table ====================
        self.table = QTableWidget()
        self.table.setColumnCount(0)  # Will be set when data is loaded
        self.table.setRowCount(0)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setMaximumHeight(500)
        main_layout.addWidget(QLabel("Filtered Data:"), 0)
        main_layout.addWidget(self.table, 1)
        
        # ==================== P-h Diagram Summary Statistics Table ====================
        summary_title_layout = QHBoxLayout()
        summary_title_layout.setContentsMargins(0, 0, 0, 0)
        summary_title_layout.setSpacing(10)
        summary_title_layout.addWidget(QLabel("P-h Diagram State Points (Average Values):"))
        
        self.copy_summary_button = QPushButton("📋 Copy Summary Table")
        self.copy_summary_button.setFixedWidth(180)
        summary_title_layout.addWidget(self.copy_summary_button)
        summary_title_layout.addStretch()
        
        main_layout.addLayout(summary_title_layout)
        
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(3)
        self.summary_table.setHorizontalHeaderLabels(['State Point', 'Description', 'Average Value'])
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.summary_table.setMaximumHeight(400)
        # Enable selection and copy
        self.summary_table.setSelectionBehavior(self.summary_table.SelectionBehavior.SelectRows)
        self.summary_table.setSelectionMode(self.summary_table.SelectionMode.MultiSelection)
        main_layout.addWidget(self.summary_table, 0)
        
        # ==================== Statistics Panel ====================
        stats_panel = self._create_stats_panel()
        main_layout.addWidget(stats_panel)
        
        # ==================== Export Panel ====================
        export_panel = self._create_export_panel()
        main_layout.addWidget(export_panel)
        
        # ==================== Spacer ====================
        main_layout.addStretch()
    
    def _create_control_panel(self):
        """Create the top control panel with threshold input."""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("Pressure Threshold Filtering & Thermodynamic Calculations")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title.setFont(title_font)
        layout.addWidget(title)
        
        layout.addSpacing(20)
        
        # Threshold input label
        layout.addWidget(QLabel("Threshold (PSI):"))
        
        # Threshold input spinbox
        self.threshold_spinbox = QDoubleSpinBox()
        self.threshold_spinbox.setMinimum(0.0)
        self.threshold_spinbox.setMaximum(500.0)
        self.threshold_spinbox.setValue(40.0)  # Default threshold for R290
        self.threshold_spinbox.setSingleStep(1.0)
        self.threshold_spinbox.setDecimals(1)
        self.threshold_spinbox.setFixedWidth(100)
        layout.addWidget(self.threshold_spinbox)
        
        # Filter button
        self.filter_button = QPushButton("Filter & Calculate")
        self.filter_button.setFixedWidth(140)
        layout.addWidget(self.filter_button)
        
        # Status label
        self.filter_status_label = QLabel("Ready")
        self.filter_status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.filter_status_label)
        
        layout.addStretch()
        
        return panel
        

    
    def _create_stats_panel(self):
        """Create statistics display panel."""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        
        # Total rows label
        self.total_rows_label = QLabel("Total Rows: -")
        layout.addWidget(self.total_rows_label)
        
        # Filtered rows label
        self.filtered_rows_label = QLabel("Filtered Rows: -")
        layout.addWidget(self.filtered_rows_label)
        
        # Percentage label
        self.percentage_label = QLabel("Percentage: -")
        layout.addWidget(self.percentage_label)
        
        layout.addStretch()
        
        return panel
    
    def _create_export_panel(self):
        """Create export panel."""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        layout.addWidget(QLabel("Export Filtered Data:"))
        
        self.export_button = QPushButton("Export to CSV")
        self.export_button.setFixedWidth(150)
        self.export_button.setEnabled(False)  # Disabled until data is filtered
        layout.addWidget(self.export_button)
        
        self.export_status_label = QLabel("(No data to export)")
        self.export_status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.export_status_label)
        
        layout.addStretch()
        
        return panel
    
    def connect_signals(self):
        """Connect UI signals to slot functions."""
        self.filter_button.clicked.connect(self.on_filter_clicked)
        self.export_button.clicked.connect(self.on_export_clicked)
        self.copy_summary_button.clicked.connect(self.on_copy_summary_clicked)
    
    def on_filter_clicked(self):
        """Handle filter button click - filters and calculates thermodynamic properties."""
        if self.data_manager.csv_data is None:
            self.filter_status_label.setText("❌ No CSV data loaded")
            self.filter_status_label.setStyleSheet("color: red;")
            QMessageBox.warning(self, "No Data", "Please load a CSV file first")
            return
        
        threshold = self.threshold_spinbox.value()
        print(f"[CALCULATIONS] Filtering with threshold: {threshold} PSI")
        
        try:
            # Call DataManager's filtering method
            filtered_data = self.data_manager.filter_by_pressure_threshold(threshold)
            
            if filtered_data is None or filtered_data.empty:
                self.filter_status_label.setText("⚠️ No data matches threshold")
                self.filter_status_label.setStyleSheet("color: orange;")
                self.threshold_data = None
                self.calculated_data = None
                self.export_button.setEnabled(False)
                self.export_status_label.setText("(No data to export)")
                return
            
            # Store the filtered data
            self.threshold_data = filtered_data
            
            # Update status
            self.filter_status_label.setText(f"✓ Calculating thermodynamic properties...")
            self.filter_status_label.setStyleSheet("color: blue;")
            
            # Calculate thermodynamic properties
            print(f"[CALCULATIONS] Processing {len(filtered_data)} rows with CoolProp...")
            self.calculated_data = self.calculator.process_dataframe(filtered_data)
            
            # Update UI
            self.filter_status_label.setText(f"✓ Filtered & calculated successfully")
            self.filter_status_label.setStyleSheet("color: green;")
            
            # Display the data (inputs + outputs in one continuous table)
            self.display_filtered_data()
            
            # Enable export button
            self.export_button.setEnabled(True)
            self.export_status_label.setText("Ready to export")
            self.export_status_label.setStyleSheet("color: gray;")
            
        except Exception as e:
            print(f"[CALCULATIONS] ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.filter_status_label.setText(f"❌ Error: {str(e)}")
            self.filter_status_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Filtering Error", f"An error occurred:\n{str(e)}")
    
    def display_filtered_data(self):
        """Display filtered data with inputs and outputs in one continuous table."""
        if self.threshold_data is None or self.threshold_data.empty:
            self.table.setColumnCount(0)
            self.table.setRowCount(0)
            return
        
        # Start with the full calculated data which has both inputs and outputs
        df = self.calculated_data if self.calculated_data is not None else self.threshold_data
        
        # Define input columns in desired order
        input_columns = [
            'Timestamp',
            # Pressures
            'Liquid Pressure ',
            'Suction Presure ',
            # Refrigerant temperatures
            'Right TXV Bulb ',
            'CTR TXV Bulb',
            'Left TXV Bulb',
            'Suction line into Comp',
            'Discharge line from comp',
            'Ref Temp in HeatX',
            'Ref Temp out HeatX',
            'Left TXV Inlet',
            'CTR TXV Inlet',
            'Right TXV Inlet ',
            # Water temperatures
            'Water in HeatX',
            'Water out HeatX',
            # Air inlet temperatures
            'Air in left evap 6 in LE',
            'Air in left evap 6 in RE',
            'Air in ctr evap 6 in LE',
            'Air in ctr evap 6 in RE',
            'Air in right evap 6 in LE',
            'Air in right evap 6 in RE',
            # Air outlet temperatures
            'Air off left evap 6 in LE',
            'Air off left evap 6 in RE',
            'Air off ctr evap 6 in LE',
            'Air off ctr evap 6 in RE',
            'Air off right evap 6 in LE',
            'Air off right evap 6 in RE',
            # Other
            'Compressor RPM'
        ]
        
        # Get output columns from calculator
        output_columns = get_calculation_output_columns()
        
        # Build combined column list: inputs first, then outputs
        all_columns = []
        
        # Add input columns that exist in data
        for col in input_columns:
            if col in df.columns:
                all_columns.append(col)
        
        # Add output columns that exist in data
        for col in output_columns:
            if col in df.columns:
                all_columns.append(col)
        
        if not all_columns:
            print(f"[CALCULATIONS] No columns found in data")
            self.table.setColumnCount(0)
            self.table.setRowCount(0)
            return
        
        # Create subset dataframe with combined columns
        display_df = df[all_columns].copy()
        
        # Set up table structure
        self.table.setColumnCount(len(all_columns))
        self.table.setHorizontalHeaderLabels(all_columns)
        self.table.setRowCount(len(display_df))
        
        # Populate table with data
        for row_idx, (_, row_data) in enumerate(display_df.iterrows()):
            for col_idx, (col_name, value) in enumerate(zip(all_columns, row_data)):
                # Format the value based on column type
                if col_name == 'Timestamp':
                    formatted_value = str(value)
                elif col_name == 'Compressor RPM':
                    formatted_value = f"{value:.0f}" if isinstance(value, float) else str(value)
                elif isinstance(value, float):
                    # Check if this is an input or output column
                    if col_name in input_columns:
                        formatted_value = f"{value:.2f}"  # Input temps/pressures with 2 decimals
                    else:
                        formatted_value = f"{value:.4f}"  # Output values with 4 decimals
                else:
                    formatted_value = str(value)
                
                item = QTableWidgetItem(formatted_value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Read-only
                self.table.setItem(row_idx, col_idx, item)
        
        # Update statistics
        total_rows = len(self.data_manager.csv_data)
        filtered_rows = len(display_df)
        percentage = (filtered_rows / total_rows * 100) if total_rows > 0 else 0
        
        self.total_rows_label.setText(f"Total Rows: {total_rows}")
        self.filtered_rows_label.setText(f"Filtered Rows: {filtered_rows}")
        self.percentage_label.setText(f"Percentage: {percentage:.1f}%")
        
        # Emit signal for P-h diagram widget to consume this data
        # Skip the units row (first row added by calculator) when emitting to diagram
        diagram_data = display_df.iloc[1:].reset_index(drop=True) if len(display_df) > 0 else display_df
        self.filtered_data_ready.emit(diagram_data, None)
        
        print(f"[CALCULATIONS] Displayed {filtered_rows} rows with {len(all_columns)} columns (inputs + outputs)")
        
        # Populate summary table with P-h diagram state points
        self.populate_summary_table(df)
    
    def populate_summary_table(self, df):
        """Populate the summary table with P-h diagram state point averages."""
        if df.empty:
            self.summary_table.setRowCount(0)
            return
        
        # Define all P-h diagram state points with descriptions
        state_points = [
            # Common state points
            ('h_2a', 'State 2a: Enthalpy (TXV Bulb, Low Pressure) [kJ/kg]'),
            ('s_2a', 'State 2a: Entropy (TXV Bulb) [kJ/(kg·K)]'),
            ('h_2b', 'State 2b: Enthalpy (Suction Line, Superheated) [kJ/kg]'),
            ('s_2b', 'State 2b: Entropy (Suction Line) [kJ/(kg·K)]'),
            ('h_3a', 'State 3a: Enthalpy (Discharge Line, Superheated) [kJ/kg]'),
            ('s_3a', 'State 3a: Entropy (Discharge Line) [kJ/(kg·K)]'),
            ('h_3b', 'State 3b: Enthalpy (Condenser Inlet, Gas) [kJ/kg]'),
            ('s_3b', 'State 3b: Entropy (Condenser Inlet) [kJ/(kg·K)]'),
            ('h_4a', 'State 4a: Enthalpy (Condenser Outlet, Subcooled) [kJ/kg]'),
            ('s_4a', 'State 4a: Entropy (Condenser Outlet) [kJ/(kg·K)]'),
            ('h_4b', 'State 4b: Enthalpy (TXV Inlet, Subcooled) [kJ/kg]'),
            ('s_4b', 'State 4b: Entropy (TXV Inlet) [kJ/(kg·K)]'),
            # Pressures
            ('P_suc', 'Suction Pressure (Low Side) [Pa]'),
            ('P_cond', 'Condenser Pressure (High Side) [Pa]'),
            # Circuit-specific state points (4b)
            ('h_4b_LH', 'State 4b LH Circuit: Enthalpy (Left Hand) [kJ/kg]'),
            ('h_4b_CTR', 'State 4b CTR Circuit: Enthalpy (Center) [kJ/kg]'),
            ('h_4b_RH', 'State 4b RH Circuit: Enthalpy (Right Hand) [kJ/kg]'),
            ('s_4b_LH', 'State 4b LH Circuit: Entropy (Left Hand) [kJ/(kg·K)]'),
            ('s_4b_CTR', 'State 4b CTR Circuit: Entropy (Center) [kJ/(kg·K)]'),
            ('s_4b_RH', 'State 4b RH Circuit: Entropy (Right Hand) [kJ/(kg·K)]'),
            # Circuit-specific state points (1 - TXV outlet)
            ('h_1_LH', 'State 1 LH Circuit: Enthalpy (Evap Inlet, TXV Exit) [kJ/kg]'),
            ('h_1_CTR', 'State 1 CTR Circuit: Enthalpy (Evap Inlet, TXV Exit) [kJ/kg]'),
            ('h_1_RH', 'State 1 RH Circuit: Enthalpy (Evap Inlet, TXV Exit) [kJ/kg]'),
            # Circuit-specific state points (2a)
            ('h_2a_LH', 'State 2a LH Circuit: Enthalpy (Left Hand, Evap Outlet) [kJ/kg]'),
            ('h_2a_CTR', 'State 2a CTR Circuit: Enthalpy (Center, Evap Outlet) [kJ/kg]'),
            ('h_2a_RH', 'State 2a RH Circuit: Enthalpy (Right Hand, Evap Outlet) [kJ/kg]'),
            ('s_2a_LH', 'State 2a LH Circuit: Entropy (Left Hand) [kJ/(kg·K)]'),
            ('s_2a_CTR', 'State 2a CTR Circuit: Entropy (Center) [kJ/(kg·K)]'),
            ('s_2a_RH', 'State 2a RH Circuit: Entropy (Right Hand) [kJ/(kg·K)]'),
        ]
        
        # Filter to only include state points that exist in the dataframe
        existing_points = [(col, desc) for col, desc in state_points if col in df.columns]
        
        # Set up table structure
        self.summary_table.setRowCount(len(existing_points))
        
        # Populate table with averages
        for row_idx, (col_name, description) in enumerate(existing_points):
            # Column 0: State Point (e.g., "h_2a")
            item_col_name = QTableWidgetItem(col_name)
            item_col_name.setFlags(item_col_name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.summary_table.setItem(row_idx, 0, item_col_name)
            
            # Column 1: Description
            item_description = QTableWidgetItem(description)
            item_description.setFlags(item_description.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.summary_table.setItem(row_idx, 1, item_description)
            
            # Column 2: Average Value
            values = pd.to_numeric(df[col_name], errors='coerce').dropna()
            if len(values) > 0:
                avg_value = values.mean()
                formatted_avg = f"{avg_value:.4f}"
            else:
                formatted_avg = "N/A"
            
            item_avg = QTableWidgetItem(formatted_avg)
            item_avg.setFlags(item_avg.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.summary_table.setItem(row_idx, 2, item_avg)
        
        print(f"[CALCULATIONS] Populated summary table with {len(existing_points)} P-h diagram state points")

    
    def on_export_clicked(self):
        """Handle export button click (Phase 4 task)."""
        if self.calculated_data is None or self.calculated_data.empty:
            QMessageBox.warning(self, "No Data", "No filtered data to export")
            return
        
        # Open file save dialog
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Filtered Data",
            "filtered_data.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filename:
            return  # User cancelled
        
        try:
            # Export to CSV
            self.calculated_data.to_csv(filename, index=False)
            
            # Update status
            self.export_status_label.setText(f"✓ Exported to {filename}")
            self.export_status_label.setStyleSheet("color: green;")
            
            print(f"[CALCULATIONS] Exported {len(self.calculated_data)} rows to {filename}")
            QMessageBox.information(self, "Export Successful", 
                                  f"Data exported successfully to:\n{filename}")
        
        except Exception as e:
            print(f"[CALCULATIONS] ERROR during export: {e}")
            self.export_status_label.setText(f"❌ Export failed")
            self.export_status_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")
    
    def on_copy_summary_clicked(self):
        """Copy summary table contents to clipboard as tab-separated values."""
        if self.summary_table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "Summary table is empty. Filter data first.")
            return
        
        try:
            # Build tab-separated table content
            lines = []
            
            # Add header
            header = []
            for col in range(self.summary_table.columnCount()):
                header_item = self.summary_table.horizontalHeaderItem(col)
                if header_item:
                    header.append(header_item.text())
            lines.append('\t'.join(header))
            
            # Add data rows
            for row in range(self.summary_table.rowCount()):
                row_data = []
                for col in range(self.summary_table.columnCount()):
                    item = self.summary_table.item(row, col)
                    if item:
                        row_data.append(item.text())
                    else:
                        row_data.append('')
                lines.append('\t'.join(row_data))
            
            # Copy to clipboard
            clipboard_text = '\n'.join(lines)
            clipboard = QApplication.clipboard()
            clipboard.setText(clipboard_text)
            
            QMessageBox.information(self, "Copied", 
                                  f"Summary table ({self.summary_table.rowCount()} rows) copied to clipboard.\n\n"
                                  f"You can now paste it into Excel, Word, or any other application using Ctrl+V")
            
            print(f"[CALCULATIONS] Copied {self.summary_table.rowCount()} rows from summary table to clipboard")
            
        except Exception as e:
            print(f"[CALCULATIONS] ERROR copying summary table: {e}")
            QMessageBox.critical(self, "Copy Error", f"Failed to copy:\n{str(e)}")
