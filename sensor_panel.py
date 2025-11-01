from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLineEdit, QCheckBox, QTreeWidget, QTreeWidgetItem, 
                             QLabel, QGroupBox, QFrame, QTreeWidgetItemIterator,
                             QAbstractItemView, QMenu, QInputDialog, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction

class SensorPanel(QWidget):
    """
    Manages the sensor list UI with a full-featured right-click context menu
    for grouping, renaming, and moving sensors.
    """
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.clipboard = [] # Simple clipboard for cut/paste
        self.setupUi()
        self.connect_signals()

    def setupUi(self):
        """Creates and arranges all the widgets for this panel."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)


        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        main_layout.addWidget(content_widget)

        file_ops_group = QGroupBox("File Operations")
        file_ops_layout = QHBoxLayout(file_ops_group)
        self.load_config_button = QPushButton("Load Config")
        self.load_csv_button = QPushButton("Load CSV")
        self.save_config_button = QPushButton("Save Config")
        file_ops_layout.addWidget(self.load_config_button)
        file_ops_layout.addWidget(self.load_csv_button)
        file_ops_layout.addWidget(self.save_config_button)
        # Audit export button (writes two header rows + current filtered data)
        self.export_audit_button = QPushButton("Write Audit CSV")
        file_ops_layout.addWidget(self.export_audit_button)
        content_layout.addWidget(file_ops_group)
        
        controls_group = QGroupBox("Controls")
        controls_layout = QVBoxLayout(controls_group)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search sensors...")
        controls_layout.addWidget(self.search_bar)
        
        # Select all graph checkbox with small text and right-aligned checkbox
        graph_all_layout = QHBoxLayout()
        graph_all_label = QLabel("<small>Graph All</small>")
        graph_all_layout.addWidget(graph_all_label)
        graph_all_layout.addStretch()
        self.select_all_graph_checkbox = QCheckBox()
        self.select_all_graph_checkbox.setTristate(True)  # Allow partially checked state
        self.select_all_graph_checkbox.setToolTip("Check/uncheck all sensors for graphing")
        graph_all_layout.addWidget(self.select_all_graph_checkbox)
        controls_layout.addLayout(graph_all_layout)
        content_layout.addWidget(controls_group)
        
        self.sensor_tree = QTreeWidget()
        self.sensor_tree.setHeaderLabels(["Sensor", "Value", "Graph"])
        self.sensor_tree.setColumnWidth(0, 200)
        self.sensor_tree.setColumnWidth(1, 60)
        # --- NEW: Enable multi-selection with Ctrl and Shift keys ---
        self.sensor_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # --- NEW: Enable the custom context menu ---
        self.sensor_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # --- NEW: Double-click header to collapse/expand all ---
        self.sensor_tree.header().sectionDoubleClicked.connect(self.toggle_expand_all)
        content_layout.addWidget(self.sensor_tree, 1)

        self.stats_label = QLabel("Sensors: 0 | Mapped: 0 | Selected: 0")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_label.setStyleSheet("background-color: #f0f0f0; padding: 8px; border-top: 1px solid #ddd;")
        main_layout.addWidget(self.stats_label)

    def connect_signals(self):
        self.sensor_tree.itemClicked.connect(self.on_item_clicked)
        self.search_bar.textChanged.connect(self.filter_tree_and_select)
        self.sensor_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.select_all_graph_checkbox.stateChanged.connect(self.on_select_all_graph_changed)
        self.export_audit_button.clicked.connect(self.on_export_audit_clicked)

    def on_item_clicked(self, item, column):
        """Handles clicks on tree items."""
        # --- GROUP ITEM CLICKED ---
        if item.childCount() > 0:
            if column == 2:  # Graph checkbox on group
                self.toggle_group_graph(item)
            else:  # Select all sensors in group
                self.select_all_in_group(item)
            return

        # --- SENSOR ITEM CLICKED ---
        sensor_name = item.text(0)
        if column == 2:
            is_checked = item.checkState(2) == Qt.CheckState.Checked
            self.data_manager.set_sensor_graphed(sensor_name, is_checked)
            self.data_manager.data_changed.emit()
        else:
            # Check if Ctrl or Shift is pressed for multi-selection
            from PyQt6.QtWidgets import QApplication
            modifiers = QApplication.keyboardModifiers()
            is_multi_select = (modifiers == Qt.KeyboardModifier.ControlModifier or 
                             modifiers == Qt.KeyboardModifier.ShiftModifier)
            
            self.data_manager.toggle_sensor_selection(sensor_name, multi_select=is_multi_select)
    
    def on_select_all_graph_changed(self, state):
        """Handles the select all graph checkbox toggle."""
        # If partially checked, treat click as "check all"
        if state == Qt.CheckState.PartiallyChecked.value:
            is_checked = True
        else:
            is_checked = state == Qt.CheckState.Checked.value
        
        # Get all sensors
        all_sensors = self.data_manager.get_sensor_list()
        
        # Update all sensors' graph state
        for sensor_name in all_sensors:
            self.data_manager.set_sensor_graphed(sensor_name, is_checked)
        
        # Emit data changed to update UI
        self.data_manager.data_changed.emit()

    def show_context_menu(self, position):
        """Creates and displays the right-click menu."""
        menu = QMenu()
        selected_items = self.sensor_tree.selectedItems()
        item_under_cursor = self.sensor_tree.itemAt(position)

        if not selected_items:
            return

        # --- Menu actions for SENSOR items ---
        if all(item.childCount() == 0 for item in selected_items):
            group_action = QAction("Group Selected Sensors", self)
            group_action.triggered.connect(self.group_selected_sensors)
            menu.addAction(group_action)

            cut_action = QAction("Cut", self)
            cut_action.triggered.connect(self.cut_sensors)
            menu.addAction(cut_action)

        # --- Menu actions for GROUP items ---
        if item_under_cursor and item_under_cursor.childCount() >= 0 and item_under_cursor.parent() is None:
            rename_action = QAction("Rename Group", self)
            rename_action.triggered.connect(lambda: self.rename_group(item_under_cursor))
            menu.addAction(rename_action)

            if self.clipboard:
                paste_action = QAction(f"Paste {len(self.clipboard)} sensor(s)", self)
                paste_action.triggered.connect(lambda: self.paste_sensors(item_under_cursor))
                menu.addAction(paste_action)
            
            delete_action = QAction("Delete Group", self)
            delete_action.triggered.connect(lambda: self.delete_group(item_under_cursor))
            menu.addAction(delete_action)

        if menu.actions():
            menu.exec(self.sensor_tree.viewport().mapToGlobal(position))

    def group_selected_sensors(self):
        """Prompts for a group name and tells the DataManager to group selected sensors."""
        selected_sensors = [item.text(0) for item in self.sensor_tree.selectedItems() if item.childCount() == 0]
        if not selected_sensors:
            return

        text, ok = QInputDialog.getText(self, 'Create Group', 'Enter group name:')
        if ok and text:
            self.data_manager.create_group(text, selected_sensors)

    def rename_group(self, group_item):
        """Prompts for a new name and renames the group in the DataManager."""
        old_name = group_item.text(0)
        new_name, ok = QInputDialog.getText(self, 'Rename Group', 'Enter new name:', text=old_name)
        if ok and new_name and new_name != old_name:
            self.data_manager.rename_group(old_name, new_name)
    
    def delete_group(self, group_item):
        """Deletes the group from the DataManager."""
        group_name = group_item.text(0)
        reply = QMessageBox.question(self, 'Delete Group', 
                                     f'Are you sure you want to delete the group "{group_name}"?\n\nSensors will be moved to Ungrouped.',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.data_manager.delete_group(group_name)

    def cut_sensors(self):
        """Copies selected sensor names to the internal clipboard."""
        self.clipboard = [item.text(0) for item in self.sensor_tree.selectedItems() if item.childCount() == 0]
        print(f"Cut {len(self.clipboard)} sensors to clipboard.")

    def paste_sensors(self, target_group_item):
        """Moves sensors from the clipboard to the target group in the DataManager."""
        if not self.clipboard:
            return
        
        target_group_name = target_group_item.text(0)
        self.data_manager.move_sensors_to_group(target_group_name, self.clipboard)
        self.clipboard.clear()

    def update_ui(self):
        """Redraws the sensor list with groups based on the DataManager's state."""
        # Save expansion states and search text before clearing
        expansion_states = {}
        iterator = QTreeWidgetItemIterator(self.sensor_tree)
        while iterator.value():
            item = iterator.value()
            if item.childCount() > 0:  # Is a group
                expansion_states[item.text(0)] = item.isExpanded()
            iterator += 1
        
        # Save current search text
        current_search = self.search_bar.text()
        
        self.sensor_tree.clear()
        
        all_sensors = set(self.data_manager.get_sensor_list())
        grouped_sensors = set()

        # Create items for each group and its sensors
        for group_name, sensor_list in sorted(self.data_manager.sensor_groups.items()):
            group_item = QTreeWidgetItem(self.sensor_tree, [group_name])
            # Restore expansion state (default to True for new groups)
            group_item.setExpanded(expansion_states.get(group_name, True))
            group_item.setFlags(group_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            group_item.setCheckState(2, Qt.CheckState.Unchecked)  # Start unchecked
            # Subtle background for group headers across all columns
            group_item.setBackground(0, QColor("#e3f2fd"))  # Light blue
            group_item.setBackground(1, QColor("#e3f2fd"))
            group_item.setBackground(2, QColor("#e3f2fd"))
            for sensor_name in sorted(sensor_list):
                if sensor_name in all_sensors:
                    self.create_sensor_item(sensor_name, group_item)
                    grouped_sensors.add(sensor_name)
            self.update_group_checkbox_state(group_item)
        
        # Create "Ungrouped" for any remaining sensors
        ungrouped_list = sorted(list(all_sensors - grouped_sensors))
        if ungrouped_list:
            ungrouped_item = QTreeWidgetItem(self.sensor_tree, ["Ungrouped"])
            ungrouped_item.setExpanded(expansion_states.get("Ungrouped", True))
            ungrouped_item.setFlags(ungrouped_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            ungrouped_item.setCheckState(2, Qt.CheckState.Unchecked)
            ungrouped_item.setBackground(0, QColor("#e3f2fd"))  # Light blue
            ungrouped_item.setBackground(1, QColor("#e3f2fd"))
            ungrouped_item.setBackground(2, QColor("#e3f2fd"))
            for sensor_name in ungrouped_list:
                self.create_sensor_item(sensor_name, ungrouped_item)
            self.update_group_checkbox_state(ungrouped_item)

        self.update_stats()
        
        # Update the "Select All Graph" checkbox state
        self.update_select_all_graph_checkbox()
        
        # Reapply search filter if there was one (don't auto-select when reapplying)
        if current_search:
            self.filter_tree_and_select(current_search, auto_select=False)
        
        # Note: Removed automatic group expansion when sensors are selected
        # Users can manually expand groups as needed
    
    def create_sensor_item(self, sensor_name, parent_item):
        """Helper function to create and configure a single sensor item."""
        sensor_item = QTreeWidgetItem(parent_item)
        sensor_item.setText(0, sensor_name)
        
        # Priority: Selected > Mapped (new diagram roles) > Unmapped (apply to all columns)
        if sensor_name in self.data_manager.selected_sensors:
            color = QColor("#ffc107")  # Yellow for selected
        elif getattr(self.data_manager, 'is_sensor_mapped_in_roles', None) and self.data_manager.is_sensor_mapped_in_roles(sensor_name):
            color = QColor("#c8e6c9")  # Light green for mapped (new diagram roles)
        else:
            color = QColor("#ffccbc")  # Light orange for unmapped
        
        sensor_item.setBackground(0, color)
        sensor_item.setBackground(1, color)
        sensor_item.setBackground(2, color)
        
        # Show sensor number in the Value column
        sensor_number = self.data_manager.get_sensor_number(sensor_name)
        if sensor_number is not None:
            sensor_item.setText(1, str(sensor_number))
        else:
            sensor_item.setText(1, "N/A")
        
        sensor_item.setFlags(sensor_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        if sensor_name in self.data_manager.graph_sensors:
             sensor_item.setCheckState(2, Qt.CheckState.Checked)
        else:
             sensor_item.setCheckState(2, Qt.CheckState.Unchecked)

    def filter_tree_and_select(self, text, auto_select=True):
        """Filters the tree and optionally auto-selects all visible items."""
        if auto_select:
            self.sensor_tree.clearSelection()
        iterator = QTreeWidgetItemIterator(self.sensor_tree)
        is_hidden = text.lower() != ""
        
        # First pass: hide/show sensors based on search
        while iterator.value():
            item = iterator.value()
            if item.childCount() == 0: # Is a sensor item
                matches = text.lower() in item.text(0).lower()
                item.setHidden(is_hidden and not matches)
                if auto_select and not item.isHidden():
                    item.setSelected(True)
            iterator += 1
        
        # Second pass: hide groups that have no visible sensors
        iterator = QTreeWidgetItemIterator(self.sensor_tree)
        while iterator.value():
            item = iterator.value()
            if item.childCount() > 0:  # Is a group item
                # Check if any child sensors are visible
                has_visible_children = False
                for i in range(item.childCount()):
                    child = item.child(i)
                    if not child.isHidden():
                        has_visible_children = True
                        break
                # Hide the group if no children are visible
                item.setHidden(is_hidden and not has_visible_children)
            iterator += 1

    def toggle_expand_all(self, section):
        """Double-click header to collapse/expand all groups."""
        if section == 0:  # Only on first column
            iterator = QTreeWidgetItemIterator(self.sensor_tree)
            # Check if any group is expanded
            any_expanded = False
            while iterator.value():
                item = iterator.value()
                if item.childCount() > 0 and item.isExpanded():
                    any_expanded = True
                    break
                iterator += 1
            
            # Toggle all groups
            iterator = QTreeWidgetItemIterator(self.sensor_tree)
            while iterator.value():
                item = iterator.value()
                if item.childCount() > 0:
                    item.setExpanded(not any_expanded)
                iterator += 1
    
    def select_all_in_group(self, group_item):
        """Selects all sensors in a group."""
        from PyQt6.QtWidgets import QApplication
        modifiers = QApplication.keyboardModifiers()
        is_multi_select = (modifiers == Qt.KeyboardModifier.ControlModifier or 
                         modifiers == Qt.KeyboardModifier.ShiftModifier)
        
        if not is_multi_select:
            self.data_manager.selected_sensors.clear()
        
        for i in range(group_item.childCount()):
            child = group_item.child(i)
            sensor_name = child.text(0)
            self.data_manager.selected_sensors.add(sensor_name)
        
        self.data_manager.data_changed.emit()
    
    def update_group_checkbox_state(self, group_item):
        """Updates group checkbox based on children states."""
        if group_item.childCount() == 0:
            return
        
        all_checked = True
        any_checked = False
        for i in range(group_item.childCount()):
            child = group_item.child(i)
            if child.checkState(2) == Qt.CheckState.Checked:
                any_checked = True
            else:
                all_checked = False
        
        if all_checked:
            group_item.setCheckState(2, Qt.CheckState.Checked)
        elif any_checked:
            group_item.setCheckState(2, Qt.CheckState.PartiallyChecked)
        else:
            group_item.setCheckState(2, Qt.CheckState.Unchecked)
    
    def toggle_group_graph(self, group_item):
        """Toggles graph checkbox for all sensors in a group."""
        # Check if all children are checked
        all_checked = True
        for i in range(group_item.childCount()):
            child = group_item.child(i)
            if child.checkState(2) != Qt.CheckState.Checked:
                all_checked = False
                break
        
        # Toggle all children
        new_state = not all_checked
        for i in range(group_item.childCount()):
            child = group_item.child(i)
            sensor_name = child.text(0)
            self.data_manager.set_sensor_graphed(sensor_name, new_state)
        
        self.data_manager.data_changed.emit()
    
    def ensure_sensor_visible(self, sensor_name):
        """Ensures a sensor is visible by expanding its group if needed."""
        # Find the sensor item in the tree
        iterator = QTreeWidgetItemIterator(self.sensor_tree)
        while iterator.value():
            item = iterator.value()
            # Check if this is the sensor we're looking for
            if item.childCount() == 0 and item.text(0) == sensor_name:
                # Expand the parent group if collapsed
                parent = item.parent()
                if parent and not parent.isExpanded():
                    parent.setExpanded(True)
                # Scroll to make it visible
                self.sensor_tree.scrollToItem(item)
                return
            iterator += 1
    
    def highlight_and_scroll_to_sensor(self, sensor_name):
        """Highlights a sensor and scrolls to it, expanding its group if needed."""
        print(f"[SENSOR HIGHLIGHT] Looking for sensor '{sensor_name}'")
        
        # Clear previous selection first
        self.sensor_tree.clearSelection()
        
        # Find the sensor item in the tree
        iterator = QTreeWidgetItemIterator(self.sensor_tree)
        while iterator.value():
            item = iterator.value()
            # Check if this is the sensor we're looking for
            if item.childCount() == 0 and item.text(0) == sensor_name:
                # Expand the parent group if collapsed
                parent = item.parent()
                if parent:
                    was_expanded = parent.isExpanded()
                    if not was_expanded:
                        print(f"[SENSOR HIGHLIGHT] Group '{parent.text(0)}' is collapsed, expanding...")
                        parent.setExpanded(True)
                        # Force tree widget to update its layout
                        self.sensor_tree.update()
                        self.sensor_tree.repaint()
                        print(f"[SENSOR HIGHLIGHT] Expanded group '{parent.text(0)}' for sensor '{sensor_name}'")
                    else:
                        print(f"[SENSOR HIGHLIGHT] Group '{parent.text(0)}' was already expanded")
                else:
                    print(f"[SENSOR HIGHLIGHT] Sensor has no parent group")
                
                # Scroll to make it visible
                self.sensor_tree.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                
                # Highlight the item by selecting it
                item.setSelected(True)
                
                print(f"[SENSOR HIGHLIGHT] Highlighted and scrolled to sensor '{sensor_name}'")
                return
            iterator += 1
        
        print(f"[SENSOR HIGHLIGHT] Sensor '{sensor_name}' not found in tree")
    
    def update_select_all_graph_checkbox(self):
        """Updates the 'Select All Graph' checkbox based on current graph state."""
        all_sensors = self.data_manager.get_sensor_list()
        if not all_sensors:
            self.select_all_graph_checkbox.setCheckState(Qt.CheckState.Unchecked)
            return
        
        # Check how many sensors are graphed
        graphed_count = len(self.data_manager.graph_sensors)
        total_count = len(all_sensors)
        
        # Block signals to avoid triggering the handler
        self.select_all_graph_checkbox.blockSignals(True)
        
        if graphed_count == total_count:
            # All sensors are graphed
            self.select_all_graph_checkbox.setCheckState(Qt.CheckState.Checked)
        elif graphed_count == 0:
            # No sensors are graphed
            self.select_all_graph_checkbox.setCheckState(Qt.CheckState.Unchecked)
        else:
            # Some sensors are graphed
            self.select_all_graph_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
        
        # Unblock signals
        self.select_all_graph_checkbox.blockSignals(False)

    def update_stats(self):
        total = len(self.data_manager.get_sensor_list())
        # Prefer new mapping system count if available
        if getattr(self.data_manager, 'count_role_mappings', None):
            mapped = self.data_manager.count_role_mappings()
        else:
            mapped = len(self.data_manager.mappings)
        selected = len(self.sensor_tree.selectedItems())
        self.stats_label.setText(f"Sensors: {total} | Mapped: {mapped} | Selected: {selected}")

    def on_export_audit_clicked(self):
        """Write audit_export.csv with two header rows and filtered data (overwrite)."""
        try:
            from PyQt6.QtWidgets import QFileDialog
            # Ask for target path once; default to audit_export.csv
            default_name = "audit_export.csv"
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Audit CSV", default_name, "CSV Files (*.csv)")
            if not file_path:
                return
            if not file_path.lower().endswith('.csv'):
                file_path = file_path + '.csv'
            ok = False
            # Use current time-range; do not restrict to graphed sensors by default; not ON-time only by default
            if hasattr(self.data_manager, 'export_audit_csv'):
                ok = self.data_manager.export_audit_csv(output_path=file_path, include_only_graphed=False, on_time_only=False)
            if ok:
                QMessageBox.information(self, "Audit CSV Saved", f"Wrote audit CSV to:\n{file_path}")
            else:
                QMessageBox.critical(self, "Export Failed", "Failed to write the audit CSV.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error writing audit CSV:\n{e}")

