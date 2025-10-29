# Goal-2C Implementation Plan: Universal Graceful Degradation + 7 Inputs

**Created:** 2025-10-29
**Priority:** ALL THREE PHASES (High Priority)
**Branch:** `claude/refactor-calculation-engine-011CUap9sd3nSiYRE7M2b2iL`

---

## 1. Requirements Summary

### 1.1 User Requirements (Confirmed)

**7 Required Inputs:**
1. ✅ Rated Capacity (BTU/hr) - **NEW**
2. ✅ Rated Power (W) - **NEW**
3. ✅ Rated Mass Flow (lb/hr) - existing
4. ✅ Rated Evap Temp (F) - existing
5. ✅ Rated Return Gas Temp (F) - existing
6. ✅ Rated Displacement (ft³) - existing
7. ✅ Rated Frequency (Hz) - existing

**Degradation Strategy:**
- ✅ Universal (not just RPM) - for ANY missing data
- ✅ Calculate everything possible
- ✅ Show detailed information on what's missing
- ✅ Help user fix things incrementally

**Priority:**
- ✅ All three phases are equally important

### 1.2 Technical Validation (Science Check)

**Question:** Are Rated Mass Flow, Displacement, and Rated Speed truly needed?

**Answer:** YES, they are all needed for the eta_vol calculation:

```python
# Step 1: Calculate volumetric efficiency
eta_vol = m_dot_rated / m_dot_theoretical

# Where:
m_dot_theoretical = density_rated * rph * displacement
rph = hz_rated * 3600
density_rated = CoolProp(T=rated_return_gas_temp, P=P_sat_at_rated_evap_temp)
```

**Dependencies:**
- m_dot_rated ← User input
- hz_rated ← User input
- displacement ← User input
- rated_evap_temp_f ← User input (for saturation pressure)
- rated_return_gas_temp_f ← User input (for density)

**Conclusion:** All 5 original inputs are thermodynamically necessary.

**However:** If these inputs are missing, we can:
- Use a default eta_vol (e.g., 0.85) with a warning
- Skip mass flow/cooling capacity calculations
- Still calculate all 43 thermodynamic state point columns

---

## 2. Implementation Strategy

### 2.1 Three-Tier Degradation Levels

**Tier 1: Full Calculation (All 7 inputs + all sensors)**
- ✅ All 47 columns calculated
- ✅ eta_vol from first principles
- ✅ Mass flow and cooling capacity accurate
- ✅ Efficiency metrics (COP, EER) available

**Tier 2: Partial Calculation (Missing some inputs or sensors)**
- ✅ Calculate everything possible
- ⚠️ Use defaults where needed (with warnings)
- ⚠️ Skip calculations that are impossible
- ⚠️ Clear reporting of what's missing and why

**Tier 3: Minimal Calculation (Only pressures and some temps)**
- ✅ Basic thermodynamic state points (superheat, subcooling)
- ❌ No mass flow or cooling capacity
- ⚠️ Extensive warnings about missing data

### 2.2 Fallback Hierarchy

```
Try: Calculate eta_vol from 5 rated inputs
  ↓ FAIL (missing inputs)
  ↓
Use: Default eta_vol = 0.85 (with warning)
  ↓
Try: Calculate mass flow with RPM sensor
  ↓ FAIL (missing RPM)
  ↓
Skip: Mass flow and cooling capacity (mark as N/A)
  ↓
Continue: Calculate all other 43 columns
```

---

## 3. Detailed Implementation Tasks

### Task 1: Update input_dialog.py (Add 2 New Inputs)

**Current:** 5 fields
**Target:** 7 fields

**New Fields:**
1. `rated_capacity_btu_hr` - Rated Cooling Capacity (BTU/hr)
2. `rated_power_w` - Rated Power Consumption (W)

**Changes:**

```python
# In input_dialog.py

FIELD_DEFINITIONS = [
    ('rated_capacity_btu_hr', 'Rated Cooling Capacity (BTU/hr)'),  # NEW
    ('rated_power_w', 'Rated Power Consumption (W)'),              # NEW
    ('m_dot_rated_lbhr', 'Rated Mass Flow Rate (lbm/hr)'),
    ('hz_rated', 'Rated Compressor Speed (Hz)'),
    ('disp_ft3', 'Compressor Displacement (ft³)'),
    ('rated_evap_temp_f', 'Rated Evaporator Temperature (°F)'),
    ('rated_return_gas_temp_f', 'Rated Return Gas Temperature (°F)'),
]
```

**Use Cases for New Inputs:**

1. **Rated Capacity:**
   - Validate calculated cooling capacity against manufacturer spec
   - Calculate capacity ratio: actual / rated
   - Warn if system is under/over performing

2. **Rated Power:**
   - Calculate rated COP: rated_capacity / rated_power
   - Calculate actual COP: actual_cooling_capacity / actual_power
   - Calculate efficiency ratio: actual_COP / rated_COP
   - Calculate EER (Energy Efficiency Ratio)

---

### Task 2: Update data_manager.py (Store 7 Inputs)

**File:** `data_manager.py`

**Changes:**

```python
# In _reset_state() method
self.rated_inputs = {
    'rated_capacity_btu_hr': None,        # NEW
    'rated_power_w': None,                # NEW
    'm_dot_rated_lbhr': None,
    'hz_rated': None,
    'disp_ft3': None,
    'rated_evap_temp_f': None,
    'rated_return_gas_temp_f': None,
}
```

**Validation:** Ensure load_session() and save_session() handle all 7 fields.

---

### Task 3: Implement Universal Graceful Degradation

**Files to Modify:**
- `calculation_engine.py` - Core calculation logic
- `calculation_orchestrator.py` - Orchestration logic
- `calculations_widget.py` - UI feedback

#### 3.1 calculation_engine.py Changes

**A. Modify calculate_volumetric_efficiency() - Add Graceful Fallback**

```python
def calculate_volumetric_efficiency(rated_inputs: Dict, refrigerant: str = 'R290') -> Dict:
    """
    Calculate eta_vol with graceful degradation.

    Returns:
        Dict with:
        - eta_vol: float (or default)
        - warnings: list of warning messages
        - method: 'calculated' | 'default'
    """
    warnings = []

    # Get inputs
    m_dot_rated = rated_inputs.get('m_dot_rated_lbhr', 0)
    hz_rated = rated_inputs.get('hz_rated', 0)
    disp_ft3 = rated_inputs.get('disp_ft3', 0)
    rated_evap_f = rated_inputs.get('rated_evap_temp_f', 0)
    rated_return_f = rated_inputs.get('rated_return_gas_temp_f', 0)

    # Check if all inputs are present
    missing = []
    if m_dot_rated == 0 or m_dot_rated is None:
        missing.append('Rated Mass Flow Rate')
    if hz_rated == 0 or hz_rated is None:
        missing.append('Rated Frequency')
    if disp_ft3 == 0 or disp_ft3 is None:
        missing.append('Compressor Displacement')
    if rated_evap_f == 0 or rated_evap_f is None:
        missing.append('Rated Evaporator Temperature')
    if rated_return_f == 0 or rated_return_f is None:
        missing.append('Rated Return Gas Temperature')

    if missing:
        # FALLBACK: Use default eta_vol
        warnings.append(f"Missing rated inputs: {', '.join(missing)}")
        warnings.append("Using default volumetric efficiency (0.85) - results will be approximate")
        return {
            'eta_vol': 0.85,
            'method': 'default',
            'warnings': warnings
        }

    # Try to calculate
    try:
        # ... existing calculation code ...

        return {
            'eta_vol': eta_vol,
            'method': 'calculated',
            'warnings': []
        }
    except Exception as e:
        # FALLBACK on error
        warnings.append(f"Error calculating eta_vol: {str(e)}")
        warnings.append("Using default volumetric efficiency (0.85)")
        return {
            'eta_vol': 0.85,
            'method': 'default',
            'warnings': warnings
        }
```

**B. Modify calculate_row_performance() - Remove Hard Failures**

```python
def calculate_row_performance(...) -> pd.Series:
    """
    Calculate with universal graceful degradation.

    Returns Series with:
    - All calculated columns (or None for impossible ones)
    - 'warnings' column with detailed missing data report
    - 'calculations_completed' column with count (e.g., "43/47")
    """
    results = {}
    warnings = []
    calculations_attempted = 0
    calculations_completed = 0

    # Helper to get values safely
    def get_val(key):
        col_name = sensor_map.get(key)
        if col_name is None:
            return None
        return row.get(col_name)

    # Get all sensor values
    p_suc_psig = get_val('P_suc')
    p_disch_psig = get_val('P_disch')
    rpm = get_val('RPM')
    t_2a_lh_f = get_val('T_2a-LH')
    # ... etc for all sensors

    # Track missing critical data
    if p_suc_psig is None:
        warnings.append("❌ Suction pressure not available - most calculations impossible")
        results['warnings'] = "; ".join(warnings)
        return pd.Series(results)

    if p_disch_psig is None:
        warnings.append("❌ Discharge pressure not available - limited calculations possible")

    # Convert pressures
    p_suc_pa = psig_to_pa(p_suc_psig)
    p_disch_pa = psig_to_pa(p_disch_psig) if p_disch_psig else None

    # Get saturation temps
    t_sat_suc_k = CP.PropsSI('T', 'P', p_suc_pa, 'Q', 0, refrigerant)
    t_sat_disch_k = CP.PropsSI('T', 'P', p_disch_pa, 'Q', 0, refrigerant) if p_disch_pa else None

    # === SECTION 1: AT LH COIL (6 columns) ===
    calculations_attempted += 6
    if t_2a_lh_f is not None:
        try:
            # ... existing calculation code ...
            results['T_2a-LH'] = t_2a_lh_f
            results['T_sat.lh'] = ...
            results['S.H_lh'] = ...
            results['H_coil lh'] = ...
            results['S_coil lh'] = ...
            results['D_coil lh'] = ...
            calculations_completed += 6
        except Exception as e:
            warnings.append(f"⚠️ LH coil calculations failed: {str(e)}")
            results['T_2a-LH'] = None
            results['T_sat.lh'] = None
            # ... etc
    else:
        warnings.append("⚠️ T_2a-LH sensor not mapped - LH coil calculations skipped")
        results['T_2a-LH'] = None
        results['T_sat.lh'] = None
        # ... etc

    # === SECTION 2-9: Similar pattern for all other sections ===
    # ... (repeat for CTR, RH, compressor inlet, condenser, TXV sections)

    # === SECTION 10: MASS FLOW & COOLING CAPACITY ===
    calculations_attempted += 2

    # Check prerequisites
    can_calculate_mass_flow = True
    mass_flow_missing = []

    if rpm is None or rpm == 0:
        can_calculate_mass_flow = False
        mass_flow_missing.append("RPM sensor")

    if rho_2b is None:
        can_calculate_mass_flow = False
        mass_flow_missing.append("Compressor inlet density (T_2b sensor)")

    if eta_vol <= 0:
        can_calculate_mass_flow = False
        mass_flow_missing.append("Volumetric efficiency (rated inputs)")

    disp_m3 = comp_specs.get('displacement_m3', 0)
    if disp_m3 <= 0:
        can_calculate_mass_flow = False
        mass_flow_missing.append("Compressor displacement (rated input)")

    if can_calculate_mass_flow:
        try:
            # Calculate mass flow
            mass_flow_kgs = rho_2b * eta_vol * disp_m3 * (rpm / 60)

            # Calculate cooling capacity
            h_4b_values = [h for h in [h_4b_lh, h_4b_ctr, h_4b_rh] if h is not None]
            if h_4b_values and h_2b:
                h_4b_avg = sum(h_4b_values) / len(h_4b_values)
                cooling_cap_w = mass_flow_kgs * (h_2b - h_4b_avg)

                results['Mass flow rate'] = mass_flow_kgs * 2.20462 * 3600  # lb/hr
                results['Cooling cap'] = cooling_cap_w * 3.41214  # BTU/hr
                calculations_completed += 2
            else:
                results['Mass flow rate'] = None
                results['Cooling cap'] = None
                warnings.append("⚠️ Cooling capacity calculation skipped - missing TXV inlet temperatures")
                calculations_completed += 1  # Mass flow was calculated
        except Exception as e:
            results['Mass flow rate'] = None
            results['Cooling cap'] = None
            warnings.append(f"⚠️ Mass flow/cooling capacity calculation failed: {str(e)}")
    else:
        results['Mass flow rate'] = None
        results['Cooling cap'] = None
        warnings.append(f"⚠️ Cannot calculate mass flow - missing: {', '.join(mass_flow_missing)}")

    # Add metadata
    results['calculations_completed'] = f"{calculations_completed}/{calculations_attempted}"
    results['warnings'] = " | ".join(warnings) if warnings else None

    return pd.Series(results)
```

---

### Task 4: Update calculations_widget.py (Better Feedback)

**A. Remove Hard Guard Clause (Make it Soft Warning)**

```python
def run_calculation(self):
    """Run calculation with universal graceful degradation."""

    # Soft check for rated inputs (warn but don't block)
    rated_inputs = self.data_manager.rated_inputs
    required_fields = [
        'rated_capacity_btu_hr',
        'rated_power_w',
        'm_dot_rated_lbhr',
        'hz_rated',
        'disp_ft3',
        'rated_evap_temp_f',
        'rated_return_gas_temp_f',
    ]

    missing_fields = []
    for field in required_fields:
        value = rated_inputs.get(field)
        if value is None or value == 0.0:
            missing_fields.append(field)

    if missing_fields:
        # Show warning but ALLOW calculation to proceed
        field_labels = {
            'rated_capacity_btu_hr': 'Rated Cooling Capacity',
            'rated_power_w': 'Rated Power',
            'm_dot_rated_lbhr': 'Rated Mass Flow Rate',
            'hz_rated': 'Rated Frequency',
            'disp_ft3': 'Compressor Displacement',
            'rated_evap_temp_f': 'Rated Evaporator Temperature',
            'rated_return_gas_temp_f': 'Rated Return Gas Temperature',
        }

        missing_labels = [field_labels.get(f, f) for f in missing_fields]

        reply = QMessageBox.question(
            self,
            "Incomplete Rated Inputs",
            f"Some rated inputs are missing:\n\n" +
            "\n".join(f"• {label}" for label in missing_labels) +
            "\n\nCalculations will proceed using defaults where possible.\n"
            "Results will be approximate.\n\n"
            "Continue anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return  # User chose to stop

    # Proceed with calculation
    self.run_button.setText("Calculating...")
    self.run_button.setEnabled(False)
    # ... rest of existing code ...
```

**B. Enhanced populate_tree() - Visual Indicators for Missing Data**

```python
def populate_tree(self, processed_df):
    """Populate tree with visual indicators for missing data."""

    self.tree_widget.clear()

    if processed_df.empty:
        return

    # Get column list
    columns = list(processed_df.columns)

    # Check for warnings column
    has_warnings = 'warnings' in columns
    has_completion = 'calculations_completed' in columns

    # Populate rows
    for idx, row in processed_df.iterrows():
        item = QTreeWidgetItem()

        for col_idx, col_name in enumerate(columns):
            value = row[col_name]

            if pd.isna(value) or value is None:
                # Missing data - gray out
                item.setText(col_idx, "N/A")
                item.setForeground(col_idx, QColor(150, 150, 150))  # Gray
                item.setFont(col_idx, QFont("Arial", 9, QFont.Weight.Normal, italic=True))
            elif col_name == 'warnings' and value:
                # Warning cell - yellow background
                item.setText(col_idx, value)
                item.setBackground(col_idx, QColor(255, 255, 200))  # Light yellow
                item.setForeground(col_idx, QColor(200, 100, 0))  # Orange text
            elif col_name == 'calculations_completed':
                # Completion status
                item.setText(col_idx, value)
                if value.startswith(value.split('/')[1]):  # All complete
                    item.setForeground(col_idx, QColor(0, 150, 0))  # Green
                else:
                    item.setForeground(col_idx, QColor(200, 100, 0))  # Orange
            else:
                # Normal data
                if isinstance(value, float):
                    item.setText(col_idx, f"{value:.2f}")
                else:
                    item.setText(col_idx, str(value))

        self.tree_widget.addTopLevelItem(item)

    # Resize columns
    for i in range(len(columns)):
        self.tree_widget.resizeColumnToContents(i)
```

---

### Task 5: Add Efficiency Calculations (Use New Inputs)

**New calculations to add using rated_capacity and rated_power:**

```python
def calculate_efficiency_metrics(
    actual_cooling_cap_btu_hr: float,
    actual_power_w: float,
    rated_capacity_btu_hr: float,
    rated_power_w: float
) -> Dict:
    """
    Calculate efficiency metrics using rated and actual values.

    Returns:
        Dict with COP, EER, capacity ratio, etc.
    """
    results = {}

    # Actual COP (dimensionless)
    if actual_power_w and actual_power_w > 0:
        actual_cop = (actual_cooling_cap_btu_hr / 3.41214) / actual_power_w
        results['actual_cop'] = actual_cop

    # Rated COP
    if rated_power_w and rated_power_w > 0:
        rated_cop = (rated_capacity_btu_hr / 3.41214) / rated_power_w
        results['rated_cop'] = rated_cop

    # COP ratio (actual / rated)
    if 'actual_cop' in results and 'rated_cop' in results:
        results['cop_ratio'] = results['actual_cop'] / results['rated_cop']

    # EER (BTU/hr per Watt)
    if actual_power_w and actual_power_w > 0:
        results['actual_eer'] = actual_cooling_cap_btu_hr / actual_power_w

    # Capacity ratio (actual / rated)
    if rated_capacity_btu_hr and rated_capacity_btu_hr > 0:
        results['capacity_ratio'] = actual_cooling_cap_btu_hr / rated_capacity_btu_hr

    return results
```

Add these as additional columns in the output.

---

### Task 6: Enhanced NestedHeaderView (Add Efficiency Section)

**Update calculations_widget.py - NestedHeaderView**

```python
self.groups = [
    ("AT LH coil", 6),
    ("AT CTR coil", 6),
    ("AT RH coil", 6),
    ("At compressor inlet", 7),
    ("Comp outlet", 2),
    ("At Condenser", 6),
    ("At TXV LH", 4),
    ("At TXV CTR", 4),
    ("At TXV RH", 4),
    ("TOTAL", 2),
    ("EFFICIENCY", 5),  # NEW: COP, EER, ratios
    ("DIAGNOSTICS", 2),  # NEW: Warnings, completion status
]

self.sub_headers = [
    # ... existing 47 columns ...
    # NEW: Efficiency columns
    "Actual COP", "Rated COP", "COP Ratio", "EER", "Capacity Ratio",
    # NEW: Diagnostic columns
    "Warnings", "Calculations Completed",
]
```

---

## 4. Testing Strategy

### 4.1 Test Scenarios

**Scenario 1: All Inputs + All Sensors (Full Calculation)**
- Enter all 7 rated inputs
- Map all required sensors
- Expected: 47+7 = 54 columns, all populated, no warnings

**Scenario 2: Missing Rated Inputs (Degraded eta_vol)**
- Missing m_dot_rated, hz_rated, or disp_ft3
- Expected: Default eta_vol (0.85), warning message, mass flow approximate

**Scenario 3: Missing RPM Sensor (No Mass Flow)**
- All rated inputs present
- RPM sensor not mapped
- Expected: 43/54 columns populated, mass flow = N/A, warning about RPM

**Scenario 4: Missing Temperature Sensors (Partial State Points)**
- Pressures mapped
- Some temperature sensors missing (e.g., T_2a-LH)
- Expected: LH coil section = N/A, other sections populated

**Scenario 5: Only Pressures (Minimal Calculation)**
- Only P_suc and P_disch mapped
- Expected: Saturation temperatures, minimal state points, extensive warnings

**Scenario 6: Completely Empty (Total Failure)**
- No sensors mapped
- Expected: Error dialog, no calculation

### 4.2 Validation Checks

1. **No Hard Failures:** Calculation should never throw an exception that stops processing
2. **Warnings Accuracy:** Each missing sensor/input should generate specific warning
3. **Visual Feedback:** N/A values should be visually distinct (grayed out)
4. **Export Integrity:** Exported CSV should include warnings column
5. **Incremental Improvement:** Mapping one more sensor should improve results

---

## 5. Implementation Order

### Phase 1: Expand to 7 Inputs (1-2 hours)

1. ✅ Update input_dialog.py (add 2 fields)
2. ✅ Update data_manager.py (add 2 fields to rated_inputs)
3. ✅ Update guard clause in calculations_widget.py (change to 7 fields)
4. ✅ Test dialog save/load

### Phase 2: Universal Graceful Degradation (3-4 hours)

1. ✅ Modify calculate_volumetric_efficiency() (add fallback)
2. ✅ Modify calculate_row_performance() (remove hard failures)
3. ✅ Add warnings collection system
4. ✅ Add missing data tracking
5. ✅ Update calculations_widget.py (remove hard guard, make soft)
6. ✅ Add visual indicators to populate_tree()
7. ✅ Test all 6 scenarios

### Phase 3: Efficiency Metrics (1-2 hours)

1. ✅ Add calculate_efficiency_metrics() function
2. ✅ Integrate into calculate_row_performance()
3. ✅ Add 5 new efficiency columns
4. ✅ Update NestedHeaderView with new sections
5. ✅ Test efficiency calculations

### Phase 4: Documentation & Polish (1 hour)

1. ✅ Update user-facing labels and messages
2. ✅ Add tooltips for new fields
3. ✅ Update GOAL_2_IMPLEMENTATION_PLAN.md
4. ✅ Create comprehensive commit message

**Total Estimated Time:** 6-9 hours

---

## 6. Success Criteria

### Functional Requirements

- [ ] Input dialog has 7 fields
- [ ] All 7 fields save/load correctly
- [ ] Calculations run even with missing data
- [ ] Warnings are specific and actionable
- [ ] Visual indicators show missing data clearly
- [ ] At least 43/47 columns calculate with only pressures + temps
- [ ] Mass flow/cooling capacity gracefully degrade when RPM missing
- [ ] Efficiency metrics calculate when both rated and actual power available

### User Experience Requirements

- [ ] User can see partial results immediately
- [ ] User understands what's missing and why
- [ ] User can fix issues incrementally
- [ ] No cryptic error messages
- [ ] No complete calculation failures for partial missing data

### Technical Requirements

- [ ] No unhandled exceptions
- [ ] All None values handled gracefully
- [ ] Warnings column included in exports
- [ ] Performance not degraded (still fast)
- [ ] Code is maintainable (clear logic)

---

## 7. Risk Mitigation

### Risk 1: Too Many Warnings

**Risk:** User overwhelmed by warning messages
**Mitigation:**
- Categorize warnings (Critical / Important / Info)
- Collapse similar warnings ("3 TXV sensors not mapped" instead of 3 separate messages)
- Use color coding (red = critical, orange = important, yellow = info)

### Risk 2: Confusion About Defaults

**Risk:** User doesn't realize eta_vol is a default, thinks it's calculated
**Mitigation:**
- Clear label: "eta_vol (default)" vs "eta_vol (calculated)"
- Warning message explains impact
- Different background color for approximate values

### Risk 3: Code Complexity

**Risk:** Too many if/else branches make code hard to maintain
**Mitigation:**
- Use clear section comments
- Extract helper functions
- Comprehensive docstrings
- Unit tests for edge cases

---

## 8. Future Enhancements (Post-Implementation)

1. **Smart Defaults:**
   - Learn typical sensor values over time
   - Suggest defaults based on similar systems

2. **Sensor Diagnostics:**
   - Detect sensors that are drifting or failing
   - Flag suspicious values (e.g., negative superheat)

3. **Calculation Confidence Scores:**
   - Rate each calculation (High/Medium/Low confidence)
   - Based on whether calculated or estimated

4. **Interactive Help:**
   - Clicking on "N/A" shows exactly what sensor to map
   - Sensor mapping wizard

5. **Historical Comparison:**
   - Compare current results to baseline
   - Flag anomalies

---

## 9. Questions Resolved

✅ **Q1: What are the 7 inputs?** - Confirmed above
✅ **Q2: Are mass flow, displacement, speed needed?** - Yes (validated)
✅ **Q3: What's priority?** - All three phases

---

## 10. Ready to Implement

All requirements are clear. The plan is comprehensive. Ready to start coding immediately.

**Estimated completion: 6-9 hours of focused work**

---

**STATUS:** Ready for Implementation
**Next Action:** Start with Phase 1 (Expand to 7 Inputs)
