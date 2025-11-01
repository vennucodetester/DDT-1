import sys
import argparse
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLabel, QFrame, QPushButton,
                             QFileDialog)
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt, QTimer

# Initialize logging early, before other imports that might log
from logging_setup import init_logging


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="HVAC System Analyzer")
    parser.add_argument(
        "--log",
        type=str,
        default=None,
        help="Path to log file (default: logs/app_YYYYMMDD_HHMMSS.log)"
    )
    return parser.parse_args()


# Parse args and initialize logging
args = parse_args()
log_file = init_logging(args.log)

# Import our component classes
from data_manager import DataManager
from sensor_panel import SensorPanel
from diagram_widget import DiagramWidget
from graph_widget import GraphWidget
from comparison_widget import ComparisonWidget
from mapping_dialog import MappingDialog
from calculations_widget import CalculationsWidget
from ph_diagram_interactive_widget import PhDiagramInteractiveWidget

class MainWindow(QMainWindow):
    """The main application window, orchestrating all other components."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HVAC System Analyzer (Python Edition)")
        self.setGeometry(100, 100, 1600, 900)
        self.set_light_theme()

        self.data_manager = DataManager(self) 

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Instantiate UI Components ---
        self.sensor_panel = SensorPanel(self.data_manager)
        
        self.diagram_widget = DiagramWidget(self.data_manager)
        self.graph_widget = GraphWidget(self.data_manager)
        self.comparison_widget = ComparisonWidget(self.data_manager)
        self.calculations_widget = CalculationsWidget(self.data_manager)
        self.ph_diagram_interactive_widget = PhDiagramInteractiveWidget(self.data_manager)

        # --- Assemble Layout ---
        self.sensor_panel.setFixedWidth(350) 
        main_layout.addWidget(self.sensor_panel)
        
        right_panel = self.setup_tabs()
        main_layout.addWidget(right_panel)
        
        # --- Connect Signals and Slots ---
        self.connect_signals()

        # Ensure window becomes visible and focused shortly after startup
        QTimer.singleShot(150, self._bring_to_front)

    def _bring_to_front(self):
        try:
            self.showNormal()
            self.raise_()
            self.activateWindow()
            print("[APP] Main window shown and focused")
        except Exception:
            pass

    def setup_tabs(self):
        """Creates the tab widget and populates it with our custom widgets."""
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        self.tabs.addTab(self.diagram_widget, "Diagram")
        self.tabs.addTab(self.graph_widget, "Graph")
        self.tabs.addTab(self.comparison_widget, "Comparison")
        self.tabs.addTab(self.calculations_widget, "Calculations")
        self.tabs.addTab(self.ph_diagram_interactive_widget, "P-h Interactive")
        
        right_layout.addWidget(self.tabs)
        return right_panel

    def connect_signals(self):
        """Central place to connect all component signals to controller slots."""
        self.sensor_panel.load_csv_button.clicked.connect(self.open_csv_file_dialog)
        self.sensor_panel.load_config_button.clicked.connect(self.open_session_file_dialog)
        self.sensor_panel.save_config_button.clicked.connect(self.save_session_file_dialog)
        
        # Update UI only for the active tab to reduce redundant work
        self.data_manager.data_changed.connect(self.update_active_tab)
        # Also listen to diagram model changes for standard component sensor mappings
        self.data_manager.diagram_model_changed.connect(self.update_active_tab)

        # --- FIX: Removed connection to the non-existent signal ---
        # self.sensor_panel.graph_sensor_toggled.connect(self.on_graph_sensor_toggled)
        
        # Connect diagram widget sensor port clicks to sensor panel highlighting
        self.diagram_widget.sensor_port_clicked.connect(self.sensor_panel.highlight_and_scroll_to_sensor)
        
        # Connect Calculations widget to P-h Diagram widget
        self.calculations_widget.filtered_data_ready.connect(self.ph_diagram_interactive_widget.load_filtered_data)
        
    def open_csv_file_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open CSV File", "", "CSV Files (*.csv)")
        if file_name:
            self.data_manager.load_csv(file_name) 

    def open_session_file_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Session File", "", "JSON Files (*.json)")
        if file_name:
            self.data_manager.load_session(file_name)
    
    def save_session_file_dialog(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Session File", "", "JSON Files (*.json)")
        if file_name:
            if not file_name.lower().endswith('.json'):
                file_name = file_name + '.json'
            self.data_manager.save_session(file_name)
    
    # --- FIX: Removed the unused slot method ---
    # def on_graph_sensor_toggled(self, sensor_name, is_selected_for_graph):
    #     self.data_manager.set_sensor_graphed(sensor_name, is_selected_for_graph)
    #     self.data_manager.data_changed.emit()

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for the main window."""
        if event.key() == Qt.Key.Key_Escape:
            # Deselect all sensors when Escape is pressed
            self.data_manager.selected_sensors.clear()
            self.data_manager.data_changed.emit()
        else:
            super().keyPressEvent(event)

    def on_tab_changed(self, index):
        # When user switches tabs, refresh that tab only
        self.update_active_tab()

    def update_active_tab(self):
        print("[SIGNAL] update_active_tab() called")
        # Always keep sensor panel in sync (lightweight)
        try:
            self.sensor_panel.update_ui()
        except Exception:
            pass
        # Update only the visible right-hand tab
        current_widget = self.tabs.currentWidget()
        try:
            if current_widget is self.diagram_widget:
                print("[SIGNAL] Updating diagram_widget")
                self.diagram_widget.update_ui()
            elif current_widget is self.graph_widget:
                print("[SIGNAL] Updating graph_widget")
                self.graph_widget.update_ui()
            elif current_widget is self.comparison_widget:
                print("[SIGNAL] Updating comparison_widget")
                self.comparison_widget.update_ui()
            elif current_widget is self.calculations_widget:
                # Update calculations widget (pressure threshold filtering)
                print("[SIGNAL] Updating calculations_widget (threshold filtering)")
                pass  # Widget updates on demand via filter button
            else:
                # Other widgets
                print("[SIGNAL] Updating other widget")
                pass
        except Exception as e:
            print(f"[SIGNAL] Error in update_active_tab: {e}")
            pass

    def set_light_theme(self):
        """Sets a professional light theme for the application."""
        app = QApplication.instance()
        app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        app.setPalette(palette)
        self.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #c4c4c4; background: #ffffff; }
            QTabBar::tab { 
                background: #e1e1e1; color: #333; padding: 10px 25px; 
                font-weight: bold; border: 1px solid #c4c4c4; border-bottom: none;
                border-top-left-radius: 4px; border-top-right-radius: 4px;
            }
            QTabBar::tab:selected { 
                background: #ffffff; color: #007bff; border-bottom: 2px solid #007bff;
            }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

