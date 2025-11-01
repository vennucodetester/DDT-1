"""
diagram_components.py

Visual components for the interactive refrigeration diagram.
"""
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem, QGraphicsPathItem, QGraphicsItem, QGraphicsEllipseItem
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath, QTransform, QPainter, QPainterPathStroker
from PyQt6.QtCore import Qt, QRectF, QPointF

from component_schemas import SCHEMAS

class BaseComponentItem(QGraphicsRectItem):
    """A draggable, rotatable component with ports."""
    
    def __init__(self, component_id, component_data, data_manager):
        # Get size from component_data
        size = component_data.get('size', {'width': 100, 'height': 60})
        super().__init__(0, 0, size['width'], size['height'])
        
        self.component_id = component_id
        self.component_data = component_data
        self.data_manager = data_manager
        self.schema = SCHEMAS.get(component_data['type'], {})
        
        # Initialize ports first
        self.ports = {}
        
        # Black outline with blue interior
        self.setBrush(QBrush(QColor("#E3F2FD")))  # Light blue fill
        self.setPen(QPen(QColor("#000000"), 3))  # Black outline
        
        # Create label
        self.label = QGraphicsTextItem(component_data['type'], self)
        self.label.setDefaultTextColor(QColor("#000000"))  # Black text on blue background
        self.label.setPos(5, 5)
        
        # IMPROVED: Smoother interaction flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)  # Better performance
        
        # Set position from data
        pos = component_data.get('position', [0, 0])
        if isinstance(pos, QPointF):
            self.setPos(pos)
        else:
            self.setPos(pos[0], pos[1])
        
        # Set rotation from data
        rotation = component_data.get('rotation', 0)
        self.setRotation(rotation)
        
        # Build ports
        self.rebuild_ports()
    
    def paint(self, painter, option, widget=None):
        """Custom paint to keep label upright."""
        super().paint(painter, option, widget)
        
        # Keep label upright regardless of component rotation
        rotation = self.rotation()
        self.label.setRotation(-rotation)
    
    def rebuild_ports(self):
        """Rebuild all ports based on schema and current properties."""
        # IMPORTANT: Save pipe connections before clearing ports
        port_connections = {}
        for port_name, port_item in self.ports.items():
            if hasattr(port_item, 'connected_pipes') and port_item.connected_pipes:
                port_connections[port_name] = list(port_item.connected_pipes)
        
        # Clear existing ports
        for port_item in list(self.ports.values()):
            if port_item.scene():
                self.scene().removeItem(port_item)
        self.ports.clear()
        
        comp_type = self.component_data['type']
        schema = SCHEMAS.get(comp_type, {})
        
        # Get component size
        width = self.rect().width()
        height = self.rect().height()
        
        # Add fixed ports
        for port_def in schema.get('ports', []):
            port_name = port_def['name']
            port_pos = port_def['position']
            x = port_pos[0] * width
            y = port_pos[1] * height
            
            port_item = PortItem(port_name, port_def, self)
            port_item.setPos(x, y)
            self.ports[port_name] = port_item
            if self.scene():
                self.scene().addItem(port_item)
        
        # Add dynamic ports (inlet side)
        dynamic_config = schema.get('dynamic_ports')
        if dynamic_config:
            prefix = dynamic_config['prefix']
            count_prop = dynamic_config['count_property']
            port_details = dynamic_config['port_details']
            side = dynamic_config['position_side']
            
            count = self.component_data.get('properties', {}).get(count_prop, 1)
            port_spacing = self.component_data.get('properties', {}).get('port_spacing', 20)
            print(f"[REBUILD] Ports for {comp_type} - {count_prop}={count}, port_spacing={port_spacing}")
            
            # Calculate total height needed for ports
            total_port_height = (count - 1) * port_spacing if count > 1 else 0
            
            for i in range(1, count + 1):
                port_name = f"{prefix}{i}"
                
                # Calculate position based on side with port_spacing
                if side == "left":
                    x = 0
                    # Center ports vertically and space them using port_spacing
                    y = height / 2 + ((i - 1) * port_spacing - total_port_height / 2)
                elif side == "right":
                    x = width
                    y = height / 2 + ((i - 1) * port_spacing - total_port_height / 2)
                elif side == "top":
                    x = width / 2 + ((i - 1) * port_spacing - total_port_height / 2)
                    y = 0
                else:  # bottom
                    x = width / 2 + ((i - 1) * port_spacing - total_port_height / 2)
                    y = height
                
                port_def = {
                    "name": port_name,
                    "type": port_details['type'],
                    "fluid_state": port_details['fluid_state'],
                    "position": [x / width, y / height]
                }
                
                port_item = PortItem(port_name, port_def, self)
                port_item.setPos(x, y)
                self.ports[port_name] = port_item
                if self.scene():
                    self.scene().addItem(port_item)
        
        # Add dynamic ports 2 (outlet side)
        dynamic_config_2 = schema.get('dynamic_ports_2')
        if dynamic_config_2:
            prefix = dynamic_config_2['prefix']
            count_prop = dynamic_config_2['count_property']
            port_details = dynamic_config_2['port_details']
            side = dynamic_config_2['position_side']
            
            count = self.component_data.get('properties', {}).get(count_prop, 1)
            port_spacing = self.component_data.get('properties', {}).get('port_spacing', 20)
            
            # Calculate total height needed for ports
            total_port_height = (count - 1) * port_spacing if count > 1 else 0
            
            for i in range(1, count + 1):
                port_name = f"{prefix}{i}"
                
                # Calculate position based on side with port_spacing
                if side == "left":
                    x = 0
                    y = height / 2 + ((i - 1) * port_spacing - total_port_height / 2)
                elif side == "right":
                    x = width
                    y = height / 2 + ((i - 1) * port_spacing - total_port_height / 2)
                elif side == "top":
                    x = width / 2 + ((i - 1) * port_spacing - total_port_height / 2)
                    y = 0
                else:  # bottom
                    x = width / 2 + ((i - 1) * port_spacing - total_port_height / 2)
                    y = height
                
                port_def = {
                    "name": port_name,
                    "type": port_details['type'],
                    "fluid_state": port_details['fluid_state'],
                    "position": [x / width, y / height]
                }
                
                port_item = PortItem(port_name, port_def, self)
                port_item.setPos(x, y)
                self.ports[port_name] = port_item
                if self.scene():
                    self.scene().addItem(port_item)
        
        # Add conditional ports (based on property value)
        conditional_ports = schema.get('conditional_ports')
        if conditional_ports:
            # Get the property that determines which ports to show
            # For Condenser, it's 'condenser_type'
            if comp_type == 'Condenser':
                condenser_type = self.component_data.get('properties', {}).get('condenser_type', 'Air Cooled')
                ports_to_add = conditional_ports.get(condenser_type, [])
                
                for port_def in ports_to_add:
                    port_name = port_def['name']
                    port_pos = port_def['position']
                    x = port_pos[0] * width
                    y = port_pos[1] * height
                    
                    port_item = PortItem(port_name, port_def, self)
                    port_item.setPos(x, y)
                    self.ports[port_name] = port_item
                    if self.scene():
                        self.scene().addItem(port_item)
        
        # IMPORTANT: Restore pipe connections to ports with matching names
        total_restored = 0
        for port_name, pipes in port_connections.items():
            if port_name in self.ports:
                new_port = self.ports[port_name]
                for pipe in pipes:
                    # Add connection to new port
                    if hasattr(new_port, 'add_connected_pipe'):
                        new_port.add_connected_pipe(pipe)
                    # Update pipe's internal port references
                    # Need to check if this pipe's start or end port was this one
                    if hasattr(pipe, 'start_port_item') and hasattr(pipe, 'end_port_item'):
                        # Check if pipe was connected to this port (by checking component_id and port name in pipe_data)
                        if hasattr(pipe, 'pipe_data') and hasattr(pipe, 'pipe_id'):
                            pipe_data = pipe.pipe_data
                            # Check if this is the start port
                            start_comp_id = pipe_data.get('start_component_id')
                            start_port = pipe_data.get('start_port')
                            end_comp_id = pipe_data.get('end_component_id')
                            end_port = pipe_data.get('end_port')
                            
                            # Update start_port_item if it matches
                            if start_comp_id == self.component_id and start_port == port_name:
                                pipe.start_port_item = new_port
                            # Update end_port_item if it matches
                            if end_comp_id == self.component_id and end_port == port_name:
                                pipe.end_port_item = new_port
                    # Update pipe path to reflect new port position
                    if hasattr(pipe, 'update_path'):
                        pipe.update_path()
                    total_restored += 1
        
        if total_restored > 0:
            print(f"[REBUILD] Restored {total_restored} pipe connections to {comp_type}")
    
    def update_size(self, width, height):
        """Update component size and reposition ports."""
        self.setRect(0, 0, width, height)
        if 'size' not in self.component_data:
            self.component_data['size'] = {}
        self.component_data['size']['width'] = width
        self.component_data['size']['height'] = height
        
        self.rebuild_ports()
        self.update_connected_pipes()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update position in model
            self.data_manager.update_component_position(self.component_id, value)
            self.update_connected_pipes()
        
        if change == QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged:
            # Save rotation to model
            self.component_data['rotation'] = value
            self.update_connected_pipes()
            
        return super().itemChange(change, value)

    def update_connected_pipes(self):
        """Update all pipes connected to this component's ports."""
        for port_item in self.ports.values():
            for pipe_item in port_item.connected_pipes:
                pipe_item.update_path()
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open property dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Notify the scene/view that this component was double-clicked
            # The DiagramWidget will handle opening the property dialog
            if hasattr(self.scene(), 'views') and self.scene().views():
                view = self.scene().views()[0]
                if hasattr(view.parent(), 'on_component_double_clicked'):
                    view.parent().on_component_double_clicked(self)
        super().mouseDoubleClickEvent(event)


class PortItem(QGraphicsEllipseItem):
    """A connection point on a component."""
    
    def __init__(self, port_name, port_def, parent_component):
        # IMPROVED: Slightly larger ports for better visibility
        super().__init__(-4, -4, 8, 8)
        self.port_name = port_name
        self.port_def = port_def
        self.parent_component = parent_component
        self.connected_pipes = []
        
        # Color-code by inlet/outlet type (consistent across all components)
        port_type = port_def.get('type', 'any')
        if port_type == 'in':
            color = QColor("#2196F3")  # Blue for all inlets
        elif port_type == 'out':
            color = QColor("#FF5722")  # Red for all outlets
        else:
            color = QColor("#4CAF50")  # Green for other/sensor ports
        
        self.setBrush(QBrush(color))
        # IMPROVED: Thicker white border for better visibility
        self.setPen(QPen(Qt.GlobalColor.white, 2))
        self.setParentItem(parent_component)
        
        self.setAcceptHoverEvents(True)
        self.setZValue(10)
        # IMPROVED: Better rendering
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        
        # Set helpful tooltip
        self._update_tooltip()
    
    def _update_tooltip(self):
        """Generate and set a helpful tooltip for this port."""
        comp_type = self.parent_component.component_data.get('type', 'Unknown')
        port_type = self.port_def.get('type', 'any')
        port_name = self.port_name
        
        # Get a user-friendly description
        from port_resolver import format_port_label, resolve_mapped_sensor, get_sensor_value
        props = self.parent_component.component_data.get('properties', {})
        label = format_port_label(comp_type, props, port_name)
        
        # Resolve mapping and current value (if available)
        mapped_sensor = None
        current_value = None
        try:
            view_parent = self.parent_component.scene().views()[0].parent()
            dm = getattr(view_parent, 'data_manager', None)
            if dm is not None:
                diagram_model = dm.diagram_model
                comp_id = getattr(self.parent_component, 'component_id', '')
                mapped_sensor = resolve_mapped_sensor(diagram_model, comp_type, comp_id, port_name)
                if mapped_sensor:
                    current_value = get_sensor_value(dm, mapped_sensor)
        except Exception:
            mapped_sensor = None
            current_value = None
        
        # Build tooltip based on port type
        if port_type == 'sensor':
            # Sensor ports - show what measurement they're for
            tooltip_lines = [
                f"<b>{label}</b>",
                f"<i>Sensor Port</i>",
                ""
            ]
            
            # Add specific guidance based on port name
            if port_name == 'SP':
                tooltip_lines.append("📍 <b>Map to:</b> Suction Pressure (PSIG)")
                tooltip_lines.append("🎯 <b>Used for:</b> Low-side pressure, ON-time filtering")
            elif port_name == 'DP':
                tooltip_lines.append("📍 <b>Map to:</b> Discharge/Liquid Pressure (PSIG)")
                tooltip_lines.append("🎯 <b>Used for:</b> High-side pressure")
            elif port_name == 'RPM':
                tooltip_lines.append("📍 <b>Map to:</b> Compressor RPM")
                tooltip_lines.append("🎯 <b>Used for:</b> Mass flow rate calculation")
            elif 'bulb' in port_name.lower():
                tooltip_lines.append("📍 <b>Map to:</b> TXV Bulb Temperature (°F)")
                tooltip_lines.append("🎯 <b>Used for:</b> Reference (optional)")
            else:
                tooltip_lines.append("📍 <b>Map to:</b> Temperature or pressure sensor")
            
            tooltip_lines.append("")
            if mapped_sensor:
                value_text = f"{current_value}" if current_value is not None else "(no data in filter)"
                tooltip_lines.append(f"<b>Mapped CSV:</b> {mapped_sensor}")
                tooltip_lines.append(f"<b>Current Value:</b> {value_text}")
            else:
                tooltip_lines.append("<span style='color:#c0392b'><b>Unmapped</b></span>")
            tooltip_lines.append("")
            tooltip_lines.append("<i>Click to map CSV column to this port</i>")
            
        elif port_type == 'in':
            # Inlet ports - can be used for temperature sensors
            tooltip_lines = [
                f"<b>{label}</b>",
                f"<i>Inlet Port</i>",
                ""
            ]
            
            if comp_type == 'Compressor' and port_name == 'inlet':
                tooltip_lines.append("📍 <b>Map to:</b> Suction Line Temperature (°F)")
                tooltip_lines.append("🎯 <b>Used for:</b> State 2b (Compressor Inlet)")
                tooltip_lines.append("📊 <b>Calculation:</b> Superheat, Mass flow density")
            elif comp_type == 'TXV' and port_name == 'inlet':
                tooltip_lines.append("📍 <b>Map to:</b> TXV Inlet Temperature (°F)")
                tooltip_lines.append("🎯 <b>Used for:</b> State 4b (TXV Inlet)")
                tooltip_lines.append("📊 <b>Calculation:</b> Subcooling")
            elif comp_type == 'Condenser' and port_name == 'inlet':
                tooltip_lines.append("📍 <b>Map to:</b> Condenser Inlet Temperature (°F)")
                tooltip_lines.append("🎯 <b>Used for:</b> State 3b (Condenser Inlet)")
                tooltip_lines.append("📊 <b>Calculation:</b> Superheat (optional)")
            else:
                tooltip_lines.append("🔵 <b>Inlet connection point</b>")
                tooltip_lines.append("💡 Can also map temperature sensor here")
            
            tooltip_lines.append("")
            tooltip_lines.append("💡 <i>Click to map CSV column or connect pipe</i>")
            
        elif port_type == 'out':
            # Outlet ports - can be used for temperature sensors
            tooltip_lines = [
                f"<b>{label}</b>",
                f"<i>Outlet Port</i>",
                ""
            ]
            
            if comp_type == 'Compressor' and port_name == 'outlet':
                tooltip_lines.append("📍 <b>Map to:</b> Discharge Line Temperature (°F)")
                tooltip_lines.append("🎯 <b>Used for:</b> State 3a (Compressor Outlet)")
                tooltip_lines.append("📊 <b>Calculation:</b> Superheat, Heat rejection")
            elif comp_type == 'Evaporator' and 'outlet' in port_name:
                tooltip_lines.append("📍 <b>Map to:</b> Evaporator Outlet Temperature (°F)")
                tooltip_lines.append("🎯 <b>Used for:</b> State 2a (Evaporator Outlet)")
                tooltip_lines.append("📊 <b>Calculation:</b> Superheat, Cooling capacity")
            elif comp_type == 'Condenser' and port_name == 'outlet':
                tooltip_lines.append("📍 <b>Map to:</b> Condenser Outlet Temperature (°F)")
                tooltip_lines.append("🎯 <b>Used for:</b> State 4a (Condenser Outlet)")
                tooltip_lines.append("📊 <b>Calculation:</b> Subcooling")
            else:
                tooltip_lines.append("🔴 <b>Outlet connection point</b>")
                tooltip_lines.append("💡 Can also map temperature sensor here")
            
            # Add special handling for condenser air/water ports
            if comp_type == 'Condenser':
                if port_name == 'air_in_temp':
                    tooltip_lines = [
                        f"<b>Air Inlet Temperature</b>",
                        f"<i>Sensor Port (Air Cooled)</i>",
                        "",
                        "📍 <b>Map to:</b> Ambient Air Temperature (°F)",
                        "🎯 <b>Used for:</b> Condenser performance analysis",
                        "📊 <b>Calculation:</b> Heat rejection, condenser efficiency",
                        "",
                        "💡 <i>Click to map CSV column to this port</i>"
                    ]
                elif port_name == 'air_out_temp':
                    tooltip_lines = [
                        f"<b>Air Outlet Temperature</b>",
                        f"<i>Sensor Port (Air Cooled)</i>",
                        "",
                        "📍 <b>Map to:</b> Condenser Air Outlet Temperature (°F)",
                        "🎯 <b>Used for:</b> Condenser performance analysis",
                        "📊 <b>Calculation:</b> Heat rejection, condenser efficiency",
                        "",
                        "💡 <i>Click to map CSV column to this port</i>"
                    ]
                elif port_name == 'water_in_temp':
                    tooltip_lines = [
                        f"<b>Water Inlet Temperature</b>",
                        f"<i>Sensor Port (Water Cooled)</i>",
                        "",
                        "📍 <b>Map to:</b> Cooling Water Inlet Temperature (°F)",
                        "🎯 <b>Used for:</b> Condenser performance analysis",
                        "📊 <b>Calculation:</b> Heat rejection, condenser efficiency",
                        "",
                        "💡 <i>Click to map CSV column to this port</i>"
                    ]
                elif port_name == 'water_out_temp':
                    tooltip_lines = [
                        f"<b>Water Outlet Temperature</b>",
                        f"<i>Sensor Port (Water Cooled)</i>",
                        "",
                        "📍 <b>Map to:</b> Cooling Water Outlet Temperature (°F)",
                        "🎯 <b>Used for:</b> Condenser performance analysis",
                        "📊 <b>Calculation:</b> Heat rejection, condenser efficiency",
                        "",
                        "💡 <i>Click to map CSV column to this port</i>"
                    ]
            
            tooltip_lines.append("")
            tooltip_lines.append("💡 <i>Click to map CSV column or connect pipe</i>")
        else:
            tooltip_lines = [
                f"<b>{label}</b>",
                f"<i>{port_type.title()} Port</i>",
                "",
                "💡 <i>Click to interact</i>"
            ]
        
        tooltip = "<br>".join(tooltip_lines)
        self.setToolTip(tooltip)
    
    def hoverEnterEvent(self, event):
        """Highlight on hover."""
        # IMPROVED: Brighter, more visible hover effect
        self.setPen(QPen(Qt.GlobalColor.yellow, 3))
        self.setScale(1.2)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Remove highlight."""
        # IMPROVED: Match the new thicker border
        self.setPen(QPen(Qt.GlobalColor.white, 2))
        self.setScale(1.0)
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse clicks on sensor ports."""
        if event.button() == Qt.MouseButton.LeftButton:
            port_type = self.port_def.get('type', 'any')
            # If this is a sensor port, notify the diagram widget
            if port_type == 'sensor':
                # Get the diagram widget through the scene
                if self.scene() and hasattr(self.scene(), 'views'):
                    views = self.scene().views()
                    if views:
                        view = views[0]
                        diagram_widget = view.parent()
                        if diagram_widget and hasattr(diagram_widget, 'on_sensor_port_clicked'):
                            diagram_widget.on_sensor_port_clicked(self)
                            event.accept()
                            return
        super().mousePressEvent(event)
    
    def get_scene_position(self):
        """Returns the center position of the port in scene coordinates."""
        return self.scenePos()
    
    def add_connected_pipe(self, pipe_item):
        """Track a pipe connected to this port."""
        if pipe_item not in self.connected_pipes:
            self.connected_pipes.append(pipe_item)
    
    def remove_connected_pipe(self, pipe_item):
        """Remove a pipe from tracking."""
        if pipe_item in self.connected_pipes:
            self.connected_pipes.remove(pipe_item)


class JunctionComponentItem(QGraphicsPathItem):
    """A junction component drawn as connecting lines instead of a box."""
    
    def __init__(self, component_id, component_data, data_manager):
        super().__init__()
        self.component_id = component_id
        self.component_data = component_data
        self.data_manager = data_manager
        self.schema = SCHEMAS.get(component_data['type'], {})
        
        # Initialize ports first
        self.ports = {}
        
        # Visual setup - copper color for Junction to make it stand out
        self.setPen(QPen(QColor("#B87333"), 4))  # Copper color
        self.setBrush(QBrush(Qt.GlobalColor.transparent))
        
        # Interaction flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        
        # Set position from data
        pos = component_data.get('position', [0, 0])
        if isinstance(pos, QPointF):
            self.setPos(pos)
        else:
            self.setPos(pos[0], pos[1])
        
        # Set rotation from data
        rotation = component_data.get('rotation', 0)
        self.setRotation(rotation)
        
        # Build the junction shape and ports
        self.rebuild_ports()
        self.update_shape()
    
    def rebuild_ports(self):
        """Rebuild all ports based on inlet/outlet counts."""
        # IMPORTANT: Save pipe connections before clearing ports
        port_connections = {}
        for port_name, port_item in self.ports.items():
            if hasattr(port_item, 'connected_pipes') and port_item.connected_pipes:
                port_connections[port_name] = list(port_item.connected_pipes)
        
        # Clear existing ports (they're child items, so just delete them)
        for port_item in list(self.ports.values()):
            port_item.setParentItem(None)  # Remove from parent
            if port_item.scene():
                port_item.scene().removeItem(port_item)
        self.ports.clear()
        
        # Get inlet and outlet counts
        inlet_count = self.component_data.get('properties', {}).get('inlet_count', 2)
        outlet_count = self.component_data.get('properties', {}).get('outlet_count', 1)
        
        # Spacing between ports (configurable)
        port_spacing = self.component_data.get('properties', {}).get('port_spacing', 20)
        
        # Create inlet ports on the left
        inlet_height = (inlet_count - 1) * port_spacing
        for i in range(inlet_count):
            port_name = f"inlet_{i+1}"
            port_def = {
                'name': port_name,
                'type': 'in',
                'fluid_state': 'any',
                'pressure_side': 'any',
                'position': [0, 0.5]  # Will be positioned manually
            }
            port_item = PortItem(port_name, port_def, self)
            y_pos = i * port_spacing - inlet_height / 2
            port_item.setPos(-30, y_pos)  # 30 pixels to the left
            self.ports[port_name] = port_item
            # Port is automatically added to scene because self is its parent
        
        # Create outlet ports on the right
        outlet_height = (outlet_count - 1) * port_spacing
        for i in range(outlet_count):
            port_name = f"outlet_{i+1}"
            port_def = {
                'name': port_name,
                'type': 'out',
                'fluid_state': 'any',
                'pressure_side': 'any',
                'position': [1, 0.5]  # Will be positioned manually
            }
            port_item = PortItem(port_name, port_def, self)
            y_pos = i * port_spacing - outlet_height / 2
            port_item.setPos(30, y_pos)  # 30 pixels to the right
            self.ports[port_name] = port_item
            # Port is automatically added to scene because self is its parent
        
        # Add sensor port at center (for mapping in Mapping mode)
        sensor_def = {
            'name': 'sensor',
            'type': 'sensor',
            'fluid_state': 'any',
            'pressure_side': 'any',
            'position': [0.5, 0.5]
        }
        sensor_port = PortItem('sensor', sensor_def, self)
        sensor_port.setPos(0, 0)  # Center of junction
        self.ports['sensor'] = sensor_port
        
        # IMPORTANT: Restore pipe connections to ports with matching names
        total_restored = 0
        comp_type = self.component_data['type']
        for port_name, pipes in port_connections.items():
            if port_name in self.ports:
                new_port = self.ports[port_name]
                for pipe in pipes:
                    # Add connection to new port
                    if hasattr(new_port, 'add_connected_pipe'):
                        new_port.add_connected_pipe(pipe)
                    # Update pipe's internal port references
                    if hasattr(pipe, 'start_port_item') and hasattr(pipe, 'end_port_item'):
                        if hasattr(pipe, 'pipe_data') and hasattr(pipe, 'pipe_id'):
                            pipe_data = pipe.pipe_data
                            start_comp_id = pipe_data.get('start_component_id')
                            start_port = pipe_data.get('start_port')
                            end_comp_id = pipe_data.get('end_component_id')
                            end_port = pipe_data.get('end_port')
                            
                            if start_comp_id == self.component_id and start_port == port_name:
                                pipe.start_port_item = new_port
                            if end_comp_id == self.component_id and end_port == port_name:
                                pipe.end_port_item = new_port
                    if hasattr(pipe, 'update_path'):
                        pipe.update_path()
                    total_restored += 1
        
        if total_restored > 0:
            print(f"[REBUILD] Restored {total_restored} pipe connections to {comp_type}")
        
        # Update the visual shape after ports are rebuilt
        self.update_shape()
        # Update any connected pipes
        self.update_connected_pipes()
    
    def update_shape(self):
        """Update the junction shape based on port configuration."""
        inlet_count = self.component_data.get('properties', {}).get('inlet_count', 2)
        outlet_count = self.component_data.get('properties', {}).get('outlet_count', 1)
        port_spacing = self.component_data.get('properties', {}).get('port_spacing', 20)
        
        path = QPainterPath()
        
        # Draw horizontal main line
        path.moveTo(-30, 0)
        path.lineTo(30, 0)
        
        # Draw inlet vertical lines
        inlet_height = (inlet_count - 1) * port_spacing
        for i in range(inlet_count):
            y_pos = i * port_spacing - inlet_height / 2
            path.moveTo(-30, 0)
            path.lineTo(-30, y_pos)
        
        # Draw outlet vertical lines
        outlet_height = (outlet_count - 1) * port_spacing
        for i in range(outlet_count):
            y_pos = i * port_spacing - outlet_height / 2
            path.moveTo(30, 0)
            path.lineTo(30, y_pos)
        
        self.setPath(path)
    
    def boundingRect(self):
        """Return the bounding rectangle for the junction."""
        return self.path().boundingRect().adjusted(-10, -10, 10, 10)
    
    def itemChange(self, change, value):
        """Handle item changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update position in model
            self.data_manager.update_component_position(self.component_id, value)
            self.update_connected_pipes()
        
        if change == QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged:
            # Save rotation to model
            self.component_data['rotation'] = value
            self.update_connected_pipes()
            
        return super().itemChange(change, value)
    
    def update_connected_pipes(self):
        """Update all pipes connected to this component's ports."""
        for port_item in self.ports.values():
            for pipe_item in port_item.connected_pipes:
                pipe_item.update_path()
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open property dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.scene(), 'views') and self.scene().views():
                view = self.scene().views()[0]
                if hasattr(view.parent(), 'on_component_double_clicked'):
                    view.parent().on_component_double_clicked(self)
        super().mouseDoubleClickEvent(event)


class TXVComponentItem(QGraphicsPathItem):
    """A TXV component drawn as two triangles (hourglass/bow-tie shape)."""
    
    def __init__(self, component_id, component_data, data_manager):
        super().__init__()
        self.component_id = component_id
        self.component_data = component_data
        self.data_manager = data_manager
        self.schema = SCHEMAS.get(component_data['type'], {})
        
        # Initialize ports
        self.ports = {}
        
        # Visual setup - black outline with blue interior
        self.setPen(QPen(QColor("#000000"), 3))  # Black outline
        self.setBrush(QBrush(QColor("#E3F2FD")))  # Light blue fill
        
        # Interaction flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        
        # Set position from data
        pos = component_data.get('position', [0, 0])
        if isinstance(pos, QPointF):
            self.setPos(pos)
        else:
            self.setPos(pos[0], pos[1])
        
        # Set rotation from data
        rotation = component_data.get('rotation', 0)
        self.setRotation(rotation)
        
        # Build the TXV shape and ports
        self.rebuild_ports()
        self.update_shape()
    
    def rebuild_ports(self):
        """Create the three ports: inlet (top), outlet (bottom), bulb (center)."""
        # IMPORTANT: Save pipe connections before clearing ports
        port_connections = {}
        for port_name, port_item in self.ports.items():
            if hasattr(port_item, 'connected_pipes') and port_item.connected_pipes:
                port_connections[port_name] = list(port_item.connected_pipes)
        
        # Clear existing ports
        for port_item in list(self.ports.values()):
            port_item.setParentItem(None)
            if port_item.scene():
                port_item.scene().removeItem(port_item)
        self.ports.clear()
        
        # Inlet at top (high pressure)
        inlet_def = {'name': 'inlet', 'type': 'in', 'fluid_state': 'liquid', 'pressure_side': 'high', 'position': [0.5, 0]}
        inlet_port = PortItem('inlet', inlet_def, self)
        inlet_port.setPos(0, -30)
        self.ports['inlet'] = inlet_port
        
        # Outlet at bottom (low pressure)
        outlet_def = {'name': 'outlet', 'type': 'out', 'fluid_state': 'two-phase', 'pressure_side': 'low', 'position': [0.5, 1]}
        outlet_port = PortItem('outlet', outlet_def, self)
        outlet_port.setPos(0, 30)
        self.ports['outlet'] = outlet_port
        
        # Bulb (sensor) at right perimeter (low pressure side)
        bulb_def = {'name': 'bulb', 'type': 'sensor', 'fluid_state': 'any', 'pressure_side': 'low', 'position': [0.5, 0.5]}
        bulb_port = PortItem('bulb', bulb_def, self)
        bulb_port.setPos(25, 0)  # Move to right perimeter of the TXV shape
        self.ports['bulb'] = bulb_port
        
        # IMPORTANT: Restore pipe connections to ports with matching names
        total_restored = 0
        comp_type = self.component_data['type']
        for port_name, pipes in port_connections.items():
            if port_name in self.ports:
                new_port = self.ports[port_name]
                for pipe in pipes:
                    # Add connection to new port
                    if hasattr(new_port, 'add_connected_pipe'):
                        new_port.add_connected_pipe(pipe)
                    # Update pipe's internal port references
                    if hasattr(pipe, 'start_port_item') and hasattr(pipe, 'end_port_item'):
                        if hasattr(pipe, 'pipe_data') and hasattr(pipe, 'pipe_id'):
                            pipe_data = pipe.pipe_data
                            start_comp_id = pipe_data.get('start_component_id')
                            start_port = pipe_data.get('start_port')
                            end_comp_id = pipe_data.get('end_component_id')
                            end_port = pipe_data.get('end_port')
                            
                            if start_comp_id == self.component_id and start_port == port_name:
                                pipe.start_port_item = new_port
                            if end_comp_id == self.component_id and end_port == port_name:
                                pipe.end_port_item = new_port
                    if hasattr(pipe, 'update_path'):
                        pipe.update_path()
                    total_restored += 1
        
        if total_restored > 0:
            print(f"[REBUILD] Restored {total_restored} pipe connections to {comp_type}")
    
    def update_shape(self):
        """Draw the bow-tie shape (two triangles touching at center)."""
        path = QPainterPath()
        
        # Top triangle (pointing down)
        path.moveTo(-20, -30)  # Top left
        path.lineTo(20, -30)   # Top right
        path.lineTo(0, 0)      # Center point
        path.closeSubpath()
        
        # Bottom triangle (pointing up)
        path.moveTo(0, 0)      # Center point
        path.lineTo(-20, 30)   # Bottom left
        path.lineTo(20, 30)    # Bottom right
        path.closeSubpath()
        
        self.setPath(path)
    
    def boundingRect(self):
        """Return the bounding rectangle."""
        return self.path().boundingRect().adjusted(-10, -10, 10, 10)
    
    def itemChange(self, change, value):
        """Handle item changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.data_manager.update_component_position(self.component_id, value)
            self.update_connected_pipes()
        
        if change == QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged:
            self.component_data['rotation'] = value
            self.update_connected_pipes()
            
        return super().itemChange(change, value)
    
    def update_connected_pipes(self):
        """Update all pipes connected to this component's ports."""
        for port_item in self.ports.values():
            for pipe_item in port_item.connected_pipes:
                pipe_item.update_path()
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open property dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.scene(), 'views') and self.scene().views():
                view = self.scene().views()[0]
                if hasattr(view.parent(), 'on_component_double_clicked'):
                    view.parent().on_component_double_clicked(self)
        super().mouseDoubleClickEvent(event)


class DistributorComponentItem(QGraphicsPathItem):
    """A distributor component drawn with double lines (like junction but distinguished)."""
    
    def __init__(self, component_id, component_data, data_manager):
        super().__init__()
        self.component_id = component_id
        self.component_data = component_data
        self.data_manager = data_manager
        self.schema = SCHEMAS.get(component_data['type'], {})
        
        # Initialize ports
        self.ports = {}
        
        # Visual setup - black double lines
        self.setPen(QPen(QColor("#000000"), 4))  # Black outline
        self.setBrush(QBrush(Qt.GlobalColor.transparent))
        
        # Interaction flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        
        # Set position from data
        pos = component_data.get('position', [0, 0])
        if isinstance(pos, QPointF):
            self.setPos(pos)
        else:
            self.setPos(pos[0], pos[1])
        
        # Set rotation from data
        rotation = component_data.get('rotation', 0)
        self.setRotation(rotation)
        
        # Build the distributor shape and ports
        self.rebuild_ports()
        self.update_shape()
    
    def rebuild_ports(self):
        """Create ports: 1 inlet and multiple outlets based on circuit_count."""
        # IMPORTANT: Save pipe connections before clearing ports
        port_connections = {}
        for port_name, port_item in self.ports.items():
            if hasattr(port_item, 'connected_pipes') and port_item.connected_pipes:
                port_connections[port_name] = list(port_item.connected_pipes)
        
        # Clear existing ports
        for port_item in list(self.ports.values()):
            port_item.setParentItem(None)
            if port_item.scene():
                port_item.scene().removeItem(port_item)
        self.ports.clear()
        
        # Get circuit count and port spacing
        circuit_count = self.component_data.get('properties', {}).get('circuit_count', 1)
        port_spacing = self.component_data.get('properties', {}).get('port_spacing', 20)
        
        # Single inlet on the left (low pressure)
        inlet_def = {'name': 'inlet', 'type': 'in', 'fluid_state': 'two-phase', 'pressure_side': 'low', 'position': [0, 0.5]}
        inlet_port = PortItem('inlet', inlet_def, self)
        inlet_port.setPos(-30, 0)
        self.ports['inlet'] = inlet_port
        
        # Multiple outlets on the right (low pressure)
        outlet_height = (circuit_count - 1) * port_spacing
        for i in range(circuit_count):
            port_name = f"outlet_{i+1}"
            outlet_def = {'name': port_name, 'type': 'out', 'fluid_state': 'two-phase', 'pressure_side': 'low', 'position': [1, 0.5]}
            outlet_port = PortItem(port_name, outlet_def, self)
            y_pos = i * port_spacing - outlet_height / 2
            outlet_port.setPos(30, y_pos)
            self.ports[port_name] = outlet_port
        
        # IMPORTANT: Restore pipe connections to ports with matching names
        total_restored = 0
        comp_type = self.component_data['type']
        for port_name, pipes in port_connections.items():
            if port_name in self.ports:
                new_port = self.ports[port_name]
                for pipe in pipes:
                    # Add connection to new port
                    if hasattr(new_port, 'add_connected_pipe'):
                        new_port.add_connected_pipe(pipe)
                    # Update pipe's internal port references
                    if hasattr(pipe, 'start_port_item') and hasattr(pipe, 'end_port_item'):
                        if hasattr(pipe, 'pipe_data') and hasattr(pipe, 'pipe_id'):
                            pipe_data = pipe.pipe_data
                            start_comp_id = pipe_data.get('start_component_id')
                            start_port = pipe_data.get('start_port')
                            end_comp_id = pipe_data.get('end_component_id')
                            end_port = pipe_data.get('end_port')
                            
                            if start_comp_id == self.component_id and start_port == port_name:
                                pipe.start_port_item = new_port
                            if end_comp_id == self.component_id and end_port == port_name:
                                pipe.end_port_item = new_port
                    if hasattr(pipe, 'update_path'):
                        pipe.update_path()
                    total_restored += 1
        
        if total_restored > 0:
            print(f"[REBUILD] Restored {total_restored} pipe connections to {comp_type}")
        
        # Update the visual shape after ports are rebuilt
        self.update_shape()
        # Update any connected pipes
        self.update_connected_pipes()
    
    def update_shape(self):
        """Draw double lines to distinguish from junction."""
        circuit_count = self.component_data.get('properties', {}).get('circuit_count', 1)
        port_spacing = self.component_data.get('properties', {}).get('port_spacing', 20)
        
        path = QPainterPath()
        
        # Double horizontal main lines (parallel lines with 4 pixel spacing)
        path.moveTo(-30, -2)
        path.lineTo(30, -2)
        path.moveTo(-30, 2)
        path.lineTo(30, 2)
        
        # Inlet double vertical line
        path.moveTo(-32, -2)
        path.lineTo(-32, 0)
        path.moveTo(-28, -2)
        path.lineTo(-28, 0)
        
        # Outlet double vertical lines
        outlet_height = (circuit_count - 1) * port_spacing
        for i in range(circuit_count):
            y_pos = i * port_spacing - outlet_height / 2
            path.moveTo(28, 0)
            path.lineTo(28, y_pos)
            path.moveTo(32, 0)
            path.lineTo(32, y_pos)
        
        self.setPath(path)
    
    def boundingRect(self):
        """Return the bounding rectangle."""
        return self.path().boundingRect().adjusted(-10, -10, 10, 10)
    
    def itemChange(self, change, value):
        """Handle item changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.data_manager.update_component_position(self.component_id, value)
            self.update_connected_pipes()
        
        if change == QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged:
            self.component_data['rotation'] = value
            self.update_connected_pipes()
            
        return super().itemChange(change, value)
    
    def update_connected_pipes(self):
        """Update all pipes connected to this component's ports."""
        for port_item in self.ports.values():
            for pipe_item in port_item.connected_pipes:
                pipe_item.update_path()
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open property dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.scene(), 'views') and self.scene().views():
                view = self.scene().views()[0]
                if hasattr(view.parent(), 'on_component_double_clicked'):
                    view.parent().on_component_double_clicked(self)
        super().mouseDoubleClickEvent(event)


class SensorBulbComponentItem(QGraphicsPathItem):
    """A sensor bulb component drawn as a rounded rectangle with 'S' inside."""
    
    def __init__(self, component_id, component_data, data_manager):
        super().__init__()
        self.component_id = component_id
        self.component_data = component_data
        self.data_manager = data_manager
        self.schema = SCHEMAS.get(component_data['type'], {})
        
        # Initialize ports
        self.ports = {}
        
        # Visual setup - rounded rectangle with blue fill and black outline
        self.setPen(QPen(QColor("#000000"), 3))  # Black outline
        self.setBrush(QBrush(QColor("#E3F2FD")))  # Light blue fill
        
        # Create "S" label centered
        self.label = QGraphicsTextItem("S", self)
        self.label.setDefaultTextColor(QColor("#000000"))
        font = self.label.font()
        font.setPointSize(20)
        font.setBold(True)
        self.label.setFont(font)
        # Center the "S" in the rounded rectangle
        self.label.setPos(12, 5)
        
        # Interaction flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        
        # Set position from data
        pos = component_data.get('position', [0, 0])
        if isinstance(pos, QPointF):
            self.setPos(pos)
        else:
            self.setPos(pos[0], pos[1])
        
        # Set rotation from data
        rotation = component_data.get('rotation', 0)
        self.setRotation(rotation)
        
        # Build the rounded rectangle shape and sensor port
        self.update_shape()
        self.rebuild_ports()
    
    def update_shape(self):
        """Draw the rounded rectangle shape."""
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QPainterPath
        
        path = QPainterPath()
        # Create rounded rectangle: 40x40 with corner radius of 8
        rect = QRectF(0, 0, 40, 40)
        path.addRoundedRect(rect, 8, 8)
        
        self.setPath(path)
    
    def rebuild_ports(self):
        """Create the sensor port on the right perimeter of the rounded rectangle."""
        # IMPORTANT: Save pipe connections before clearing ports
        port_connections = {}
        for port_name, port_item in self.ports.items():
            if hasattr(port_item, 'connected_pipes') and port_item.connected_pipes:
                port_connections[port_name] = list(port_item.connected_pipes)
        
        # Clear existing ports
        for port_item in list(self.ports.values()):
            port_item.setParentItem(None)
            if port_item.scene():
                port_item.scene().removeItem(port_item)
        self.ports.clear()
        
        # Measurement point on the right perimeter
        sensor_def = {'name': 'measurement', 'type': 'sensor', 'fluid_state': 'any', 'pressure_side': 'any', 'position': [0.5, 0.5]}
        sensor_port = PortItem('measurement', sensor_def, self)
        sensor_port.setPos(45, 20)  # Right perimeter of the 40x40 rounded rectangle
        self.ports['measurement'] = sensor_port
        
        # IMPORTANT: Restore pipe connections to ports with matching names
        total_restored = 0
        comp_type = self.component_data['type']
        for port_name, pipes in port_connections.items():
            if port_name in self.ports:
                new_port = self.ports[port_name]
                for pipe in pipes:
                    # Add connection to new port
                    if hasattr(new_port, 'add_connected_pipe'):
                        new_port.add_connected_pipe(pipe)
                    # Update pipe's internal port references
                    if hasattr(pipe, 'start_port_item') and hasattr(pipe, 'end_port_item'):
                        if hasattr(pipe, 'pipe_data') and hasattr(pipe, 'pipe_id'):
                            pipe_data = pipe.pipe_data
                            start_comp_id = pipe_data.get('start_component_id')
                            start_port = pipe_data.get('start_port')
                            end_comp_id = pipe_data.get('end_component_id')
                            end_port = pipe_data.get('end_port')
                            
                            if start_comp_id == self.component_id and start_port == port_name:
                                pipe.start_port_item = new_port
                            if end_comp_id == self.component_id and end_port == port_name:
                                pipe.end_port_item = new_port
                    if hasattr(pipe, 'update_path'):
                        pipe.update_path()
                    total_restored += 1
        
        if total_restored > 0:
            print(f"[REBUILD] Restored {total_restored} pipe connections to {comp_type}")
    
    def boundingRect(self):
        """Return the bounding rectangle."""
        return self.path().boundingRect().adjusted(-10, -10, 10, 10)
    
    def itemChange(self, change, value):
        """Handle item changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.data_manager.update_component_position(self.component_id, value)
            self.update_connected_pipes()
        
        if change == QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged:
            self.component_data['rotation'] = value
            self.update_connected_pipes()
            
        return super().itemChange(change, value)
    
    def update_connected_pipes(self):
        """Update all pipes connected to this component's ports."""
        for port_item in self.ports.values():
            for pipe_item in port_item.connected_pipes:
                pipe_item.update_path()
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open property dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.scene(), 'views') and self.scene().views():
                view = self.scene().views()[0]
                if hasattr(view.parent(), 'on_component_double_clicked'):
                    view.parent().on_component_double_clicked(self)
        super().mouseDoubleClickEvent(event)


class FanComponentItem(QGraphicsPathItem):
    """A fan component drawn with fan blade shape."""
    
    def __init__(self, component_id, component_data, data_manager):
        super().__init__()
        self.component_id = component_id
        self.component_data = component_data
        self.data_manager = data_manager
        self.schema = SCHEMAS.get(component_data['type'], {})
        
        # MIGRATION: Convert old property names to new ones for backward compatibility
        self._migrate_old_properties()
        
        # Initialize ports
        self.ports = {}
        
        # Visual setup - fan shape with blue fill and black outline
        self.setPen(QPen(QColor("#000000"), 3))  # Black outline
        self.setBrush(QBrush(QColor("#E3F2FD")))  # Light blue fill
        
        # Interaction flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        
        # Set position from data
        pos = component_data.get('position', [0, 0])
        if isinstance(pos, QPointF):
            self.setPos(pos)
        else:
            self.setPos(pos[0], pos[1])
        
        # Set rotation from data
        rotation = component_data.get('rotation', 0)
        self.setRotation(rotation)
        
        # Build the fan shape and ports
        self.rebuild_ports()
        self.update_shape()
    
    def _migrate_old_properties(self):
        """Convert old property names to new schema format for backward compatibility."""
        props = self.component_data.get('properties', {})
        
        # Migration: air_direction -> air_flow_type
        if 'air_direction' in props and 'air_flow_type' not in props:
            old_value = props['air_direction']
            # Map old direction values to new flow type format if needed
            if old_value in ['up', 'down', 'left', 'right']:
                # Old arrow-based system - convert to Air Inlet (default)
                props['air_flow_type'] = 'Air Inlet'
                print(f"[FAN MIGRATION] Converted air_direction '{old_value}' to air_flow_type 'Air Inlet'")
            elif old_value in ['Air Inlet', 'Air Outlet']:
                # Already in new format
                props['air_flow_type'] = old_value
            else:
                # Default to Air Inlet
                props['air_flow_type'] = 'Air Inlet'
            
            # Remove old property
            del props['air_direction']
            self.component_data['properties'] = props
    
    def rebuild_ports(self):
        """Rebuild dynamic sensor ports based on sensor_count property."""
        # IMPORTANT: Save pipe connections before clearing ports
        port_connections = {}
        for port_name, port_item in self.ports.items():
            if hasattr(port_item, 'connected_pipes') and port_item.connected_pipes:
                port_connections[port_name] = list(port_item.connected_pipes)
        
        try:
            # Clear existing ports
            for port_item in list(self.ports.values()):
                try:
                    port_item.setParentItem(None)
                except:
                    pass
                try:
                    if port_item.scene():
                        port_item.scene().removeItem(port_item)
                except:
                    pass
            self.ports.clear()
            
            # Get sensor count from properties (default 6 if not specified)
            sensor_count = self.component_data.get('properties', {}).get('sensor_count', 6)
            
            if sensor_count > 0:
                # Create dynamic sensor ports (sensor_0, sensor_1, etc.)
                for i in range(int(sensor_count)):
                    port_name = f"sensor_{i}"
                    port_def = {
                        'name': port_name,
                        'type': 'sensor',
                        'fluid_state': 'any',
                        'pressure_side': 'any',
                        'position': [1, i / max(sensor_count - 1, 1)]
                    }
                    
                    # Create port and position it along the right side
                    port_item = PortItem(port_name, port_def, self)
                    port_y = -30 + (i * (60 / max(sensor_count, 1)))
                    port_x = 35
                    port_item.setPos(port_x, port_y)
                    self.ports[port_name] = port_item
            
            # IMPORTANT: Restore pipe connections to ports with matching names
            total_restored = 0
            comp_type = self.component_data['type']
            for port_name, pipes in port_connections.items():
                if port_name in self.ports:
                    new_port = self.ports[port_name]
                    for pipe in pipes:
                        # Add connection to new port
                        if hasattr(new_port, 'add_connected_pipe'):
                            new_port.add_connected_pipe(pipe)
                        # Update pipe's internal port references
                        if hasattr(pipe, 'start_port_item') and hasattr(pipe, 'end_port_item'):
                            if hasattr(pipe, 'pipe_data') and hasattr(pipe, 'pipe_id'):
                                pipe_data = pipe.pipe_data
                                start_comp_id = pipe_data.get('start_component_id')
                                start_port = pipe_data.get('start_port')
                                end_comp_id = pipe_data.get('end_component_id')
                                end_port = pipe_data.get('end_port')
                                
                                if start_comp_id == self.component_id and start_port == port_name:
                                    pipe.start_port_item = new_port
                                if end_comp_id == self.component_id and end_port == port_name:
                                    pipe.end_port_item = new_port
                        if hasattr(pipe, 'update_path'):
                            pipe.update_path()
                        total_restored += 1
            
            if total_restored > 0:
                print(f"[REBUILD] Restored {total_restored} pipe connections to {comp_type}")
            
        except Exception as e:
            print(f"[FAN] Error rebuilding ports: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Always try to update shape
            try:
                self.update_shape()
            except Exception as e:
                print(f"[FAN] Error in update_shape: {e}")
    
    def update_shape(self):
        """Draw fan blades in a circular pattern."""
        try:
            import math
            path = QPainterPath()
            
            # Outer circle (housing)
            center_x, center_y = 0, 0
            radius = 30
            path.addEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
            
            # Draw 4 fan blades
            num_blades = 4
            for i in range(num_blades):
                angle = (360 / num_blades) * i
                angle_rad = math.radians(angle)
                
                # Blade is a curved shape from center outward
                blade_path = QPainterPath()
                
                # Start at center
                blade_path.moveTo(center_x, center_y)
                
                # Draw a curved blade
                # Point 1: Outward to one side
                angle1_rad = math.radians(angle - 15)
                x1 = center_x + math.cos(angle1_rad) * radius * 0.9
                y1 = center_y + math.sin(angle1_rad) * radius * 0.9
                
                # Point 2: Tip of blade
                x2 = center_x + math.cos(angle_rad) * radius * 0.85
                y2 = center_y + math.sin(angle_rad) * radius * 0.85
                
                # Point 3: Other side
                angle2_rad = math.radians(angle + 15)
                x3 = center_x + math.cos(angle2_rad) * radius * 0.9
                y3 = center_y + math.sin(angle2_rad) * radius * 0.9
                
                blade_path.lineTo(x1, y1)
                blade_path.lineTo(x2, y2)
                blade_path.lineTo(x3, y3)
                blade_path.closeSubpath()
                
                path.addPath(blade_path)
            
            # Center hub (small circle)
            hub_radius = 5
            path.addEllipse(center_x - hub_radius, center_y - hub_radius, hub_radius * 2, hub_radius * 2)
            
            self.setPath(path)
        except Exception as e:
            print(f"[FAN] Error updating shape: {e}")
            import traceback
            traceback.print_exc()
    
    def boundingRect(self):
        """Return the bounding rectangle."""
        return self.path().boundingRect().adjusted(-10, -10, 10, 10)
    
    def itemChange(self, change, value):
        """Handle item changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.data_manager.update_component_position(self.component_id, value)
            self.update_connected_pipes()
        
        if change == QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged:
            self.component_data['rotation'] = value
            self.update_connected_pipes()
            
        return super().itemChange(change, value)
    
    def update_connected_pipes(self):
        """Update all pipes connected to this component's ports."""
        for port_item in self.ports.values():
            for pipe_item in port_item.connected_pipes:
                pipe_item.update_path()
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open property dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.scene(), 'views') and self.scene().views():
                view = self.scene().views()[0]
                if hasattr(view.parent(), 'on_component_double_clicked'):
                    view.parent().on_component_double_clicked(self)
        super().mouseDoubleClickEvent(event)


class AirSensorArrayComponentItem(QGraphicsRectItem):
    """Air sensor array block - horizontal rectangle with evenly spaced sensor dots."""
    
    def __init__(self, component_id, component_data, data_manager):
        # Get dimensions from properties
        width = component_data.get('properties', {}).get('block_width', 300)
        height = component_data.get('properties', {}).get('block_height', 25)
        
        super().__init__(0, 0, width, height)
        self.component_id = component_id
        self.component_data = component_data
        self.data_manager = data_manager
        self.schema = SCHEMAS.get(component_data['type'], {})
        
        # Initialize ports
        self.ports = {}
        
        # Visual setup - color based on curtain type
        curtain_type = component_data.get('properties', {}).get('curtain_type', 'Primary')
        if curtain_type == 'Primary':
            fill_color = QColor("#B3E5FC")  # Light blue (cooler air)
        elif curtain_type == 'Secondary':
            fill_color = QColor("#FFE0B2")  # Light orange (warmer)
        else:  # Return
            fill_color = QColor("#FFAB91")  # Darker red/orange (warmest air)
        
        self.setBrush(QBrush(fill_color))
        self.setPen(QPen(QColor("#000000"), 2))  # Black outline
        
        # Create label outside the rectangle
        label_text = f"{curtain_type} Air"
        self.label = QGraphicsTextItem(label_text, self)
        self.label.setDefaultTextColor(QColor("#000000"))
        # Position label above the rectangle
        self.label.setPos(5, -20)
        
        # Interaction flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        
        # Set position from data
        pos = component_data.get('position', [0, 0])
        if isinstance(pos, QPointF):
            self.setPos(pos)
        else:
            self.setPos(pos[0], pos[1])
        
        # Set rotation from data
        rotation = component_data.get('rotation', 0)
        self.setRotation(rotation)
        
        # Build sensor ports
        self.rebuild_ports()
    
    def rebuild_ports(self):
        """Create evenly spaced sensor ports along the horizontal block."""
        # IMPORTANT: Save pipe connections before clearing ports
        port_connections = {}
        for port_name, port_item in self.ports.items():
            if hasattr(port_item, 'connected_pipes') and port_item.connected_pipes:
                port_connections[port_name] = list(port_item.connected_pipes)
        
        # Clear existing ports
        for port_item in list(self.ports.values()):
            port_item.setParentItem(None)
            if port_item.scene():
                port_item.scene().removeItem(port_item)
        self.ports.clear()
        
        # Get current properties
        sensor_count = self.component_data.get('properties', {}).get('sensor_count', 11)
        width = self.component_data.get('properties', {}).get('block_width', 300)
        height = self.component_data.get('properties', {}).get('block_height', 25)
        
        # Update rectangle size
        self.setRect(0, 0, width, height)
        
        # Update label
        curtain_type = self.component_data.get('properties', {}).get('curtain_type', 'Primary')
        self.label.setPlainText(f"{curtain_type} Air")
        
        # Update fill color based on curtain type
        if curtain_type == 'Primary':
            fill_color = QColor("#B3E5FC")  # Light blue (cooler)
        elif curtain_type == 'Secondary':
            fill_color = QColor("#FFE0B2")  # Light orange (warmer)
        else:  # Return
            fill_color = QColor("#FFAB91")  # Darker red/orange (warmest)
        self.setBrush(QBrush(fill_color))
        
        # Create sensor ports evenly spaced
        for i in range(sensor_count):
            # Calculate even spacing
            if sensor_count == 1:
                x_pos = width / 2
            else:
                spacing = width / (sensor_count + 1)
                x_pos = spacing * (i + 1)
            
            y_pos = height / 2
            
            # Create sensor port
            port_name = f"sensor_{i+1}"
            port_def = {
                'name': port_name,
                'type': 'sensor',
                'fluid_state': 'any',
                'pressure_side': 'any',
                'position': [x_pos / width, 0.5]
            }
            port_item = PortItem(port_name, port_def, self)
            port_item.setPos(x_pos, y_pos)
            self.ports[port_name] = port_item
        
        # IMPORTANT: Restore pipe connections to ports with matching names
        total_restored = 0
        comp_type = self.component_data['type']
        for port_name, pipes in port_connections.items():
            if port_name in self.ports:
                new_port = self.ports[port_name]
                for pipe in pipes:
                    # Add connection to new port
                    if hasattr(new_port, 'add_connected_pipe'):
                        new_port.add_connected_pipe(pipe)
                    # Update pipe's internal port references
                    if hasattr(pipe, 'start_port_item') and hasattr(pipe, 'end_port_item'):
                        if hasattr(pipe, 'pipe_data') and hasattr(pipe, 'pipe_id'):
                            pipe_data = pipe.pipe_data
                            start_comp_id = pipe_data.get('start_component_id')
                            start_port = pipe_data.get('start_port')
                            end_comp_id = pipe_data.get('end_component_id')
                            end_port = pipe_data.get('end_port')
                            
                            if start_comp_id == self.component_id and start_port == port_name:
                                pipe.start_port_item = new_port
                            if end_comp_id == self.component_id and end_port == port_name:
                                pipe.end_port_item = new_port
                    if hasattr(pipe, 'update_path'):
                        pipe.update_path()
                    total_restored += 1
        
        if total_restored > 0:
            print(f"[REBUILD] Restored {total_restored} pipe connections to {comp_type}")
    
    def update_size(self, width, height):
        """Update the block size and rebuild ports."""
        self.component_data['properties']['block_width'] = width
        self.component_data['properties']['block_height'] = height
        self.rebuild_ports()
    
    def itemChange(self, change, value):
        """Handle item changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.data_manager.update_component_position(self.component_id, value)
        
        if change == QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged:
            self.component_data['rotation'] = value
            
        return super().itemChange(change, value)
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open property dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.scene(), 'views') and self.scene().views():
                view = self.scene().views()[0]
                if hasattr(view.parent(), 'on_component_double_clicked'):
                    view.parent().on_component_double_clicked(self)
        super().mouseDoubleClickEvent(event)


class ShelvingGridComponentItem(QGraphicsPathItem):
    """Shelving grid with sensor dots at shelf corners - shared at junctions."""
    
    def __init__(self, component_id, component_data, data_manager):
        super().__init__()
        self.component_id = component_id
        self.component_data = component_data
        self.data_manager = data_manager
        self.schema = SCHEMAS.get(component_data['type'], {})
        
        # Initialize ports
        self.ports = {}
        
        # Visual setup
        self.setPen(QPen(QColor("#000000"), 2))  # Black outline for shelves
        self.setBrush(QBrush(Qt.GlobalColor.transparent))
        
        # Interaction flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        
        # Set position from data
        pos = component_data.get('position', [0, 0])
        if isinstance(pos, QPointF):
            self.setPos(pos)
        else:
            self.setPos(pos[0], pos[1])
        
        # Set rotation from data
        rotation = component_data.get('rotation', 0)
        self.setRotation(rotation)
        
        # Build the grid
        self.rebuild_ports()
        self.update_shape()
    
    def rebuild_ports(self):
        """Create sensor ports at grid intersections (shelf corners)."""
        # IMPORTANT: Save pipe connections before clearing ports
        port_connections = {}
        for port_name, port_item in self.ports.items():
            if hasattr(port_item, 'connected_pipes') and port_item.connected_pipes:
                port_connections[port_name] = list(port_item.connected_pipes)
        
        # Clear existing ports
        for port_item in list(self.ports.values()):
            port_item.setParentItem(None)
            if port_item.scene():
                port_item.scene().removeItem(port_item)
        self.ports.clear()
        
        # Get properties
        props = self.component_data.get('properties', {})
        shelving_type = props.get('shelving_type', 'Modular')
        shelf_rows = props.get('shelf_rows', 6)
        shelf_width = props.get('shelf_width', 100)
        shelf_height = props.get('shelf_height', 60)
        row_gap = props.get('row_gap', 20)
        
        # Determine number of columns
        if shelving_type == 'Modular':
            columns = props.get('module_count', 3)
        else:  # Non-Modular
            columns = props.get('door_count', 3)
        
        # Create sensors at shelf corners - each row has top and bottom sensors
        # Sensors are shared horizontally within a row, but NOT between rows (due to gap)
        for row_idx in range(shelf_rows):
            # Y positions for this row
            top_y = row_idx * (shelf_height + row_gap)
            bottom_y = top_y + shelf_height
            
            # Top edge sensors for this row
            for col in range(columns + 1):
                x_pos = col * shelf_width
                port_name = f"sensor_r{row_idx}_top_c{col}"
                port_def = {
                    'name': port_name,
                    'type': 'sensor',
                    'fluid_state': 'any',
                    'pressure_side': 'any',
                    'position': [x_pos / (columns * shelf_width), top_y / ((shelf_height + row_gap) * shelf_rows)]
                }
                port_item = PortItem(port_name, port_def, self)
                port_item.setPos(x_pos, top_y)
                self.ports[port_name] = port_item
            
            # Bottom edge sensors for this row
            for col in range(columns + 1):
                x_pos = col * shelf_width
                port_name = f"sensor_r{row_idx}_bottom_c{col}"
                port_def = {
                    'name': port_name,
                    'type': 'sensor',
                    'fluid_state': 'any',
                    'pressure_side': 'any',
                    'position': [x_pos / (columns * shelf_width), bottom_y / ((shelf_height + row_gap) * shelf_rows)]
                }
                port_item = PortItem(port_name, port_def, self)
                port_item.setPos(x_pos, bottom_y)
                self.ports[port_name] = port_item
        
        print(f"[SHELVING] Created grid with {len(self.ports)} sensors ({columns+1} cols x {shelf_rows} rows x 2 edges)")
        
        # IMPORTANT: Restore pipe connections to ports with matching names
        total_restored = 0
        comp_type = self.component_data['type']
        for port_name, pipes in port_connections.items():
            if port_name in self.ports:
                new_port = self.ports[port_name]
                for pipe in pipes:
                    # Add connection to new port
                    if hasattr(new_port, 'add_connected_pipe'):
                        new_port.add_connected_pipe(pipe)
                    # Update pipe's internal port references
                    if hasattr(pipe, 'start_port_item') and hasattr(pipe, 'end_port_item'):
                        if hasattr(pipe, 'pipe_data') and hasattr(pipe, 'pipe_id'):
                            pipe_data = pipe.pipe_data
                            start_comp_id = pipe_data.get('start_component_id')
                            start_port = pipe_data.get('start_port')
                            end_comp_id = pipe_data.get('end_component_id')
                            end_port = pipe_data.get('end_port')
                            
                            if start_comp_id == self.component_id and start_port == port_name:
                                pipe.start_port_item = new_port
                            if end_comp_id == self.component_id and end_port == port_name:
                                pipe.end_port_item = new_port
                    if hasattr(pipe, 'update_path'):
                        pipe.update_path()
                    total_restored += 1
        
        if total_restored > 0:
            print(f"[REBUILD] Restored {total_restored} pipe connections to {comp_type}")
        
        # Update visual
        self.update_shape()
    
    def update_shape(self):
        """Draw the shelf grid with gaps between rows."""
        props = self.component_data.get('properties', {})
        shelving_type = props.get('shelving_type', 'Modular')
        shelf_rows = props.get('shelf_rows', 6)
        shelf_width = props.get('shelf_width', 100)
        shelf_height = props.get('shelf_height', 60)
        row_gap = props.get('row_gap', 20)
        
        # Determine number of columns
        if shelving_type == 'Modular':
            columns = props.get('module_count', 3)
        else:  # Non-Modular
            columns = props.get('door_count', 3)
        
        path = QPainterPath()
        
        # Draw each shelf row (with gaps between rows)
        for row_idx in range(shelf_rows):
            # Y positions for this row
            top_y = row_idx * (shelf_height + row_gap)
            bottom_y = top_y + shelf_height
            
            # Top horizontal line
            path.moveTo(0, top_y)
            path.lineTo(columns * shelf_width, top_y)
            
            # Bottom horizontal line
            path.moveTo(0, bottom_y)
            path.lineTo(columns * shelf_width, bottom_y)
            
            # Vertical lines connecting top to bottom for this row
            for col in range(columns + 1):
                x = col * shelf_width
                path.moveTo(x, top_y)
                path.lineTo(x, bottom_y)
        
        self.setPath(path)
        total_height = shelf_rows * (shelf_height + row_gap) - row_gap
        print(f"[SHELVING] Updated shape: {columns}x{shelf_rows}, size: {columns*shelf_width}x{total_height}")
    
    def boundingRect(self):
        """Return the bounding rectangle."""
        return self.path().boundingRect().adjusted(-10, -10, 10, 10)
    
    def itemChange(self, change, value):
        """Handle item changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.data_manager.update_component_position(self.component_id, value)
        
        if change == QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged:
            self.component_data['rotation'] = value
            
        return super().itemChange(change, value)
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open property dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.scene(), 'views') and self.scene().views():
                view = self.scene().views()[0]
                if hasattr(view.parent(), 'on_component_double_clicked'):
                    view.parent().on_component_double_clicked(self)
        super().mouseDoubleClickEvent(event)


class PipeItem(QGraphicsPathItem):
    """A connection between two ports with editable waypoints."""
    
    def __init__(self, pipe_id, pipe_data, start_port_item, end_port_item):
        super().__init__()
        self.pipe_id = pipe_id
        self.pipe_data = pipe_data
        self.start_port_item = start_port_item
        self.end_port_item = end_port_item
        self.waypoint_handles = []
        
        # Track this pipe in the ports
        start_port_item.add_connected_pipe(self)
        end_port_item.add_connected_pipe(self)
        
        # Visual setup
        pen = self._get_pen_style()
        self.setPen(pen)
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self.setZValue(1)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        # IMPROVED: Better rendering for smoother lines
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        
        # Rich tooltip with pipe diagnostics
        try:
            tooltip = (
                f"Pipe ID: {pipe_id}\n"
                f"Fluid: {pipe_data.get('fluid_state', 'unknown')}\n"
                f"Pressure: {pipe_data.get('pressure_side', 'any')}\n"
                f"Circuit: {pipe_data.get('circuit_label', 'None')}\n"
                f"From: {pipe_data.get('start_component_id')}.{pipe_data.get('start_port')}\n"
                f"To:   {pipe_data.get('end_component_id')}.{pipe_data.get('end_port')}\n"
                f"Waypoints: {len(pipe_data.get('waypoints', []))}\n\n"
                f"Double-click: add waypoint\nDelete: remove pipe"
            )
        except Exception:
            tooltip = (
                f"Pipe: {pipe_data.get('fluid_state', 'unknown')}\n"
                f"Double-click to add waypoint for custom routing\n"
                f"Delete key to remove pipe"
            )
        self.setToolTip(tooltip)
        
        # Dragging state
        self._is_dragging = False
        self._last_drag_scene_pos = None
        
        # Store original pen for selection highlighting
        self._original_pen = pen
        
        self.update_path()
        self.create_waypoint_handles()
    
    def _get_pen_style(self):
        """Return pen based on pressure side - only two colors."""
        pressure_side = self.pipe_data.get('pressure_side', 'any')
        
        # Red for high pressure, Blue for low pressure
        if pressure_side == 'high':
            return QPen(QColor("#FF5722"), 4)  # Red for high pressure
        elif pressure_side == 'low':
            return QPen(QColor("#2196F3"), 4)  # Blue for low pressure
        else:
            return QPen(QColor("#4CAF50"), 4)  # Green for unspecified (junctions, etc.)

    def _get_port_exit_vector(self, port_item):
        """Get the perpendicular exit vector for a port, accounting for component rotation."""
        # Get port position relative to parent component (0-1 normalized)
        port_def = port_item.port_def
        port_pos = port_def.get('position', [0.5, 0.5])
        x, y = port_pos
        
        # Determine the normal (perpendicular) direction based on which edge
        # These are in component's local coordinate system
        if x <= 0.05:  # Left edge
            normal = QPointF(-1, 0)  # Points left
        elif x >= 0.95:  # Right edge
            normal = QPointF(1, 0)   # Points right
        elif y <= 0.05:  # Top edge
            normal = QPointF(0, -1)  # Points up
        elif y >= 0.95:  # Bottom edge
            normal = QPointF(0, 1)   # Points down
        else:
            # Default to horizontal if unclear
            normal = QPointF(1, 0) if x > 0.5 else QPointF(-1, 0)
        
        # Apply the component's rotation to the normal vector
        component = port_item.parent_component
        rotation_deg = component.rotation()
        rotation_rad = rotation_deg * 3.14159 / 180.0
        
        # Rotate the normal vector
        cos_r = QPointF(normal.x(), normal.y()).x() * (rotation_rad ** 0 - rotation_rad ** 2 / 2)
        sin_r = rotation_rad - rotation_rad ** 3 / 6
        
        # Use QTransform for proper rotation
        transform = QTransform()
        transform.rotate(rotation_deg)
        rotated_normal = transform.map(normal)
        
        return rotated_normal
    
    def update_path(self):
        """Update the pipe path - exits perpendicular to component edges with orthogonal routing."""
        start_pos = self.start_port_item.get_scene_position()
        end_pos = self.end_port_item.get_scene_position()
        waypoints = self.pipe_data.get('waypoints', [])
        
        # Get exit vectors (perpendicular to component edges, accounting for rotation)
        start_vector = self._get_port_exit_vector(self.start_port_item)
        end_vector = self._get_port_exit_vector(self.end_port_item)
        
        path = QPainterPath()
        path.moveTo(start_pos)
        
        # Define perpendicular offset distance from port
        offset = 30
        
        # Calculate first point by moving along the exit vector
        start_point = QPointF(
            start_pos.x() + start_vector.x() * offset,
            start_pos.y() + start_vector.y() * offset
        )
        
        # Calculate last point by moving along the entry vector (opposite of exit)
        end_point = QPointF(
            end_pos.x() + end_vector.x() * offset,
            end_pos.y() + end_vector.y() * offset
        )
        
        if waypoints:
            path.lineTo(start_point)
            current_pos = start_point
            
            # Draw through waypoints with orthogonal routing
            for wp in waypoints:
                wp_pos = QPointF(wp[0], wp[1])
                # Create orthogonal path: horizontal then vertical
                path.lineTo(wp_pos.x(), current_pos.y())
                path.lineTo(wp_pos.x(), wp_pos.y())
                current_pos = wp_pos
            
            # Route from current position to last point, then to end
            path.lineTo(end_point.x(), current_pos.y())
            path.lineTo(end_point)
            path.lineTo(end_pos)
        else:
            # Simple right-angle routing with perpendicular exits
            path.lineTo(start_point)
            
            # Connect the two perpendicular segments with orthogonal routing
            # Determine if we should route horizontally or vertically first based on the vectors
            abs_x_diff = abs(start_point.x() - end_point.x())
            abs_y_diff = abs(start_point.y() - end_point.y())
            
            # Use midpoint routing
            mid_x = (start_point.x() + end_point.x()) / 2
            mid_y = (start_point.y() + end_point.y()) / 2
            
            # Route through midpoints to maintain orthogonal paths
            if abs(start_vector.x()) > abs(start_vector.y()):
                # Start vector is mostly horizontal
                path.lineTo(mid_x, start_point.y())
                path.lineTo(mid_x, end_point.y())
            else:
                # Start vector is mostly vertical
                path.lineTo(start_point.x(), mid_y)
                path.lineTo(end_point.x(), mid_y)
            
            path.lineTo(end_point)
            path.lineTo(end_pos)
        
        self.setPath(path)

    def shape(self):
        """Widen the interactive shape so drags/clicks are easy to hit."""
        base_path = super().shape() if not self.path().isEmpty() else QPainterPath()
        if not self.path().isEmpty():
            stroker = QPainterPathStroker()
            stroker.setWidth(12)  # generous hit area
            return stroker.createStroke(self.path())
        return base_path

    def hoverEnterEvent(self, event):
        """Highlight pipe on hover."""
        pen = self.pen()
        # IMPROVED: More visible hover effect
        pen.setWidth(6)
        self.setPen(pen)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Remove highlight."""
        # Only restore if not selected
        if not self.isSelected():
            pen = self.pen()
            # IMPROVED: Match new thicker default
            pen.setWidth(4)
            self.setPen(pen)
        super().hoverLeaveEvent(event)
    
    def itemChange(self, change, value):
        """Handle selection changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            if value:  # Selected
                # Highlight with yellow border
                pen = self.pen()
                pen.setWidth(6)
                pen.setColor(QColor("#FFD700"))  # Gold color for selection
                self.setPen(pen)
                # Detailed console dump for diagnostics
                try:
                    start = self.start_port_item
                    end = self.end_port_item
                    sp = start.parent_component.component_data if hasattr(start, 'parent_component') else {}
                    ep = end.parent_component.component_data if hasattr(end, 'parent_component') else {}
                    print("[PIPE DEBUG] ========= Selected Pipe =========")
                    print(f"[PIPE DEBUG] pipe_id            : {self.pipe_id}")
                    print(f"[PIPE DEBUG] fluid_state        : {self.pipe_data.get('fluid_state')}")
                    print(f"[PIPE DEBUG] pressure_side      : {self.pipe_data.get('pressure_side')}")
                    print(f"[PIPE DEBUG] circuit_label      : {self.pipe_data.get('circuit_label')}")
                    print(f"[PIPE DEBUG] waypoints          : {self.pipe_data.get('waypoints')}")
                    print(f"[PIPE DEBUG] start_component_id : {self.pipe_data.get('start_component_id')}")
                    print(f"[PIPE DEBUG] start_port         : {self.pipe_data.get('start_port')}")
                    print(f"[PIPE DEBUG] end_component_id   : {self.pipe_data.get('end_component_id')}")
                    print(f"[PIPE DEBUG] end_port           : {self.pipe_data.get('end_port')}")
                    # Start component details
                    print(f"[PIPE DEBUG] -- START COMPONENT --")
                    print(f"[PIPE DEBUG] type               : {sp.get('type')}")
                    print(f"[PIPE DEBUG] properties         : {sp.get('properties')}")
                    print(f"[PIPE DEBUG] rotation           : {sp.get('rotation')}")
                    print(f"[PIPE DEBUG] position           : {sp.get('position')}")
                    # End component details
                    print(f"[PIPE DEBUG] -- END COMPONENT --")
                    print(f"[PIPE DEBUG] type               : {ep.get('type')}")
                    print(f"[PIPE DEBUG] properties         : {ep.get('properties')}")
                    print(f"[PIPE DEBUG] rotation           : {ep.get('rotation')}")
                    print(f"[PIPE DEBUG] position           : {ep.get('position')}")
                    # Derived info
                    try:
                        dm = self.start_port_item.parent_component.data_manager
                        model = dm.diagram_model
                        print(f"[PIPE DEBUG] components_count   : {len((model or {}).get('components', {}))}")
                        print(f"[PIPE DEBUG] pipes_count        : {len((model or {}).get('pipes', {}))}")
                    except Exception:
                        pass
                    print("[PIPE DEBUG] ===================================")
                except Exception as e:
                    print(f"[PIPE DEBUG] Error while dumping pipe info: {e}")
            else:  # Deselected
                # Restore original pen
                self.setPen(self._original_pen)
        return super().itemChange(change, value)
    
    def mouseDoubleClickEvent(self, event):
        """Add waypoint on double-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = event.scenePos()
            if 'waypoints' not in self.pipe_data:
                self.pipe_data['waypoints'] = []
            
            self.pipe_data['waypoints'].append([scene_pos.x(), scene_pos.y()])
            print(f"[WAYPOINT] Added at ({scene_pos.x():.1f}, {scene_pos.y():.1f})")
            self.update_path()
            self.create_waypoint_handles()
        super().mouseDoubleClickEvent(event)
    
    def create_waypoint_handles(self):
        """Create draggable waypoint handles."""
        # Remove old handles
        for handle in self.waypoint_handles:
            if handle.scene():
                self.scene().removeItem(handle)
        self.waypoint_handles.clear()
        
        # Create new handles
        waypoints = self.pipe_data.get('waypoints', [])
        for i, wp in enumerate(waypoints):
            handle = WaypointHandle(self, i)
            if self.scene():
                self.scene().addItem(handle)
            self.waypoint_handles.append(handle)

    def mousePressEvent(self, event):
        """Start dragging the pipe to move all waypoints together (only if waypoints exist)."""
        if event.button() == Qt.MouseButton.LeftButton:
            waypoints = self.pipe_data.get('waypoints', [])
            # Only allow dragging if waypoints already exist
            if waypoints:
                print("[PIPE DRAG] Starting whole-line drag")
                self._is_dragging = True
                self._last_drag_scene_pos = event.scenePos()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
            # If no waypoints, just allow selection without creating waypoints
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """On drag, offset all waypoints by the mouse delta."""
        if self._is_dragging and self._last_drag_scene_pos is not None:
            print(f"[PIPE DRAG] Moving line - dragging={self._is_dragging}")
            current_pos = event.scenePos()
            delta = current_pos - self._last_drag_scene_pos
            waypoints = self.pipe_data.get('waypoints', [])
            print(f"[PIPE DRAG] Delta: ({delta.x():.1f}, {delta.y():.1f}), Waypoints: {len(waypoints)}")
            if waypoints:
                for i in range(len(waypoints)):
                    waypoints[i] = [waypoints[i][0] + delta.x(), waypoints[i][1] + delta.y()]
                self.update_path()
                # Move handles to new positions
                for i, handle in enumerate(self.waypoint_handles):
                    if i < len(waypoints):
                        handle.setPos(waypoints[i][0], waypoints[i][1])
            self._last_drag_scene_pos = current_pos
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """End dragging."""
        if self._is_dragging and event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self._last_drag_scene_pos = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class WaypointHandle(QGraphicsEllipseItem):
    """Draggable handle for pipe waypoints."""
    
    def __init__(self, pipe_item, waypoint_index):
        super().__init__(-5, -5, 10, 10)
        self.pipe_item = pipe_item
        self.waypoint_index = waypoint_index
        self.setAcceptHoverEvents(True)
        
        self.setBrush(QBrush(QColor("#FF9800")))  # Orange color
        self.setPen(QPen(Qt.GlobalColor.black, 2))
        
        # Custom drag handling instead of ItemIsMovable
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(5)  # Just above pipes but below components
        self._is_dragging = False
        
        # Set initial position
        waypoints = pipe_item.pipe_data.get('waypoints', [])
        if waypoint_index < len(waypoints):
            wp = waypoints[waypoint_index]
            self.setPos(wp[0], wp[1])
        
        self.setToolTip("Drag to move • Double-click to delete")
        
    def hoverEnterEvent(self, event):
        """Highlight on hover."""
        self.setBrush(QBrush(QColor("#FFC107")))  # Lighter orange
        self.setScale(1.3)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Remove highlight."""
        self.setBrush(QBrush(QColor("#FF9800")))
        self.setScale(1.0)
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """Start dragging this waypoint."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()  # Don't let pipe handle this
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Drag this waypoint."""
        if self._is_dragging:
            new_pos = event.scenePos()
            self.setPos(new_pos)
            
            # Update waypoint data
            waypoints = self.pipe_item.pipe_data.get('waypoints', [])
            if self.waypoint_index < len(waypoints):
                waypoints[self.waypoint_index] = [new_pos.x(), new_pos.y()]
                self.pipe_item.update_path()
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """End dragging this waypoint."""
        if self._is_dragging and event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """Delete waypoint on double-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            waypoints = self.pipe_item.pipe_data.get('waypoints', [])
            if self.waypoint_index < len(waypoints):
                del waypoints[self.waypoint_index]
                print(f"[WAYPOINT] Removed point {self.waypoint_index}")
                self.pipe_item.update_path()
                self.pipe_item.create_waypoint_handles()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)
