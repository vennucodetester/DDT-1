import pandas as pd
from pandas.api.types import is_datetime64_any_dtype
import json
import base64
import os
import uuid
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap
from mapping_dialog import MappingDialog
import sys
from timestamp_diagnostics import log_conversion, compare_timestamps, verify_range_selection
from timestamp_fixer import fix_ambiguous_dates

# Force stdout to flush immediately so logs appear in real-time
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

class DataManager(QObject):
    """
    Centralized class to manage all application data, including sensor groups.
    """
    data_changed = pyqtSignal()
    diagram_model_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._reset_state()

    def _reset_state(self):
        """Resets all data to initial state."""
        self.csv_data = None
        self.mappings = {}
        self.selected_sensors = set()
        self.graph_sensors = set()
        self.sensor_groups = {}
        self.group_states = {}  # Format: {group_name: True/False} for expansion state
        self.sensor_ranges = {}  # Format: {sensor_name: {'min': value, 'max': value}}
        self.image_path = None
        self.image_pixmap = None
        self.config_path = None
        self.current_mode = 'mapping'
        self.config_sensor_list = []
        # Preserve original config headers and their mapping to current CSV headers
        self.original_config_sensor_list = []
        self.config_label_mapping = {}

        self.time_range = 'All Data'  # Options: '1 Hour', '3 Hours', '8 Hours', '16 Hours', 'All Data', 'Custom'
        self.value_aggregation = 'Average'  # Options: 'Average', 'Maximum', 'Minimum'
        self.custom_time_range = None  # Stores custom time range as {'start': timestamp, 'end': timestamp}

        # Calculation settings
        self.refrigerant = 'R290'  # Changed from R410A to R290 (Propane) per plan.txt

        # ON-time filtering settings
        self.on_time_threshold_psig = 40.0  # Default threshold for R290 low-temp systems
        self.on_time_filtering_enabled = True
        self.on_time_percentage = 0.0
        self.on_time_row_count = 0
        self.total_row_count = 0
        self.aggregation_method = 'Average'

        # Rated inputs for volumetric efficiency calculation (Step 1 from spec)
        self.rated_inputs = {
            'm_dot_rated_lbhr': None,  # Rated mass flow rate (lbm/hr)
            'hz_rated': None,  # Rated compressor speed (Hz)
            'disp_ft3': None,  # Compressor displacement (ft³)
            'rated_evap_temp_f': None,  # Rated evaporator temperature (°F)
            'rated_return_gas_temp_f': None,  # Rated return gas temperature (°F)
        }

        # Diagram model for refrigeration system designer
        self.diagram_model = {
            "components": {},
            "pipes": {},
            "sensor_roles": {},
            "custom_sensors": {}
        }

    # --- load_csv and reconcile_csv are unchanged ---
    def load_csv(self, file_path):
        """
        Loads a CSV. If a config is already loaded, it triggers
        the reconciliation process.
        """
        try:
            new_csv_data = pd.read_csv(file_path)
            print(f"[LOAD_CSV] CSV columns: {list(new_csv_data.columns)}")
            
            # Handle timestamp column creation
            if 'Timestamp' in new_csv_data.columns:
                # Already has Timestamp column
                try:
                    new_csv_data['Timestamp'] = pd.to_datetime(new_csv_data['Timestamp'], errors='coerce')
                    print(f"[LOAD_CSV] Parsed existing Timestamp column successfully")
                except Exception:
                    print(f"[LOAD_CSV] Failed to parse existing Timestamp column")
                    pass
            elif 'Date' in new_csv_data.columns and 'Time' in new_csv_data.columns:
                # Combine Date and Time columns to create Timestamp
                try:
                    print(f"[LOAD_CSV] Found Date and Time columns, combining them...")
                    print(f"[LOAD_CSV] Sample Date values: {new_csv_data['Date'].head(3).tolist()}")
                    print(f"[LOAD_CSV] Sample Time values: {new_csv_data['Time'].head(3).tolist()}")
                    
                    # Convert Date and Time to strings and combine
                    date_str = new_csv_data['Date'].astype(str)
                    time_str = new_csv_data['Time'].astype(str)
                    timestamp_str = date_str + ' ' + time_str
                    print(f"[LOAD_CSV] Sample combined timestamp strings: {timestamp_str.head(3).tolist()}")
                    
                    # CRITICAL FIX: Use intelligent timestamp fixing
                    print(f"[LOAD_CSV] Using intelligent timestamp fixing...")
                    new_csv_data['Timestamp'] = fix_ambiguous_dates(
                        new_csv_data['Date'], 
                        new_csv_data['Time']
                    )
                    
                    print(f"[LOAD_CSV] Created Timestamp column from Date and Time columns")
                    print(f"[LOAD_CSV] Sample timestamps: {new_csv_data['Timestamp'].head(3).tolist()}")
                    print(f"[LOAD_CSV] Timestamp column created successfully: {new_csv_data['Timestamp'].dtype}")
                    
                    # Verify the timestamp range makes sense
                    if not new_csv_data['Timestamp'].dropna().empty:
                        first_ts = new_csv_data['Timestamp'].dropna().iloc[0]
                        last_ts = new_csv_data['Timestamp'].dropna().iloc[-1]
                        print(f"[LOAD_CSV] Timestamp range: {first_ts} to {last_ts}")
                        print(f"[LOAD_CSV] Duration: {last_ts - first_ts}")
                        
                        # Check for reasonable date range (not in distant future)
                        current_year = pd.Timestamp.now().year
                        if first_ts.year > current_year + 1:
                            print(f"[LOAD_CSV] WARNING: Data appears to be from future year {first_ts.year}")
                            print(f"[LOAD_CSV] This may indicate incorrect year parsing")
                    
                    # DIAGNOSTIC: Log the timestamp creation
                    log_conversion(
                        stage="DATA_LOAD",
                        description="Created Timestamp column from Date+Time",
                        value=new_csv_data['Timestamp'],
                        source_format="Date + Time strings",
                        result_dtype=str(new_csv_data['Timestamp'].dtype),
                        sample_values=new_csv_data['Timestamp'].head(3).tolist()
                    )
                    
                    # Move Timestamp to the front
                    cols = ['Timestamp'] + [col for col in new_csv_data.columns if col not in ['Timestamp', 'Date', 'Time']]
                    new_csv_data = new_csv_data[cols]
                    print(f"[LOAD_CSV] Reordered columns, new shape: {new_csv_data.shape}")
                    print(f"[LOAD_CSV] New column order: {list(new_csv_data.columns[:5])}...")
                except Exception as e:
                    print(f"[LOAD_CSV] Failed to create Timestamp from Date and Time: {e}")
                    import traceback
                    traceback.print_exc()
                    # Fallback: use first column as timestamp if it looks like a datetime
                    first_col = new_csv_data.columns[0]
                    try:
                        new_csv_data['Timestamp'] = pd.to_datetime(new_csv_data[first_col], errors='coerce')
                        print(f"[LOAD_CSV] Created Timestamp from first column: {first_col}")
                    except Exception:
                        print(f"[LOAD_CSV] No suitable timestamp column found")
            else:
                print(f"[LOAD_CSV] No 'Timestamp' column or Date/Time columns found in CSV")
            
            new_sensor_list = [col for col in new_csv_data.columns if col != 'Timestamp'] 

            print(f"[LOAD_CSV] config_path={self.config_path}, config_sensor_list has {len(self.config_sensor_list)} sensors")
            print(f"[LOAD_CSV] new CSV has {len(new_sensor_list)} sensors")
            
            if self.config_path and self.config_sensor_list:
                print(f"[LOAD_CSV] Triggering reconciliation...")
                self.reconcile_csv(new_csv_data, new_sensor_list)
            else:
                print(f"[LOAD_CSV] Skipping reconciliation (no config loaded)")
                self.csv_data = new_csv_data
                self.data_changed.emit()
            return True
        except Exception as e:
            print(f"Error loading CSV file: {e}")
            return False

    def reconcile_csv(self, new_csv_data, new_sensor_list):
        """
        Compares the new CSV against the loaded config and opens a dialog
        for the user to map sensor name changes.
        """
        print(f"[RECONCILE_CSV] Starting reconciliation...")
        print(f"[RECONCILE_CSV] Config has {len(self.config_sensor_list)} sensors")
        print(f"[RECONCILE_CSV] CSV has {len(new_sensor_list)} sensors")
        
        orphaned = sorted([s for s in self.config_sensor_list if s not in new_sensor_list])
        new = sorted([s for s in new_sensor_list if s not in self.config_sensor_list])
        matched = sorted([s for s in self.config_sensor_list if s in new_sensor_list])
        
        print(f"[RECONCILE_CSV] Matched: {len(matched)}, Orphaned: {len(orphaned)}, New: {len(new)}")

        if not orphaned and not new:
            # No changes; ensure original list and identity mapping exist
            if not self.original_config_sensor_list:
                self.original_config_sensor_list = list(self.config_sensor_list)
            if not self.config_label_mapping:
                self.config_label_mapping = {label: label for label in self.original_config_sensor_list}
            self.csv_data = new_csv_data
            self.data_changed.emit()
            return

        dialog = MappingDialog(orphaned, new, matched, parent=self.parent)
        if dialog.exec():
            user_mappings = dialog.get_mappings()  # old_config_name -> new_csv_name
            
            # Update old mappings dict (legacy system)
            new_mappings_dict = {}
            for old_sensor, mapping_data in self.mappings.items():
                if old_sensor in matched:
                    new_mappings_dict[old_sensor] = mapping_data
                elif old_sensor in user_mappings:
                    new_sensor_name = user_mappings[old_sensor]
                    new_mappings_dict[new_sensor_name] = mapping_data
            self.mappings = new_mappings_dict
            
            # Update sensor_roles dict to use new CSV sensor names
            roles = self.diagram_model.get('sensor_roles', {})
            updated_roles = {}
            for role_key, old_sensor_name in roles.items():
                if old_sensor_name in user_mappings:
                    # Remap to new CSV name
                    updated_roles[role_key] = user_mappings[old_sensor_name]
                    print(f"[RECONCILE] Remapped {role_key}: {old_sensor_name} -> {user_mappings[old_sensor_name]}")
                elif old_sensor_name in matched:
                    # Keep matched sensors (identical names)
                    updated_roles[role_key] = old_sensor_name
                else:
                    # Sensor was not matched - PRESERVE the original mapping
                    # (it may exist in the CSV under a different header)
                    updated_roles[role_key] = old_sensor_name
                    print(f"[RECONCILE] PRESERVED unmapped {role_key}: {old_sensor_name} (assuming different column name)")
            self.diagram_model['sensor_roles'] = updated_roles
            print(f"[RECONCILE] Updated sensor_roles: {len(roles)} -> {len(updated_roles)} mappings (all preserved)")
            
            # Update sensor_groups to use new CSV sensor names
            updated_groups = {}
            for group_name, sensor_list in self.sensor_groups.items():
                updated_sensor_list = []
                for old_sensor in sensor_list:
                    if old_sensor in user_mappings:
                        # Remap to new CSV name
                        updated_sensor_list.append(user_mappings[old_sensor])
                        print(f"[RECONCILE] Group '{group_name}': {old_sensor} -> {user_mappings[old_sensor]}")
                    elif old_sensor in matched:
                        # Keep matched sensors
                        updated_sensor_list.append(old_sensor)
                    else:
                        # Sensor was not matched - PRESERVE it (may exist under different header)
                        updated_sensor_list.append(old_sensor)
                        print(f"[RECONCILE] Group '{group_name}': PRESERVED {old_sensor}")
                updated_groups[group_name] = updated_sensor_list
            self.sensor_groups = updated_groups
            print(f"[RECONCILE] Updated sensor_groups (all mappings preserved)")
            
            self.csv_data = new_csv_data
            # Preserve original config list if not already set
            if not self.original_config_sensor_list:
                self.original_config_sensor_list = list(self.config_sensor_list)
            # Build mapping from original config labels to new CSV labels
            mapping = {}
            for label in self.original_config_sensor_list:
                if label in matched:
                    mapping[label] = label
                elif label in user_mappings:
                    mapping[label] = user_mappings[label]
                else:
                    mapping[label] = None
            self.config_label_mapping = mapping
            # Update current config sensor list to the new CSV headers
            self.config_sensor_list = new_sensor_list
            self.diagram_model_changed.emit()
            self.data_changed.emit()

    def load_session(self, file_path):
        """Loads a .json session file with specified UTF-8 encoding."""
        try:
            self._reset_state()
            self.config_path = file_path
            with open(file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            self.mappings = session_data.get('mappings', {})
            # --- UPDATED: Now loads sensor groups from the config file ---
            self.sensor_groups = session_data.get('sensorGroups', {})
            # Load group states (expansion states)
            self.group_states = session_data.get('groupStates', {})
            # Load sensor ranges
            self.sensor_ranges = session_data.get('sensorRanges', {})
            # Load graph sensors (which sensors are checked for graphing)
            self.graph_sensors = set(session_data.get('graphSensors', []))
            # Load rated inputs
            self.rated_inputs = session_data.get('ratedInputs', {
                'm_dot_rated_lbhr': None,
                'hz_rated': None,
                'disp_ft3': None,
                'rated_evap_temp_f': None,
                'rated_return_gas_temp_f': None,
            })

            # Load diagram model - preserve existing structure
            default_diagram_model = {
                "components": {},
                "pipes": {},
                "sensor_roles": {},
                "custom_sensors": {}
            }
            self.diagram_model = session_data.get('diagramModel', default_diagram_model)
            
            # Ensure all required fields exist and are dictionaries
            if 'sensor_roles' not in self.diagram_model or not isinstance(self.diagram_model['sensor_roles'], dict):
                self.diagram_model['sensor_roles'] = {}
            if 'custom_sensors' not in self.diagram_model or not isinstance(self.diagram_model['custom_sensors'], dict):
                self.diagram_model['custom_sensors'] = {}
            if 'components' not in self.diagram_model or not isinstance(self.diagram_model['components'], dict):
                self.diagram_model['components'] = {}
            if 'pipes' not in self.diagram_model or not isinstance(self.diagram_model['pipes'], dict):
                self.diagram_model['pipes'] = {}

            # Clear old sensor mappings when loading new system
            # Keep only the new smart sensor system mappings (sensor_roles)
            sensor_roles = self.diagram_model.get('sensor_roles', {})
            if sensor_roles:
                print(f"[LOAD] Found {len(sensor_roles)} smart sensor mappings")
                # Debug: Print the first few mappings
                for i, (role_key, sensor_name) in enumerate(sensor_roles.items()):
                    if i < 3:  # Show first 3 mappings
                        print(f"[LOAD]   {role_key} -> {sensor_name}")
                    elif i == 3:
                        print(f"[LOAD]   ... and {len(sensor_roles) - 3} more mappings")
                        break
            else:
                print("[LOAD] No smart sensor mappings found - starting fresh")
            
            # Clear old legacy mappings to avoid confusion
            old_mappings_count = len(self.mappings)
            if old_mappings_count > 0:
                print(f"[LOAD] Clearing {old_mappings_count} old legacy mappings")
                self.mappings = {}  # Clear old mappings

            csv_data_obj = session_data.get('csvData')
            if csv_data_obj and 'headers' in csv_data_obj:
                self.config_sensor_list = csv_data_obj.get('headers', [])
            else:
                self.config_sensor_list = session_data.get('csvHeaders', [])

            # Normalize headers: drop only the Timestamp header, not an arbitrary first column
            if self.config_sensor_list:
                if len(self.config_sensor_list) > 0 and self.config_sensor_list[0] == 'Timestamp':
                    self.config_sensor_list = self.config_sensor_list[1:]
                else:
                    self.config_sensor_list = [h for h in self.config_sensor_list if h != 'Timestamp']

            # Always ensure a usable DataFrame exists even if csvPath is present but unreachable
            # This allows sessions to open immediately after saving
            if self.csv_data is None and self.config_sensor_list:
                self.csv_data = pd.DataFrame(columns=['Timestamp'] + self.config_sensor_list)

            # Try to load from imagePath first (highest quality)
            image_path = session_data.get('imagePath')
            if image_path:
                import os
                if os.path.exists(image_path):
                    self.image_pixmap = QPixmap(image_path)
                    print(f"Loaded high-quality image from: {image_path}")
            
            # Fallback to base64 if no file path or file not found
            if not self.image_pixmap or self.image_pixmap.isNull():
                image_data_base64 = session_data.get('imageData')
                if image_data_base64:
                    try:
                        header, encoded = image_data_base64.split(",", 1)
                        image_bytes = base64.b64decode(encoded)
                        pixmap = QPixmap()
                        pixmap.loadFromData(image_bytes, format='PNG')  # Force PNG for best quality
                        if not pixmap.isNull():
                            pixmap.setDevicePixelRatio(1.0)
                        self.image_pixmap = pixmap
                        print("Loaded image from base64 (compressed)")
                    except Exception as e:
                        print(f"Error decoding base64 image data: {e}")

            if self.config_sensor_list and not session_data.get('csvPath'):
                self.csv_data = pd.DataFrame(columns=['Timestamp'] + self.config_sensor_list)
            
            # Preserve original config list and initialize identity mapping for export
            self.original_config_sensor_list = list(self.config_sensor_list)
            self.config_label_mapping = {label: label for label in self.original_config_sensor_list}
            
            # If CSV is already loaded, reconcile sensor names
            if self.csv_data is not None and not self.csv_data.empty:
                current_csv_sensors = [col for col in self.csv_data.columns if col != 'Timestamp']
                if current_csv_sensors and self.config_sensor_list:
                    print(f"[LOAD_SESSION] CSV already loaded. Checking for sensor name differences...")
                    self.reconcile_csv(self.csv_data, current_csv_sensors)
                    return True  # reconcile_csv emits signals
            
            # Don't automatically load CSV - let user load it manually

            self.diagram_model_changed.emit()
            self.data_changed.emit()
            return True
        except Exception as e:
            print(f"Error loading session file: {e}")
            return False

    # --- NEW METHODS FOR GROUP MANAGEMENT ---
    def create_group(self, group_name, sensor_names):
        """Creates a new group or adds sensors to an existing one."""
        if group_name not in self.sensor_groups:
            self.sensor_groups[group_name] = []
        
        # Remove sensors from any other group they might be in
        for name in sensor_names:
            for g_name, g_list in self.sensor_groups.items():
                if name in g_list:
                    g_list.remove(name)

        # Add sensors to the new group
        self.sensor_groups[group_name].extend(sensor_names)
        self.data_changed.emit()

    def rename_group(self, old_name, new_name):
        """Renames an existing sensor group."""
        if old_name in self.sensor_groups and new_name not in self.sensor_groups:
            self.sensor_groups[new_name] = self.sensor_groups.pop(old_name)
            self.data_changed.emit()
    
    def delete_group(self, group_name):
        """Deletes a sensor group. Sensors in the group will become ungrouped."""
        if group_name in self.sensor_groups:
            del self.sensor_groups[group_name]
            self.data_changed.emit()
    
    def set_sensor_ranges(self, ranges_dict):
        """Sets ranges for multiple sensors at once."""
        self.sensor_ranges = ranges_dict
        self.data_changed.emit()
    
    def get_sensor_ranges(self):
        """Returns the current sensor ranges."""
        return self.sensor_ranges
    
    def get_sensor_range(self, sensor_name):
        """Returns the range for a specific sensor, or None if not set."""
        return self.sensor_ranges.get(sensor_name, None)

    def move_sensors_to_group(self, target_group_name, sensor_names):
        """Moves a list of sensors to a specified group."""
        # Remove sensors from their old groups
        for name in sensor_names:
            for g_list in self.sensor_groups.values():
                if name in g_list:
                    g_list.remove(name)
        
        # Add them to the new group
        if target_group_name in self.sensor_groups:
            self.sensor_groups[target_group_name].extend(sensor_names)
        
        self.data_changed.emit()


    # --- Unchanged methods below ---
    def load_image_from_path(self, file_path):
        self.image_path = file_path
        # Load image with high quality settings
        self.image_pixmap = QPixmap(file_path)
        if not self.image_pixmap.isNull():
            # Ensure high DPI scaling for crisp images
            self.image_pixmap.setDevicePixelRatio(1.0)
        self.data_changed.emit()

    def update_mapping(self, sensor_name, x, y):
        if sensor_name not in self.mappings:
            self.mappings[sensor_name] = {}
        self.mappings[sensor_name]['x'] = x
        self.mappings[sensor_name]['y'] = y
    
    def update_mapping_and_notify(self, sensor_name, x, y):
        self.update_mapping(sensor_name, x, y)
        self.data_changed.emit()

    def toggle_sensor_selection(self, sensor_name, multi_select=False):
        """
        Toggle sensor selection.
        
        Args:
            sensor_name: Name of the sensor to toggle
            multi_select: If True, adds/removes from selection. If False, replaces selection.
        """
        if multi_select:
            # Multi-select mode: toggle individual sensor
            if sensor_name in self.selected_sensors:
                self.selected_sensors.discard(sensor_name)
            else:
                self.selected_sensors.add(sensor_name)
        else:
            # Single-select mode: replace selection
            if sensor_name in self.selected_sensors:
                self.selected_sensors.clear()
            else:
                self.selected_sensors.clear()
                self.selected_sensors.add(sensor_name)
        self.data_changed.emit()

    def set_sensor_selected(self, sensor_name, is_selected):
        if is_selected:
            self.selected_sensors.clear()
            self.selected_sensors.add(sensor_name)
        else:
            self.selected_sensors.discard(sensor_name)

    def set_sensor_graphed(self, sensor_name, is_graphed):
        if is_graphed:
            self.graph_sensors.add(sensor_name)
        else:
            self.graph_sensors.discard(sensor_name)

    def get_sensor_list(self):
        if self.csv_data is not None:
            return self.csv_data.columns.tolist()[1:]
        elif self.config_sensor_list:
            return self.config_sensor_list
        return []
    
    def update_refrigerant(self, refrigerant: str):
        """Updates the refrigerant type and notifies listeners."""
        self.refrigerant = refrigerant
        self.data_changed.emit()
    
    def update_aggregation_method(self, method: str):
        """Updates the aggregation method for calculations and notifies listeners."""
        self.aggregation_method = method
        self.data_changed.emit()
    
    def get_current_dataframe(self):
        """Returns the currently filtered dataframe based on time range settings."""
        return self.get_filtered_data()
    
    def get_sensor_number(self, sensor_name):
        """Returns the sequential number (1-based) for a sensor based on the full sensor list."""
        sensor_list = self.get_sensor_list()
        if sensor_name in sensor_list:
            return sensor_list.index(sensor_name) + 1
        return None
    
    def set_time_range(self, time_range):
        """Sets the time range filter for data display."""
        self.time_range = time_range
        self.data_changed.emit()
    
    def set_custom_time_range(self, start_timestamp, end_timestamp):
        """Sets a custom time range and switches to 'Custom' mode."""
        # DIAGNOSTIC: Log the input timestamps
        log_conversion(
            stage="SET_CUSTOM_RANGE_INPUT",
            description="Received start_timestamp for custom range",
            value=start_timestamp,
            timezone=getattr(start_timestamp, 'tzinfo', None),
            is_naive=getattr(start_timestamp, 'tzinfo', None) is None
        )
        log_conversion(
            stage="SET_CUSTOM_RANGE_INPUT",
            description="Received end_timestamp for custom range",
            value=end_timestamp,
            timezone=getattr(end_timestamp, 'tzinfo', None),
            is_naive=getattr(end_timestamp, 'tzinfo', None) is None
        )
        
        self.custom_time_range = {
            'start': start_timestamp,
            'end': end_timestamp
        }
        self.time_range = 'Custom'
        
        # DIAGNOSTIC: Log what was stored
        print(f"[SET_CUSTOM_RANGE] Stored custom range:")
        print(f"  Start: {self.custom_time_range['start']}")
        print(f"  End: {self.custom_time_range['end']}")
        print(f"  Duration: {self.custom_time_range['end'] - self.custom_time_range['start']}")
        
        self.data_changed.emit()
    
    def get_custom_time_range(self):
        """Returns the current custom time range."""
        return self.custom_time_range
    
    def set_value_aggregation(self, aggregation):
        """Sets the value aggregation method (Average, Maximum, Minimum)."""
        self.value_aggregation = aggregation
        self.data_changed.emit()
    
    def filter_by_pressure_threshold(self, threshold_psig):
        """
        Filters time-range filtered data by suction pressure threshold.
        Uses the suction pressure sensor mapped to Compressor SP port.
        Respects the current time_range selection (All Data, 1 Hour, etc).
        
        Args:
            threshold_psig: Minimum suction pressure threshold in PSI
            
        Returns:
            DataFrame with rows where suction pressure >= threshold_psig, or None if sensor not found
        """
        # Get time-range filtered data (respects current time_range selection)
        df = self.get_filtered_data()
        
        if df is None or df.empty:
            print(f"[PRESSURE_FILTER] No time-filtered data available")
            return None
        
        # Find suction pressure sensor from Compressor SP port mapping
        model = self.diagram_model
        components = model.get('components', {})
        suction_sensor = None
        
        # Search for Compressor component and get its SP (suction pressure) port mapping
        for comp_id, comp in components.items():
            if comp.get('type') == 'Compressor':
                from port_resolver import resolve_mapped_sensor
                suction_sensor = resolve_mapped_sensor(model, 'Compressor', comp_id, 'SP')
                if suction_sensor:
                    print(f"[PRESSURE_FILTER] Found suction pressure sensor: {suction_sensor}")
                    break
        
        if not suction_sensor:
            print(f"[PRESSURE_FILTER] ERROR: Suction pressure sensor not mapped to Compressor SP port")
            print(f"[PRESSURE_FILTER] Please map suction pressure sensor in the Diagram tab first")
            return None
        
        if suction_sensor not in df.columns:
            print(f"[PRESSURE_FILTER] ERROR: Sensor '{suction_sensor}' not found in filtered data columns")
            print(f"[PRESSURE_FILTER] Available columns: {list(df.columns)}")
            return None
        
        print(f"[PRESSURE_FILTER] Using sensor: '{suction_sensor}'")
        print(f"[PRESSURE_FILTER] Time range: {self.time_range}")
        print(f"[PRESSURE_FILTER] Threshold: {threshold_psig} PSI")
        
        try:
            # Filter rows where suction pressure < threshold (BELOW threshold)
            filtered_df = df[df[suction_sensor] < threshold_psig].copy()
            
            print(f"[PRESSURE_FILTER] Time-filtered rows: {len(df)}")
            print(f"[PRESSURE_FILTER] Pressure-filtered rows (< {threshold_psig}): {len(filtered_df)} ({len(filtered_df)/len(df)*100:.1f}%)")
            
            return filtered_df
            
        except Exception as e:
            print(f"[PRESSURE_FILTER] ERROR during filtering: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_on_time_filtered_data(self):
        """
        Returns DataFrame with only 'compressor ON' rows.
        Filters by: Suction Pressure > threshold
        """
        df = self.get_filtered_data()  # Get time-filtered data first
        
        if df is None or df.empty:
            return None
        
        if not self.on_time_filtering_enabled:
            # If filtering is disabled, return all data but still calculate stats
            self.on_time_percentage = 100.0
            self.on_time_row_count = len(df)
            self.total_row_count = len(df)
            return df
        
        # Find suction pressure sensor from compressor SP port
        model = self.diagram_model
        components = model.get('components', {})
        suction_sensor = None
        
        for comp_id, comp in components.items():
            if comp.get('type') == 'Compressor':
                from port_resolver import resolve_mapped_sensor
                suction_sensor = resolve_mapped_sensor(model, 'Compressor', comp_id, 'SP')
                if suction_sensor:
                    break
        
        if not suction_sensor or suction_sensor not in df.columns:
            print(f"[ON-TIME] Warning: Suction pressure sensor not mapped or not in CSV")
            # Return all data if sensor not available
            self.on_time_percentage = 100.0
            self.on_time_row_count = len(df)
            self.total_row_count = len(df)
            return df
        
        # Filter rows where suction pressure > threshold
        on_time_df = df[df[suction_sensor] > self.on_time_threshold_psig].copy()
        
        # Calculate % On-Time
        total_rows = len(df)
        on_rows = len(on_time_df)
        on_time_pct = (on_rows / total_rows * 100) if total_rows > 0 else 0
        
        print(f"[ON-TIME] Total rows: {total_rows}, ON rows: {on_rows}, % ON: {on_time_pct:.1f}%")
        print(f"[ON-TIME] Threshold: {self.on_time_threshold_psig} psig, Sensor: {suction_sensor}")
        
        # Store for UI display
        self.on_time_percentage = on_time_pct
        self.on_time_row_count = on_rows
        self.total_row_count = total_rows
        
        return on_time_df
    
    def get_filtered_data(self):
        """
        Returns the CSV data filtered by the current time range.
        Returns the full dataframe if no valid timestamp column or if 'All Data' is selected.
        """
        print(f"[FILTERED_DATA] Called with time_range: {self.time_range}")
        
        if self.csv_data is None or self.csv_data.empty:
            print(f"[FILTERED_DATA] CSV data is None or empty")
            return None
        
        print(f"[FILTERED_DATA] CSV data shape: {self.csv_data.shape}")
        print(f"[FILTERED_DATA] CSV data columns: {list(self.csv_data.columns)[:5]}...")  # Only show first 5 columns
        
        # If "All Data" is selected, return everything (as copy to avoid caching issues)
        if self.time_range == 'All Data':
            print(f"[FILTERED_DATA] Returning all data ({len(self.csv_data)} rows)")
            return self.csv_data.copy()  # FIXED: Return copy instead of reference
        
        # If "Custom" is selected, use custom time range if available
        if self.time_range == 'Custom':
            print(f"[FILTERED_DATA] Custom time range selected")
            if self.custom_time_range and 'Timestamp' in self.csv_data.columns:
                try:
                    df = self.csv_data.copy()
                    
                    # DIAGNOSTIC: Log original data timestamps
                    log_conversion(
                        stage="FILTER_DATA_ORIGINAL",
                        description="Original data timestamps before filtering",
                        value=df['Timestamp'],
                        row_count=len(df)
                    )
                    
                    if not is_datetime64_any_dtype(df['Timestamp']):
                        df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
                    
                    # Convert custom range to pandas timestamps
                    start_time = pd.to_datetime(self.custom_time_range['start'])
                    end_time = pd.to_datetime(self.custom_time_range['end'])
                    
                    # DIAGNOSTIC: Log the converted filter timestamps
                    log_conversion(
                        stage="FILTER_DATA_START",
                        description="Start time after pd.to_datetime conversion",
                        value=start_time,
                        original_value=str(self.custom_time_range['start']),
                        original_type=type(self.custom_time_range['start']).__name__
                    )
                    log_conversion(
                        stage="FILTER_DATA_END",
                        description="End time after pd.to_datetime conversion",
                        value=end_time,
                        original_value=str(self.custom_time_range['end']),
                        original_type=type(self.custom_time_range['end']).__name__
                    )
                    
                    # Compare the filter values with actual data
                    compare_timestamps(
                        "Start time vs First data point",
                        start_time,
                        df['Timestamp'].iloc[0]
                    )
                    compare_timestamps(
                        "End time vs Last data point",
                        end_time,
                        df['Timestamp'].iloc[-1]
                    )
                    
                    print(f"[CUSTOM RANGE] Applying filter: {start_time} to {end_time}")
                    print(f"[CUSTOM RANGE] Data timestamp range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
                    
                    # Apply the filter
                    filtered_df = df[(df['Timestamp'] >= start_time) & (df['Timestamp'] <= end_time)]
                    
                    print(f"[CUSTOM RANGE] Filtered from {start_time} to {end_time}, {len(filtered_df)} rows")
                    if len(filtered_df) > 0:
                        print(f"[CUSTOM RANGE] Filtered data range: {filtered_df['Timestamp'].min()} to {filtered_df['Timestamp'].max()}")
                        
                        # DIAGNOSTIC: Log filtered result
                        log_conversion(
                            stage="FILTER_DATA_RESULT",
                            description="Filtered data timestamps",
                            value=filtered_df['Timestamp'],
                            row_count=len(filtered_df),
                            expected_count=len(df[(df['Timestamp'] >= start_time) & (df['Timestamp'] <= end_time)])
                        )
                        
                        # DIAGNOSTIC: Comprehensive verification
                        verify_range_selection(df, filtered_df, start_time, end_time)
                    else:
                        print(f"[CUSTOM RANGE] WARNING: Filtered result is EMPTY!")
                        # Log why filtering failed
                        print(f"[CUSTOM RANGE] Debug info:")
                        print(f"  Data start: {df['Timestamp'].min()}")
                        print(f"  Data end: {df['Timestamp'].max()}")
                        print(f"  Filter start: {start_time}")
                        print(f"  Filter end: {end_time}")
                        print(f"  Data dtype: {df['Timestamp'].dtype}")
                        print(f"  Filter start dtype: {type(start_time)}")
                        print(f"  Filter end dtype: {type(end_time)}")
                    
                    return filtered_df
                except Exception as e:
                    print(f"[CUSTOM RANGE] Error applying custom range: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[FILTERED_DATA] No custom time range or no Timestamp column, returning all data")
                if not self.custom_time_range:
                    print(f"[FILTERED_DATA] custom_time_range is None")
                if 'Timestamp' not in self.csv_data.columns:
                    print(f"[FILTERED_DATA] Timestamp column not found in CSV data")
            return self.csv_data.copy()
        
        # Check if we have a Timestamp column
        if 'Timestamp' not in self.csv_data.columns:
            print(f"[FILTERED_DATA] No Timestamp column found, returning all data")
            print(f"[FILTERED_DATA] Available columns: {list(self.csv_data.columns)}")
            return self.csv_data.copy()
        
        try:
            # Always work with a fresh copy to avoid any caching issues
            df = self.csv_data.copy()
            
            # Ensure Timestamp column is datetime type
            if not is_datetime64_any_dtype(df['Timestamp']):
                print(f"[FILTERED_DATA] Converting Timestamp column to datetime...")
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
                # Check if conversion was successful
                if df['Timestamp'].isna().all():
                    print(f"[FILTERED_DATA] ERROR: Timestamp conversion failed - all values are NaT")
                    return self.csv_data.copy()
            
            # Get the time range mapping
            time_ranges = {
                '1 Hour': 1,
                '3 Hours': 3,
                '8 Hours': 8,
                '16 Hours': 16
            }
            
            hours = time_ranges.get(self.time_range)
            if hours is None:
                print(f"[FILTERED_DATA] Unknown time range: {self.time_range}, returning all data")
                return self.csv_data.copy()
            
            # Get the last timestamp and calculate the cutoff time
            last_timestamp = df['Timestamp'].max()
            cutoff_time = last_timestamp - pd.Timedelta(hours=hours)
            
            print(f"[DATA FILTER] Time range: {self.time_range} ({hours} hours)")
            print(f"[DATA FILTER] Last timestamp: {last_timestamp}")
            print(f"[DATA FILTER] Cutoff time: {cutoff_time}")
            print(f"[DATA FILTER] Time span: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} to {last_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Filter the data
            filtered_df = df[df['Timestamp'] >= cutoff_time].copy()
            
            # Debug output
            print(f"[DATA FILTER] Total rows: {len(self.csv_data)}, Filtered rows: {len(filtered_df)}")
            
            if len(filtered_df) == 0:
                print(f"[DATA FILTER] WARNING: Filter resulted in 0 rows! Returning all data")
                return self.csv_data.copy()
            
            # Show a sample of the first and last filtered timestamps
            if len(filtered_df) > 0:
                first_ts = filtered_df['Timestamp'].iloc[0]
                last_ts = filtered_df['Timestamp'].iloc[-1]
                print(f"[DATA FILTER] First filtered row: {first_ts}")
                print(f"[DATA FILTER] Last filtered row: {last_ts}")
            
            return filtered_df
            
        except Exception as e:
            print(f"[FILTERED_DATA] ERROR filtering data by time range: {e}")
            import traceback
            traceback.print_exc()
            return self.csv_data.copy()
    
    def get_sensor_value(self, sensor_name):
        """Returns the aggregated value for a sensor from filtered CSV data based on the aggregation method."""
        print(f"[SENSOR_VALUE] Getting value for sensor: {sensor_name}")
        
        filtered_data = self.get_filtered_data()
        print(f"[SENSOR_VALUE] Filtered data status: {filtered_data is not None}")
        if filtered_data is not None:
            print(f"[SENSOR_VALUE] Filtered data shape: {filtered_data.shape}")
            print(f"[SENSOR_VALUE] Filtered data columns: {list(filtered_data.columns)}")
        
        if filtered_data is not None and sensor_name in filtered_data.columns:
            print(f"[SENSOR_VALUE] Sensor found in filtered data")
            sensor_data = filtered_data[sensor_name].dropna()
            print(f"[SENSOR_VALUE] Sensor data after dropna: {len(sensor_data)} values")
            
            if not sensor_data.empty:
                if self.value_aggregation == 'Average':
                    result = sensor_data.mean()
                    print(f"[SENSOR_VALUE] Average calculated: {result}")
                    return result
                elif self.value_aggregation == 'Maximum':
                    result = sensor_data.max()
                    print(f"[SENSOR_VALUE] Maximum calculated: {result}")
                    return result
                elif self.value_aggregation == 'Minimum':
                    result = sensor_data.min()
                    print(f"[SENSOR_VALUE] Minimum calculated: {result}")
                    return result
                else:
                    result = sensor_data.iloc[-1]  # Fallback to last value
                    print(f"[SENSOR_VALUE] Last value: {result}")
                    return result
            else:
                print(f"[SENSOR_VALUE] Sensor data is empty after dropna()")
        else:
            if filtered_data is None:
                print(f"[SENSOR_VALUE] Filtered data is None")
            elif sensor_name not in filtered_data.columns:
                print(f"[SENSOR_VALUE] Sensor '{sensor_name}' not found in filtered data columns")
        
        print(f"[SENSOR_VALUE] Returning None for sensor: {sensor_name}")
        return None

    
    
    def get_data_info(self):
        """
        Returns comprehensive information about the current data state and filtering.
        Used for debugging and displaying data information to users.
        """
        info = {
            'csv_loaded': self.csv_data is not None,
            'csv_path': None,
            'total_rows': 0,
            'filtered_rows': 0,
            'total_columns': 0,
            'time_range': self.time_range,
            'timestamp_range': None,
            'filtered_timestamp_range': None,
            'row_indices': None,
            'has_timestamps': False
        }
        
        if self.csv_data is None:
            return info
        
        # Basic CSV info
        info['total_rows'] = len(self.csv_data)
        info['total_columns'] = len(self.csv_data.columns) - 1  # Exclude timestamp column
        
        # Get filtered data
        filtered_data = self.get_filtered_data()
        if filtered_data is not None:
            info['filtered_rows'] = len(filtered_data)
            
            # Get row indices being used
            if not filtered_data.empty:
                info['row_indices'] = f"{filtered_data.index[0] + 2}-{filtered_data.index[-1] + 2}"  # +2 for Excel-style (1-indexed + header)
        
        # Timestamp information
        if 'Timestamp' in self.csv_data.columns:
            info['has_timestamps'] = True
            try:
                # Full data timestamp range
                timestamps = pd.to_datetime(self.csv_data['Timestamp'])
                info['timestamp_range'] = {
                    'start': timestamps.min(),
                    'end': timestamps.max()
                }
                
                # Filtered data timestamp range
                if filtered_data is not None and not filtered_data.empty:
                    filtered_timestamps = pd.to_datetime(filtered_data['Timestamp'])
                    info['filtered_timestamp_range'] = {
                        'start': filtered_timestamps.min(),
                        'end': filtered_timestamps.max()
                    }
            except Exception as e:
                print(f"Error parsing timestamps: {e}")
        
        return info
    
    def get_sensor_detailed_info(self, sensor_name):
        """
        Returns detailed information about a specific sensor including the data being used.
        """
        info = {
            'sensor_name': sensor_name,
            'sensor_number': self.get_sensor_number(sensor_name),
            'displayed_value': None,
            'aggregation_method': self.value_aggregation,
            'data_points': 0,
            'row_range': None,
            'column_letter': None,
            'min_value': None,
            'max_value': None,
            'avg_value': None
        }
        
        filtered_data = self.get_filtered_data()
        if filtered_data is None or sensor_name not in filtered_data.columns:
            return info
        
        sensor_data = filtered_data[sensor_name].dropna()
        if sensor_data.empty:
            return info
        
        # Get column letter (Excel-style)
        sensor_list = self.get_sensor_list()
        if sensor_name in sensor_list:
            col_index = sensor_list.index(sensor_name) + 1  # +1 because timestamp is column A
            info['column_letter'] = self._index_to_excel_column(col_index)
        
        # Calculate statistics
        info['min_value'] = sensor_data.min()
        info['max_value'] = sensor_data.max()
        info['avg_value'] = sensor_data.mean()
        info['data_points'] = len(sensor_data)
        
        # Get displayed value based on aggregation method
        info['displayed_value'] = self.get_sensor_value(sensor_name)
        
        # Get row range
        first_row = sensor_data.index[0] + 2  # +2 for Excel-style (1-indexed + header)
        last_row = sensor_data.index[-1] + 2
        info['row_range'] = f"{first_row}-{last_row}"
        
        return info
    
    def save_session(self, file_path):
        """
        Saves the current session state to a JSON file with the same structure as the original.
        Includes high-resolution image data optimized for reasonable file size.
        """
        try:
            from datetime import datetime
            import tempfile
            
            # Prepare session data - match original JSON structure exactly
            sanitized_diagram = self._sanitize_diagram_model(self.diagram_model)
            session_data = {
                "name": os.path.splitext(os.path.basename(file_path))[0],
                "timestamp": datetime.now().isoformat() + "Z",
                "csvPath": os.path.basename(getattr(self, 'csv_path', 'data.csv')),
                "csvData": self._prepare_csv_data(),
                "imagePath": self._prepare_image_data(),
                "imageData": self._prepare_image_base64(),
                "mappings": self._prepare_mappings_with_ranges(),
                "sensorGroups": self._prepare_sensor_groups(),
                "groupStates": self._prepare_group_states(),
                "ratedInputs": self.rated_inputs,  # Save rated inputs for volumetric efficiency calculation
                "diagramModel": sanitized_diagram,  # Save diagram designer data (sanitized)
                "graphSensors": list(self.graph_sensors),  # Save which sensors are checked for graphing
                "ui": {
                    "selectedSensors": list(self.selected_sensors),
                    "currentMode": self.current_mode,
                    "selectedTimeRange": self.time_range
                }
            }
            
            # Atomic write: write to a temp file in the same directory, then replace
            target_dir = os.path.dirname(file_path) or "."
            base_name = os.path.basename(file_path)
            tmp_path = os.path.join(target_dir, f".{base_name}.tmp")

            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            # Replace the target file atomically
            os.replace(tmp_path, file_path)
            
            print(f"Session saved successfully to: {file_path}")
            return True
            
        except Exception as e:
            print(f"Error saving session: {e}")
            return False
            
    def _sanitize_diagram_model(self, diagram_model):
        """Ensure all values in diagramModel are JSON-serializable (no QPointF)."""
        def to_xy_list(pos):
            try:
                if hasattr(pos, 'x') and hasattr(pos, 'y'):
                    return [pos.x(), pos.y()]
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    return [float(pos[0]), float(pos[1])]
            except Exception:
                pass
            return pos

        out = {"components": {}, "pipes": {}}
        comps = diagram_model.get("components", {}) or {}
        for cid, cdata in comps.items():
            ccopy = dict(cdata)
            if 'position' in ccopy:
                ccopy['position'] = to_xy_list(ccopy['position'])
            out["components"][cid] = ccopy
        pipes = diagram_model.get("pipes", {}) or {}
        for pid, pdata in pipes.items():
            pcopy = dict(pdata)
            if 'waypoints' in pcopy and isinstance(pcopy['waypoints'], list):
                new_wps = []
                for wp in pcopy['waypoints']:
                    new_wps.append(to_xy_list(wp))
                pcopy['waypoints'] = new_wps
            out["pipes"][pid] = pcopy
        # Pass through optional properties
        if isinstance(diagram_model, dict):
            for k in diagram_model.keys():
                if k not in out:
                    out[k] = diagram_model[k]
        return out

    # === SENSOR ROLE MAPPING API ===
    def map_sensor_to_role(self, role_key, sensor_name):
        """Map a sensor name to a canonical role key in the diagram model.
        
        Ensures that:
        1. One sensor can only be mapped to one role at a time
        2. If sensor is already mapped to a different role, it gets unmapped from that role first
        3. One role can only have one sensor mapped to it
        """
        if 'sensor_roles' not in self.diagram_model or not isinstance(self.diagram_model['sensor_roles'], dict):
            self.diagram_model['sensor_roles'] = {}
        
        roles = self.diagram_model['sensor_roles']
        print(f"[MAP] Current mappings before operation: {len(roles)}")
        print(f"[MAP] Attempting to map {sensor_name} to {role_key}")
        
        # Check if sensor is already mapped to any different roles (find ALL duplicates)
        existing_roles = []
        for existing_role_key, existing_sensor in roles.items():
            if existing_sensor == sensor_name and existing_role_key != role_key:
                existing_roles.append(existing_role_key)
        
        # Check if the target role already has a different sensor mapped to it
        existing_sensor_in_role = roles.get(role_key)
        if existing_sensor_in_role and existing_sensor_in_role != sensor_name:
            print(f"[MAP] Role {role_key} already has sensor {existing_sensor_in_role} mapped to it")
            print(f"[MAP] Automatically replacing {existing_sensor_in_role} with {sensor_name}")
            # Don't delete the role_key, we'll overwrite it below
        
        # If sensor is already mapped to different roles, unmap from ALL of them
        if existing_roles:
            print(f"[MAP] Sensor {sensor_name} already mapped to {len(existing_roles)} role(s), unmapping all:")
            for old_role in existing_roles:
                print(f"[MAP]   - Unmapping from {old_role}")
                del roles[old_role]
        
        # Map the sensor to the new role (this ensures one-to-one mapping)
        roles[role_key] = sensor_name
        
        print(f"[MAP] Successfully mapped {sensor_name} to {role_key}")
        print(f"[MAP] Total mappings after operation: {len(roles)}")
        
        # Validate the mapping is correct (only during mapping operations)
        self._validate_sensor_mappings()
        
        print(f"[MAP] Total mappings after validation: {len(roles)}")
        
        self.diagram_model_changed.emit()
        self.data_changed.emit()
    
    def export_audit_csv(self, output_path: str = "audit_export.csv", include_only_graphed: bool = False, on_time_only: bool = False):
        """
        Writes a lightweight audit CSV that you can open in Excel to visually validate:
        - Row 1: Config labels (Timestamp + config sensor list order)
        - Row 2: CSV labels (Timestamp + actual CSV column names mapped to those config labels)
        - Rows 3+: Data from the current filtered DataFrame (or ON-time subset),
                    restricted to the chosen columns, overwriting the file each time.

        Args:
            output_path: Target CSV path to overwrite.
            include_only_graphed: If True, restrict columns to sensors currently checked for graphing.
            on_time_only: If True, use ON-time filtered data; otherwise use time-range filtered data.
        """
        try:
            import csv
            # Determine original config labels for Row 1 (exclude Timestamp)
            base_labels = []
            if getattr(self, 'original_config_sensor_list', None):
                base_labels = [label for label in self.original_config_sensor_list if label != 'Timestamp']
            elif self.config_sensor_list:
                base_labels = [label for label in self.config_sensor_list if label != 'Timestamp']
            elif self.csv_data is not None and not self.csv_data.empty:
                base_labels = list(self.csv_data.columns[1:])
            config_labels = base_labels

            # Optionally restrict to graphed sensors
            if include_only_graphed and self.graph_sensors:
                config_labels = [s for s in config_labels if s in self.graph_sensors]

            # Build CSV labels row based on actual dataframe columns available
            df_source = None
            if on_time_only:
                df_source = self.get_on_time_filtered_data()
                print(f"[AUDIT EXPORT] Using ON-time filtered data: {len(df_source) if df_source is not None else 0} rows")
            else:
                df_source = self.get_filtered_data()
                print(f"[AUDIT EXPORT] Using time-range filtered data: {len(df_source) if df_source is not None else 0} rows")
                print(f"[AUDIT EXPORT] Current time_range setting: {self.time_range}")

            if df_source is None:
                df_source = self.csv_data if self.csv_data is not None else None
                print(f"[AUDIT EXPORT] Fallback to full CSV data: {len(df_source) if df_source is not None else 0} rows")

            # Row 2 values: mapped CSV labels for each original config label
            csv_labels = []
            if getattr(self, 'config_label_mapping', None):
                for label in config_labels:
                    mapped = self.config_label_mapping.get(label)
                    csv_labels.append(mapped if mapped in (df_source.columns if (df_source is not None and not df_source.empty) else []) else (mapped or ""))
            else:
                # Fallback: identity mapping if no mapping stored
                for label in config_labels:
                    csv_labels.append(label)

            # Final column order: Timestamp + chosen labels
            header_config = ['Timestamp'] + config_labels
            header_csv = ['Timestamp'] + csv_labels

            # Prepare data rows from df_source restricted to these columns if available
            data_rows = []
            if df_source is not None and not df_source.empty:
                # Ensure Timestamp exists; if missing, synthesize empty column for alignment
                temp_df = df_source.copy()
                if 'Timestamp' not in temp_df.columns:
                    temp_df.insert(0, 'Timestamp', None)
                # Reorder/select columns; missing columns will be filled with empty values
                for _, row in temp_df.iterrows():
                    values = []
                    # Timestamp first
                    ts_val = row.get('Timestamp')
                    values.append(ts_val if ts_val is not pd.NaT else '')
                    # Then per config label
                    for original_label, mapped_label in zip(config_labels, csv_labels):
                        col_name = mapped_label if mapped_label else original_label
                        values.append(row.get(col_name, ''))
                    data_rows.append(values)

            # Write CSV (overwrite) - handle file locking issues
            try:
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(header_config)
                    writer.writerow(header_csv)
                    writer.writerows(data_rows)
            except PermissionError:
                # If file is locked, try with a different name
                import time
                timestamp = int(time.time())
                backup_path = f"{output_path}.{timestamp}"
                print(f"[AUDIT EXPORT] Permission denied, trying backup path: {backup_path}")
                with open(backup_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(header_config)
                    writer.writerow(header_csv)
                    writer.writerows(data_rows)
                output_path = backup_path

            print(f"[AUDIT EXPORT] Wrote {len(data_rows)} data rows to {output_path}")
            print(f"[AUDIT EXPORT] Row1 (config): {header_config[:6]}{'...' if len(header_config) > 6 else ''}")
            print(f"[AUDIT EXPORT] Row2 (csv):    {header_csv[:6]}{'...' if len(header_csv) > 6 else ''}")
            return True
        except Exception as e:
            print(f"[AUDIT EXPORT] Error writing CSV: {e}")
            return False

    def _validate_sensor_mappings(self):
        """Validate that sensor mappings are one-to-one (no duplicates).
        
        This method only logs duplicate mappings but doesn't remove them.
        Duplicates are allowed to exist (e.g., from JSON files) and will only
        be cleaned up when there's an actual mapping conflict.
        """
        roles = self.diagram_model.get('sensor_roles', {})
        original_count = len(roles)
        print(f"[VALIDATION] Starting validation with {original_count} mappings")
        
        # Check for duplicate sensors but don't remove them
        sensor_to_roles = {}
        duplicates_found = []
        
        for role_key, sensor_name in roles.items():
            if sensor_name in sensor_to_roles:
                duplicates_found.append((sensor_name, sensor_to_roles[sensor_name], role_key))
                print(f"[VALIDATION INFO] Sensor {sensor_name} is mapped to multiple roles: {sensor_to_roles[sensor_name]} and {role_key}")
            else:
                sensor_to_roles[sensor_name] = role_key
        
        if duplicates_found:
            print(f"[VALIDATION INFO] Found {len(duplicates_found)} sensors mapped to multiple roles")
            print(f"[VALIDATION INFO] This is normal when loading from JSON files - duplicates will be handled during mapping operations")
        else:
            print(f"[VALIDATION INFO] No duplicate sensor mappings found")
        
        print(f"[VALIDATION] Sensor mappings preserved: {len(roles)} total mappings")

    def unmap_role(self, role_key):
        """Remove mapping for a role key if present."""
        roles = self.diagram_model.get('sensor_roles', {})
        if role_key in roles:
            del roles[role_key]
            self.diagram_model_changed.emit()
            self.data_changed.emit()
    
    def clear_all_sensor_mappings(self):
        """Clear all sensor mappings (both old and new system)."""
        # Clear new smart sensor system mappings
        if 'sensor_roles' in self.diagram_model:
            old_count = len(self.diagram_model['sensor_roles'])
            self.diagram_model['sensor_roles'] = {}
            print(f"[CLEAR] Cleared {old_count} smart sensor mappings")
        
        # Clear old legacy mappings
        old_mappings_count = len(self.mappings)
        self.mappings = {}
        if old_mappings_count > 0:
            print(f"[CLEAR] Cleared {old_mappings_count} legacy mappings")
        
        self.diagram_model_changed.emit()
        self.data_changed.emit()
        print("[CLEAR] All sensor mappings cleared - all sensors will appear orange (unmapped)")

    def get_mapped_sensor_for_role(self, role_key):
        roles = self.diagram_model.get('sensor_roles', {})
        return roles.get(role_key)

    def is_sensor_mapped_in_roles(self, sensor_name):
        """Return True if sensor_name appears as a value in diagram_model.sensor_roles."""
        try:
            roles = self.diagram_model.get('sensor_roles', {})
            return any(mapped == sensor_name for mapped in roles.values())
        except Exception:
            return False
    
    def get_custom_sensor_roles_for_sensor(self, sensor_name):
        """Return list of custom sensor role keys (sensor IDs) that are mapped to this sensor."""
        roles = self.diagram_model.get('sensor_roles', {})
        custom_roles = []
        for role_key, mapped_sensor in roles.items():
            # Check if this is a custom sensor role (starts with 'custom_') and maps to our sensor
            if role_key.startswith('custom_') and mapped_sensor == sensor_name:
                custom_roles.append(role_key)
        return custom_roles

    def count_role_mappings(self):
        """Return count of unique sensors mapped in diagram_model.sensor_roles."""
        try:
            roles = self.diagram_model.get('sensor_roles', {})
            return len(set(roles.values()))
        except Exception:
            return 0
    
    def get_sensor_mapping_status(self, sensor_name):
        """Get the mapping status for a specific sensor."""
        roles = self.diagram_model.get('sensor_roles', {})
        
        # Find which role this sensor is mapped to
        mapped_role = None
        for role_key, mapped_sensor in roles.items():
            if mapped_sensor == sensor_name:
                mapped_role = role_key
                break
        
        return {
            'sensor_name': sensor_name,
            'is_mapped': mapped_role is not None,
            'mapped_to_role': mapped_role,
            'total_mappings': len(roles)
        }
    
    def debug_sensor_mappings(self):
        """Print debug information about all sensor mappings."""
        roles = self.diagram_model.get('sensor_roles', {})
        print(f"[DEBUG] Total sensor mappings: {len(roles)}")
        
        for role_key, sensor_name in roles.items():
            print(f"  {role_key} -> {sensor_name}")
        
        # Check for duplicates
        sensor_counts = {}
        for sensor_name in roles.values():
            sensor_counts[sensor_name] = sensor_counts.get(sensor_name, 0) + 1
        
        duplicates = {sensor: count for sensor, count in sensor_counts.items() if count > 1}
        if duplicates:
            print(f"[DEBUG] WARNING: Duplicate sensor mappings found: {duplicates}")
        else:
            print(f"[DEBUG] No duplicate mappings found - all mappings are unique")

    def merge_sessions_to_file(self, file_path_a, file_path_b, output_file_path):
        """Merges two session JSON files and saves the combined result to output_file_path."""
        try:
            with open(file_path_a, 'r', encoding='utf-8') as fa:
                session_a = json.load(fa)
            with open(file_path_b, 'r', encoding='utf-8') as fb:
                session_b = json.load(fb)
            merged = self._merge_sessions_data(session_a, session_b)
            with open(output_file_path, 'w', encoding='utf-8') as fo:
                json.dump(merged, fo, indent=2, ensure_ascii=False)
            print(f"Merged sessions saved to: {output_file_path}")
            return True
        except Exception as e:
            print(f"Error merging sessions: {e}")
            return False

    def _merge_sessions_data(self, session_a, session_b):
        """Merge two in-memory session dicts into one combined dict.
        Preference: values from B override A on conflicts.
        """
        from datetime import datetime

        def get_headers(sess):
            csv_obj = sess.get('csvData') or {}
            headers = csv_obj.get('headers') or sess.get('csvHeaders') or []
            return headers

        def merge_mappings(map_a, map_b):
            out = dict(map_a or {})
            for k, v in (map_b or {}).items():
                out[k] = v
            return out

        def merge_ranges(r_a, r_b):
            out = dict(r_a or {})
            for k, v in (r_b or {}).items():
                out[k] = v
            return out

        def merge_groups(g_a, g_b):
            out = {}
            for g, lst in (g_a or {}).items():
                out[g] = list(dict.fromkeys(lst))
            for g, lst in (g_b or {}).items():
                if g in out:
                    combined = list(dict.fromkeys(out[g] + lst))
                    out[g] = combined
                else:
                    out[g] = list(dict.fromkeys(lst))
            return out

        def merge_group_states(s_a, s_b):
            out = dict(s_a or {})
            for g, state in (s_b or {}).items():
                out[g] = bool(state) or bool(out.get(g, False))
            return out

        def choose_diagram(a, b):
            diag_a = (a or {}).get('diagramModel') or {}
            diag_b = (b or {}).get('diagramModel') or {}
            # Prefer the one that actually has components/pipes
            def has_content(diag):
                return bool(diag.get('components')) or bool(diag.get('pipes'))
            if has_content(diag_b):
                return diag_b
            if has_content(diag_a):
                return diag_a
            return {}

        def choose_image_path(a, b):
            path_b = b.get('imagePath') if isinstance(b, dict) else None
            path_a = a.get('imagePath') if isinstance(a, dict) else None
            return path_b or path_a

        def choose_image_data(a, b):
            data_b = b.get('imageData') if isinstance(b, dict) else None
            data_a = a.get('imageData') if isinstance(a, dict) else None
            return data_b or data_a

        mappings = merge_mappings(session_a.get('mappings'), session_b.get('mappings'))
        sensor_ranges = merge_ranges(session_a.get('sensorRanges'), session_b.get('sensorRanges'))
        sensor_groups = merge_groups(session_a.get('sensorGroups'), session_b.get('sensorGroups'))
        group_states = merge_group_states(session_a.get('groupStates'), session_b.get('groupStates'))

        # CSV headers: prefer available headers; fallback to mapping keys
        headers = get_headers(session_a) or get_headers(session_b)
        if not headers:
            if mappings:
                headers = ["Timestamp"] + sorted(list(mappings.keys()))
            else:
                headers = []

        # CSV data: preserve csvData object from the session that has it
        csv_data_obj = session_a.get('csvData') or session_b.get('csvData') or None
        if csv_data_obj and csv_data_obj.get('headers'):
            merged_csv = csv_data_obj
        else:
            merged_csv = {"headers": headers, "data": [], "rows": 0, "fileName": session_a.get('csvPath') or session_b.get('csvPath') or ""}

        merged = {
            "name": "merged_session",
            "timestamp": datetime.now().isoformat() + "Z",
            "csvPath": session_b.get('csvPath') or session_a.get('csvPath') or "",
            "csvData": merged_csv,
            "imagePath": choose_image_path(session_a, session_b),
            "imageData": choose_image_data(session_a, session_b),
            "mappings": mappings,
            "sensorGroups": sensor_groups,
            "groupStates": group_states,
            "sensorRanges": sensor_ranges,
            "diagramModel": choose_diagram(session_a, session_b),
            "ui": session_b.get('ui') or session_a.get('ui') or {"selectedSensors": [], "currentMode": "mapping", "selectedTimeRange": "All Data"}
        }

        # Carry through any optional diagram properties if present
        if 'diagramModel' in merged and isinstance(merged['diagramModel'], dict):
            merged['diagramModel'].setdefault('properties', (session_b.get('diagramModel', {}) or session_a.get('diagramModel', {})).get('properties', {}))

        return merged

    def _prepare_csv_data(self):
        """Prepares minimal CSV metadata for saving.
        To ensure compatibility and avoid non-serializable timestamp values,
        we include headers and row count only; data is left empty.
        """
        # Get sensor names from either CSV data or config sensor list
        sensor_names = []
        if self.csv_data is not None and not self.csv_data.empty:
            sensor_names = list(self.csv_data.columns[1:])  # Exclude timestamp column
        elif self.config_sensor_list:
            sensor_names = [name for name in self.config_sensor_list if name != "Timestamp"]

        headers = ["Timestamp"] + sensor_names if sensor_names else []
        rows = len(self.csv_data) if (self.csv_data is not None and not self.csv_data.empty) else 0

        return {
            "headers": headers,
            "data": [],  # Intentionally empty to avoid timestamp serialization issues
            "rows": rows,
            "fileName": os.path.basename(getattr(self, 'csv_path', 'data.csv'))
        }
    
    def _prepare_image_data(self):
        """Prepares image path for saving."""
        if self.image_path:
            return os.path.basename(self.image_path)
        return None
    
    def _prepare_image_base64(self):
        """Prepares base64 encoded image data with size optimization."""
        if self.image_pixmap is None:
            return None
        
        try:
            from PyQt6.QtCore import Qt, QBuffer, QIODevice
            
            # Convert QPixmap to QImage for processing
            qimage = self.image_pixmap.toImage()
            
            # Optimize image size while maintaining quality
            # Scale down if image is very large (>2000px on longest side)
            max_dimension = 2000
            if qimage.width() > max_dimension or qimage.height() > max_dimension:
                scale_factor = max_dimension / max(qimage.width(), qimage.height())
                new_width = int(qimage.width() * scale_factor)
                new_height = int(qimage.height() * scale_factor)
                qimage = qimage.scaled(new_width, new_height, 
                                     Qt.AspectRatioMode.KeepAspectRatio, 
                                     Qt.TransformationMode.SmoothTransformation)
            
            # Convert to PNG format with reasonable compression
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            qimage.save(buffer, "PNG", quality=85)  # 85% quality for good balance
            
            # Convert to base64
            image_data = buffer.data()
            base64_data = base64.b64encode(image_data).decode('utf-8')
            
            return f"data:image/png;base64,{base64_data}"
            
        except Exception as e:
            print(f"Error preparing image data: {e}")
            return None
    
    def _prepare_mappings_with_ranges(self):
        """Prepares mappings with ranges embedded in each mapping."""
        mappings_with_ranges = {}
        for sensor_name, mapping in self.mappings.items():
            mapping_copy = mapping.copy()
            
            # Add range information if it exists for this sensor
            if sensor_name in self.sensor_ranges:
                range_info = self.sensor_ranges[sensor_name]
                mapping_copy["range"] = {
                    "min": range_info.get("min", 0),
                    "max": range_info.get("max", 100)
                }
            
            mappings_with_ranges[sensor_name] = mapping_copy
        
        return mappings_with_ranges
    
    def _prepare_sensor_groups(self):
        """Prepares sensor groups structure including all individual sensors."""
        # Get all sensors from either CSV data or config sensor list
        all_sensors = set()
        if self.csv_data is not None:
            all_sensors = set(self.csv_data.columns[1:])  # Exclude timestamp column
        elif self.config_sensor_list:
            # Remove timestamp if it exists in config list
            all_sensors = set([name for name in self.config_sensor_list if name != "Timestamp"])
        
        # Start with existing groups
        prepared_groups = {}
        grouped_sensors = set()
        
        for group_name, sensor_list in self.sensor_groups.items():
            # Only include sensors that actually exist in our sensor list
            valid_sensors = [sensor for sensor in sensor_list if sensor in all_sensors]
            if valid_sensors:
                prepared_groups[group_name] = valid_sensors
                grouped_sensors.update(valid_sensors)
        
        # Add ungrouped sensors if any exist
        ungrouped_sensors = all_sensors - grouped_sensors
        if ungrouped_sensors:
            prepared_groups["_ungrouped"] = list(ungrouped_sensors)
        
        return prepared_groups
    
    def _prepare_group_states(self):
        """Prepares group states (which groups are expanded)."""
        # For now, default all groups to expanded (True)
        # In a more advanced implementation, this could track actual UI state
        group_states = {}
        for group_name in self.sensor_groups.keys():
            group_states[group_name] = True
        
        # Add _ungrouped state if it exists
        if "_ungrouped" in self.sensor_groups:
            group_states["_ungrouped"] = True
            
        return group_states
    
    def _index_to_excel_column(self, index):
        """Converts a 0-based column index to Excel column letter(s)."""
        result = ""
        while index >= 0:
            result = chr(65 + (index % 26)) + result
            index = index // 26 - 1
        return result
    
    @staticmethod
    def format_date_friendly(dt):
        """Formats date as 'Month Day' (e.g., 'March 15')"""
        if hasattr(dt, 'strftime'):
            # Use %#d on Windows, %-d on Unix
            import platform
            if platform.system() == 'Windows':
                return dt.strftime('%B %#d')
            else:
                return dt.strftime('%B %-d')
        return str(dt)
    
    @staticmethod
    def format_time_friendly(dt):
        """Formats time as '1:30 AM' (12-hour format with AM/PM)"""
        if hasattr(dt, 'strftime'):
            # Use %#I on Windows, %-I on Unix
            import platform
            if platform.system() == 'Windows':
                return dt.strftime('%#I:%M %p')
            else:
                return dt.strftime('%-I:%M %p')
        return str(dt)
    
    # === DIAGRAM DESIGNER METHODS ===
    
    def add_component_to_model(self, component_type, position):
        """Add a component to the diagram model."""
        from component_schemas import SCHEMAS
        
        comp_id = f"{component_type.lower()}_{uuid.uuid4().hex[:6]}"
        
        # Initialize properties with default values from schema
        schema = SCHEMAS.get(component_type, {})
        properties = {}
        for prop_name, prop_schema in schema.get('properties', {}).items():
            properties[prop_name] = prop_schema.get('default')
        
        self.diagram_model['components'][comp_id] = {
            "type": component_type,
            "position": [position.x(), position.y()],
            "properties": properties,
            "size": {"width": 100, "height": 60},
            "rotation": 0
        }
        self.diagram_model_changed.emit()
        return comp_id

    def remove_components_from_model(self, component_ids):
        """Remove components from diagram model."""
        for comp_id in component_ids:
            if comp_id in self.diagram_model['components']:
                del self.diagram_model['components'][comp_id]
        
        pipes_to_delete = []
        for pipe_id, pipe_data in self.diagram_model['pipes'].items():
            if pipe_data['start_component_id'] in component_ids or pipe_data['end_component_id'] in component_ids:
                pipes_to_delete.append(pipe_id)
        
        for pipe_id in pipes_to_delete:
            del self.diagram_model['pipes'][pipe_id]
            
        self.diagram_model_changed.emit()

    def update_component_position(self, component_id, position):
        """Update component position."""
        if component_id in self.diagram_model['components']:
            # Ensure position is stored as a plain [x, y] list for JSON serialization
            try:
                x = position.x() if hasattr(position, 'x') else position[0]
                y = position.y() if hasattr(position, 'y') else position[1]
                self.diagram_model['components'][component_id]['position'] = [x, y]
            except Exception:
                # Fallback: attempt to coerce to list if possible
                try:
                    self.diagram_model['components'][component_id]['position'] = list(position)
                except Exception:
                    pass
    
    def add_pipe_to_model(self, start_comp_id, start_port, end_comp_id, end_port, fluid_state='any', pressure_side='any', circuit_label='None'):
        """Add pipe connection to diagram model."""
        pipe_id = f"pipe_{uuid.uuid4().hex[:6]}"
        self.diagram_model['pipes'][pipe_id] = {
            "start_component_id": start_comp_id,
            "start_port": start_port,
            "end_component_id": end_comp_id,
            "end_port": end_port,
            "fluid_state": fluid_state,
            "pressure_side": pressure_side,
            "circuit_label": circuit_label,
            "waypoints": []
        }
        self.diagram_model_changed.emit()
        return pipe_id
    
    def remove_pipes_from_model(self, pipe_ids):
        """Remove pipes from diagram model."""
        for pipe_id in pipe_ids:
            if pipe_id in self.diagram_model['pipes']:
                del self.diagram_model['pipes'][pipe_id]
        self.diagram_model_changed.emit()

