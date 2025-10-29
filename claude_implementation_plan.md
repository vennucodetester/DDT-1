# Claude Implementation Plan
## Complete Calculation Engine Refactoring for DDT-1 Diagnostic Application

**Date**: 2025-10-29
**Author**: Claude (Sonnet 4.5)
**Status**: Implementation Ready

---

## Executive Summary

This document provides a comprehensive analysis and implementation plan for refactoring the DDT-1 diagnostic application's calculation engine. The application currently has two conflicting calculation systems, and this refactoring will create a single, unified, flexible system that follows the specifications in `Calculations-DDT.txt` and `ph diagram-DDT.txt`.

**Critical Note**: The `Calculation_Migration_Plan.md` file mentioned by the user was not found in the repository. This plan has been created from scratch based on the specification files that ARE present.

---

## A. Codebase Analysis

### Current System Architecture

The application has **TWO SEPARATE, CONFLICTING calculation systems**:

#### 1. **Old System** (Currently Active in Calculations Tab)
- **Files**: `coolprop_calculator.py`, `calculations_widget.py`
- **Architecture**:
  - `ThermodynamicCalculator` class processes entire DataFrames
  - Hardcoded CSV column names (e.g., `'Right TXV Bulb '`, `'Suction Presure '`)
  - Calculates circuit-specific properties (LH, CTR, RH)
  - Uses CoolProp for thermodynamic properties
  - Produces comprehensive output with all state points
- **Strengths**:
  - Works end-to-end for current data
  - Comprehensive circuit-specific calculations
  - Produces Excel-exportable results
- **Weaknesses**:
  - Hardcoded column names (not flexible)
  - No support for user-provided rated inputs
  - No volumetric efficiency calculation from first principles
  - Cannot adapt to different sensor configurations

#### 2. **New System** (Partially Implemented, Not Used)
- **Files**: `calculation_orchestrator.py`, `calculation_engine.py`, `port_resolver.py`
- **Architecture**:
  - Uses diagram model + port_resolver pattern
  - Flexible sensor mapping via `sensor_roles` dictionary
  - Calculates 8-point cycle (states 1, 2a, 2b, 3a, 3b, 4a, 4b)
  - More modular and maintainable
- **Strengths**:
  - Flexible - adapts to any sensor configuration
  - Clean separation of concerns
  - Uses modern port_resolver pattern
- **Weaknesses**:
  - **Missing critical features**:
    - No support for user rated inputs
    - No volumetric efficiency calculation (Step 1 from spec)
    - No per-row batch processing (Step 2 from spec)
    - No integration with Calculations tab UI
  - **Incomplete**: Only calculates state points, not final performance metrics

### Supporting Infrastructure

#### DataManager (`data_manager.py`)
- Central data management class
- Currently stores:
  - CSV data
  - Sensor mappings (sensor_roles dictionary)
  - Diagram model
  - Session state
- **Missing**: `rated_inputs = {}` dictionary for user manual inputs

#### Port Resolver System (`port_resolver.py`)
- Resolves sensor roles to actual CSV column names
- Functions like `resolve_mapped_sensor(model, 'Compressor', comp_id, 'SP')`
- Returns the actual CSV column name for a given port
- **Status**: Fully functional and ready to use

#### Inputs Widget (`inputs_widget.py`)
- Currently displays live sensor values
- **Missing**: UI for user to enter rated inputs

#### P-h Diagram Plotter (`ph_diagram_plotter.py`)
- Plots pressure-enthalpy diagrams
- Supports circuit-specific overlays (LH, CTR, RH)
- **Status**: Architecture is correct, but needs updated column names

---

## B. Specification Requirements

### From Calculations-DDT.txt

The specification describes a two-step calculation process:

#### **Step 1: Calculate Volumetric Efficiency (One-Time)**
```
eta_vol = m_dot_rated / m_dot_theoretical

Where:
- m_dot_rated: User input from datasheet (e.g., 211 lbm/hr)
- m_dot_theoretical = dens_rated * rph * disp_ft3
- rph = hz_rated * 3600
- dens_rated = CoolProp.PropsSI('D', 'T', Rated_Return_Gas_Temp_K, 'P', P_rated_sat, 'R290')
- P_rated_sat = CoolProp.PropsSI('P', 'T', Rated_Evap_Temp_K, 'Q', 0, 'R290')

Required User Inputs:
1. m_dot_rated (lbm/hr)
2. hz_rated (Hz)
3. disp_ft3 (ft³)
4. Rated_Evap_Temp (°F)
5. Rated_Return_Gas_Temp (°F)
```

#### **Step 2: Calculate Real-Time Performance (Per Row)**
```
For each row in CSV:
  Mass flow rate = Density * eta_vol * disp * (Comp.rpm / 60)

  Where:
  - Density: from "At compressor inlet" section
  - eta_vol: from Step 1
  - disp: converted from disp_ft3
  - Comp.rpm: from CSV sensor data

  Cooling cap = Mass flow rate * (H_in - H_out_avg)

  Where:
  - H_in: Enthalpy at compressor inlet (state 2b)
  - H_out_avg: Average of three TXV inlet enthalpies (h_4b_lh, h_4b_ctr, h_4b_rh)
```

#### **Required Calculations Per Row:**
1. **At Each Coil** (LH, CTR, RH):
   - T_sat (from suction pressure)
   - Superheat = T_outlet - T_sat
   - Density, Enthalpy, Entropy at coil outlet

2. **At Compressor Inlet**:
   - T_sat (from suction pressure)
   - Total Superheat = T_2b - T_sat
   - Density, Enthalpy, Entropy at state 2b

3. **At Condenser**:
   - T_sat (from discharge pressure)
   - Subcooling = T_sat - T_outlet

4. **At Each TXV** (LH, CTR, RH):
   - T_sat (from discharge pressure)
   - Subcooling = T_sat - T_inlet
   - Enthalpy at TXV inlet (h_4b)

### From ph diagram-DDT.txt

The P-h diagram must show:
1. **High-Pressure Line** (P_disch):
   - Three distinct TXV inlet points (3-LH, 3-CTR, 3-RH)
   - Each plotted using (P_disch, T_4b-lh/ctr/rh)

2. **Low-Pressure Line** (P_suction):
   - Three distinct evaporator outlet points
   - Each plotted using (P_suction, T_2a-LH/CTR/RH)
   - Compressor inlet point (T_2b) as the mixed average

3. **Main Cycle**: Standard 8-point cycle overlay

### From Calculations-DDT.xlsx - Sheet1.csv

The output table must have:
- Nested/hierarchical headers
- Sections: "At LH/CTR/RH Coil", "At compressor inlet", "At Condenser", "At TXV LH/CTR/RH", "TOTAL"
- Complex multi-level column structure

---

## C. Final Implementation Scope

### Files to Create:
- ✓ `claude_implementation_plan.md` (this file)

### Files to Modify:

1. **data_manager.py**
   - Add `self.rated_inputs = {}` dictionary
   - Add getter/setter methods
   - Add save/load to session JSON

2. **inputs_widget.py**
   - Add UI section for "Rated Inputs"
   - Add QLineEdit widgets for: m_dot_rated, hz_rated, disp_ft3, Rated_Evap_Temp, Rated_Return_Gas_Temp
   - Add "Save Rated Inputs" button
   - Connect to data_manager

3. **calculation_engine.py**
   - Add `calculate_volumetric_efficiency()` function (Step 1 logic)
   - Add `calculate_row_performance()` function (Step 2 logic)
   - Keep existing 8-point cycle functions
   - Add helper functions for unit conversions

4. **calculation_orchestrator.py**
   - Add new `run_batch_processing()` function
   - Use port_resolver to map sensor roles to CSV columns
   - Process entire DataFrame (all rows)
   - Return augmented DataFrame with new calculated columns

5. **calculations_widget.py**
   - Replace QTableWidget with QTreeWidget
   - Implement `NestedHeaderView` custom class for hierarchical headers
   - Update "Run" button to call new `run_batch_processing()`
   - Display results in nested format

6. **ph_diagram_plotter.py**
   - Update `convert_diagram_model_to_points()` function
   - Read new DataFrame column names (H_coil_lh, Enthalpy_txv_lh, etc.)
   - Plot circuit-specific points as per spec

7. **coolprop_calculator.py**
   - Mark as **DEPRECATED**
   - Add warning comments
   - Keep file for reference but remove all imports from other files

---

## D. Implementation Strategy

### Phase 1: Infrastructure (Data Storage)
1. Add `rated_inputs` dict to DataManager
2. Add session save/load support
3. Add validation logic

### Phase 2: UI for Rated Inputs
1. Rebuild inputs_widget.py
2. Add input form for 5 rated values
3. Test save/load functionality

### Phase 3: Calculation Engine
1. Implement Step 1: `calculate_volumetric_efficiency()`
2. Implement Step 2: `calculate_row_performance()`
3. Unit test with sample data

### Phase 4: Batch Orchestrator
1. Implement `run_batch_processing()` in calculation_orchestrator.py
2. Use port_resolver for flexible sensor mapping
3. Process all rows
4. Return augmented DataFrame

### Phase 5: UI Rebuild (Calculations Tab)
1. Replace QTableWidget with QTreeWidget
2. Implement nested headers
3. Connect to new orchestrator
4. Test with real data

### Phase 6: P-h Diagram Update
1. Update column name mapping
2. Test multi-circuit plotting
3. Verify against spec

### Phase 7: Integration & Testing
1. Remove all references to coolprop_calculator.py
2. Update imports
3. End-to-end testing
4. Commit and document

---

## E. Risks and Mitigation

### Risk 1: Missing Rated Inputs
**Risk**: User hasn't entered rated inputs yet
**Mitigation**: Show clear error message, guide user to Inputs tab

### Risk 2: Sensor Mapping Incomplete
**Risk**: Required sensors not mapped in diagram
**Mitigation**: port_resolver returns None, show specific error about which port is missing

### Risk 3: Column Name Changes
**Risk**: CSV column names don't match expectations
**Mitigation**: Use port_resolver system exclusively (already handles this)

### Risk 4: CoolProp Errors
**Risk**: Invalid thermodynamic states
**Mitigation**: Wrap all CoolProp calls in try/except, log errors, continue processing

---

## F. Verification Checklist

After implementation, verify:
- [ ] Rated inputs can be entered and saved
- [ ] Volumetric efficiency calculates correctly
- [ ] Per-row performance calculations work
- [ ] Batch processing handles full CSV
- [ ] Calculations tab displays nested headers
- [ ] P-h diagram shows multi-circuit data
- [ ] Session save/load preserves rated inputs
- [ ] Error handling works for missing sensors
- [ ] No references to coolprop_calculator.py remain
- [ ] All tests pass

---

## G. Gaps and Refinements to Original Plan

Since the `Calculation_Migration_Plan.md` file was missing, I created this plan from the specifications. Key observations:

### What Was Clear:
- Two-step calculation process (Step 1: eta_vol, Step 2: per-row)
- Required user inputs (5 rated values)
- Output format (nested table structure)
- P-h diagram multi-circuit requirements

### What I Inferred:
- Keep the new port_resolver-based architecture (it's superior)
- Retire coolprop_calculator.py completely
- Use QTreeWidget for nested table display
- Augment DataFrame with new columns rather than replacing

### What I Added:
- Specific function signatures for new calculation functions
- Detailed UI mockup for rated inputs
- Error handling strategy
- Session save/load for rated inputs
- Clear migration path from old to new system

---

## H. Implementation Timeline

**Total Estimated Time**: 2-3 hours (for AI implementation in single session)

1. **Data Manager Updates** (15 min)
2. **Inputs Widget Rebuild** (30 min)
3. **Calculation Engine Functions** (45 min)
4. **Batch Orchestrator** (30 min)
5. **Calculations Widget Rebuild** (45 min)
6. **P-h Diagram Updates** (15 min)
7. **Integration & Testing** (30 min)

---

## I. Success Criteria

The refactoring is successful when:
1. User can enter 5 rated inputs and they persist in session
2. Volumetric efficiency is calculated from rated inputs
3. Batch processing calculates mass flow and cooling capacity for all rows
4. Calculations tab shows nested table matching spec
5. P-h diagram plots 3 separate subcooling and superheat points
6. No errors when switching between tabs
7. Export to CSV works with new columns
8. All old coolprop_calculator.py references removed

---

## Conclusion

This refactoring unifies two conflicting systems into a single, flexible, powerful calculation engine that:
- Adapts to any sensor configuration (via port_resolver)
- Uses user-provided rated inputs (via new UI)
- Calculates volumetric efficiency from first principles (Step 1)
- Processes entire datasets efficiently (Step 2)
- Displays results in specification-compliant format
- Supports advanced multi-circuit P-h diagrams

The implementation follows modern software architecture principles:
- Separation of concerns
- Single source of truth (diagram model + rated inputs)
- Flexible sensor mapping
- Comprehensive error handling
- Maintainable and extensible code

**Ready to proceed with implementation.**
