"""
Calculations Widget (REBUILT from goal.md Step 4)

Provides the new unified calculation tab with:
- QTreeWidget for hierarchical data display
- Custom NestedHeaderView for complex multi-level headers
- Integration with run_batch_processing() orchestrator
- Replaces old coolprop_calculator.py system entirely
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTreeWidget, QTreeWidgetItem, QHeaderView, QLabel,
                             QMessageBox, QApplication, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QFont, QColor
import pandas as pd
from input_dialog import InputDialog


class NestedHeaderView(QHeaderView):
    """
    Custom QHeaderView that draws nested headers based on Calculations-DDT.xlsx layout.

    Creates a two-row header structure:
    - Row 1: Group headers (e.g., "AT LH coil", "At compressor inlet")
    - Row 2: Column headers (e.g., "TXV out", "Coil in", "Density")
    """

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setStretchLastSection(True)

        # Define the nested header structure (Top Label, Column Span)
        # UPDATED to match Calculations-DDT.xlsx EXACTLY (54 columns total)
        self.groups = [
            ("AT LH coil", 8),      # Was 6, now 8 (added T_1a-lh, T_1b-lh)
            ("AT CTR coil", 8),     # Was 6, now 8 (added T_1a-ctr, T_1b-ctr)
            ("AT RH coil", 8),      # Was 6, now 8 (added T_1a-rh, T_1c-rh)
            ("At compressor inlet", 7),
            ("Comp outlet", 2),
            ("At Condenser", 7),    # Was 6, now 7 (added T_waterin)
            ("At TXV LH", 4),
            ("At TXV CTR", 4),
            ("At TXV RH", 4),
            ("TOTAL", 2)
        ]
        # Total: 8+8+8+7+2+7+4+4+4+2 = 54 columns

        # Define the sub-header labels matching EXACT Excel column names
        # This matches the output from calculate_row_performance()
        self.sub_headers = [
            # LH Coil (8 cols) - ADDED T_1a-lh, T_1b-lh
            "T_1a-lh", "T_1b-lh", "T_2a-LH", "T_sat.lh", "S.H_lh coil", "D_coil lh", "H_coil lh", "S_coil lh",
            # CTR Coil (8 cols) - ADDED T_1a-ctr, T_1b-ctr
            "T_1a-ctr", "T_1b-ctr", "T_2a-ctr", "T_sat.ctr", "S.H_ctr coil", "D_coil ctr", "H_coil ctr", "S_coil ctr",
            # RH Coil (8 cols) - ADDED T_1a-rh, T_1c-rh
            "T_1a-rh", "T_1c-rh", "T_2a-RH", "T_sat.rh", "S.H_rh coil", "D_coil rh", "H_coil rh", "S_coil rh",
            # Compressor Inlet (7 cols) - UPDATED to Excel names
            "P_suction", "T_2b", "T_sat.comp.in", "S.H_total", "D_comp.in", "H_comp.in", "S_comp.in",
            # Comp Outlet (2 cols) - UPDATED to Excel names
            "T_3a", "rpm",
            # Condenser (7 cols) - UPDATED to Excel names, ADDED T_waterin, T_waterout
            "T_3b", "P_disch", "T_4a", "T_sat.cond", "S.C", "T_waterin", "T_waterout",
            # TXV LH (4 cols) - UPDATED to Excel names
            "T_4b-lh", "T_sat.txv.lh", "S.C-txv.lh", "H_txv.lh",
            # TXV CTR (4 cols) - UPDATED to Excel names
            "T_4b-ctr", "T_sat.txv.ctr", "S.C-txv.ctr", "H_txv.ctr",
            # TXV RH (4 cols) - UPDATED to Excel names
            "T_4b-rh", "T_sat.txv.rh", "S.C-txv.rh", "H_txv.rh",
            # TOTAL (2 cols) - UPDATED to Excel names
            "m_dot", "qc"
        ]

        # Define the data keys (Row 3 from CSV - actual DataFrame column names)
        # This is the crucial link to the DataFrame returned by run_batch_processing
        self.data_keys = self.sub_headers  # They match in the new system

    def paintEvent(self, event):
        """Custom paint event to draw nested headers."""
        # Draw the base header (sub-headers)
        super().paintEvent(event)

        painter = QPainter(self)
        painter.save()

        # Set font for group headers
        font = self.font()
        font.setBold(True)
        painter.setFont(font)

        # Draw background for group header row
        painter.fillRect(0, 0, self.width(), self.height() // 2, QColor(240, 240, 240))

        col_index = 0
        for text, span in self.groups:
            if span == 0:
                continue

            # Get rectangle for this group
            first_col_rect = self.sectionViewportPosition(col_index)
            last_col_rect = self.sectionViewportPosition(col_index + span - 1)

            group_width = (last_col_rect + self.sectionSize(col_index + span - 1)) - first_col_rect
            group_rect = self.rect()
            group_rect.setLeft(first_col_rect)
            group_rect.setWidth(group_width)
            group_rect.setHeight(self.height() // 2)  # Top half

            # Draw border
            painter.setPen(QColor(100, 100, 100))
            painter.drawRect(group_rect.adjusted(0, 0, -1, -1))

            # Draw text
            painter.drawText(group_rect, Qt.AlignmentFlag.AlignCenter, text)

            col_index += span

        painter.restore()

    def sizeHint(self):
        """Double the height to make space for nested groups."""
        size = super().sizeHint()
        size.setHeight(size.height() * 2)
        return size


class CalculationsWidget(QWidget):
    """
    New unified Calculations tab widget.

    Replaces the old coolprop_calculator.py system with the new
    run_batch_processing() orchestrator.
    """

    # Signal emitted when processed data is ready for P-h diagram
    filtered_data_ready = pyqtSignal(object)

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.processed_df = None

        self.setup_ui()

    def setup_ui(self):
        """Create the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # ==================== Title & Control Panel ====================
        title_layout = QHBoxLayout()

        title = QLabel("Calculations")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_layout.addWidget(title)

        title_layout.addStretch()

        # Add "Enter Rated Inputs" button (Goal-2 Phase 3)
        self.enter_inputs_button = QPushButton("⚙️ Enter Rated Inputs")
        self.enter_inputs_button.setFont(QFont("Arial", 10))
        self.enter_inputs_button.setFixedWidth(180)
        self.enter_inputs_button.clicked.connect(self.open_input_dialog)
        self.enter_inputs_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        title_layout.addWidget(self.enter_inputs_button)

        self.run_button = QPushButton("▶️ Run Full Calculation")
        self.run_button.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.run_button.setFixedWidth(200)
        self.run_button.clicked.connect(self.run_calculation)
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        title_layout.addWidget(self.run_button)

        layout.addLayout(title_layout)

        # ==================== Status Label ====================
        self.status_label = QLabel("Ready. Click 'Run Full Calculation' to process data.")
        self.status_label.setStyleSheet("color: gray; font-size: 10pt;")
        layout.addWidget(self.status_label)

        # ==================== Tree Widget with Nested Headers ====================
        self.tree_widget = QTreeWidget()

        # Create and set custom header
        self.header = NestedHeaderView(self.tree_widget)
        self.tree_widget.setHeader(self.header)

        # Set the sub-header labels
        self.tree_widget.setHeaderLabels(self.header.sub_headers)

        # Configure tree appearance
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.setRootIsDecorated(False)  # No expand/collapse icons

        layout.addWidget(self.tree_widget, 1)  # Stretch factor 1

        # ==================== Export Panel ====================
        export_layout = QHBoxLayout()
        export_layout.addWidget(QLabel("Export Results:"))

        self.export_button = QPushButton("Export to CSV")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_to_csv)
        export_layout.addWidget(self.export_button)

        export_layout.addStretch()

        layout.addLayout(export_layout)

    def open_input_dialog(self):
        """
        Open the input dialog for entering rated performance inputs.

        This method:
        1. Creates an InputDialog instance
        2. Pre-fills it with existing rated_inputs from data_manager
        3. If user clicks OK, saves the new values
        4. Provides feedback to the user
        """
        dialog = InputDialog(self)

        # Pre-fill with existing values from data_manager
        dialog.set_data(self.data_manager.rated_inputs)

        # Show dialog and wait for user action
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # User clicked OK - get the data
            new_data = dialog.get_data()

            # Save to data_manager
            self.data_manager.rated_inputs = new_data

            # Provide feedback
            QMessageBox.information(
                self,
                "Inputs Saved",
                "Rated performance inputs have been saved successfully.\n\n"
                "You can now click 'Run Full Calculation' to process your data."
            )

            # Update status
            self.status_label.setText("✓ Rated inputs saved. Ready to run calculations.")
            self.status_label.setStyleSheet("color: green; font-size: 10pt;")

    def run_calculation(self):
        """Run the full batch calculation using the new unified engine."""

        # SOFT WARNING: Check for rated inputs (Goal-2C)
        # If missing, calculation will use default eta_vol (0.85) with warnings
        # This is the degradation strategy for missing rated inputs
        required_fields = [
            'rated_capacity_btu_hr',
            'rated_power_w',
            'm_dot_rated_lbhr',
            'hz_rated',
            'disp_ft3',
            'rated_evap_temp_f',
            'rated_return_gas_temp_f',
        ]

        rated_inputs = self.data_manager.rated_inputs
        missing_fields = []

        for field in required_fields:
            value = rated_inputs.get(field)
            if value is None or value == 0.0:
                missing_fields.append(field)

        if missing_fields:
            # Show user-friendly field names
            field_labels = {
                'rated_capacity_btu_hr': 'Rated Cooling Capacity',
                'rated_power_w': 'Rated Power',
                'm_dot_rated_lbhr': 'Rated Mass Flow Rate',
                'hz_rated': 'Rated Compressor Speed',
                'disp_ft3': 'Compressor Displacement',
                'rated_evap_temp_f': 'Rated Evaporator Temperature',
                'rated_return_gas_temp_f': 'Rated Return Gas Temperature',
            }

            missing_labels = [field_labels.get(f, f) for f in missing_fields]

            # SOFT WARNING - Allow user to continue
            reply = QMessageBox.question(
                self,
                "Incomplete Rated Inputs",
                "Some rated performance inputs are missing:\n\n" +
                "\n".join(f"• {label}" for label in missing_labels) +
                "\n\nCalculations will proceed using default values where needed.\n"
                "Results may be approximate.\n\n"
                "Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.No:
                return  # User chose to stop

        self.run_button.setText("Calculating...")
        self.run_button.setEnabled(False)
        self.status_label.setText("Processing...")
        self.status_label.setStyleSheet("color: blue; font-size: 10pt;")
        QApplication.processEvents()  # Allow UI to update

        try:
            # 1. Get filtered data from data manager
            input_df = self.data_manager.get_filtered_data()

            if input_df is None or input_df.empty:
                self.status_label.setText("❌ No data to process. Please load a CSV file.")
                self.status_label.setStyleSheet("color: red; font-size: 10pt;")
                QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
                return

            print(f"[CALCULATIONS] Starting calculation on {len(input_df)} rows...")

            # 2. Call the NEW orchestrator function (replaces coolprop_calculator.py)
            from calculation_orchestrator import run_batch_processing
            processed_df = run_batch_processing(self.data_manager, input_df)

            # 3. Check for errors
            if 'error' in processed_df.columns:
                error_msg = processed_df['error'].iloc[0] if len(processed_df) > 0 else "Unknown error"
                self.status_label.setText(f"❌ Error: {error_msg}")
                self.status_label.setStyleSheet("color: red; font-size: 10pt;")
                QMessageBox.critical(
                    self,
                    "Calculation Error",
                    f"An error occurred during calculation:\n\n{error_msg}\n\n"
                    "Please ensure:\n"
                    "1. Rated inputs are entered (click '⚙️ Enter Rated Inputs' button)\n"
                    "2. All required sensors are mapped in the Diagram tab"
                )
                return

            # 4. Store and display results
            self.processed_df = processed_df
            self.populate_tree(processed_df)

            # 5. Enable export
            self.export_button.setEnabled(True)

            # 6. Emit signal for P-h Diagram
            self.filtered_data_ready.emit(processed_df)

            # 7. Update status
            self.status_label.setText(f"✓ Calculation complete! Processed {len(processed_df)} rows.")
            self.status_label.setStyleSheet("color: green; font-size: 10pt;")

            print(f"[CALCULATIONS] Calculation complete! {len(processed_df)} rows processed.")

        except Exception as e:
            print(f"[CALCULATIONS] ERROR during calculation: {e}")
            import traceback
            traceback.print_exc()

            self.status_label.setText(f"❌ Error: {str(e)}")
            self.status_label.setStyleSheet("color: red; font-size: 10pt;")
            QMessageBox.critical(self, "Calculation Error", f"An error occurred:\n\n{str(e)}")

        finally:
            self.run_button.setText("Run Full Calculation")
            self.run_button.setEnabled(True)

    def populate_tree(self, df):
        """Populate the tree widget with calculated data."""
        self.tree_widget.clear()

        # Get the data keys from the header
        data_keys = self.header.data_keys

        items = []
        for index, row in df.iterrows():
            row_data = []
            for key in data_keys:
                val = row.get(key)
                if isinstance(val, (int, float)):
                    row_data.append(f"{val:.2f}")  # Format numbers
                else:
                    row_data.append(str(val) if val is not None else "---")

            item = QTreeWidgetItem(row_data)
            items.append(item)

        self.tree_widget.addTopLevelItems(items)

        # Resize columns after adding data
        for i in range(len(data_keys)):
            self.tree_widget.resizeColumnToContents(i)

        print(f"[CALCULATIONS] Populated tree with {len(items)} rows and {len(data_keys)} columns")

    def export_to_csv(self):
        """Export the processed data to CSV."""
        if self.processed_df is None or self.processed_df.empty:
            QMessageBox.warning(self, "No Data", "No data to export")
            return

        from PyQt6.QtWidgets import QFileDialog

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Calculated Data",
            "calculated_results.csv",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not filename:
            return  # User cancelled

        try:
            self.processed_df.to_csv(filename, index=False)
            QMessageBox.information(
                self,
                "Export Successful",
                f"Data exported successfully to:\n{filename}"
            )
            print(f"[CALCULATIONS] Exported {len(self.processed_df)} rows to {filename}")

        except Exception as e:
            print(f"[CALCULATIONS] ERROR during export: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")
