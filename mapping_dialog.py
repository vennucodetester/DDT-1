from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QListWidget, QListWidgetItem, QLabel, QDialogButtonBox,
                             QScrollBar, QLineEdit)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class MappingDialog(QDialog):
    """Simple dialog to map sensors between config and CSV."""
    
    def __init__(self, orphaned_sensors, new_sensors, matched_sensors, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reconcile Sensor Changes")
        self.setMinimumSize(1000, 600)
        
        # Store all sensors
        self.config_sensors = list(orphaned_sensors) + list(matched_sensors)
        self.csv_sensors = list(new_sensors) + list(matched_sensors)
        
        # Pre-map matched sensors
        self.user_mappings = {}
        for sensor in matched_sensors:
            self.user_mappings[sensor] = sensor
        
        # UI state
        self.selected_config_sensor = None
        self.config_search_text = ""
        self.csv_search_text = ""
        
        self.setup_ui()
        self.refresh_lists()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        info = QLabel(
            "<b>CSV Sensor Reconciliation</b><br>"
            "• <span style='color: #4CAF50;'><b>Green sensors</b></span> are already matched between config and CSV<br>"
            "• <span style='color: black;'><b>White sensors</b></span> need mapping: Click config sensor, then CSV sensor to map<br>"
            "• Click a green sensor to unmap it"
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "padding: 10px; background-color: #e3f2fd; "
            "border-radius: 4px; border: 1px solid #90caf9;"
        )
        layout.addWidget(info)
        
        # Search boxes
        search_layout = QHBoxLayout()
        
        # Config search
        config_search_label = QLabel("Config Search:")
        self.config_search_input = QLineEdit()
        self.config_search_input.setPlaceholderText("Filter unmapped config sensors...")
        self.config_search_input.textChanged.connect(self.on_config_search_changed)
        self.config_clear_btn = QPushButton("Clear")
        self.config_clear_btn.clicked.connect(self.clear_config_search)
        
        search_layout.addWidget(config_search_label)
        search_layout.addWidget(self.config_search_input)
        search_layout.addWidget(self.config_clear_btn)
        
        search_layout.addSpacing(20)
        
        # CSV search
        csv_search_label = QLabel("CSV Search:")
        self.csv_search_input = QLineEdit()
        self.csv_search_input.setPlaceholderText("Filter unmapped CSV sensors...")
        self.csv_search_input.textChanged.connect(self.on_csv_search_changed)
        self.csv_clear_btn = QPushButton("Clear")
        self.csv_clear_btn.clicked.connect(self.clear_csv_search)
        
        search_layout.addWidget(csv_search_label)
        search_layout.addWidget(self.csv_search_input)
        search_layout.addWidget(self.csv_clear_btn)
        
        layout.addLayout(search_layout)
        
        # Lists side by side with synchronized scrollbar
        lists_layout = QHBoxLayout()
        
        # Config list
        config_box = QVBoxLayout()
        config_box.addWidget(QLabel("<b>Config Sensors</b>"))
        self.config_list = QListWidget()
        self.config_list.itemClicked.connect(self.on_config_clicked)
        # Hide individual scrollbars - we'll use a shared one
        self.config_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.config_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        config_box.addWidget(self.config_list)
        lists_layout.addLayout(config_box)
        
        # CSV list
        csv_box = QVBoxLayout()
        csv_box.addWidget(QLabel("<b>CSV Sensors</b>"))
        self.csv_list = QListWidget()
        self.csv_list.itemClicked.connect(self.on_csv_clicked)
        # Hide individual scrollbars - we'll use a shared one
        self.csv_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.csv_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        csv_box.addWidget(self.csv_list)
        lists_layout.addLayout(csv_box)
        
        # Shared vertical scrollbar on the right
        self.sync_scrollbar = QScrollBar(Qt.Orientation.Vertical)
        self.sync_scrollbar.valueChanged.connect(self.on_sync_scroll)
        lists_layout.addWidget(self.sync_scrollbar)
        
        layout.addLayout(lists_layout)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        auto_match_btn = QPushButton("🔄 Auto-Match Sensors")
        auto_match_btn.setToolTip("Automatically match sensors based on name similarity")
        auto_match_btn.clicked.connect(self.auto_match_sensors)
        button_layout.addWidget(auto_match_btn)
        
        clear_all_btn = QPushButton("Clear All Mappings")
        clear_all_btn.clicked.connect(self.clear_all_mappings)
        button_layout.addWidget(clear_all_btn)
        
        button_layout.addStretch()
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)
        
        layout.addLayout(button_layout)
    
    def refresh_lists(self):
        """Refresh both lists with current mappings and search filters."""
        self.config_list.clear()
        self.csv_list.clear()
        
        # Separate mapped and unmapped config sensors
        mapped_config = []
        unmapped_config = []
        
        for sensor in self.config_sensors:
            if sensor in self.user_mappings:
                mapped_config.append(sensor)
            else:
                unmapped_config.append(sensor)
        
        # Separate mapped and unmapped CSV sensors
        mapped_csv = []
        unmapped_csv = []
        
        for sensor in self.csv_sensors:
            if sensor in self.user_mappings.values():
                mapped_csv.append(sensor)
            else:
                unmapped_csv.append(sensor)
        
        # Apply search filter to UNMAPPED sensors only
        filtered_unmapped_config = unmapped_config
        if self.config_search_text:
            filtered_unmapped_config = [s for s in unmapped_config if self.config_search_text.lower() in s.lower()]
        
        filtered_unmapped_csv = unmapped_csv
        if self.csv_search_text:
            filtered_unmapped_csv = [s for s in unmapped_csv if self.csv_search_text.lower() in s.lower()]
        
        # Build ALIGNED display lists where mapped pairs appear on the same row
        config_display_list = []
        csv_display_list = []
        
        # Add filtered unmapped sensors with gap at TOP (not middle)
        max_unmapped = max(len(filtered_unmapped_config), len(filtered_unmapped_csv))
        if max_unmapped > 0:
            # Calculate how many placeholders needed at the top for each side
            config_gap = max_unmapped - len(filtered_unmapped_config)
            csv_gap = max_unmapped - len(filtered_unmapped_csv)
            
            # Add gap placeholders at the TOP for the side with fewer sensors
            for i in range(config_gap):
                config_display_list.append(None)
            for i in range(csv_gap):
                csv_display_list.append(None)
            
            # Then add the actual unmapped sensors (aligned at bottom of unmapped section)
            config_display_list.extend(filtered_unmapped_config)
            csv_display_list.extend(filtered_unmapped_csv)
        
        # Add mapped pairs aligned on the same row
        for config_sensor in mapped_config:
            csv_sensor = self.user_mappings[config_sensor]
            config_display_list.append(config_sensor)
            csv_display_list.append(csv_sensor)
        
        # Add config sensors to list
        for sensor in config_display_list:
            if sensor is None:
                # Empty placeholder row
                item = QListWidgetItem("")
                item.setFlags(Qt.ItemFlag.NoItemFlags)  # Make it non-selectable
                item.setBackground(QColor("#f0f0f0"))
            else:
                item = QListWidgetItem(sensor)
                item.setData(Qt.ItemDataRole.UserRole, sensor)
                
                # Color based on mapping status
                if sensor in self.user_mappings:
                    # Mapped = Green (always visible)
                    item.setBackground(QColor("#4CAF50"))
                    item.setForeground(QColor("white"))
                elif sensor == self.selected_config_sensor:
                    # Selected for mapping = Yellow highlight
                    item.setBackground(QColor("#FFF59D"))
                    item.setForeground(QColor("black"))
                else:
                    # Unmapped = White
                    item.setBackground(QColor("white"))
                    item.setForeground(QColor("black"))
            
            self.config_list.addItem(item)
        
        # Add CSV sensors to list
        for sensor in csv_display_list:
            if sensor is None:
                # Empty placeholder row
                item = QListWidgetItem("")
                item.setFlags(Qt.ItemFlag.NoItemFlags)  # Make it non-selectable
                item.setBackground(QColor("#f0f0f0"))
            else:
                item = QListWidgetItem(sensor)
                item.setData(Qt.ItemDataRole.UserRole, sensor)
                
                # Color based on mapping status
                if sensor in self.user_mappings.values():
                    # Mapped = Green (always visible)
                    item.setBackground(QColor("#4CAF50"))
                    item.setForeground(QColor("white"))
                else:
                    # Unmapped = White
                    item.setBackground(QColor("white"))
                    item.setForeground(QColor("black"))
            
            self.csv_list.addItem(item)
        
        # Update synchronized scrollbar range
        config_max = self.config_list.verticalScrollBar().maximum()
        csv_max = self.csv_list.verticalScrollBar().maximum()
        max_range = max(config_max, csv_max)
        self.sync_scrollbar.setMaximum(max_range)
        self.sync_scrollbar.setPageStep(self.config_list.verticalScrollBar().pageStep())
    
    def on_config_clicked(self, item):
        """Select a config sensor for mapping."""
        sensor = item.data(Qt.ItemDataRole.UserRole)
        
        # If already mapped, unmap it
        if sensor in self.user_mappings:
            del self.user_mappings[sensor]
            self.selected_config_sensor = None
            self.refresh_lists()
        else:
            # Select for mapping (yellow highlight)
            self.selected_config_sensor = sensor
            self.refresh_lists()  # Refresh to show selection
    
    def on_csv_clicked(self, item):
        """Map selected config sensor to this CSV sensor."""
        if not self.selected_config_sensor:
            return
        
        csv_sensor = item.data(Qt.ItemDataRole.UserRole)
        
        # Remove any existing mapping to this CSV sensor
        for config, csv in list(self.user_mappings.items()):
            if csv == csv_sensor:
                del self.user_mappings[config]
        
        # Create new mapping
        self.user_mappings[self.selected_config_sensor] = csv_sensor
        self.selected_config_sensor = None
        self.refresh_lists()
    
    def on_sync_scroll(self, value):
        """Synchronize both lists when the shared scrollbar moves."""
        self.config_list.verticalScrollBar().setValue(value)
        self.csv_list.verticalScrollBar().setValue(value)
    
    def on_config_search_changed(self, text):
        """Handle config search text change."""
        self.config_search_text = text
        self.refresh_lists()
    
    def on_csv_search_changed(self, text):
        """Handle CSV search text change."""
        self.csv_search_text = text
        self.refresh_lists()
    
    def clear_config_search(self):
        """Clear config search box."""
        self.config_search_input.clear()
    
    def clear_csv_search(self):
        """Clear CSV search box."""
        self.csv_search_input.clear()
    
    def auto_match_sensors(self):
        """Automatically match sensors based on name similarity."""
        # Get currently unmapped sensors
        unmapped_config = [s for s in self.config_sensors if s not in self.user_mappings]
        unmapped_csv = [s for s in self.csv_sensors if s not in self.user_mappings.values()]
        
        # Levenshtein distance function for similarity
        def levenshtein_distance(s1, s2):
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
            if len(s2) == 0:
                return len(s1)
            previous_row = list(range(len(s2) + 1))
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            return previous_row[-1]
        
        # Calculate similarity scores and find best matches
        new_mappings = {}
        used_csv_sensors = set()
        
        for config_sensor in unmapped_config:
            best_match = None
            best_score = 0.5  # Require at least 50% similarity
            
            for csv_sensor in unmapped_csv:
                if csv_sensor in used_csv_sensors:
                    continue
                
                # Calculate similarity (0-1, where 1 is identical)
                distance = levenshtein_distance(config_sensor.lower(), csv_sensor.lower())
                max_len = max(len(config_sensor), len(csv_sensor))
                similarity = 1 - (distance / max_len) if max_len > 0 else 0
                
                if similarity > best_score:
                    best_score = similarity
                    best_match = csv_sensor
            
            if best_match:
                new_mappings[config_sensor] = best_match
                used_csv_sensors.add(best_match)
                print(f"Auto-matched: {config_sensor} -> {best_match} (similarity: {best_score:.2f})")
        
        # Apply new mappings
        self.user_mappings.update(new_mappings)
        self.refresh_lists()
        
        print(f"Auto-matched {len(new_mappings)} sensor pairs")
    
    def clear_all_mappings(self):
        """Clear all user-created mappings."""
        self.user_mappings.clear()
        self.refresh_lists()
        print("All mappings cleared")
    
    def get_mappings(self):
        """Return the user-created mappings."""
        return self.user_mappings
