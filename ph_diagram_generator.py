"""
P-h Diagram Generator for R290 Refrigerant

Generates saturation data and cycle data for P-h diagram visualization.
Uses CoolProp to calculate thermodynamic properties.
"""

import numpy as np
import pandas as pd
from CoolProp.CoolProp import PropsSI
import warnings

warnings.filterwarnings('ignore')


class PhDiagramGenerator:
    """Generates P-h diagram data for R290 refrigeration cycles."""
    
    def __init__(self, refrigerant='R290'):
        self.refrigerant = refrigerant
        
    def generate_saturation_data(self, P_min_kpa=100, P_max_kpa=4500, num_points=50):
        """
        Generate saturation line data (liquid and vapor lines) for R290.
        
        Args:
            P_min_kpa: Minimum pressure in kPa
            P_max_kpa: Maximum pressure in kPa
            num_points: Number of points to generate along saturation curve
            
        Returns:
            dict with keys: pressures, h_liquid, h_vapor (all in kPa and kJ/kg)
        """
        pressures_pa = np.logspace(np.log10(P_min_kpa * 1000), 
                                   np.log10(P_max_kpa * 1000), 
                                   num_points)
        pressures_kpa = pressures_pa / 1000
        
        h_liquid = []
        h_vapor = []
        valid_pressures = []
        
        for P_pa in pressures_pa:
            try:
                # Saturated liquid (Q=0)
                h_f = PropsSI('H', 'P', P_pa, 'Q', 0, self.refrigerant) / 1000  # kJ/kg
                # Saturated vapor (Q=1)
                h_g = PropsSI('H', 'P', P_pa, 'Q', 1, self.refrigerant) / 1000  # kJ/kg
                
                # Only include valid points
                if 0 < h_f < 1000 and 0 < h_g < 1000:
                    h_liquid.append(h_f)
                    h_vapor.append(h_g)
                    valid_pressures.append(P_pa / 1000)  # Convert back to kPa
            except:
                pass
        
        return {
            'pressures': np.array(valid_pressures),
            'h_liquid': np.array(h_liquid),
            'h_vapor': np.array(h_vapor)
        }
    
    def extract_cycle_data(self, filtered_df):
        """
        Extract cycle state points from filtered DataFrame.
        
        Args:
            filtered_df: DataFrame with calculated columns from CalculationsWidget
            
        Returns:
            dict with cycle data including common and circuit-specific points
        """
        if filtered_df.empty:
            return None
        
        # Use the first row (latest data point)
        data_row = filtered_df.iloc[0]
        
        cycle_data = {
            'P_suc_pa': data_row.get('P_suc', np.nan),      # Suction pressure in Pa
            'P_cond_pa': data_row.get('P_cond', np.nan),    # Condenser pressure in Pa
            'common_points': {},
            'circuit_points': {'LH': {}, 'CTR': {}, 'RH': {}}
        }
        
        # Convert pressures from Pa to kPa
        P_suc_kpa = cycle_data['P_suc_pa'] / 1000 if not np.isnan(cycle_data['P_suc_pa']) else 0
        P_cond_kpa = cycle_data['P_cond_pa'] / 1000 if not np.isnan(cycle_data['P_cond_pa']) else 0
        
        # ===== Common Points (non-circuit-specific) =====
        
        # Point 2b (Suction line, superheated)
        if 'h_2b' in data_row.index:
            h_2b = data_row['h_2b']
            if not np.isnan(h_2b) and 200 < h_2b < 700:
                cycle_data['common_points']['2b'] = {
                    'h': h_2b,
                    'P': P_suc_kpa,
                    'desc': 'Suction Line (Superheated)',
                    'color': '#111827'
                }
        
        # Point 3a (Discharge line, superheated)
        if 'h_3a' in data_row.index:
            h_3a = data_row['h_3a']
            if not np.isnan(h_3a) and 200 < h_3a < 700:
                cycle_data['common_points']['3a'] = {
                    'h': h_3a,
                    'P': P_cond_kpa,
                    'desc': 'Discharge Line (Superheated)',
                    'color': '#111827'
                }
        
        # Point 3b (Condenser inlet, gas)
        if 'h_3b' in data_row.index:
            h_3b = data_row['h_3b']
            if not np.isnan(h_3b) and 200 < h_3b < 700:
                cycle_data['common_points']['3b'] = {
                    'h': h_3b,
                    'P': P_cond_kpa,
                    'desc': 'Condenser Inlet',
                    'color': '#111827'
                }
        
        # Point 4a (Condenser outlet, subcooled)
        if 'h_4a' in data_row.index:
            h_4a = data_row['h_4a']
            if not np.isnan(h_4a) and 200 < h_4a < 700:
                cycle_data['common_points']['4a'] = {
                    'h': h_4a,
                    'P': P_cond_kpa,
                    'desc': 'Condenser Outlet (Subcooled)',
                    'color': '#111827'
                }
        
        # ===== Circuit-Specific Points =====
        circuits = {
            'LH': {'color': '#3b82f6', 'desc_prefix': 'Left Hand'},
            'CTR': {'color': '#16a34a', 'desc_prefix': 'Center'},
            'RH': {'color': '#a855f7', 'desc_prefix': 'Right Hand'}
        }
        
        for circuit, circuit_info in circuits.items():
            color = circuit_info['color']
            
            # Point 4b (TXV inlet, high pressure side)
            h_4b_col = f'h_4b_{circuit}'
            h_4b = None
            if h_4b_col in data_row.index:
                h_4b = data_row[h_4b_col]
                if not np.isnan(h_4b) and 200 < h_4b < 700:
                    cycle_data['circuit_points'][circuit]['4b'] = {
                        'h': h_4b,
                        'P': P_cond_kpa,
                        'desc': f'{circuit_info["desc_prefix"]} - TXV Inlet (Subcooled)',
                        'color': color
                    }
            
            # Point 1 (TXV outlet / Evap inlet) - Isenthalpic expansion: h_1 = h_4b, P_1 = P_suc
            if h_4b is not None and not np.isnan(h_4b):
                cycle_data['circuit_points'][circuit]['1'] = {
                    'h': h_4b,  # Isenthalpic expansion through TXV
                    'P': P_suc_kpa,
                    'desc': f'{circuit_info["desc_prefix"]} - Evap Inlet (TXV Exit)',
                    'color': color
                }
            
            # Point 2a (TXV bulb, low pressure side)
            h_2a_col = f'h_2a_{circuit}'
            if h_2a_col in data_row.index:
                h_2a = data_row[h_2a_col]
                if not np.isnan(h_2a) and 200 < h_2a < 700:
                    cycle_data['circuit_points'][circuit]['2a'] = {
                        'h': h_2a,
                        'P': P_suc_kpa,
                        'desc': f'{circuit_info["desc_prefix"]} - Evap Outlet',
                        'color': color
                    }
        
        return cycle_data
    
    def get_cycle_paths(self, cycle_data):
        """
        Generate path sequences for plotting cycles.
        
        Args:
            cycle_data: Output from extract_cycle_data()
            
        Returns:
            dict with paths for common and circuit-specific cycles
        """
        paths = {
            'common_compression': [],  # 2b -> 3a
            'LH_cycle': [],   # 3a -> 4b_LH -> 2a_LH -> 2b
            'CTR_cycle': [],  # 3a -> 4b_CTR -> 2a_CTR -> 2b
            'RH_cycle': [],   # 3a -> 4b_RH -> 2a_RH -> 2b
            'LH_mix': [],     # 2a_LH -> 2b
            'CTR_mix': [],    # 2a_CTR -> 2b
            'RH_mix': []      # 2a_RH -> 2b
        }
        
        common = cycle_data['common_points']
        circuits = cycle_data['circuit_points']
        
        # Common compression: 2b -> 3a
        if '2b' in common and '3a' in common:
            paths['common_compression'] = [
                common['2b'],
                common['3a']
            ]
        
        # Build cycle paths for each circuit
        # IMPORTANT: Circuit paths should NOT include the compression (2b -> 3a)
        # That is drawn separately as the common compression line
        for circuit_name in ['LH', 'CTR', 'RH']:
            # Circuit-specific cycle: 3a -> 4b -> 1 -> 2a (NOT back to 2b)
            cycle_path = []
            if '3a' in common:
                cycle_path.append(common['3a'])
            if '4b' in circuits[circuit_name]:
                cycle_path.append(circuits[circuit_name]['4b'])
            if '1' in circuits[circuit_name]:
                cycle_path.append(circuits[circuit_name]['1'])
            if '2a' in circuits[circuit_name]:
                cycle_path.append(circuits[circuit_name]['2a'])
            
            paths[f'{circuit_name}_cycle'] = cycle_path
            
            # Mixing line: 2a -> 2b (dashed line showing flow convergence)
            mix_path = []
            if '2a' in circuits[circuit_name]:
                mix_path.append(circuits[circuit_name]['2a'])
            if '2b' in common:
                mix_path.append(common['2b'])
            
            paths[f'{circuit_name}_mix'] = mix_path
        
        return paths
    
    def get_all_points(self, cycle_data):
        """
        Get all state points as a flat list for plotting.
        
        Args:
            cycle_data: Output from extract_cycle_data()
            
        Returns:
            list of point dicts with id, h, P, desc, color
        """
        all_points = []
        
        # Add common points
        for point_id, point_data in cycle_data['common_points'].items():
            all_points.append({
                'id': point_id,
                'h': point_data['h'],
                'P': point_data['P'],
                'desc': point_data['desc'],
                'color': point_data['color']
            })
        
        # Add circuit points
        for circuit, points in cycle_data['circuit_points'].items():
            for point_id, point_data in points.items():
                all_points.append({
                    'id': f'{point_id}_{circuit}',
                    'h': point_data['h'],
                    'P': point_data['P'],
                    'desc': point_data['desc'],
                    'color': point_data['color']
                })
        
        return all_points


# Example usage for testing
if __name__ == '__main__':
    gen = PhDiagramGenerator('R290')
    
    # Generate saturation data
    sat_data = gen.generate_saturation_data()
    print(f"Generated {len(sat_data['pressures'])} saturation points")
    print(f"Pressure range: {sat_data['pressures'][0]:.1f} - {sat_data['pressures'][-1]:.1f} kPa")
    print(f"Enthalpy range (liquid): {sat_data['h_liquid'].min():.1f} - {sat_data['h_liquid'].max():.1f} kJ/kg")
    print(f"Enthalpy range (vapor): {sat_data['h_vapor'].min():.1f} - {sat_data['h_vapor'].max():.1f} kJ/kg")
