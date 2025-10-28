#!/usr/bin/env python3
"""
Calculation Output Generator
Generates detailed CSV/Excel files showing all calculation steps for verification.
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from calculation_orchestrator import CalculationOrchestrator
from data_manager import DataManager


class CalculationOutputGenerator:
    """
    Generates detailed output files showing all calculation results
    for verification and analysis.
    """
    
    def __init__(self, data_manager, config_json_path):
        self.data_manager = data_manager
        self.config_json_path = config_json_path
        self.orchestrator = CalculationOrchestrator(data_manager, config_json_path)
        
    def generate_full_output(self, output_dir='calculation_outputs'):
        """
        Generate comprehensive output files showing all calculations.
        
        Creates:
        1. on_time_data.csv - Rows where compressor is ON
        2. off_time_data.csv - Rows where compressor is OFF
        3. state_points.csv - All 8 state points for each ON-time row
        4. performance_metrics.csv - Superheat, subcooling, COP, etc.
        5. summary_report.txt - Human-readable summary
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        print("=" * 80)
        print("GENERATING CALCULATION OUTPUT FILES")
        print("=" * 80)
        
        # Get the full dataset
        full_df = self.data_manager.get_filtered_data()
        if full_df is None or full_df.empty:
            print("❌ No data available")
            return
        
        print(f"📊 Total rows in CSV: {len(full_df)}")
        
        # 1. Segregate ON-time vs OFF-time data
        print("\n🔍 STEP 1: Segregating ON-time vs OFF-time data...")
        on_time_df, off_time_df = self._segregate_on_off_time(full_df)
        
        # Save ON-time data
        on_time_file = output_path / f"on_time_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        on_time_df.to_csv(on_time_file, index=False)
        print(f"✅ Saved ON-time data: {on_time_file}")
        print(f"   Rows: {len(on_time_df)}")
        
        # Save OFF-time data
        off_time_file = output_path / f"off_time_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        off_time_df.to_csv(off_time_file, index=False)
        print(f"✅ Saved OFF-time data: {off_time_file}")
        print(f"   Rows: {len(off_time_df)}")
        
        # 2. Calculate 8-point cycle for ON-time data
        print("\n🔍 STEP 2: Calculating 8-point refrigeration cycle...")
        state_points_df = self._calculate_state_points(on_time_df)
        
        if state_points_df is not None:
            state_points_file = output_path / f"state_points_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            state_points_df.to_csv(state_points_file, index=False)
            print(f"✅ Saved state points: {state_points_file}")
            print(f"   Rows: {len(state_points_df)}")
            print(f"   Columns: {len(state_points_df.columns)}")
        
        # 3. Calculate performance metrics
        print("\n🔍 STEP 3: Calculating performance metrics...")
        performance_df = self._calculate_performance_metrics(on_time_df, state_points_df)
        
        if performance_df is not None:
            performance_file = output_path / f"performance_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            performance_df.to_csv(performance_file, index=False)
            print(f"✅ Saved performance metrics: {performance_file}")
            print(f"   Rows: {len(performance_df)}")
        
        # 4. Generate summary report
        print("\n🔍 STEP 4: Generating summary report...")
        summary_file = output_path / f"summary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        self._generate_summary_report(
            summary_file, 
            full_df, 
            on_time_df, 
            off_time_df, 
            state_points_df, 
            performance_df
        )
        print(f"✅ Saved summary report: {summary_file}")
        
        print("\n" + "=" * 80)
        print("✅ ALL OUTPUT FILES GENERATED SUCCESSFULLY")
        print("=" * 80)
        print(f"\n📁 Output directory: {output_path.absolute()}")
        
        return {
            'on_time_file': on_time_file,
            'off_time_file': off_time_file,
            'state_points_file': state_points_file,
            'performance_file': performance_file,
            'summary_file': summary_file
        }
    
    def _segregate_on_off_time(self, full_df):
        """Segregate data into ON-time and OFF-time based on suction pressure."""
        # Get suction pressure sensor
        with open(self.config_json_path, 'r') as f:
            data = json.load(f)
        
        # Try different JSON formats
        sensor_roles = data.get('sensor_roles', {})
        if not sensor_roles:
            sensor_roles = data.get('diagramModel', {}).get('sensor_roles', {})
        
        # Find suction pressure sensor
        suction_sensor = None
        for key, value in sensor_roles.items():
            if '.SP' in key and 'Compressor' in key:
                suction_sensor = value
                break
        
        if not suction_sensor or suction_sensor not in full_df.columns:
            print(f"⚠️  Warning: Suction pressure sensor not found. Using all data as ON-time.")
            return full_df.copy(), pd.DataFrame()
        
        threshold = self.data_manager.on_time_threshold_psig
        
        # Segregate
        on_time_df = full_df[full_df[suction_sensor] > threshold].copy()
        off_time_df = full_df[full_df[suction_sensor] <= threshold].copy()
        
        # Add a flag column
        on_time_df['COMPRESSOR_STATE'] = 'ON'
        off_time_df['COMPRESSOR_STATE'] = 'OFF'
        
        print(f"   Suction Pressure Sensor: {suction_sensor}")
        print(f"   Threshold: {threshold} psig")
        print(f"   ON-time rows: {len(on_time_df)} ({len(on_time_df)/len(full_df)*100:.1f}%)")
        print(f"   OFF-time rows: {len(off_time_df)} ({len(off_time_df)/len(full_df)*100:.1f}%)")
        
        return on_time_df, off_time_df
    
    def _calculate_state_points(self, on_time_df):
        """Calculate all 8 state points for each row."""
        if on_time_df.empty:
            return None
        
        # Run the orchestrator
        try:
            results = self.orchestrator.calculate_all()
            
            if not results or 'state_points' not in results:
                print("⚠️  No state points calculated")
                return None
            
            state_points = results['state_points']
            
            # Build a DataFrame with all state points
            rows = []
            for i in range(len(state_points.get('point_1', {}).get('P', []))):
                row = {}
                
                # Add timestamp if available
                if 'Timestamp' in on_time_df.columns:
                    row['Timestamp'] = on_time_df.iloc[i]['Timestamp']
                
                # Add all 8 state points
                for point_name in ['point_1', 'point_2a', 'point_2b', 'point_3a', 
                                   'point_3b', 'point_4a', 'point_4b', 'point_5']:
                    if point_name in state_points:
                        point_data = state_points[point_name]
                        row[f'{point_name}_P_psia'] = point_data['P'][i] if i < len(point_data['P']) else None
                        row[f'{point_name}_T_F'] = point_data['T'][i] if i < len(point_data['T']) else None
                        row[f'{point_name}_h_Btu_lb'] = point_data['h'][i] if i < len(point_data['h']) else None
                        row[f'{point_name}_s_Btu_lbR'] = point_data['s'][i] if i < len(point_data['s']) else None
                        row[f'{point_name}_quality'] = point_data.get('quality', [None]*len(point_data['P']))[i]
                
                rows.append(row)
            
            df = pd.DataFrame(rows)
            print(f"   Calculated {len(df)} rows × {len(df.columns)} state point values")
            
            return df
            
        except Exception as e:
            print(f"❌ Error calculating state points: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _calculate_performance_metrics(self, on_time_df, state_points_df):
        """Calculate performance metrics (superheat, subcooling, COP, etc.)."""
        if on_time_df.empty:
            return None
        
        try:
            results = self.orchestrator.calculate_all()
            
            if not results:
                print("⚠️  No performance metrics calculated")
                return None
            
            rows = []
            
            # Get lengths
            n_rows = len(results.get('superheat', []))
            
            for i in range(n_rows):
                row = {}
                
                # Add timestamp if available
                if 'Timestamp' in on_time_df.columns:
                    row['Timestamp'] = on_time_df.iloc[i]['Timestamp']
                
                # Superheat & Subcooling
                row['Superheat_F'] = results.get('superheat', [None]*n_rows)[i]
                row['Subcooling_F'] = results.get('subcooling', [None]*n_rows)[i]
                
                # Mass flow rate
                row['Mass_Flow_Rate_lb_hr'] = results.get('mass_flow_rate', [None]*n_rows)[i]
                
                # Performance metrics
                row['Cooling_Capacity_Btu_hr'] = results.get('cooling_capacity', [None]*n_rows)[i]
                row['Compressor_Power_Btu_hr'] = results.get('compressor_power', [None]*n_rows)[i]
                row['Heat_Rejection_Btu_hr'] = results.get('heat_rejection', [None]*n_rows)[i]
                row['COP'] = results.get('cop', [None]*n_rows)[i]
                row['EER'] = results.get('eer', [None]*n_rows)[i]
                
                rows.append(row)
            
            df = pd.DataFrame(rows)
            print(f"   Calculated {len(df)} rows × {len(df.columns)} performance metrics")
            
            return df
            
        except Exception as e:
            print(f"❌ Error calculating performance metrics: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_summary_report(self, output_file, full_df, on_time_df, off_time_df, 
                                  state_points_df, performance_df):
        """Generate a human-readable summary report."""
        with open(output_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("REFRIGERATION SYSTEM CALCULATION REPORT\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Configuration: {self.config_json_path}\n")
            f.write(f"CSV Path: {self.data_manager.csv_path}\n")
            f.write("\n")
            
            # Data overview
            f.write("-" * 80 + "\n")
            f.write("DATA OVERVIEW\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total rows in CSV: {len(full_df)}\n")
            f.write(f"ON-time rows: {len(on_time_df)} ({len(on_time_df)/len(full_df)*100:.1f}%)\n")
            f.write(f"OFF-time rows: {len(off_time_df)} ({len(off_time_df)/len(full_df)*100:.1f}%)\n")
            f.write(f"ON-time threshold: {self.data_manager.on_time_threshold_psig} psig\n")
            f.write(f"Refrigerant: {self.data_manager.refrigerant}\n")
            f.write("\n")
            
            # State points summary
            if state_points_df is not None and not state_points_df.empty:
                f.write("-" * 80 + "\n")
                f.write("STATE POINTS SUMMARY (8-Point Cycle)\n")
                f.write("-" * 80 + "\n")
                
                for point_name in ['point_1', 'point_2a', 'point_2b', 'point_3a', 
                                   'point_3b', 'point_4a', 'point_4b', 'point_5']:
                    p_col = f'{point_name}_P_psia'
                    t_col = f'{point_name}_T_F'
                    h_col = f'{point_name}_h_Btu_lb'
                    
                    if p_col in state_points_df.columns:
                        f.write(f"\n{point_name.upper()}:\n")
                        f.write(f"  Pressure (psia): {state_points_df[p_col].mean():.2f} avg, "
                               f"{state_points_df[p_col].min():.2f} min, "
                               f"{state_points_df[p_col].max():.2f} max\n")
                        f.write(f"  Temperature (°F): {state_points_df[t_col].mean():.2f} avg, "
                               f"{state_points_df[t_col].min():.2f} min, "
                               f"{state_points_df[t_col].max():.2f} max\n")
                        f.write(f"  Enthalpy (Btu/lb): {state_points_df[h_col].mean():.2f} avg, "
                               f"{state_points_df[h_col].min():.2f} min, "
                               f"{state_points_df[h_col].max():.2f} max\n")
                
                f.write("\n")
            
            # Performance metrics summary
            if performance_df is not None and not performance_df.empty:
                f.write("-" * 80 + "\n")
                f.write("PERFORMANCE METRICS SUMMARY\n")
                f.write("-" * 80 + "\n")
                
                metrics = {
                    'Superheat_F': 'Superheat (°F)',
                    'Subcooling_F': 'Subcooling (°F)',
                    'Mass_Flow_Rate_lb_hr': 'Mass Flow Rate (lb/hr)',
                    'Cooling_Capacity_Btu_hr': 'Cooling Capacity (Btu/hr)',
                    'Compressor_Power_Btu_hr': 'Compressor Power (Btu/hr)',
                    'Heat_Rejection_Btu_hr': 'Heat Rejection (Btu/hr)',
                    'COP': 'COP',
                    'EER': 'EER'
                }
                
                for col, label in metrics.items():
                    if col in performance_df.columns:
                        f.write(f"\n{label}:\n")
                        f.write(f"  Average: {performance_df[col].mean():.2f}\n")
                        f.write(f"  Min: {performance_df[col].min():.2f}\n")
                        f.write(f"  Max: {performance_df[col].max():.2f}\n")
                        f.write(f"  Std Dev: {performance_df[col].std():.2f}\n")
                
                f.write("\n")
            
            f.write("=" * 80 + "\n")
            f.write("END OF REPORT\n")
            f.write("=" * 80 + "\n")


def main():
    """Command-line interface for generating calculation outputs."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python calculation_output_generator.py <config.json>")
        print("Example: python calculation_output_generator.py ID6SU12WE-5.json")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    if not Path(config_file).exists():
        print(f"❌ Error: Config file not found: {config_file}")
        sys.exit(1)
    
    # Load config to get CSV path
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    csv_path = config.get('csvPath', 'data.csv')
    
    # Create data manager
    data_manager = DataManager()
    
    # Load CSV
    print(f"📂 Loading CSV: {csv_path}")
    if not data_manager.load_csv(csv_path):
        print(f"❌ Error: Could not load CSV file: {csv_path}")
        sys.exit(1)
    
    # Load diagram model
    print(f"📂 Loading configuration: {config_file}")
    diagram_model = config.get('diagramModel', config.get('diagram', {}))
    data_manager.diagram_model = diagram_model
    
    # Generate outputs
    generator = CalculationOutputGenerator(data_manager, config_file)
    generator.generate_full_output()


if __name__ == '__main__':
    main()



