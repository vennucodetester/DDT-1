"""
CoolProp-based thermodynamic calculation engine for R290 refrigerant.
Calculates state point properties and system performance metrics.

⚠️ ⚠️ ⚠️ DEPRECATED - DO NOT USE ⚠️ ⚠️ ⚠️

This module has been RETIRED and replaced by the unified calculation system:
- calculation_engine.py: Core calculation functions (Step 1 & Step 2)
- calculation_orchestrator.py: Batch processing orchestrator
- port_resolver.py: Flexible sensor mapping

The new system:
✓ Adapts to any sensor configuration (no hardcoded column names)
✓ Uses user-provided rated inputs for volumetric efficiency
✓ Calculates from first principles (per Calculations-DDT.txt spec)
✓ Supports row-by-row batch processing
✓ Follows goal.md implementation plan

This file is kept for reference only. All imports have been removed from active code.
If you see this module being imported anywhere, it is a bug - please remove the import.

Last updated: 2025-10-29 (Step 6 of goal.md migration)
"""

import pandas as pd
import numpy as np
from CoolProp.CoolProp import PropsSI
import warnings

warnings.filterwarnings('ignore')

# Emit deprecation warning
warnings.warn(
    "coolprop_calculator.py is DEPRECATED and will be removed in a future version. "
    "Use calculation_orchestrator.run_batch_processing() instead.",
    DeprecationWarning,
    stacklevel=2
)

class ThermodynamicCalculator:
    """
    Calculates thermodynamic properties for R290 refrigeration cycle.
    Uses CoolProp to determine enthalpy, entropy, and other state properties.
    """
    
    # Mapping from old names (with units) to clean names (without units)
    COLUMN_NAME_MAPPING = {
        # State point properties - common
        'h_2a_kJ_kg': 'h_2a',
        's_2a_kJ_kgK': 's_2a',
        'rho_2a_kg_m3': 'rho_2a',
        'h_2b_kJ_kg': 'h_2b',
        's_2b_kJ_kgK': 's_2b',
        'rho_2b_kg_m3': 'rho_2b',
        'h_3a_kJ_kg': 'h_3a',
        's_3a_kJ_kgK': 's_3a',
        'rho_3a_kg_m3': 'rho_3a',
        'h_3b_kJ_kg': 'h_3b',
        's_3b_kJ_kgK': 's_3b',
        'h_4a_kJ_kg': 'h_4a',
        's_4a_kJ_kgK': 's_4a',
        'rho_4a_kg_m3': 'rho_4a',
        'h_4b_kJ_kg': 'h_4b',
        's_4b_kJ_kgK': 's_4b',
        'rho_4b_kg_m3': 'rho_4b',
        # Saturation properties
        'T_sat_evap_K': 'T_sat_evap',
        'h_f_evap_kJ_kg': 'h_f_evap',
        'h_g_evap_kJ_kg': 'h_g_evap',
        's_f_evap_kJ_kgK': 's_f_evap',
        's_g_evap_kJ_kgK': 's_g_evap',
        'T_sat_cond_K': 'T_sat_cond',
        'h_f_cond_kJ_kg': 'h_f_cond',
        'h_g_cond_kJ_kg': 'h_g_cond',
        's_f_cond_kJ_kgK': 's_f_cond',
        's_g_cond_kJ_kgK': 's_g_cond',
        # Circuit-specific properties
        'h_2a_LH_kJ_kg': 'h_2a_LH',
        's_2a_LH_kJ_kgK': 's_2a_LH',
        'h_4b_LH_kJ_kg': 'h_4b_LH',
        's_4b_LH_kJ_kgK': 's_4b_LH',
        'h_2a_CTR_kJ_kg': 'h_2a_CTR',
        's_2a_CTR_kJ_kgK': 's_2a_CTR',
        'h_4b_CTR_kJ_kg': 'h_4b_CTR',
        's_4b_CTR_kJ_kgK': 's_4b_CTR',
        'h_2a_RH_kJ_kg': 'h_2a_RH',
        's_2a_RH_kJ_kgK': 's_2a_RH',
        'h_4b_RH_kJ_kg': 'h_4b_RH',
        's_4b_RH_kJ_kgK': 's_4b_RH',
    }
    
    def __init__(self):
        self.refrigerant = 'R290'  # Propane
        self.pa_to_mpa = 1e-6
        self.kelvin_to_celsius = 273.15
    
    def fahrenheit_to_kelvin(self, temp_f):
        """Convert Fahrenheit to Kelvin."""
        return (temp_f - 32) / 1.8 + 273.15
    
    def fahrenheit_to_celsius(self, temp_f):
        """Convert Fahrenheit to Celsius."""
        return (temp_f - 32) / 1.8
    
    def psig_to_pa(self, pressure_psig):
        """Convert PSIG to Pascals. Note: absolute pressure = gauge + 14.7 PSI."""
        pressure_psia = pressure_psig + 14.7
        return pressure_psia * 6894.757  # 1 PSI = 6894.757 Pa
    
    def celsius_to_kelvin(self, temp_c):
        """Convert Celsius to Kelvin."""
        return temp_c + 273.15
    
    def calculate_state_point(self, T_K, P_pa, property_set='TP'):
        """
        Calculate state point properties at given T and P.
        Returns dictionary with h, s, rho, quality (if applicable).
        """
        try:
            h = PropsSI('H', 'T', T_K, 'P', P_pa, self.refrigerant)  # [J/kg]
            s = PropsSI('S', 'T', T_K, 'P', P_pa, self.refrigerant)  # [J/(kg·K)]
            rho = PropsSI('D', 'T', T_K, 'P', P_pa, self.refrigerant)  # [kg/m³]
            
            # Try to get quality (will fail if single-phase)
            try:
                quality = PropsSI('Q', 'T', T_K, 'P', P_pa, self.refrigerant)
            except:
                quality = np.nan
            
            return {
                'h': h / 1000,  # Convert to kJ/kg
                's': s / 1000,  # Convert to kJ/(kg·K)
                'rho': rho,
                'quality': quality
            }
        except Exception as e:
            print(f"[CoolProp] Error calculating state point (T={T_K}K, P={P_pa}Pa): {e}")
            return None
    
    def get_saturation_properties(self, P_pa):
        """
        Get saturation properties at given pressure.
        Returns T_sat, h_f, h_g, s_f, s_g.
        """
        try:
            T_sat = PropsSI('T', 'P', P_pa, 'Q', 0, self.refrigerant)  # Saturation temperature [K]
            h_f = PropsSI('H', 'P', P_pa, 'Q', 0, self.refrigerant) / 1000  # [kJ/kg]
            h_g = PropsSI('H', 'P', P_pa, 'Q', 1, self.refrigerant) / 1000  # [kJ/kg]
            s_f = PropsSI('S', 'P', P_pa, 'Q', 0, self.refrigerant) / 1000  # [kJ/(kg·K)]
            s_g = PropsSI('S', 'P', P_pa, 'Q', 1, self.refrigerant) / 1000  # [kJ/(kg·K)]
            
            return {
                'T_sat': T_sat,
                'h_f': h_f,
                'h_g': h_g,
                's_f': s_f,
                's_g': s_g
            }
        except Exception as e:
            print(f"[CoolProp] Error calculating saturation properties at P={P_pa}Pa: {e}")
            return None
    
    def calculate_superheat(self, T_K, T_sat_K):
        """Calculate degree of superheat in Kelvin."""
        return T_K - T_sat_K
    
    def calculate_subcooling(self, T_sat_K, T_K):
        """Calculate degree of subcooling in Kelvin."""
        return T_sat_K - T_K
    
    def calculate_state_point_hp(self, h_j_kg, P_pa):
        """
        Calculate state point properties at given H and P.
        Used for isenthalpic processes (e.g., Point 1 after TXV expansion).
        
        Args:
            h_j_kg: Enthalpy in J/kg
            P_pa: Pressure in Pa
        
        Returns: Dictionary with h, s, rho, quality (if applicable)
        """
        try:
            # Use CoolProp PropsSI with H and P inputs
            s = PropsSI('S', 'H', h_j_kg, 'P', P_pa, self.refrigerant)  # [J/(kg·K)]
            rho = PropsSI('D', 'H', h_j_kg, 'P', P_pa, self.refrigerant)  # [kg/m³]
            
            # Try to get quality (will fail if single-phase)
            try:
                quality = PropsSI('Q', 'H', h_j_kg, 'P', P_pa, self.refrigerant)
            except:
                quality = np.nan
            
            return {
                'h': h_j_kg / 1000,  # Convert to kJ/kg
                's': s / 1000,  # Convert to kJ/(kg·K)
                'rho': rho,
                'quality': quality
            }
        except Exception as e:
            print(f"[CoolProp] Error calculating state point (H={h_j_kg}J/kg, P={P_pa}Pa): {e}")
            return None
    
    def process_row(self, row):
        """
        Process a single row of data and calculate all thermodynamic properties.
        
        Returns: Dictionary with all calculated values
        """
        results = {}
        
        try:
            # ===== Extract inputs =====
            p_liq_psig = row['Liquid Pressure ']
            p_suc_psig = row['Suction Presure ']
            
            # Convert pressures to Pa
            P_liq_pa = self.psig_to_pa(p_liq_psig)
            P_suc_pa = self.psig_to_pa(p_suc_psig)
            
            # Store converted pressures for reference
            results['P_liq_psig'] = p_liq_psig
            results['P_suc_psig'] = p_suc_psig
            results['P_liq_pa'] = P_liq_pa
            results['P_suc_pa'] = P_suc_pa
            
            # Aliases for P-h diagram widget (uses these names)
            results['P_cond'] = P_liq_pa  # Condenser pressure = liquid line pressure
            results['P_suc'] = P_suc_pa   # Suction pressure
            
            # Temperature inputs (°F → K)
            txv_bulb_temps_f = [
                row['Right TXV Bulb '],
                row['CTR TXV Bulb'],
                row['Left TXV Bulb']
            ]
            T_2a_K = np.mean([self.fahrenheit_to_kelvin(t) for t in txv_bulb_temps_f])
            
            T_2b_K = self.fahrenheit_to_kelvin(row['Suction line into Comp'])
            T_3a_K = self.fahrenheit_to_kelvin(row['Discharge line from comp'])
            T_3b_K = self.fahrenheit_to_kelvin(row['Ref Temp in HeatX'])
            T_4a_K = self.fahrenheit_to_kelvin(row['Ref Temp out HeatX'])
            
            txv_inlet_temps_f = [
                row['Left TXV Inlet'],
                row['CTR TXV Inlet'],
                row['Right TXV Inlet ']
            ]
            T_4b_K = np.mean([self.fahrenheit_to_kelvin(t) for t in txv_inlet_temps_f])
            
            # Air temperatures
            air_inlet_temps_f = [
                row['Air in left evap 6 in LE'],
                row['Air in left evap 6 in RE'],
                row['Air in ctr evap 6 in LE'],
                row['Air in ctr evap 6 in RE'],
                row['Air in right evap 6 in LE'],
                row['Air in right evap 6 in RE']
            ]
            T_ai_K = np.mean([self.fahrenheit_to_kelvin(t) for t in air_inlet_temps_f])
            
            air_outlet_temps_f = [
                row['Air off left evap 6 in LE'],
                row['Air off left evap 6 in RE'],
                row['Air off ctr evap 6 in LE'],
                row['Air off ctr evap 6 in RE'],
                row['Air off right evap 6 in LE'],
                row['Air off right evap 6 in RE']
            ]
            T_ao_K = np.mean([self.fahrenheit_to_kelvin(t) for t in air_outlet_temps_f])
            
            T_wi_K = self.fahrenheit_to_kelvin(row['Water in HeatX'])
            T_wo_K = self.fahrenheit_to_kelvin(row['Water out HeatX'])
            
            rpm = row['Compressor RPM']
            
            # Store temperature conversions
            results['T_2a_K'] = T_2a_K
            results['T_2b_K'] = T_2b_K
            results['T_3a_K'] = T_3a_K
            results['T_3b_K'] = T_3b_K
            results['T_4a_K'] = T_4a_K
            results['T_4b_K'] = T_4b_K
            results['T_ai_K'] = T_ai_K
            results['T_ao_K'] = T_ao_K
            results['T_wi_K'] = T_wi_K
            results['T_wo_K'] = T_wo_K
            results['RPM'] = rpm
            
            # ===== Get Saturation Properties =====
            sat_evap = self.get_saturation_properties(P_suc_pa)
            sat_cond = self.get_saturation_properties(P_liq_pa)
            
            if sat_evap:
                results['T_sat_evap'] = sat_evap['T_sat']
                results['h_f_evap'] = sat_evap['h_f']
                results['h_g_evap'] = sat_evap['h_g']
                results['s_f_evap'] = sat_evap['s_f']
                results['s_g_evap'] = sat_evap['s_g']
            
            if sat_cond:
                results['T_sat_cond'] = sat_cond['T_sat']
                results['h_f_cond'] = sat_cond['h_f']
                results['h_g_cond'] = sat_cond['h_g']
                results['s_f_cond'] = sat_cond['s_f']
                results['s_g_cond'] = sat_cond['s_g']
            
            # ===== Calculate State Point Properties =====
            
            # State 2a: TXV Bulb (Low Pressure, Saturated)
            state_2a = self.calculate_state_point(T_2a_K, P_suc_pa)
            if state_2a:
                results['h_2a'] = state_2a['h']
                results['s_2a'] = state_2a['s']
                results['rho_2a'] = state_2a['rho']
                results['x_2a'] = state_2a['quality']
            
            # State 2b: Suction Line (Low Pressure, Superheated)
            state_2b = self.calculate_state_point(T_2b_K, P_suc_pa)
            if state_2b and sat_evap:
                results['h_2b'] = state_2b['h']
                results['s_2b'] = state_2b['s']
                results['rho_2b'] = state_2b['rho']
                results['SH_2b'] = self.calculate_superheat(T_2b_K, sat_evap['T_sat'])
            
            # State 3a: Discharge Line (High Pressure, Superheated)
            state_3a = self.calculate_state_point(T_3a_K, P_liq_pa)
            if state_3a and sat_cond:
                results['h_3a'] = state_3a['h']
                results['s_3a'] = state_3a['s']
                results['rho_3a'] = state_3a['rho']
                results['SH_3a'] = self.calculate_superheat(T_3a_K, sat_cond['T_sat'])
            
            # State 3b: Condenser Inlet (High Pressure, Gas/Vapor)
            state_3b = self.calculate_state_point(T_3b_K, P_liq_pa)
            if state_3b:
                results['h_3b'] = state_3b['h']
                results['s_3b'] = state_3b['s']
                results['x_3b'] = state_3b['quality']
            
            # State 4a: Condenser Outlet (High Pressure, Subcooled Liquid)
            state_4a = self.calculate_state_point(T_4a_K, P_liq_pa)
            if state_4a and sat_cond:
                results['h_4a'] = state_4a['h']
                results['s_4a'] = state_4a['s']
                results['rho_4a'] = state_4a['rho']
                results['SC_4a'] = self.calculate_subcooling(sat_cond['T_sat'], T_4a_K)
            
            # State 4b: TXV Inlet (High Pressure, Subcooled Liquid)
            state_4b = self.calculate_state_point(T_4b_K, P_liq_pa)
            if state_4b and sat_cond:
                results['h_4b'] = state_4b['h']
                results['s_4b'] = state_4b['s']
                results['rho_4b'] = state_4b['rho']
                results['SC_4b'] = self.calculate_subcooling(sat_cond['T_sat'], T_4b_K)
            
            # ===== CIRCUIT-SPECIFIC CALCULATIONS =====
            # State Point 2a: TXV Bulb (One per circuit)
            
            # Left Hand Circuit
            T_2a_LH_K = self.fahrenheit_to_kelvin(row['Left TXV Bulb'])
            state_2a_LH = self.calculate_state_point(T_2a_LH_K, P_suc_pa)
            if state_2a_LH:
                results['h_2a_LH'] = state_2a_LH['h']
                results['s_2a_LH'] = state_2a_LH['s']
                results['x_2a_LH'] = state_2a_LH['quality']
                results['T_2a_LH_K'] = T_2a_LH_K
            
            # Center Circuit
            T_2a_CTR_K = self.fahrenheit_to_kelvin(row['CTR TXV Bulb'])
            state_2a_CTR = self.calculate_state_point(T_2a_CTR_K, P_suc_pa)
            if state_2a_CTR:
                results['h_2a_CTR'] = state_2a_CTR['h']
                results['s_2a_CTR'] = state_2a_CTR['s']
                results['x_2a_CTR'] = state_2a_CTR['quality']
                results['T_2a_CTR_K'] = T_2a_CTR_K
            
            # Right Hand Circuit
            T_2a_RH_K = self.fahrenheit_to_kelvin(row['Right TXV Bulb '])
            state_2a_RH = self.calculate_state_point(T_2a_RH_K, P_suc_pa)
            if state_2a_RH:
                results['h_2a_RH'] = state_2a_RH['h']
                results['s_2a_RH'] = state_2a_RH['s']
                results['x_2a_RH'] = state_2a_RH['quality']
                results['T_2a_RH_K'] = T_2a_RH_K
            
            # ===== CIRCUIT-SPECIFIC STATE POINT 4b: TXV Inlet =====
            
            # Left Hand Circuit
            T_4b_LH_K = self.fahrenheit_to_kelvin(row['Left TXV Inlet'])
            state_4b_LH = self.calculate_state_point(T_4b_LH_K, P_liq_pa)
            if state_4b_LH and sat_cond:
                results['h_4b_LH'] = state_4b_LH['h']
                results['s_4b_LH'] = state_4b_LH['s']
                results['SC_4b_LH'] = self.calculate_subcooling(sat_cond['T_sat'], T_4b_LH_K)
                results['T_4b_LH_K'] = T_4b_LH_K
            
            # Center Circuit
            T_4b_CTR_K = self.fahrenheit_to_kelvin(row['CTR TXV Inlet'])
            state_4b_CTR = self.calculate_state_point(T_4b_CTR_K, P_liq_pa)
            if state_4b_CTR and sat_cond:
                results['h_4b_CTR'] = state_4b_CTR['h']
                results['s_4b_CTR'] = state_4b_CTR['s']
                results['SC_4b_CTR'] = self.calculate_subcooling(sat_cond['T_sat'], T_4b_CTR_K)
                results['T_4b_CTR_K'] = T_4b_CTR_K
            
            # Right Hand Circuit
            T_4b_RH_K = self.fahrenheit_to_kelvin(row['Right TXV Inlet '])
            state_4b_RH = self.calculate_state_point(T_4b_RH_K, P_liq_pa)
            if state_4b_RH and sat_cond:
                results['h_4b_RH'] = state_4b_RH['h']
                results['s_4b_RH'] = state_4b_RH['s']
                results['SC_4b_RH'] = self.calculate_subcooling(sat_cond['T_sat'], T_4b_RH_K)
                results['T_4b_RH_K'] = T_4b_RH_K
            
            # ===== CIRCUIT-SPECIFIC STATE POINT 1: TXV Outlet (Isenthalpic Expansion) =====
            # Point 1 represents the refrigerant after passing through the TXV valve
            # h_1 = h_4b (isenthalpic process through expansion valve)
            # P_1 = P_suc (pressure drops from high side to low side)
            
            # Left Hand Circuit
            if 'h_4b_LH' in results:
                # At Point 1: h_1 = h_4b, P_1 = P_suc
                state_1_LH = self.calculate_state_point_hp(results['h_4b_LH'] * 1000, P_suc_pa)  # Convert h to J/kg for CoolProp
                if state_1_LH:
                    results['h_1_LH'] = state_1_LH['h']  # Should match h_4b_LH
                    results['s_1_LH'] = state_1_LH['s']
                    results['x_1_LH'] = state_1_LH['quality']  # Quality at Point 1
            
            # Center Circuit
            if 'h_4b_CTR' in results:
                state_1_CTR = self.calculate_state_point_hp(results['h_4b_CTR'] * 1000, P_suc_pa)
                if state_1_CTR:
                    results['h_1_CTR'] = state_1_CTR['h']
                    results['s_1_CTR'] = state_1_CTR['s']
                    results['x_1_CTR'] = state_1_CTR['quality']
            
            # Right Hand Circuit
            if 'h_4b_RH' in results:
                state_1_RH = self.calculate_state_point_hp(results['h_4b_RH'] * 1000, P_suc_pa)
                if state_1_RH:
                    results['h_1_RH'] = state_1_RH['h']
                    results['s_1_RH'] = state_1_RH['s']
                    results['x_1_RH'] = state_1_RH['quality']
            
            # ===== CIRCUIT-SPECIFIC AIR TEMPERATURES =====
            
            # Left Circuit Air (LE, RE = Left/Right circuit within left evaporator)
            T_ai_L_K = np.mean([
                self.fahrenheit_to_kelvin(row['Air in left evap 6 in LE']),
                self.fahrenheit_to_kelvin(row['Air in left evap 6 in RE'])
            ])
            T_ao_L_K = np.mean([
                self.fahrenheit_to_kelvin(row['Air off left evap 6 in LE']),
                self.fahrenheit_to_kelvin(row['Air off left evap 6 in RE'])
            ])
            DT_L_K = T_ao_L_K - T_ai_L_K
            
            results['T_ai_L_K'] = T_ai_L_K
            results['T_ao_L_K'] = T_ao_L_K
            results['DT_L_K'] = DT_L_K
            
            # Center Circuit Air
            T_ai_C_K = np.mean([
                self.fahrenheit_to_kelvin(row['Air in ctr evap 6 in LE']),
                self.fahrenheit_to_kelvin(row['Air in ctr evap 6 in RE'])
            ])
            T_ao_C_K = np.mean([
                self.fahrenheit_to_kelvin(row['Air off ctr evap 6 in LE']),
                self.fahrenheit_to_kelvin(row['Air off ctr evap 6 in RE'])
            ])
            DT_C_K = T_ao_C_K - T_ai_C_K
            
            results['T_ai_C_K'] = T_ai_C_K
            results['T_ao_C_K'] = T_ao_C_K
            results['DT_C_K'] = DT_C_K
            
            # Right Circuit Air
            T_ai_R_K = np.mean([
                self.fahrenheit_to_kelvin(row['Air in right evap 6 in LE']),
                self.fahrenheit_to_kelvin(row['Air in right evap 6 in RE'])
            ])
            T_ao_R_K = np.mean([
                self.fahrenheit_to_kelvin(row['Air off right evap 6 in LE']),
                self.fahrenheit_to_kelvin(row['Air off right evap 6 in RE'])
            ])
            DT_R_K = T_ao_R_K - T_ai_R_K
            
            results['T_ai_R_K'] = T_ai_R_K
            results['T_ao_R_K'] = T_ao_R_K
            results['DT_R_K'] = DT_R_K
            
            # ===== System Performance Metrics =====
            # Note: Mass flow calculation would require compressor displacement info
            # For now, we calculate specific values (per unit mass)
            
            if 'h_2a' in results and 'h_4b' in results:
                results['q_evap_specific'] = results['h_2a'] - results['h_4b']  # [kJ/kg]
            
            if 'h_3a' in results and 'h_2b' in results:
                results['w_comp_specific'] = results['h_3a'] - results['h_2b']  # [kJ/kg]
            
            if 'h_3a' in results and 'h_4a' in results:
                results['q_cond_specific'] = results['h_3a'] - results['h_4a']  # [kJ/kg]
            
            if 'q_evap_specific' in results and 'w_comp_specific' in results:
                if results['w_comp_specific'] != 0:
                    results['cop'] = results['q_evap_specific'] / results['w_comp_specific']
            
            return results
        
        except Exception as e:
            print(f"[ThermodynamicCalculator] Error processing row: {e}")
            return results
    
    def process_dataframe(self, df):
        """
        Process entire DataFrame and add calculated columns.
        Adds a 'units' row at the beginning with unit labels.
        
        Returns: DataFrame with units row + all calculated columns added
        """
        results_list = []
        
        for idx, row in df.iterrows():
            results = self.process_row(row)
            results_list.append(results)
        
        results_df = pd.DataFrame(results_list)
        
        # Combine original data with calculated results
        combined_df = pd.concat([df.reset_index(drop=True), results_df.reset_index(drop=True)], axis=1)
        
        # Create units row with labels for all columns
        units_row = {}
        for col in combined_df.columns:
            if col in self.COLUMN_NAME_MAPPING:
                # Use reverse mapping to find the unit label from the old name
                unit_col = col + '_K' if 'T_' in col else col + '_kJ_kg' if 'h_' in col or 's_' in col else ''
                if unit_col in self.COLUMN_NAME_MAPPING:
                    unit_col = unit_col  # Already has suffix, use as is
            
            # Better approach: extract unit from column name patterns
            if 'K' == col[-1]:
                units_row[col] = 'K'
            elif col.startswith('h_') or col.startswith('q_') or col.startswith('w_'):
                units_row[col] = 'kJ/kg'
            elif col.startswith('s_'):
                units_row[col] = 'kJ/(kg·K)'
            elif col.startswith('rho_'):
                units_row[col] = 'kg/m³'
            elif col.startswith('SH_') or col.startswith('SC_') or col.startswith('DT_'):
                units_row[col] = 'K'
            elif col == 'x_2a' or col == 'x_2a_LH' or col == 'x_2a_CTR' or col == 'x_2a_RH' or col == 'x_3b':
                units_row[col] = '-'
            elif col == 'cop':
                units_row[col] = '-'
            elif col == 'RPM':
                units_row[col] = 'RPM'
            elif col == 'P_liq_psig' or col == 'P_suc_psig':
                units_row[col] = 'PSIG'
            elif col == 'P_liq_pa' or col == 'P_suc_pa':
                units_row[col] = 'Pa'
            else:
                units_row[col] = ''  # Original sensor data, no unit row
        
        # Insert units row at the top
        units_df = pd.DataFrame([units_row])
        combined_df = pd.concat([units_df, combined_df], ignore_index=True)
        
        return combined_df


def get_calculation_output_columns():
    """
    Returns list of all calculated output columns in display order.
    Now uses clean column names (without unit suffixes).
    """
    columns = [
        # Pressure conversions
        'P_liq_psig',
        'P_suc_psig',
        'P_cond',  # Condenser pressure in Pa
        'P_suc',   # Suction pressure in Pa
        
        # Temperature conversions
        'T_2a_K',
        'T_2b_K',
        'T_3a_K',
        'T_3b_K',
        'T_4a_K',
        'T_4b_K',
        'T_ai_K',
        'T_ao_K',
        'T_wi_K',
        'T_wo_K',
        
        # Saturation properties - Evaporator (low side)
        'T_sat_evap',
        'h_f_evap',
        'h_g_evap',
        's_f_evap',
        's_g_evap',
        
        # Saturation properties - Condenser (high side)
        'T_sat_cond',
        'h_f_cond',
        'h_g_cond',
        's_f_cond',
        's_g_cond',
        
        # State 2a properties
        'h_2a',
        's_2a',
        'rho_2a',
        'x_2a',
        
        # State 2b properties
        'h_2b',
        's_2b',
        'rho_2b',
        'SH_2b',
        
        # State 3a properties
        'h_3a',
        's_3a',
        'rho_3a',
        'SH_3a',
        
        # State 3b properties
        'h_3b',
        's_3b',
        'x_3b',
        
        # State 4a properties
        'h_4a',
        's_4a',
        'rho_4a',
        'SC_4a',
        
        # State 4b properties
        'h_4b',
        's_4b',
        'rho_4b',
        'SC_4b',
        
        # ===== CIRCUIT-SPECIFIC CALCULATIONS =====
        # Left Hand Circuit - State 2a (TXV Bulb outlet)
        'T_2a_LH_K',
        'h_2a_LH',
        's_2a_LH',
        'x_2a_LH',
        
        # Left Hand Circuit - State 4b (TXV Inlet)
        'T_4b_LH_K',
        'h_4b_LH',
        's_4b_LH',
        'SC_4b_LH',
        
        # Left Hand Circuit - Air temperatures & ΔT
        'T_ai_L_K',
        'T_ao_L_K',
        'DT_L_K',
        
        # Center Circuit - State 2a (TXV Bulb outlet)
        'T_2a_CTR_K',
        'h_2a_CTR',
        's_2a_CTR',
        'x_2a_CTR',
        
        # Center Circuit - State 4b (TXV Inlet)
        'T_4b_CTR_K',
        'h_4b_CTR',
        's_4b_CTR',
        'SC_4b_CTR',
        
        # Center Circuit - Air temperatures & ΔT
        'T_ai_C_K',
        'T_ao_C_K',
        'DT_C_K',
        
        # Right Hand Circuit - State 2a (TXV Bulb outlet)
        'T_2a_RH_K',
        'h_2a_RH',
        's_2a_RH',
        'x_2a_RH',
        
        # Right Hand Circuit - State 4b (TXV Inlet)
        'T_4b_RH_K',
        'h_4b_RH',
        's_4b_RH',
        'SC_4b_RH',
        
        # Right Hand Circuit - Air temperatures & ΔT
        'T_ai_R_K',
        'T_ao_R_K',
        'DT_R_K',
        
        # Performance metrics
        'q_evap_specific',
        'w_comp_specific',
        'q_cond_specific',
        'cop',
    ]
    return columns
