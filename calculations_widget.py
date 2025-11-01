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
                             QMessageBox, QApplication, QDialog, QTableWidget,
                             QTableWidgetItem, QMenu, QTextEdit, QDialogButtonBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QFont, QColor, QClipboard, QAction
import pandas as pd
from input_dialog import InputDialog
import math
from calculation_orchestrator import REQUIRED_SENSOR_ROLES, _find_sensor_for_role
from port_resolver import resolve_mapped_sensor


class NestedHeaderView(QHeaderView):
    """
    Custom QHeaderView that draws 4-ROW nested headers matching Calculations-DDT.xlsx layout.

    Creates a FOUR-row header structure:
    - Row 1: Main section headers (e.g., "AT LH coil", "At compressor inlet")
    - Row 2: Sub-section headers (e.g., "TXV out", "Coil out", "Density")
    - Row 3: Units (e.g., "°F", "kg/m³", "kJ/kg")
    - Row 4: Actual column names (e.g., "T_1a-lh", "D_coil lh")
    """

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setStretchLastSection(True)

        # Row 1: Main section headers (Top Label, Column Span)
        self.main_sections = [
            ("AT LH coil", 8),
            ("AT CTR coil", 8),
            ("AT RH coil", 8),
            ("At compressor inlet", 7),
            ("Comp outlet", 2),
            ("At Condenser", 7),
            ("At TXV LH", 4),
            ("At TXV CTR", 4),
            ("At TXV RH", 4),
            ("TOTAL", 2)
        ]
        # Total: 8+8+8+7+2+7+4+4+4+2 = 54 columns

        # Row 2: Sub-section headers (descriptive labels for groups of columns)
        self.sub_sections = [
            # AT LH coil (8)
            "TXV out", "TXV out", "Coil out", "T sat", "Superheat", "Density", "Enthalpy", "Entropy",
            # AT CTR coil (8)
            "TXV out", "TXV out", "Coil out", "T sat", "Superheat", "Density", "Enthalpy", "Entropy",
            # AT RH coil (8)
            "TXV out", "TXV out", "Coil out", "T sat", "Superheat", "Density", "Enthalpy", "Entropy",
            # At compressor inlet (7)
            "Pressure", "Temp", "T sat", "Superheat", "Density", "Enthalpy", "Entropy",
            # Comp outlet (2)
            "Temp", "RPM",
            # At Condenser (7)
            "Inlet", "Pressure", "Outlet", "T sat", "Subcool", "Water in", "Water out",
            # At TXV LH (4)
            "Temp", "T sat", "Subcool", "Enthalpy",
            # At TXV CTR (4)
            "Temp", "T sat", "Subcool", "Enthalpy",
            # At TXV RH (4)
            "Temp", "T sat", "Subcool", "Enthalpy",
            # TOTAL (2)
            "Mass flow", "Capacity"
        ]

        # Row 3: Units for each column
        self.units = [
            # LH Coil (8)
            "°F", "°F", "°F", "°F", "°F", "kg/m³", "kJ/kg", "kJ/(kg·K)",
            # CTR Coil (8)
            "°F", "°F", "°F", "°F", "°F", "kg/m³", "kJ/kg", "kJ/(kg·K)",
            # RH Coil (8)
            "°F", "°F", "°F", "°F", "°F", "kg/m³", "kJ/kg", "kJ/(kg·K)",
            # Compressor Inlet (7)
            "PSIG", "°F", "°F", "°F", "kg/m³", "kJ/kg", "kJ/(kg·K)",
            # Comp Outlet (2)
            "°F", "RPM",
            # Condenser (7)
            "°F", "PSIG", "°F", "°F", "°F", "°F", "°F",
            # TXV LH (4)
            "°F", "°F", "°F", "kJ/kg",
            # TXV CTR (4)
            "°F", "°F", "°F", "kJ/kg",
            # TXV RH (4)
            "°F", "°F", "°F", "kJ/kg",
            # TOTAL (2)
            "lb/hr", "BTU/hr"
        ]

        # Row 4: Actual column names (data keys from DataFrame)
        self.column_names = [
            # LH Coil (8)
            "T_1a-lh", "T_1b-lh", "T_2a-LH", "T_sat.lh", "S.H_lh coil", "D_coil lh", "H_coil lh", "S_coil lh",
            # CTR Coil (8)
            "T_1a-ctr", "T_1b-ctr", "T_2a-ctr", "T_sat.ctr", "S.H_ctr coil", "D_coil ctr", "H_coil ctr", "S_coil ctr",
            # RH Coil (8)
            "T_1a-rh", "T_1c-rh", "T_2a-RH", "T_sat.rh", "S.H_rh coil", "D_coil rh", "H_coil rh", "S_coil rh",
            # Compressor Inlet (7)
            "P_suction", "T_2b", "T_sat.comp.in", "S.H_total", "D_comp.in", "H_comp.in", "S_comp.in",
            # Comp Outlet (2)
            "T_3a", "rpm",
            # Condenser (7)
            "T_3b", "P_disch", "T_4a", "T_sat.cond", "S.C", "T_waterin", "T_waterout",
            # TXV LH (4)
            "T_4b-lh", "T_sat.txv.lh", "S.C-txv.lh", "H_txv.lh",
            # TXV CTR (4)
            "T_4b-ctr", "T_sat.txv.ctr", "S.C-txv.ctr", "H_txv.ctr",
            # TXV RH (4)
            "T_4b-rh", "T_sat.txv.rh", "S.C-txv.rh", "H_txv.rh",
            # TOTAL (2)
            "m_dot", "qc"
        ]

        # This is what QTreeWidget will use for actual data column headers
        self.sub_headers = self.column_names  # For backward compatibility
        self.data_keys = self.column_names

    def paintEvent(self, event):
        """Custom paint event to draw 4-ROW nested headers (we fully render all rows)."""
        painter = QPainter(self.viewport())
        painter.save()

        height_quarter = self.height() // 4

        # ===== ROW 1: Main Section Headers (Top quarter) =====
        font = self.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        painter.setFont(font)
        painter.fillRect(0, 0, self.width(), height_quarter, QColor(220, 220, 220))

        col_index = 0
        for text, span in self.main_sections:
            if span == 0:
                continue

            first_col_rect = self.sectionViewportPosition(col_index)
            last_col_rect = self.sectionViewportPosition(col_index + span - 1)
            group_width = (last_col_rect + self.sectionSize(col_index + span - 1)) - first_col_rect

            rect = self.rect()
            rect.setLeft(first_col_rect)
            rect.setWidth(group_width)
            rect.setTop(0)
            rect.setHeight(height_quarter)

            painter.setPen(QColor(80, 80, 80))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

            col_index += span

        # ===== ROW 2: Sub-section Headers (Second quarter) =====
        font.setBold(False)
        font.setPointSize(font.pointSize() - 1)
        font.setItalic(True)
        painter.setFont(font)
        painter.fillRect(0, height_quarter, self.width(), height_quarter, QColor(240, 240, 240))

        for col_idx, sub_text in enumerate(self.sub_sections):
            col_rect = self.sectionViewportPosition(col_idx)
            col_width = self.sectionSize(col_idx)

            rect = self.rect()
            rect.setLeft(col_rect)
            rect.setWidth(col_width)
            rect.setTop(height_quarter)
            rect.setHeight(height_quarter)

            painter.setPen(QColor(100, 100, 100))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, sub_text)

        # ===== ROW 3: Units (Third quarter) =====
        font.setItalic(True)
        font.setBold(False)
        font.setPointSize(max(9, font.pointSize() - 1))
        painter.setFont(font)
        painter.fillRect(0, height_quarter * 2, self.width(), height_quarter, QColor(230, 240, 255))

        for col_idx, unit_text in enumerate(self.units):
            col_rect = self.sectionViewportPosition(col_idx)
            col_width = self.sectionSize(col_idx)

            rect = self.rect()
            rect.setLeft(col_rect)
            rect.setWidth(col_width)
            rect.setTop(height_quarter * 2)
            rect.setHeight(height_quarter)

            painter.setPen(QColor(120, 120, 120))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            painter.drawText(rect.adjusted(2, 0, -2, 0), Qt.AlignmentFlag.AlignCenter, unit_text)

        # ===== ROW 4: Actual column names (Bottom quarter) =====
        font.setItalic(False)
        font.setBold(False)
        font.setPointSize(max(9, font.pointSize()))
        painter.setFont(font)
        painter.fillRect(0, height_quarter * 3, self.width(), height_quarter, QColor(255, 255, 255))

        for col_idx, col_name in enumerate(self.column_names):
            col_rect = self.sectionViewportPosition(col_idx)
            col_width = self.sectionSize(col_idx)

            rect = self.rect()
            rect.setLeft(col_rect)
            rect.setWidth(col_width)
            rect.setTop(height_quarter * 3)
            rect.setHeight(height_quarter)

            painter.setPen(QColor(120, 120, 120))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            painter.drawText(rect.adjusted(2, 0, -2, 0), Qt.AlignmentFlag.AlignCenter, col_name)

        painter.restore()

    def sizeHint(self):
        """Quadruple the height for 4 rows."""
        size = super().sizeHint()
        size.setHeight(size.height() * 4)
        return size


class CalculationAuditDialog(QDialog):
    """Dialog to display detailed calculation audit for a specific row."""
    
    def __init__(self, audit_text, row_index, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Calculation Audit - Row {row_index}")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Text area for audit output
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 9))
        text_edit.setText(audit_text)
        layout.addWidget(text_edit)
        
        # Close button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)


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
        self.audit_mode = False

        self.setup_ui()
        
        # Enable keyboard shortcuts
        copy_shortcut = QAction("Copy", self)
        copy_shortcut.setShortcut("Ctrl+C")
        copy_shortcut.triggered.connect(self.on_copy_triggered)
        self.addAction(copy_shortcut)
    
    def on_copy_triggered(self):
        """Handle Ctrl+C keyboard shortcut for both tables."""
        # Determine which widget has focus
        focused_widget = QApplication.focusWidget()
        
        if focused_widget == self.stats_table:
            # Copy from statistics table
            self.copy_stats_selection()
        elif focused_widget == self.tree_widget:
            # Copy from tree widget
            self.copy_tree_selection()

    def setup_ui(self):
        """Create the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # ==================== Compact Control Panel ====================
        # All controls in one line: discharge press input, Apply, Export buttons, Inputs, status
        control_row = QHBoxLayout()
        control_row.setContentsMargins(0, 0, 0, 0)
        control_row.setSpacing(8)

        self.lbl_filter = QLabel("discharge press")
        self.lbl_filter.setStyleSheet("font-size: 10pt; color: #333;")
        control_row.addWidget(self.lbl_filter)

        from PyQt6.QtWidgets import QDoubleSpinBox, QTableWidget
        self.spn_filter = QDoubleSpinBox()
        self.spn_filter.setDecimals(2)
        self.spn_filter.setRange(-1e12, 1e12)
        self.spn_filter.setValue(55.0)
        self.spn_filter.setFixedWidth(90)
        control_row.addWidget(self.spn_filter)

        self.btn_filter = QPushButton("Apply")
        self.btn_filter.setFixedHeight(24)
        self.btn_filter.clicked.connect(self.on_apply_filter)
        control_row.addWidget(self.btn_filter)

        control_row.addStretch()

        # Export buttons
        self.export_button = QPushButton("Export CSV")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_to_csv)
        control_row.addWidget(self.export_button)

        self.export_mapping_button = QPushButton("Export Mapping")
        self.export_mapping_button.setToolTip("Export port mapping and required roles to CSV")
        self.export_mapping_button.clicked.connect(self.export_mapping_audit)
        control_row.addWidget(self.export_mapping_button)

        # Inputs button
        self.enter_inputs_button = QPushButton("Inputs")
        self.enter_inputs_button.clicked.connect(self.open_input_dialog)
        control_row.addWidget(self.enter_inputs_button)

        # Info button for audit mode
        self.info_btn = QPushButton("ℹ")
        self.info_btn.setFixedSize(24, 24)
        self.info_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #999;
                border-radius: 12px;
                font-size: 12pt;
                font-weight: bold;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        self.info_btn.setCheckable(True)
        self.info_btn.setToolTip("Click to enable calculation audit mode")
        self.info_btn.clicked.connect(self.toggle_audit_mode)
        control_row.addWidget(self.info_btn)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 9pt; font-style: italic;")
        control_row.addWidget(self.status_label)

        layout.addLayout(control_row)

        # current discharge pressure threshold (None => no filter)
        self._dp_threshold = None

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
        self.tree_widget.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.tree_widget.itemClicked.connect(self.on_tree_item_clicked)

        layout.addWidget(self.tree_widget, 1)  # Stretch factor 1

        # ==================== Statistics Table ====================
        stats_label = QLabel("Statistics")
        stats_label.setStyleSheet("font-size: 10pt; font-weight: bold; margin-top: 10px;")
        layout.addWidget(stats_label)
        
        self.stats_table = QTableWidget()
        self.stats_table.setRowCount(3)  # Avg, Min, Max
        self.stats_table.setColumnCount(54)
        self.stats_table.setHorizontalHeaderLabels([""] * 54)  # Hide headers - use row labels
        self.stats_table.setVerticalHeaderLabels(["Avg", "Min", "Max"])
        self.stats_table.verticalHeader().setVisible(True)
        self.stats_table.horizontalHeader().setVisible(False)
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stats_table.setSelectionMode(QTableWidget.SelectionMode.ContiguousSelection)
        self.stats_table.setMaximumHeight(100)
        layout.addWidget(self.stats_table)
        
        # Enable copy functionality for statistics table
        self.stats_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.stats_table.customContextMenuRequested.connect(self.show_stats_context_menu)

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
                "You can now click 'Apply' to run calculations."
            )

            # Update status
            self.status_label.setText("✓ Rated inputs saved. Ready to run calculations.")
            self.status_label.setStyleSheet("color: green; font-size: 10pt;")

    def run_calculation(self):
        """Run the full batch calculation using the new unified engine."""

        # SOFT WARNING: Check for rated inputs
        # If missing, calculation will skip mass flow and capacity calculations
        required_fields = [
            'gpm_water',
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
                'gpm_water': 'Water Flow Rate (GPM)',
            }

            missing_labels = [field_labels.get(f, f) for f in missing_fields]

            # SOFT WARNING - Allow user to continue
            reply = QMessageBox.question(
                self,
                "Incomplete System Parameters",
                "Some system parameters are missing:\n\n" +
                "\n".join(f"• {label}" for label in missing_labels) +
                "\n\nMass flow and cooling capacity calculations will be skipped.\n"
                "Other calculations will proceed normally.\n\n"
                "Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.No:
                return  # User chose to stop

        self.status_label.setText("Processing...")
        self.status_label.setStyleSheet("color: blue; font-size: 10pt;")
        QApplication.processEvents()  # Allow UI to update

        try:
            # 1. Get filtered data from data manager
            base_df = self.data_manager.get_filtered_data()

            # apply discharge pressure filter if user set threshold
            input_df = self._apply_discharge_filter(base_df)

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
                    "1. Rated inputs are entered (click 'Enter Rated Inputs' button)\n"
                    "2. All required sensors are mapped in the Diagram tab"
                )
                return

            # 4. Store and display results
            # Force a stable schema: include ALL expected columns and fill missing with NaN
            # This prevents adjacent/shifted values when some sensors are unmapped
            expected_cols = list(self.header.data_keys)
            
            # IMPORTANT: Add hidden calculation columns that are needed for audit report
            # These are calculated but not displayed in the table
            hidden_cols = ['h_3a', 'h_4a', 'h_2b', 'h_4b_LH', 'h_4b_CTR', 'h_4b_RH']
            for col in hidden_cols:
                if col not in expected_cols and col in processed_df.columns:
                    expected_cols.append(col)
            
            # Reindex to ensure all expected columns exist (adds NaN for missing, keeps existing)
            processed_df = processed_df.reindex(columns=expected_cols)
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

    def on_apply_filter(self):
        """Store threshold from UI and re-run calculation."""
        try:
            self._dp_threshold = float(self.spn_filter.value())
        except Exception:
            self._dp_threshold = None
        self.run_calculation()

    def _apply_discharge_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """Keep only rows where mapped Compressor DP >= threshold.

        If threshold is None, or mapping/column missing, return df unchanged.
        """
        try:
            if df is None or df.empty:
                return df
            if self._dp_threshold is None:
                return df
            # find mapped discharge pressure column from Compressor DP
            model = self.data_manager.diagram_model
            components = model.get('components', {})
            from port_resolver import resolve_mapped_sensor
            dp_col = None
            for comp_id, comp in components.items():
                if comp.get('type') == 'Compressor':
                    dp_col = resolve_mapped_sensor(model, 'Compressor', comp_id, 'DP')
                    if dp_col:
                        break
            if not dp_col or dp_col not in df.columns:
                print(f"[CALCULATIONS] discharge press filter skipped: DP not mapped or not in DF: {dp_col}")
                return df
            thr = self._dp_threshold
            out = df[df[dp_col] >= thr].copy()
            print(f"[CALCULATIONS] discharge press filter: {dp_col} >= {thr} -> {len(out)}/{len(df)} rows")
            return out
        except Exception as e:
            print(f"[CALCULATIONS] discharge press filter error: {e}")
            return df

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
                # Treat NaN/NA as missing
                try:
                    import math
                    is_missing = val is None or (isinstance(val, float) and math.isnan(val))
                except Exception:
                    # Fallback for pandas NA
                    is_missing = val is None
                if is_missing:
                    row_data.append("---")
                elif isinstance(val, (int, float)):
                    row_data.append(f"{val:.2f}")  # Format numbers
                else:
                    row_data.append(str(val))

            item = QTreeWidgetItem(row_data)
            items.append(item)

        self.tree_widget.addTopLevelItems(items)

        # Resize columns after adding data
        for i in range(len(data_keys)):
            self.tree_widget.resizeColumnToContents(i)

        print(f"[CALCULATIONS] Populated tree with {len(items)} rows and {len(data_keys)} columns")
        
        # Populate statistics table
        self.populate_stats_table(df)

    def populate_stats_table(self, df):
        """Populate statistics table with Avg/Min/Max for all columns."""
        if df is None or df.empty:
            return
        
        # Get the data keys from the header
        data_keys = self.header.data_keys
        
        # Calculate statistics for numeric columns only
        for col_idx, key in enumerate(data_keys):
            if key in df.columns:
                col_data = df[key].dropna()
                if len(col_data) > 0 and pd.api.types.is_numeric_dtype(col_data):
                    avg_val = col_data.mean()
                    min_val = col_data.min()
                    max_val = col_data.max()
                    
                    # Set values with formatting
                    self.stats_table.setItem(0, col_idx, QTableWidgetItem(f"{avg_val:.2f}"))
                    self.stats_table.setItem(1, col_idx, QTableWidgetItem(f"{min_val:.2f}"))
                    self.stats_table.setItem(2, col_idx, QTableWidgetItem(f"{max_val:.2f}"))
                else:
                    # Non-numeric or empty - show dashes
                    self.stats_table.setItem(0, col_idx, QTableWidgetItem("---"))
                    self.stats_table.setItem(1, col_idx, QTableWidgetItem("---"))
                    self.stats_table.setItem(2, col_idx, QTableWidgetItem("---"))
            else:
                # Column not present
                self.stats_table.setItem(0, col_idx, QTableWidgetItem("---"))
                self.stats_table.setItem(1, col_idx, QTableWidgetItem("---"))
                self.stats_table.setItem(2, col_idx, QTableWidgetItem("---"))
        
        # Resize columns to match main table
        for i in range(len(data_keys)):
            width = self.tree_widget.columnWidth(i)
            self.stats_table.setColumnWidth(i, width)

    def show_stats_context_menu(self, position):
        """Show context menu for copy operations on statistics table."""
        menu = QMenu(self)
        
        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(lambda: self.copy_stats_selection())
        menu.addAction(copy_action)
        
        copy_with_headers_action = QAction("Copy with Headers", self)
        copy_with_headers_action.triggered.connect(lambda: self.copy_stats_selection(with_headers=True))
        menu.addAction(copy_with_headers_action)
        
        menu.exec(self.stats_table.viewport().mapToGlobal(position))

    def show_tree_context_menu(self, position):
        """Show context menu for copy operations on tree widget."""
        menu = QMenu(self)
        
        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(self.copy_tree_selection)
        menu.addAction(copy_action)
        
        menu.exec(self.tree_widget.viewport().mapToGlobal(position))

    def copy_stats_selection(self, with_headers=False):
        """Copy selected statistics table data to clipboard."""
        selected_ranges = self.stats_table.selectedRanges()
        if not selected_ranges:
            return
        
        clipboard = QApplication.clipboard()
        rows = []
        
        for range_obj in selected_ranges:
            left_col = range_obj.leftColumn()
            right_col = range_obj.rightColumn()
            
            # Add 4 header rows if requested
            if with_headers:
                # Row 1: Main section headers (simplified - repeat section for each column)
                header1 = [""]  # Empty cell for vertical header alignment
                col_idx = 0
                for section_name, span in self.header.main_sections:
                    for _ in range(span):
                        if col_idx >= left_col and col_idx <= right_col:
                            header1.append(section_name)
                        col_idx += 1
                rows.append("\t".join(header1))
                
                # Row 2: Sub-section headers
                header2 = [""]  # Empty cell for vertical header alignment
                header2.extend(self.header.sub_sections[left_col:right_col+1])
                rows.append("\t".join(header2))
                
                # Row 3: Units
                header3 = [""]  # Empty cell for vertical header alignment
                header3.extend(self.header.units[left_col:right_col+1])
                rows.append("\t".join(header3))
                
                # Row 4: Column names (sensor names)
                header4 = [""]  # Empty cell for vertical header alignment
                header4.extend(self.header.column_names[left_col:right_col+1])
                rows.append("\t".join(header4))
            
            # Add data rows with vertical headers
            for row in range(range_obj.topRow(), range_obj.bottomRow() + 1):
                row_data = []
                # Add vertical header (Avg, Min, or Max)
                if with_headers:
                    row_data.append(self.stats_table.verticalHeaderItem(row).text())
                for col in range(left_col, right_col + 1):
                    item = self.stats_table.item(row, col)
                    row_data.append(item.text() if item else "")
                rows.append("\t".join(row_data))
        
        clipboard.setText("\n".join(rows))

    def copy_tree_selection(self):
        """Copy selected tree widget data to clipboard."""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return
        
        clipboard = QApplication.clipboard()
        rows = []
        
        for item in selected_items:
            row_data = []
            for col in range(self.tree_widget.columnCount()):
                row_data.append(item.text(col))
            rows.append("\t".join(row_data))
        
        clipboard.setText("\n".join(rows))

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
            # Export only the displayed columns, in the same order, with UTF-8 BOM
            display_keys = [k for k in self.header.data_keys if k in self.processed_df.columns]
            export_df = self.processed_df[display_keys] if display_keys else self.processed_df
            export_df.to_csv(filename, index=False, encoding='utf-8-sig')
            QMessageBox.information(
                self,
                "Export Successful",
                f"Data exported successfully to:\n{filename}"
            )
            print(f"[CALCULATIONS] Exported {len(self.processed_df)} rows to {filename}")

        except Exception as e:
            print(f"[CALCULATIONS] ERROR during export: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")

    def export_mapping_audit(self):
        """Export both port-level mapping and required role mapping CSVs for auditing."""
        try:
            port_path = self.data_manager.export_port_mapping_csv("port_mapping_audit.csv")
            roles_path = self.data_manager.export_required_roles_csv("required_roles_mapping.csv")
            QMessageBox.information(
                self,
                "Mapping Audit Exported",
                f"Wrote:\n- {port_path}\n- {roles_path}\n\nAttach these CSVs with corrections to remap."
            )
        except Exception as e:
            print(f"[MAPPING EXPORT] ERROR: {e}")
            QMessageBox.critical(self, "Mapping Export Error", str(e))
    
    def toggle_audit_mode(self):
        """Toggle audit mode on/off."""
        self.audit_mode = not self.audit_mode
        if self.audit_mode:
            self.info_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #0078d4;
                    border-radius: 12px;
                    font-size: 12pt;
                    font-weight: bold;
                    background-color: #0078d4;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #005a9e;
                }
            """)
            self.status_label.setText("Audit mode ON - Click any row to see calculations")
        else:
            self.info_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #999;
                    border-radius: 12px;
                    font-size: 12pt;
                    font-weight: bold;
                    background-color: #f0f0f0;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
                QPushButton:pressed {
                    background-color: #d0d0d0;
                }
            """)
            self.status_label.setText("Ready")
    
    def on_tree_item_clicked(self, item, column):
        """Handle row click - show audit dialog if audit mode is active."""
        if not self.audit_mode:
            return
        
        if self.processed_df is None or self.processed_df.empty:
            QMessageBox.warning(self, "No Data", "No calculation data available for audit")
            return
        
        # Get row index
        row_index = self.tree_widget.indexOfTopLevelItem(item)
        if row_index < 0 or row_index >= len(self.processed_df):
            return
        
        # Get the row data
        row_data = self.processed_df.iloc[row_index]
        
        # DEBUG: Print all columns to console for debugging
        print(f"\n[DEBUG] Row {row_index} - Available columns ({len(row_data.index)} total):")
        if hasattr(row_data, 'index'):
            all_cols = list(row_data.index)
            # Find all enthalpy-related columns
            h_cols = [col for col in all_cols if ('h' in str(col).lower() or 'H' in str(col)) and ('3' in str(col) or '4' in str(col) or 'comp' in str(col).lower() or 'cond' in str(col).lower())]
            print(f"[DEBUG] Enthalpy columns found: {h_cols}")
            for col in sorted(h_cols):
                val = row_data.get(col) if hasattr(row_data, 'get') else row_data[col]
                print(f"[DEBUG]   {col} = {val}")
            # Specifically check for h_3a and h_4a
            for test_col in ['h_3a', 'H_3a', 'h_4a', 'H_4a', 'H_comp.out', 'H_cond.out']:
                if test_col in all_cols:
                    val = row_data.get(test_col) if hasattr(row_data, 'get') else row_data[test_col]
                    print(f"[DEBUG] FOUND: {test_col} = {val}")
        print()
        
        # Generate audit text
        audit_text = self.generate_audit_text(row_index, row_data)
        
        # Show dialog
        dialog = CalculationAuditDialog(audit_text, row_index, self)
        dialog.exec()
    
    def generate_audit_text(self, row_index, row_data):
        """Generate detailed audit text for a specific row."""
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append(f"CALCULATION AUDIT - ROW {row_index}")
        lines.append("=" * 80)
        lines.append("")
        
        # Get sensor map and specs - use the same method as calculations
        sensor_map = {}
        comp_specs = {}
        input_data = None
        
        try:
            diagram_model = self.data_manager.diagram_model
            
            # Get original input data for Section 1 (raw CSV values)
            input_data = self.data_manager.get_filtered_data()
            if input_data is not None and not input_data.empty and row_index < len(input_data):
                input_data = input_data.iloc[row_index]
            else:
                input_data = None
            
            # Validate against actual input columns
            if input_data is not None:
                input_columns = set(input_data.index if hasattr(input_data, 'index') else set())
            else:
                # Fallback: try to get columns from processed_df if available
                if hasattr(row_data, 'index'):
                    input_columns = set(row_data.index)
                else:
                    input_columns = set()
            
            # Build sensor map using REQUIRED_SENSOR_ROLES (same as calculations)
            for key, role_defs in REQUIRED_SENSOR_ROLES.items():
                for role_def in role_defs:
                    sensor_name = _find_sensor_for_role(diagram_model, role_def)
                    # Only accept mappings that exist in the input data
                    if sensor_name and (not input_columns or sensor_name in input_columns):
                        sensor_map[key] = sensor_name
                        break  # Found it
            
            # Special handling for averaged sensors (same as calculation_orchestrator)
            components = diagram_model.get('components', {})
            
            for side in ['Left', 'Center', 'Right']:
                # Find the evaporator for this side
                evap_id = None
                comp = None
                for comp_id, c in components.items():
                    if c.get('type') == 'Evaporator' and c.get('properties', {}).get('circuit_label') == side:
                        evap_id = comp_id
                        comp = c
                        break
                
                if evap_id and comp:
                    # Check how many circuits this evaporator has
                    circuits = comp.get('properties', {}).get('circuits', 1)
                    
                    # Collect all inlet circuit sensors
                    inlet_sensors = []
                    outlet_sensors = []
                    for i in range(1, circuits + 1):
                        inlet_port = f'inlet_circuit_{i}'
                        outlet_port = f'outlet_circuit_{i}'
                        inlet_sensor = resolve_mapped_sensor(diagram_model, 'Evaporator', evap_id, inlet_port)
                        outlet_sensor = resolve_mapped_sensor(diagram_model, 'Evaporator', evap_id, outlet_port)
                        
                        if inlet_sensor and (not input_columns or inlet_sensor in input_columns):
                            inlet_sensors.append(inlet_sensor)
                        if outlet_sensor and (not input_columns or outlet_sensor in input_columns):
                            outlet_sensors.append(outlet_sensor)
                    
                    # Store for averaging
                    if side == 'Left':
                        if inlet_sensors:
                            sensor_map['_avg_T_1b-lh'] = inlet_sensors
                        if outlet_sensors:
                            sensor_map['_avg_T_2a-LH'] = outlet_sensors
                    elif side == 'Center':
                        if inlet_sensors:
                            sensor_map['_avg_T_1b-ctr'] = inlet_sensors
                        if outlet_sensors:
                            sensor_map['_avg_T_2a-ctr'] = outlet_sensors
                    elif side == 'Right':
                        if inlet_sensors:
                            sensor_map['_avg_T_1c-rh'] = inlet_sensors
                        if outlet_sensors:
                            sensor_map['_avg_T_2a-RH'] = outlet_sensors
            
            comp_specs = self.data_manager.rated_inputs
        except Exception as e:
            lines.append(f"Warning: Could not retrieve sensor mappings: {e}")
            lines.append("")
            import traceback
            traceback.print_exc()
        
        # Section 1: Input Sensors
        lines.append("=" * 80)
        lines.append("SECTION 1: INPUT SENSORS (Raw CSV Data)")
        lines.append("=" * 80)
        lines.append("")
        
        sensor_groups = {
            "Pressures": ["P_suc", "P_disch"],
            "LH Circuit": ["T_1a-lh", "T_1b-lh", "_avg_T_1b-lh", "T_2a-LH", "_avg_T_2a-LH", "T_4b-lh"],
            "CTR Circuit": ["T_1a-ctr", "T_1b-ctr", "_avg_T_1b-ctr", "T_2a-ctr", "_avg_T_2a-ctr", "T_4b-ctr"],
            "RH Circuit": ["T_1a-rh", "T_1c-rh", "_avg_T_1c-rh", "T_2a-RH", "_avg_T_2a-RH", "T_4b-rh"],
            "Compressor": ["T_2b", "T_3a"],
            "Condenser": ["T_3b", "T_4a", "T_waterin", "T_water_out", "T_waterout"],
        }
        
        for group_name, sensor_keys in sensor_groups.items():
            lines.append(f"{group_name}:")
            for key in sensor_keys:
                csv_name_or_list = sensor_map.get(key)
                if csv_name_or_list is None:
                    lines.append(f"  {key:20s} : Not mapped")
                else:
                    # Handle averaged sensors (lists) or single sensors
                    if isinstance(csv_name_or_list, list):
                        # This is an averaged sensor - get values from all sensors and average
                        values = []
                        sensor_names = []
                        data_source = input_data if input_data is not None else row_data
                        
                        for sensor_name in csv_name_or_list:
                            val = None
                            if data_source is not None:
                                if hasattr(data_source, 'get'):
                                    val = data_source.get(sensor_name)
                                elif hasattr(data_source, '__getitem__'):
                                    try:
                                        val = data_source[sensor_name]
                                    except (KeyError, IndexError):
                                        pass
                            
                            if val is not None and isinstance(val, (int, float)) and not math.isnan(val):
                                values.append(val)
                                sensor_names.append(sensor_name)
                        
                        if values:
                            avg_val = sum(values) / len(values)
                            if len(values) > 1:
                                sensor_list_str = ", ".join(sensor_names)
                                lines.append(f"  {key:20s} : {avg_val:.2f} °F (avg of {len(values)}: {sensor_list_str})" 
                                           if 'T' in key else 
                                           f"  {key:20s} : {avg_val:.2f} PSIG (avg of {len(values)}: {sensor_list_str})")
                            else:
                                lines.append(f"  {key:20s} : {avg_val:.2f} °F" 
                                           if 'T' in key else 
                                           f"  {key:20s} : {avg_val:.2f} PSIG")
                        else:
                            lines.append(f"  {key:20s} : Missing")
                    else:
                        # Single sensor - get value directly
                        data_source = input_data if input_data is not None else row_data
                        val = None
                        if data_source is not None:
                            if hasattr(data_source, 'get'):
                                val = data_source.get(csv_name_or_list)
                            elif hasattr(data_source, '__getitem__'):
                                try:
                                    val = data_source[csv_name_or_list]
                                except (KeyError, IndexError):
                                    pass
                        
                        if val is not None and isinstance(val, (int, float)) and not math.isnan(val):
                            lines.append(f"  {key:20s} : {val:.2f} °F" if 'T' in key else f"  {key:20s} : {val:.2f} PSIG")
                        else:
                            lines.append(f"  {key:20s} : Missing")
            lines.append("")
        
        # Section 2: Rated Inputs
        lines.append("=" * 80)
        lines.append("SECTION 2: RATED INPUTS")
        lines.append("=" * 80)
        lines.append("")
        
        for key, val in comp_specs.items():
            if isinstance(val, (int, float)) and not math.isnan(val):
                lines.append(f"  {key:20s} : {val:.4f}")
            else:
                lines.append(f"  {key:20s} : Not set")
        lines.append("")
        
        # Section 3: Unit Conversions
        lines.append("=" * 80)
        lines.append("SECTION 3: UNIT CONVERSIONS")
        lines.append("=" * 80)
        lines.append("")
        
        p_suc_psig = row_data.get('P_suction', None)
        if p_suc_psig is not None and not math.isnan(p_suc_psig):
            p_suc_pa = (p_suc_psig + 14.7) * 6894.76
            lines.append(f"Suction Pressure:")
            lines.append(f"  Input: {p_suc_psig:.2f} PSIG")
            lines.append(f"  Formula: ({p_suc_psig:.2f} + 14.7) × 6894.76")
            lines.append(f"  Output: {p_suc_pa:.2f} Pa")
            lines.append("")
        
        p_disch_psig = row_data.get('P_disch', None)
        if p_disch_psig is not None and not math.isnan(p_disch_psig):
            p_disch_pa = (p_disch_psig + 14.7) * 6894.76
            lines.append(f"Discharge Pressure:")
            lines.append(f"  Input: {p_disch_psig:.2f} PSIG")
            lines.append(f"  Formula: ({p_disch_psig:.2f} + 14.7) × 6894.76")
            lines.append(f"  Output: {p_disch_pa:.2f} Pa")
            lines.append("")
        
        # Show temperature conversions for key sensors
        temp_sensors = ["T_1a-lh", "T_2a-LH", "T_2b", "T_3a", "T_4a", "T_4b-lh"]
        for sensor_key in temp_sensors:
            csv_name = sensor_map.get(sensor_key) or sensor_map.get(f"_avg_{sensor_key}")
            if csv_name and csv_name in row_data.index:
                val_f = row_data[csv_name]
                if isinstance(val_f, (int, float)) and not math.isnan(val_f):
                    val_k = (val_f + 459.67) * 5.0 / 9.0
                    lines.append(f"{sensor_key}:")
                    lines.append(f"  Input: {val_f:.2f} °F")
                    lines.append(f"  Formula: ({val_f:.2f} + 459.67) × 5/9")
                    lines.append(f"  Output: {val_k:.2f} K")
                    lines.append("")
        
        # Section 4: Saturation Temperatures
        lines.append("=" * 80)
        lines.append("SECTION 4: SATURATION TEMPERATURES (from CoolProp)")
        lines.append("=" * 80)
        lines.append("")
        
        if p_suc_psig is not None and not math.isnan(p_suc_psig):
            p_suc_pa = (p_suc_psig + 14.7) * 6894.76
            lines.append(f"Suction Saturation:")
            lines.append(f"  CoolProp: PropsSI('T', 'P', {p_suc_pa:.2f}, 'Q', 0, 'R290')")
            t_sat_suc_f = row_data.get('T_sat.lh')
            if t_sat_suc_f is not None and not math.isnan(t_sat_suc_f):
                lines.append(f"  Result: {t_sat_suc_f:.2f} °F")
            lines.append("")
        
        if p_disch_psig is not None and not math.isnan(p_disch_psig):
            p_disch_pa = (p_disch_psig + 14.7) * 6894.76
            lines.append(f"Discharge Saturation:")
            lines.append(f"  CoolProp: PropsSI('T', 'P', {p_disch_pa:.2f}, 'Q', 0, 'R290')")
            t_sat_disch_f = row_data.get('T_sat.cond')
            if t_sat_disch_f is not None and not math.isnan(t_sat_disch_f):
                lines.append(f"  Result: {t_sat_disch_f:.2f} °F")
            lines.append("")
        
        # Section 5: Key Property Calculations
        lines.append("=" * 80)
        lines.append("SECTION 5: KEY PROPERTY CALCULATIONS")
        lines.append("=" * 80)
        lines.append("")
        lines.append("This section shows the key thermodynamic properties (enthalpy, density) at")
        lines.append("important points in the refrigeration cycle. These values are essential")
        lines.append("for calculating mass flow rate and cooling capacity.")
        lines.append("")
        
        # Compressor Inlet (h_2b) - needed for evaporator enthalpy change
        t_2b = row_data.get('T_2b')
        h_2b = row_data.get('H_comp.in')
        if h_2b is not None and not math.isnan(h_2b):
            lines.append("Compressor Inlet (Point 2b):")
            if t_2b is not None and not math.isnan(t_2b):
                lines.append(f"  Temperature: {t_2b:.2f} °F")
            lines.append(f"  Enthalpy (h_2b): {h_2b:.3f} kJ/kg")
            lines.append(f"    This is the refrigerant enthalpy entering the compressor.")
            lines.append(f"    It represents the energy content after leaving the evaporator.")
            d = row_data.get('D_comp.in')
            if d is not None and not math.isnan(d):
                lines.append(f"  Density: {d:.3f} kg/m³")
            sh = row_data.get('S.H_total')
            if sh is not None and not math.isnan(sh):
                lines.append(f"  Total Superheat: {sh:.2f} °F")
            lines.append("")
        
        # Compressor Outlet / Condenser Inlet (h_3a) - needed for condenser enthalpy change
        t_3a = row_data.get('T_3a') if hasattr(row_data, 'get') else None
        if t_3a is None and hasattr(row_data, '__getitem__'):
            try:
                t_3a = row_data['T_3a']
            except (KeyError, IndexError):
                pass
        
        h_3a = None
        # Try to get from stored column first
        for col_name in ['h_3a', 'H_3a', 'H_comp.out', 'h_comp.out']:
            val = row_data.get(col_name) if hasattr(row_data, 'get') else None
            if val is None and hasattr(row_data, '__getitem__'):
                try:
                    val = row_data[col_name]
                except (KeyError, IndexError):
                    continue
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                h_3a = val
                if h_3a > 1000:
                    h_3a = h_3a / 1000
                break
        
        # If not found, calculate from T_3a and P_disch (existing table columns)
        if h_3a is None and t_3a is not None and not math.isnan(t_3a):
            p_disch_psig = row_data.get('P_disch') if hasattr(row_data, 'get') else None
            if p_disch_psig is None and hasattr(row_data, '__getitem__'):
                try:
                    p_disch_psig = row_data['P_disch']
                except (KeyError, IndexError):
                    pass
            if p_disch_psig is not None and not math.isnan(p_disch_psig):
                try:
                    from CoolProp.CoolProp import PropsSI
                    t_3a_k = (t_3a + 459.67) * 5.0 / 9.0
                    p_disch_pa = (p_disch_psig + 14.7) * 6894.76
                    h_3a_jkg = PropsSI('H', 'T', t_3a_k, 'P', p_disch_pa, 'R290')
                    h_3a = h_3a_jkg / 1000  # Convert to kJ/kg
                except Exception as e:
                    pass
        
        if h_3a is not None and not math.isnan(h_3a):
            lines.append("Compressor Outlet / Condenser Inlet (Point 3a):")
            if t_3a is not None and not math.isnan(t_3a):
                lines.append(f"  Temperature: {t_3a:.2f} °F")
            lines.append(f"  Enthalpy (h_3a): {h_3a:.3f} kJ/kg")
            if p_disch_psig is not None:
                lines.append(f"    Calculated from: T_3a = {t_3a:.2f} °F, P_disch = {p_disch_psig:.2f} PSIG")
            lines.append(f"    This is the refrigerant enthalpy leaving the compressor.")
            lines.append(f"    It represents the energy content after compression.")
            lines.append("")
        
        # Condenser Outlet (h_4a) - needed for condenser enthalpy change
        t_4a = row_data.get('T_4a') if hasattr(row_data, 'get') else None
        if t_4a is None and hasattr(row_data, '__getitem__'):
            try:
                t_4a = row_data['T_4a']
            except (KeyError, IndexError):
                pass
        
        h_4a = None
        # Try to get from stored column first
        for col_name in ['h_4a', 'H_4a', 'H_cond.out', 'h_cond.out']:
            val = row_data.get(col_name) if hasattr(row_data, 'get') else None
            if val is None and hasattr(row_data, '__getitem__'):
                try:
                    val = row_data[col_name]
                except (KeyError, IndexError):
                    continue
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                h_4a = val
                if h_4a > 1000:
                    h_4a = h_4a / 1000
                break
        
        # If not found, calculate from T_4a and P_disch (existing table columns)
        if h_4a is None and t_4a is not None and not math.isnan(t_4a):
            p_disch_psig = row_data.get('P_disch') if hasattr(row_data, 'get') else None
            if p_disch_psig is None and hasattr(row_data, '__getitem__'):
                try:
                    p_disch_psig = row_data['P_disch']
                except (KeyError, IndexError):
                    pass
            if p_disch_psig is not None and not math.isnan(p_disch_psig):
                try:
                    from CoolProp.CoolProp import PropsSI
                    t_4a_k = (t_4a + 459.67) * 5.0 / 9.0
                    p_disch_pa = (p_disch_psig + 14.7) * 6894.76
                    h_4a_jkg = PropsSI('H', 'T', t_4a_k, 'P', p_disch_pa, 'R290')
                    h_4a = h_4a_jkg / 1000  # Convert to kJ/kg
                except Exception as e:
                    pass
        
        if h_4a is not None and not math.isnan(h_4a):
            lines.append("Condenser Outlet (Point 4a):")
            if t_4a is not None and not math.isnan(t_4a):
                lines.append(f"  Temperature: {t_4a:.2f} °F")
            lines.append(f"  Enthalpy (h_4a): {h_4a:.3f} kJ/kg")
            if p_disch_psig is not None:
                lines.append(f"    Calculated from: T_4a = {t_4a:.2f} °F, P_disch = {p_disch_psig:.2f} PSIG")
            lines.append(f"    This is the refrigerant enthalpy leaving the condenser.")
            lines.append(f"    It represents the energy content after rejecting heat to water.")
            lines.append("")
        
        # TXV Inlets (h_4b) - needed for evaporator enthalpy change
        # Use existing table columns: H_txv.lh, H_txv.ctr, H_txv.rh (these ARE in the table)
        h_4b_lh = None
        h_4b_ctr = None
        h_4b_rh = None
        
        # Try to get from table columns first (these exist!)
        for col_name in ['H_txv.lh', 'h_4b_LH', 'H_4b_LH', 'h_txv.lh']:
            val = row_data.get(col_name) if hasattr(row_data, 'get') else None
            if val is None and hasattr(row_data, '__getitem__'):
                try:
                    val = row_data[col_name]
                except (KeyError, IndexError):
                    continue
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                h_4b_lh = val
                if h_4b_lh > 1000:
                    h_4b_lh = h_4b_lh / 1000
                break
        
        for col_name in ['H_txv.ctr', 'h_4b_CTR', 'H_4b_CTR', 'h_txv.ctr']:
            val = row_data.get(col_name) if hasattr(row_data, 'get') else None
            if val is None and hasattr(row_data, '__getitem__'):
                try:
                    val = row_data[col_name]
                except (KeyError, IndexError):
                    continue
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                h_4b_ctr = val
                if h_4b_ctr > 1000:
                    h_4b_ctr = h_4b_ctr / 1000
                break
        
        for col_name in ['H_txv.rh', 'h_4b_RH', 'H_4b_RH', 'h_txv.rh']:
            val = row_data.get(col_name) if hasattr(row_data, 'get') else None
            if val is None and hasattr(row_data, '__getitem__'):
                try:
                    val = row_data[col_name]
                except (KeyError, IndexError):
                    continue
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                h_4b_rh = val
                if h_4b_rh > 1000:
                    h_4b_rh = h_4b_rh / 1000
                break
        
        # If not found, calculate from T_4b temperatures and P_disch (existing table columns)
        if h_4b_lh is None:
            t_4b_lh_f = row_data.get('T_4b-lh') if hasattr(row_data, 'get') else None
            if t_4b_lh_f is None and hasattr(row_data, '__getitem__'):
                try:
                    t_4b_lh_f = row_data['T_4b-lh']
                except (KeyError, IndexError):
                    pass
            p_disch_psig = row_data.get('P_disch') if hasattr(row_data, 'get') else None
            if p_disch_psig is None and hasattr(row_data, '__getitem__'):
                try:
                    p_disch_psig = row_data['P_disch']
                except (KeyError, IndexError):
                    pass
            if t_4b_lh_f is not None and not math.isnan(t_4b_lh_f) and p_disch_psig is not None and not math.isnan(p_disch_psig):
                try:
                    from CoolProp.CoolProp import PropsSI
                    t_4b_lh_k = (t_4b_lh_f + 459.67) * 5.0 / 9.0
                    p_disch_pa = (p_disch_psig + 14.7) * 6894.76
                    h_4b_lh_jkg = PropsSI('H', 'T', t_4b_lh_k, 'P', p_disch_pa, 'R290')
                    h_4b_lh = h_4b_lh_jkg / 1000
                except:
                    pass
        
        if h_4b_ctr is None:
            t_4b_ctr_f = row_data.get('T_4b-ctr') if hasattr(row_data, 'get') else None
            if t_4b_ctr_f is None and hasattr(row_data, '__getitem__'):
                try:
                    t_4b_ctr_f = row_data['T_4b-ctr']
                except (KeyError, IndexError):
                    pass
            p_disch_psig = row_data.get('P_disch') if hasattr(row_data, 'get') else None
            if p_disch_psig is None and hasattr(row_data, '__getitem__'):
                try:
                    p_disch_psig = row_data['P_disch']
                except (KeyError, IndexError):
                    pass
            if t_4b_ctr_f is not None and not math.isnan(t_4b_ctr_f) and p_disch_psig is not None and not math.isnan(p_disch_psig):
                try:
                    from CoolProp.CoolProp import PropsSI
                    t_4b_ctr_k = (t_4b_ctr_f + 459.67) * 5.0 / 9.0
                    p_disch_pa = (p_disch_psig + 14.7) * 6894.76
                    h_4b_ctr_jkg = PropsSI('H', 'T', t_4b_ctr_k, 'P', p_disch_pa, 'R290')
                    h_4b_ctr = h_4b_ctr_jkg / 1000
                except:
                    pass
        
        if h_4b_rh is None:
            t_4b_rh_f = row_data.get('T_4b-rh') if hasattr(row_data, 'get') else None
            if t_4b_rh_f is None and hasattr(row_data, '__getitem__'):
                try:
                    t_4b_rh_f = row_data['T_4b-rh']
                except (KeyError, IndexError):
                    pass
            p_disch_psig = row_data.get('P_disch') if hasattr(row_data, 'get') else None
            if p_disch_psig is None and hasattr(row_data, '__getitem__'):
                try:
                    p_disch_psig = row_data['P_disch']
                except (KeyError, IndexError):
                    pass
            if t_4b_rh_f is not None and not math.isnan(t_4b_rh_f) and p_disch_psig is not None and not math.isnan(p_disch_psig):
                try:
                    from CoolProp.CoolProp import PropsSI
                    t_4b_rh_k = (t_4b_rh_f + 459.67) * 5.0 / 9.0
                    p_disch_pa = (p_disch_psig + 14.7) * 6894.76
                    h_4b_rh_jkg = PropsSI('H', 'T', t_4b_rh_k, 'P', p_disch_pa, 'R290')
                    h_4b_rh = h_4b_rh_jkg / 1000
                except:
                    pass
        
        t_4b_lh = row_data.get('T_4b-lh')
        t_4b_ctr = row_data.get('T_4b-ctr')
        t_4b_rh = row_data.get('T_4b-rh')
        
        lines.append("TXV Inlets (Point 4b - Before Expansion):")
        if h_4b_lh is not None and not math.isnan(h_4b_lh):
            if t_4b_lh is not None and not math.isnan(t_4b_lh):
                lines.append(f"  LH Circuit - Temperature: {t_4b_lh:.2f} °F")
            lines.append(f"    Enthalpy (h_4b_LH): {h_4b_lh:.3f} kJ/kg")
        if h_4b_ctr is not None and not math.isnan(h_4b_ctr):
            if t_4b_ctr is not None and not math.isnan(t_4b_ctr):
                lines.append(f"  CTR Circuit - Temperature: {t_4b_ctr:.2f} °F")
            lines.append(f"    Enthalpy (h_4b_CTR): {h_4b_ctr:.3f} kJ/kg")
        if h_4b_rh is not None and not math.isnan(h_4b_rh):
            if t_4b_rh is not None and not math.isnan(t_4b_rh):
                lines.append(f"  RH Circuit - Temperature: {t_4b_rh:.2f} °F")
            lines.append(f"    Enthalpy (h_4b_RH): {h_4b_rh:.3f} kJ/kg")
        
        # Calculate and show average
        h_4b_values = []
        if h_4b_lh is not None and not math.isnan(h_4b_lh):
            h_4b_values.append(h_4b_lh)
        if h_4b_ctr is not None and not math.isnan(h_4b_ctr):
            h_4b_values.append(h_4b_ctr)
        if h_4b_rh is not None and not math.isnan(h_4b_rh):
            h_4b_values.append(h_4b_rh)
        
        if h_4b_values:
            h_4b_avg = sum(h_4b_values) / len(h_4b_values)
            if len(h_4b_values) > 1:
                h_4b_list = " + ".join([f"{v:.3f}" for v in h_4b_values])
                lines.append(f"  Average Enthalpy (h_4b_avg): ({h_4b_list}) / {len(h_4b_values)} = {h_4b_avg:.3f} kJ/kg")
            else:
                lines.append(f"  Average Enthalpy (h_4b_avg): {h_4b_avg:.3f} kJ/kg")
            lines.append(f"    This average represents the refrigerant enthalpy before expansion")
            lines.append(f"    across all three circuits (LH, CTR, RH). We use the average")
            lines.append(f"    because the three circuits may have slightly different conditions.")
        else:
            lines.append("  Average Enthalpy: Cannot calculate (missing TXV inlet data)")
        lines.append("")
        
        # Show evaporator enthalpy change preview
        if h_2b is not None and not math.isnan(h_2b) and h_4b_values:
            h_2b_kjkg = h_2b if h_2b < 1000 else h_2b / 1000
            delta_h_evap = h_2b_kjkg - h_4b_avg
            lines.append("Evaporator Enthalpy Change (Preview):")
            lines.append(f"  Δh_evap = h_2b - h_4b_avg")
            lines.append(f"  Δh_evap = {h_2b_kjkg:.3f} - {h_4b_avg:.3f} = {delta_h_evap:.3f} kJ/kg")
            lines.append(f"    This is the energy absorbed by the refrigerant in the evaporator.")
            lines.append(f"    It will be used to calculate cooling capacity.")
            lines.append("")
        
        # Section 6: Mass Flow & Capacity Calculations
        lines.append("=" * 80)
        lines.append("SECTION 6: MASS FLOW & CAPACITY CALCULATIONS")
        lines.append("=" * 80)
        lines.append("")
        lines.append("This section calculates the mass flow rate of refrigerant and the total")
        lines.append("cooling capacity. We use energy balance between water and refrigerant sides.")
        lines.append("")
        
        # DEBUG: Show available columns that contain 'h' or 'H' and '3' or '4'
        if hasattr(row_data, 'index'):
            all_cols = list(row_data.index)
            h_cols = [col for col in all_cols if ('h' in str(col).lower() or 'H' in str(col)) and ('3' in str(col) or '4' in str(col) or 'comp' in str(col).lower() or 'cond' in str(col).lower() or 'txv' in str(col).lower())]
            if h_cols:
                lines.append("DEBUG - All enthalpy columns found in DataFrame:")
                for col in sorted(h_cols):
                    try:
                        val = row_data.get(col) if hasattr(row_data, 'get') else (row_data[col] if col in row_data.index else None)
                        if val is not None and not (isinstance(val, float) and math.isnan(val)):
                            lines.append(f"  {col}: {val}")
                    except:
                        pass
                lines.append("")
                
                # Specifically test our target columns
                lines.append("DEBUG - Testing target column names:")
                target_tests = [
                    ('h_3a', ['h_3a', 'H_3a', 'H_comp.out', 'h_comp.out']),
                    ('h_4a', ['h_4a', 'H_4a', 'H_cond.out', 'h_cond.out']),
                    ('h_2b', ['h_2b', 'H_2b', 'H_comp.in', 'h_comp.in']),
                ]
                for target_name, variants in target_tests:
                    found = False
                    for variant in variants:
                        if variant in all_cols:
                            val = row_data.get(variant) if hasattr(row_data, 'get') else row_data[variant]
                            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                                lines.append(f"  {target_name}: FOUND as '{variant}' = {val}")
                                found = True
                                break
                    if not found:
                        lines.append(f"  {target_name}: NOT FOUND (tried: {variants})")
                lines.append("")
        
        # Get all required values
        gpm_water = comp_specs.get('gpm_water')
        t_waterin = row_data.get('T_waterin')
        t_waterout = row_data.get('T_waterout')
        
        # Get enthalpies - Calculate from existing table columns if not available
        # h_3a: Calculate from T_3a (compressor outlet temp) and P_disch
        h_3a = None
        # First try to get from stored column (if it exists)
        for col_name in ['h_3a', 'H_3a', 'H_comp.out', 'h_comp.out']:
            val = row_data.get(col_name) if hasattr(row_data, 'get') else None
            if val is None and hasattr(row_data, '__getitem__'):
                try:
                    val = row_data[col_name]
                except (KeyError, IndexError):
                    continue
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                h_3a = val
                if h_3a > 1000:
                    h_3a = h_3a / 1000  # Convert J/kg to kJ/kg
                break
        
        # If not found, calculate from T_3a and P_disch (which ARE in the table)
        if h_3a is None:
            t_3a_f = row_data.get('T_3a') if hasattr(row_data, 'get') else None
            if t_3a_f is None and hasattr(row_data, '__getitem__'):
                try:
                    t_3a_f = row_data['T_3a']
                except (KeyError, IndexError):
                    pass
            
            p_disch_psig = row_data.get('P_disch') if hasattr(row_data, 'get') else None
            if p_disch_psig is None and hasattr(row_data, '__getitem__'):
                try:
                    p_disch_psig = row_data['P_disch']
                except (KeyError, IndexError):
                    pass
            
            if t_3a_f is not None and not math.isnan(t_3a_f) and p_disch_psig is not None and not math.isnan(p_disch_psig):
                try:
                    from CoolProp.CoolProp import PropsSI
                    t_3a_k = (t_3a_f + 459.67) * 5.0 / 9.0
                    p_disch_pa = (p_disch_psig + 14.7) * 6894.76
                    h_3a_jkg = PropsSI('H', 'T', t_3a_k, 'P', p_disch_pa, 'R290')
                    h_3a = h_3a_jkg / 1000  # Convert to kJ/kg
                except:
                    pass
        
        # h_4a: Calculate from T_4a (condenser outlet temp) and P_disch
        h_4a = None
        # First try to get from stored column (if it exists)
        for col_name in ['h_4a', 'H_4a', 'H_cond.out', 'h_cond.out']:
            val = row_data.get(col_name) if hasattr(row_data, 'get') else None
            if val is None and hasattr(row_data, '__getitem__'):
                try:
                    val = row_data[col_name]
                except (KeyError, IndexError):
                    continue
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                h_4a = val
                if h_4a > 1000:
                    h_4a = h_4a / 1000  # Convert J/kg to kJ/kg
                break
        
        # If not found, calculate from T_4a and P_disch (which ARE in the table)
        if h_4a is None:
            t_4a_f = row_data.get('T_4a') if hasattr(row_data, 'get') else None
            if t_4a_f is None and hasattr(row_data, '__getitem__'):
                try:
                    t_4a_f = row_data['T_4a']
                except (KeyError, IndexError):
                    pass
            
            p_disch_psig = row_data.get('P_disch') if hasattr(row_data, 'get') else None
            if p_disch_psig is None and hasattr(row_data, '__getitem__'):
                try:
                    p_disch_psig = row_data['P_disch']
                except (KeyError, IndexError):
                    pass
            
            if t_4a_f is not None and not math.isnan(t_4a_f) and p_disch_psig is not None and not math.isnan(p_disch_psig):
                try:
                    from CoolProp.CoolProp import PropsSI
                    t_4a_k = (t_4a_f + 459.67) * 5.0 / 9.0
                    p_disch_pa = (p_disch_psig + 14.7) * 6894.76
                    h_4a_jkg = PropsSI('H', 'T', t_4a_k, 'P', p_disch_pa, 'R290')
                    h_4a = h_4a_jkg / 1000  # Convert to kJ/kg
                except:
                    pass
        
        # h_2b: Use existing table column H_comp.in (compressor inlet enthalpy)
        h_2b = None
        # Try to get from table column first (H_comp.in exists in the table!)
        for col_name in ['H_comp.in', 'h_2b', 'H_2b', 'h_comp.in']:
            val = row_data.get(col_name) if hasattr(row_data, 'get') else None
            if val is None and hasattr(row_data, '__getitem__'):
                try:
                    val = row_data[col_name]
                except (KeyError, IndexError):
                    continue
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                h_2b = val
                if h_2b > 1000:
                    h_2b = h_2b / 1000  # Convert J/kg to kJ/kg
                break
        
        # If not found, calculate from T_2b and P_suction (existing table columns)
        if h_2b is None:
            t_2b_f = row_data.get('T_2b') if hasattr(row_data, 'get') else None
            if t_2b_f is None and hasattr(row_data, '__getitem__'):
                try:
                    t_2b_f = row_data['T_2b']
                except (KeyError, IndexError):
                    pass
            
            p_suc_psig = row_data.get('P_suction') if hasattr(row_data, 'get') else None
            if p_suc_psig is None and hasattr(row_data, '__getitem__'):
                try:
                    p_suc_psig = row_data['P_suction']
                except (KeyError, IndexError):
                    pass
            
            if t_2b_f is not None and not math.isnan(t_2b_f) and p_suc_psig is not None and not math.isnan(p_suc_psig):
                try:
                    from CoolProp.CoolProp import PropsSI
                    t_2b_k = (t_2b_f + 459.67) * 5.0 / 9.0
                    p_suc_pa = (p_suc_psig + 14.7) * 6894.76
                    h_2b_jkg = PropsSI('H', 'T', t_2b_k, 'P', p_suc_pa, 'R290')
                    h_2b = h_2b_jkg / 1000  # Convert to kJ/kg
                except:
                    pass
        
        # Note: h_4b_lh, h_4b_ctr, h_4b_rh were already retrieved/calculated above in Section 5
        # (lines 1287-1401), so they're already available as local variables for use in Section 6
        
        # Step 1: Water Flow Input
        if not gpm_water or math.isnan(gpm_water):
            lines.append("Step 1 - Water Flow Input:")
            lines.append("  gpm_water = Not set in rated inputs")
            lines.append("  ERROR: Cannot proceed without water flow rate")
            lines.append("")
        else:
            lines.append("Step 1 - Water Flow Input:")
            lines.append(f"  gpm_water = {gpm_water:.4f} GPM")
            lines.append("    This is the water flow rate through the condenser.")
            lines.append("    It tells us how much water is flowing per minute.")
            lines.append("")
        
        # Step 2: Water Temperature Change
        if t_waterin is not None and t_waterout is not None and not math.isnan(t_waterin) and not math.isnan(t_waterout):
            delta_t_water = t_waterout - t_waterin
            lines.append("Step 2 - Water Temperature Change:")
            lines.append(f"  T_water_out = {t_waterout:.2f} °F")
            lines.append(f"  T_water_in  = {t_waterin:.2f} °F")
            lines.append(f"  ΔT_water = T_water_out - T_water_in")
            lines.append(f"  ΔT_water = {t_waterout:.2f} - {t_waterin:.2f} = {delta_t_water:.2f} °F")
            lines.append("    This is how much the water temperature increased.")
            lines.append("    The water got hotter because it absorbed heat from the refrigerant.")
            lines.append("")
        else:
            lines.append("Step 2 - Water Temperature Change:")
            lines.append("  ERROR: Missing water temperature data")
            lines.append("")
        
        # Step 3: Water-Side Heat Rejection (with educational breakdown)
        if gpm_water and t_waterin is not None and t_waterout is not None:
            delta_t_water = t_waterout - t_waterin
            lines.append("Step 3 - Water-Side Heat Rejection (Q_water):")
            lines.append("    The water absorbs heat from the refrigerant in the condenser.")
            lines.append("    We calculate this using the water properties:")
            lines.append("")
            lines.append("    Q_water = density_water × gpm_water × cp_water × ΔT_water")
            lines.append("")
            lines.append("    Where:")
            lines.append("      density_water = 8.34 lb/gal (weight of water per gallon)")
            lines.append("      cp_water = 1.0 BTU/(lb·°F) (heat capacity of water)")
            lines.append("      Conversion factor = 60 min/hr (convert GPM to gallons/hour)")
            lines.append("")
            lines.append("    Combining these:")
            lines.append("      density_water × cp_water × 60 = 8.34 × 1.0 × 60 = 500.4")
            lines.append("")
            lines.append("    So the formula simplifies to:")
            lines.append("      Q_water = 500.4 × gpm_water × ΔT_water")
            lines.append("")
            q_water = 500.4 * gpm_water * delta_t_water
            lines.append(f"    Q_water = 500.4 × {gpm_water:.4f} × {delta_t_water:.2f}")
            lines.append(f"    Q_water = {q_water:.2f} BTU/hr")
            lines.append("")
            lines.append("    This is the total heat rejected by the refrigerant to the water.")
            lines.append("    By conservation of energy, this equals the heat rejected by refrigerant.")
            lines.append("")
        
        # Step 4: Condenser Enthalpy Change (Refrigerant Side)
        # Show step 4 even if values are missing, but indicate the issue
        if h_3a is None or h_4a is None:
            lines.append("Step 4 - Condenser Enthalpy Change (Refrigerant Side):")
            lines.append("  ERROR: Missing enthalpy data")
            if h_3a is None:
                lines.append("    h_3a (Compressor Outlet) not found in calculation results")
            if h_4a is None:
                lines.append("    h_4a (Condenser Outlet) not found in calculation results")
            lines.append("    Cannot calculate mass flow rate without these values.")
            lines.append("")
        elif h_3a is not None and h_4a is not None and not math.isnan(h_3a) and not math.isnan(h_4a):
            lines.append("Step 4 - Condenser Enthalpy Change (Refrigerant Side):")
            lines.append("    The refrigerant loses energy (enthalpy) as it flows through the condenser.")
            lines.append("    This energy is transferred to the water.")
            lines.append("")
            
            # Convert kJ/kg to BTU/lb
            h_3a_jkg = h_3a * 1000  # Convert kJ/kg to J/kg
            h_4a_jkg = h_4a * 1000
            h_3a_btulb = h_3a_jkg * 0.0004299  # Convert J/kg to BTU/lb
            h_4a_btulb = h_4a_jkg * 0.0004299
            delta_h_ref_cond_btulb = h_3a_btulb - h_4a_btulb
            
            lines.append(f"    h_3a (Compressor Outlet) = {h_3a:.3f} kJ/kg")
            lines.append(f"      = {h_3a_jkg:.1f} J/kg")
            lines.append(f"      = {h_3a_btulb:.3f} BTU/lb")
            lines.append("")
            lines.append(f"    h_4a (Condenser Outlet) = {h_4a:.3f} kJ/kg")
            lines.append(f"      = {h_4a_jkg:.1f} J/kg")
            lines.append(f"      = {h_4a_btulb:.3f} BTU/lb")
            lines.append("")
            lines.append(f"    Δh_ref_cond = h_3a - h_4a")
            lines.append(f"    Δh_ref_cond = {h_3a_btulb:.3f} - {h_4a_btulb:.3f}")
            lines.append(f"    Δh_ref_cond = {delta_h_ref_cond_btulb:.3f} BTU/lb")
            lines.append("")
            lines.append("    This is how much enthalpy (energy per pound) the refrigerant lost")
            lines.append("    in the condenser. This energy was transferred to the water.")
            lines.append("")
        
        # Step 5: Mass Flow Rate of Refrigerant (User's Formula)
        # Show step 5 even if values are missing, but indicate the issue
        if not (gpm_water and t_waterin is not None and t_waterout is not None):
            lines.append("Step 5 - Mass Flow Rate of Refrigerant:")
            lines.append("  ERROR: Missing water flow or temperature data")
            lines.append("    Cannot calculate mass flow rate.")
            lines.append("")
        elif h_3a is None or h_4a is None or math.isnan(h_3a) or math.isnan(h_4a):
            lines.append("Step 5 - Mass Flow Rate of Refrigerant:")
            lines.append("  ERROR: Missing condenser enthalpy data (h_3a or h_4a)")
            lines.append("    Cannot calculate mass flow rate without these values.")
            lines.append("")
        elif (gpm_water and t_waterin is not None and t_waterout is not None and 
            h_3a is not None and h_4a is not None and not math.isnan(h_3a) and not math.isnan(h_4a)):
            delta_t_water = t_waterout - t_waterin
            q_water = 500.4 * gpm_water * delta_t_water
            h_3a_jkg = h_3a * 1000
            h_4a_jkg = h_4a * 1000
            h_3a_btulb = h_3a_jkg * 0.0004299
            h_4a_btulb = h_4a_jkg * 0.0004299
            delta_h_ref_cond_btulb = h_3a_btulb - h_4a_btulb
            
            if delta_h_ref_cond_btulb > 0:
                lines.append("Step 5 - Mass Flow Rate of Refrigerant:")
                lines.append("")
                lines.append("    Formula (as specified):")
                lines.append("      massflow_ref = (m × cp × dt) / delta_h_ref")
                lines.append("")
                lines.append("    Where:")
                lines.append("      m = mass flow rate of water (lb/hr)")
                lines.append("      cp = specific heat of water (BTU/(lb·°F))")
                lines.append("      dt = water temperature change (°F)")
                lines.append("      delta_h_ref = enthalpy change of refrigerant in condenser (BTU/lb)")
                lines.append("")
                
                # Calculate mass flow rate of water
                # density_water = 8.34 lb/gal
                # gpm_water is in gallons per minute
                # Convert to lb/hr: 8.34 lb/gal × gpm gal/min × 60 min/hr
                mass_flow_water_lbhr = 8.34 * gpm_water * 60
                cp_water_value = 1.0
                
                lines.append("    First, calculate mass flow rate of water (m):")
                lines.append("      m = density_water × gpm_water × 60 min/hr")
                lines.append(f"      m = 8.34 lb/gal × {gpm_water:.4f} gal/min × 60 min/hr")
                lines.append(f"      m = {mass_flow_water_lbhr:.2f} lb/hr")
                lines.append("")
                
                lines.append("    Now calculate the formula:")
                lines.append("      massflow_ref = (m × cp × dt) / delta_h_ref")
                lines.append("")
                lines.append("    Where:")
                lines.append(f"      m = {mass_flow_water_lbhr:.2f} lb/hr")
                lines.append(f"      cp = {cp_water_value:.1f} BTU/(lb·°F)")
                lines.append(f"      dt = ΔT_water = {delta_t_water:.2f} °F")
                lines.append(f"      delta_h_ref = Δh_ref_cond = {delta_h_ref_cond_btulb:.3f} BTU/lb")
                lines.append("")
                
                # Calculate using the formula
                numerator = mass_flow_water_lbhr * cp_water_value * delta_t_water
                massflow_ref = numerator / delta_h_ref_cond_btulb
                
                lines.append(f"    Calculation:")
                lines.append(f"      massflow_ref = ({mass_flow_water_lbhr:.2f} × {cp_water_value:.1f} × {delta_t_water:.2f}) / {delta_h_ref_cond_btulb:.3f}")
                lines.append(f"      massflow_ref = {numerator:.2f} / {delta_h_ref_cond_btulb:.3f}")
                lines.append(f"      massflow_ref = {massflow_ref:.2f} lb/hr")
                lines.append("")
                lines.append("    Note: This is equivalent to Q_water / delta_h_ref_cond,")
                lines.append("          since Q_water = m × cp × dt")
                lines.append("")
                lines.append("    This is the mass flow rate of refrigerant through the system.")
                lines.append("    It tells us how many pounds of refrigerant flow per hour.")
                lines.append("")
                
                # Step 6: Evaporator Enthalpy Change (with averaging)
                if h_2b is not None and not math.isnan(h_2b):
                    h_4b_values = []
                    if h_4b_lh is not None and not math.isnan(h_4b_lh):
                        h_4b_values.append(h_4b_lh)
                    if h_4b_ctr is not None and not math.isnan(h_4b_ctr):
                        h_4b_values.append(h_4b_ctr)
                    if h_4b_rh is not None and not math.isnan(h_4b_rh):
                        h_4b_values.append(h_4b_rh)
                    
                    if h_4b_values:
                        lines.append("Step 6 - Evaporator Enthalpy Change:")
                        lines.append("    The refrigerant gains energy (enthalpy) in the evaporator.")
                        lines.append("    This energy comes from the air being cooled.")
                        lines.append("")
                        
                        # Convert h_2b to kJ/kg if needed
                        h_2b_kjkg = h_2b if h_2b < 1000 else h_2b / 1000
                        
                        lines.append(f"    h_2b (Compressor Inlet / Evap Outlet) = {h_2b_kjkg:.3f} kJ/kg")
                        h_2b_jkg = h_2b_kjkg * 1000
                        h_2b_btulb = h_2b_jkg * 0.0004299
                        lines.append(f"      = {h_2b_btulb:.3f} BTU/lb")
                        lines.append("")
                        
                        lines.append("    h_4b (TXV Inlets - Before Expansion):")
                        h_4b_list = []
                        h_4b_btulb_list = []
                        for i, h_val in enumerate(h_4b_values):
                            circuit_name = ['LH', 'CTR', 'RH'][i] if i < 3 else f'Circuit {i+1}'
                            h_val_jkg = h_val * 1000
                            h_val_btulb = h_val_jkg * 0.0004299
                            h_4b_list.append(f"{h_val:.3f}")
                            h_4b_btulb_list.append(h_val_btulb)
                            lines.append(f"      h_4b_{circuit_name} = {h_val:.3f} kJ/kg = {h_val_btulb:.3f} BTU/lb")
                        
                        # Calculate average
                        h_4b_avg = sum(h_4b_values) / len(h_4b_values)
                        h_4b_avg_jkg = h_4b_avg * 1000
                        h_4b_avg_btulb = h_4b_avg_jkg * 0.0004299
                        
                        lines.append("")
                        if len(h_4b_values) > 1:
                            h_4b_sum_str = " + ".join([f"{v:.3f}" for v in h_4b_values])
                            lines.append(f"    h_4b_avg = (h_4b_LH + h_4b_CTR + h_4b_RH) / {len(h_4b_values)}")
                            lines.append(f"    h_4b_avg = ({h_4b_sum_str}) / {len(h_4b_values)}")
                            lines.append(f"    h_4b_avg = {h_4b_avg:.3f} kJ/kg = {h_4b_avg_btulb:.3f} BTU/lb")
                            lines.append("")
                            lines.append("    Note: We average the three circuits (LH, CTR, RH) because")
                            lines.append("          they may have slightly different conditions.")
                        else:
                            lines.append(f"    h_4b_avg = {h_4b_avg:.3f} kJ/kg = {h_4b_avg_btulb:.3f} BTU/lb")
                            lines.append("    (Only one circuit available)")
                            lines.append("")
                        
                        delta_h_evap_btulb = h_2b_btulb - h_4b_avg_btulb
                        lines.append(f"    Δh_evap = h_2b - h_4b_avg")
                        lines.append(f"    Δh_evap = {h_2b_btulb:.3f} - {h_4b_avg_btulb:.3f}")
                        lines.append(f"    Δh_evap = {delta_h_evap_btulb:.3f} BTU/lb")
                        lines.append("")
                        lines.append("    This is how much enthalpy (energy per pound) the refrigerant")
                        lines.append("    gained in the evaporator. This energy came from the air.")
                        lines.append("")
                        
                        # Step 7: Cooling Capacity
                        lines.append("Step 7 - Total Cooling Capacity (Q_c):")
                        lines.append("")
                        lines.append("    Formula:")
                        lines.append("      Q_c = massflow_ref × delta_h_evap")
                        lines.append("")
                        lines.append("    This tells us the total cooling capacity: how much heat")
                        lines.append("    the system removes from the air per hour.")
                        lines.append("")
                        
                        q_c = massflow_ref * delta_h_evap_btulb
                        lines.append(f"    Calculation:")
                        lines.append(f"      Q_c = {massflow_ref:.2f} lb/hr × {delta_h_evap_btulb:.3f} BTU/lb")
                        lines.append(f"      Q_c = {q_c:.2f} BTU/hr")
                        lines.append("")
                        
                        # Summary: Show final values from table
                        m_dot_table = row_data.get('m_dot')
                        qc_table = row_data.get('qc')
                        
                        lines.append("=" * 80)
                        lines.append("FINAL VALUES (as displayed in calculation table):")
                        lines.append("=" * 80)
                        lines.append("")
                        if m_dot_table is not None and not math.isnan(m_dot_table):
                            lines.append(f"  m_dot (Mass Flow Rate) = {m_dot_table:.2f} lb/hr")
                            if abs(m_dot_table - massflow_ref) < 0.01:
                                lines.append("    ✓ Matches calculated value")
                            else:
                                lines.append(f"    Calculated value: {massflow_ref:.2f} lb/hr")
                        else:
                            lines.append("  m_dot = Not calculated")
                        
                        if qc_table is not None and not math.isnan(qc_table):
                            lines.append(f"  qc (Cooling Capacity) = {qc_table:.2f} BTU/hr")
                            if abs(qc_table - q_c) < 0.01:
                                lines.append("    ✓ Matches calculated value")
                            else:
                                lines.append(f"    Calculated value: {q_c:.2f} BTU/hr")
                        else:
                            lines.append("  qc = Not calculated")
                        lines.append("")
        
        # Footer
        lines.append("=" * 80)
        lines.append("END OF CALCULATION AUDIT")
        lines.append("=" * 80)
        
        return "\n".join(lines)
