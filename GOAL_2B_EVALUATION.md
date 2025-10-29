# Goal-2B Evaluation: Graceful Degradation Strategy for Missing Inputs

**Created:** 2025-10-29
**Issue:** "Missing or zero RPM" error blocks ALL calculations
**User Request:** Allow calculations to proceed with partial data, gracefully degrading when inputs are missing

---

## 1. Current Problem Analysis

### 1.1 The Error

**Error Message:**
```
An error occurred during calculation:
Missing or zero RPM

Please ensure:
1. Rated inputs are entered (click '⚙️ Enter Rated Inputs' button)
2. All required sensors are mapped in the Diagram tab
```

**Location:** `calculation_engine.py` line 51
```python
if rpm is None or rpm == 0:
    return pd.Series({'error': 'Missing or zero RPM'})
```

**Impact:** Entire calculation stops. User gets ZERO results, even though 90% of the calculations don't need RPM.

### 1.2 User's Correct Assessment

The user identified two key issues:

1. **Missing Inputs:** The system actually needs **7 inputs**, not 5:
   - ✅ Currently implemented (5):
     1. `m_dot_rated_lbhr` - Rated mass flow rate
     2. `hz_rated` - Rated compressor speed
     3. `disp_ft3` - Compressor displacement
     4. `rated_evap_temp_f` - Rated evaporator temperature
     5. `rated_return_gas_temp_f` - Rated return gas temperature

   - ❌ Missing (2):
     6. **Rated power** (for fixed compressors) OR **RPM** (for variable compressors)
     7. **Some other rated value** (need to investigate)

2. **All-or-Nothing Approach is Bad:** Blocking ALL calculations because ONE input is missing provides a poor user experience.

---

## 2. Calculation Dependency Analysis

### 2.1 What Calculations DON'T Need RPM or Rated Inputs

**✅ These work without ANY rated inputs or RPM:**

| Calculation Group | Columns Produced | Requires |
|-------------------|------------------|----------|
| **AT LH coil** | T_2a-LH, T_sat.lh, S.H_lh, H_coil lh, S_coil lh, D_coil lh (6 cols) | P_suc, T_2a-LH |
| **AT CTR coil** | T_2a-ctr, T_sat.ctr, S.H_ctr, H_coil ctr, S_coil ctr, D_coil ctr (6 cols) | P_suc, T_2a-ctr |
| **AT RH coil** | T_2a-RH, T_sat.rh, S.H_rh, H_coil rh, S_coil rh, D_coil rh (6 cols) | P_suc, T_2a-RH |
| **At compressor inlet** | Press.suc, Comp.in, T saturation, Super heat, Density, Enthalpy, Entropy (7 cols) | P_suc, T_2b |
| **Comp outlet** | T comp outlet (1 col) | T_3a |
| **At Condenser** | T cond inlet, Press disch, T cond. Outlet, T_sat_cond, Sub cooling_cond (5 cols) | P_disch, T_3b, T_4a |
| **At TXV LH** | TXV in-LH, T_Saturation_txv_lh, Subcooling_txv_lh, Enthalpy_txv_lh (4 cols) | P_disch, T_4b-lh |
| **At TXV CTR** | TXV in-CTR, T_Saturation_txv_ctr, Subcooling_txv_ctr, Enthalpy_txv_ctr (4 cols) | P_disch, T_4b-ctr |
| **At TXV RH** | TXV in-RH, T_Saturation_txv_rh, Subcooling_txv_rh, Enthalpy_txv_rh (4 cols) | P_disch, T_4b-rh |

**Total: 43 out of 47 columns (91.5%) can be calculated without RPM or rated inputs!**

### 2.2 What Calculations NEED RPM

**❌ These require RPM + rated inputs:**

| Calculation | Columns Produced | Requires |
|-------------|------------------|----------|
| **Comp. rpm display** | Comp. rpm (1 col) | RPM sensor |
| **Mass flow rate** | Mass flow rate (1 col) | RPM + density + displacement + eta_vol |
| **Cooling capacity** | Cooling cap (1 col) | Mass flow rate + enthalpies |

**Total: 4 out of 47 columns (8.5%) need RPM**

### 2.3 Dependency Chain

```
User enters rated inputs (5 values)
    ↓
calculate_volumetric_efficiency() → eta_vol
    ↓ (eta_vol required)
    ↓
    ├→ Mass flow rate calculation ← ALSO needs: RPM, density, displacement
    │       ↓
    │   Cooling capacity ← ALSO needs: enthalpies
    │
    └→ All other 43 calculations ← Do NOT need eta_vol or RPM!
```

**Key Insight:** The dependency is ONLY for 2 final calculations (mass flow & cooling cap). Everything else is independent!

---

## 3. Real Input Requirements Investigation

### 3.1 What Does the Code Actually Use?

**From `calculate_volumetric_efficiency()` (calculation_engine.py line 249):**
```python
def calculate_volumetric_efficiency(rated_inputs: Dict, refrigerant: str = 'R290') -> Dict:
    # 1. Get User Inputs
    m_dot_rated_lb_hr = rated_inputs.get('m_dot_rated_lbhr', 0)
    rated_evap_f = rated_inputs.get('rated_evap_temp_f', 0)
    rated_return_f = rated_inputs.get('rated_return_gas_temp_f', 0)
    rated_disp_ft3 = rated_inputs.get('disp_ft3', 0)
    rated_hz = rated_inputs.get('hz_rated', 0)  # ← Uses Hz, not RPM!
```

**Actual inputs used: 5 (not 7)**

**From `calculate_row_performance()` (calculation_engine.py line 51):**
```python
rpm = get_val('RPM')  # ← Gets RPM from CSV data (sensor), NOT from rated inputs!
```

### 3.2 The Confusion: Hz vs RPM

There are TWO different speed values:

1. **`hz_rated` (user input):** Rated compressor frequency in Hz
   - Used ONLY for calculating eta_vol
   - This is a constant from the manufacturer's datasheet
   - Example: 75 Hz

2. **`RPM` (CSV sensor data):** Real-time compressor speed in revolutions per minute
   - Used for calculating actual mass flow rate
   - This varies with each row of data
   - Example: 4500 RPM

**Relationship:**
```python
RPM ≈ Hz * some_constant_depending_on_compressor_design
```

For variable-speed compressors, RPM changes. For fixed-speed compressors, RPM is constant (but still measured by a sensor).

### 3.3 Missing Input Investigation

**User said "7 inputs" but code only uses 5. Let me check Calculations-DDT.txt:**

<details>
<summary>Searching Calculations-DDT.txt for required inputs...</summary>

From previous analysis:
```
* m_dot_rated: User Manual Input. Get the "Rated Mass Flow" (e.g., 211 lbm/hr)
* hz_rated: User Manual Input. Get the "Rated Speed" (e.g., 75 Hz)
* disp_ft3: User Manual Input. Get the "Compressor Displacement" (in ft^3)
* Rated Evap Temp: User Manual Input
* Rated Return Gas Temp: User Manual Input
```

**Conclusion: The spec only requires 5 inputs. User's "7 inputs" might be a misunderstanding, OR they have additional requirements not in the current spec.**

</details>

### 3.4 Two Possible Scenarios

**Scenario A: Fixed-Speed Compressor**
- Compressor always runs at same speed
- RPM should be constant (but still measured)
- If RPM sensor fails → can fall back to calculating RPM from Hz rating

**Scenario B: Variable-Speed Compressor**
- Compressor speed varies based on load
- RPM MUST come from sensor (cannot be estimated)
- If RPM sensor fails → mass flow calculations impossible

---

## 4. Proposed Solution: Graceful Degradation Strategy

### 4.1 Core Principle

**"Calculate what we can, report what we can't"**

Instead of:
```
❌ Missing RPM → ERROR → User gets nothing
```

We should do:
```
✅ Missing RPM → Calculate 43/47 columns → Show warning → User gets 91.5% of results
```

### 4.2 Implementation Strategy

#### Strategy 1: Partial Results with Warnings (RECOMMENDED)

**Behavior:**
1. Check for missing inputs/sensors at the START
2. Proceed with ALL calculations that are possible
3. For calculations that can't be done:
   - Insert `None` or `"N/A"` in result columns
   - Add warning message to a "warnings" column
4. Display results with clear visual indication of missing data

**Pseudocode:**
```python
def calculate_row_performance(...):
    results = {}
    warnings = []

    # Try to get all inputs
    rpm = get_val('RPM')
    p_suc = get_val('P_suc')
    # ... etc

    # Check what's missing
    if rpm is None:
        warnings.append("RPM sensor not mapped - cannot calculate mass flow or cooling capacity")
    if p_suc is None:
        warnings.append("Suction pressure not available - limited calculations possible")

    # Do ALL calculations that are possible
    if p_suc is not None and p_disch is not None:
        # Calculate all 43 state point columns
        # ... (existing code)
        results['T_2a-LH'] = ...
        results['H_coil lh'] = ...
        # etc

    # Only do mass flow if we have everything needed
    if rpm is not None and rho_2b is not None and eta_vol > 0 and disp_m3 > 0:
        results['Mass flow rate'] = ...
        results['Cooling cap'] = ...
    else:
        results['Mass flow rate'] = None
        results['Cooling cap'] = None
        if rpm is None:
            warnings.append("Cannot calculate mass flow: RPM sensor not available")
        if rho_2b is None:
            warnings.append("Cannot calculate mass flow: Density not available (need T_2b)")
        # ... etc

    # Always include Comp. rpm even if it's None
    results['Comp. rpm'] = rpm if rpm is not None else None

    # Add warnings column
    if warnings:
        results['warnings'] = "; ".join(warnings)

    return pd.Series(results)
```

**User Experience:**
```
Calculations tab shows:
- All 43 thermodynamic state point columns populated
- "Mass flow rate" column shows: <blank> or "N/A"
- "Cooling cap" column shows: <blank> or "N/A"
- Status bar shows: "⚠️ Calculated 43/47 columns. See warnings for details."
- Warnings column shows: "RPM sensor not mapped - cannot calculate mass flow or cooling capacity"
```

#### Strategy 2: Two-Tier Validation (ALTERNATIVE)

**Behavior:**
1. **Tier 1 (Critical):** Must have pressures (P_suc, P_disch) to do ANY calculations
2. **Tier 2 (Optional):** Everything else is optional, calculations degrade gracefully

**Pseudocode:**
```python
def run_calculation(self):
    # Tier 1: Check absolutely critical inputs
    critical_missing = []
    if p_suc is None:
        critical_missing.append("Suction Pressure")
    if p_disch is None:
        critical_missing.append("Discharge Pressure")

    if critical_missing:
        QMessageBox.critical(
            "Cannot Calculate",
            f"Critical sensors missing: {critical_missing}\n"
            "At minimum, you must map Suction Pressure and Discharge Pressure."
        )
        return  # STOP

    # Tier 2: Warn about optional missing inputs
    warnings = []
    if rpm is None:
        warnings.append("⚠️ RPM sensor not mapped - mass flow and cooling capacity will not be calculated")
    if rated_inputs incomplete:
        warnings.append("⚠️ Rated inputs not entered - mass flow and cooling capacity will not be calculated")

    if warnings:
        # Show warnings but DON'T stop
        QMessageBox.warning(
            "Partial Data",
            "Some calculations will be skipped due to missing data:\n\n" +
            "\n".join(warnings) +
            "\n\nProceed with partial calculations?"
        )

    # Proceed with calculation (graceful degradation inside)
    processed_df = run_batch_processing(...)
```

### 4.3 Recommended Approach

**Use Strategy 1 (Partial Results with Warnings) because:**

1. ✅ **Better UX:** User always gets something useful
2. ✅ **Transparent:** Warnings column shows exactly what's missing
3. ✅ **Flexible:** Works for both fixed and variable-speed compressors
4. ✅ **Progressive:** User can fix sensors one-by-one and see incremental improvement
5. ✅ **Educational:** Warnings teach the user what each sensor/input is for

---

## 5. Additional Input Requirements Analysis

### 5.1 Do We Really Need 7 Inputs?

**User's claim:** "Rated power and rated displacement (fixed compressors) / or rpm (for variable compressors) is missing"

**Current inputs (5):**
1. m_dot_rated_lbhr
2. hz_rated
3. disp_ft3
4. rated_evap_temp_f
5. rated_return_gas_temp_f

**Potentially missing (2):**
6. **Rated power (W or HP)?**
   - Use: Calculating efficiency (COP, EER)
   - Current status: Not implemented
   - Priority: MEDIUM (nice-to-have for performance analysis)

7. **Something else?**
   - Condenser water flow rate?
   - Rated cooling capacity?
   - Need user clarification

### 5.2 Fixed vs Variable Compressor Handling

**Current system assumes:** Variable-speed compressor (needs RPM sensor)

**Should also support:** Fixed-speed compressor (can calculate RPM from Hz rating)

**Proposed enhancement:**
```python
# In input_dialog.py, add option:
compressor_type = QComboBox(['Variable Speed', 'Fixed Speed'])

# In data_manager.py:
rated_inputs = {
    ...
    'compressor_type': 'variable',  # or 'fixed'
}

# In calculate_row_performance():
rpm = get_val('RPM')

if rpm is None and compressor_type == 'fixed' and hz_rated is not None:
    # Fallback for fixed-speed compressor
    # Typical relationship: RPM = Hz * 60 * 2 (for 2-pole motor)
    # This should come from compressor specs
    poles = 2  # Or get from rated_inputs
    rpm = hz_rated * 60 * (2 / poles)
    warnings.append(f"Using calculated RPM ({rpm:.0f}) from rated Hz (fixed-speed compressor)")
```

---

## 6. Implementation Plan (High-Level)

### Phase 1: Graceful Degradation (Priority: HIGH)

**Goal:** Stop blocking calculations when RPM is missing

**Changes:**

1. **calculation_engine.py - calculate_row_performance()**
   - Remove hard-coded failure: `if rpm is None: return error`
   - Change to: `if rpm is None: warnings.append(...)`
   - Wrap mass flow calculation in: `if rpm is not None and ...`
   - Return Series with partial results + warnings column

2. **calculations_widget.py - run_calculation()**
   - Remove hard-coded failure for missing rated inputs
   - Change to warning dialog: "Some calculations will be skipped..."
   - Allow calculation to proceed
   - Update status to show: "Calculated X/47 columns"

3. **calculations_widget.py - populate_tree()**
   - Add visual indicator for None/missing values (grayed out, "N/A" text)
   - Add "Warnings" column to tree display
   - Highlight rows with warnings in yellow/orange

### Phase 2: Additional Inputs (Priority: MEDIUM)

**Goal:** Add missing rated inputs (rated power, etc.)

**Investigation needed:**
1. Confirm with user: What are the actual 7 required inputs?
2. Check manufacturer datasheets: What values are standard?
3. Determine use cases: What calculations need rated power?

**Changes:**

1. **input_dialog.py**
   - Add 2 more QDoubleSpinBox fields
   - Update field list to 7 items

2. **data_manager.py**
   - Extend rated_inputs dict to 7 fields

3. **calculation_engine.py**
   - Add calculations that use the new inputs (e.g., efficiency metrics)

### Phase 3: Fixed vs Variable Compressor (Priority: LOW)

**Goal:** Support fixed-speed compressors with RPM calculation fallback

**Changes:**

1. **input_dialog.py**
   - Add compressor type selection (Variable/Fixed)
   - Conditional field display based on type

2. **calculation_engine.py**
   - Add RPM fallback logic for fixed-speed compressors

---

## 7. Comparison Table: Current vs Proposed

| Aspect | Current Behavior | Proposed Behavior |
|--------|------------------|-------------------|
| **Missing RPM** | ❌ Entire calculation fails | ✅ 43/47 columns calculated, 2 show "N/A" |
| **User Feedback** | ❌ Generic error dialog | ✅ Specific warnings for each missing item |
| **Data Loss** | ❌ User gets zero results | ✅ User gets 91.5% of results |
| **Debugging** | ❌ Hard to know what's wrong | ✅ Warnings column explains each issue |
| **Fixed Compressors** | ❌ Not supported | ✅ Can calculate RPM from Hz rating |
| **Input Requirements** | ❓ Claims 5, user says 7 | ✅ Clarify and implement actual needs |
| **Incremental Progress** | ❌ All-or-nothing | ✅ Fix sensors one-by-one, see improvement |

---

## 8. Risk Assessment

### 8.1 Risks of Current Approach (All-or-Nothing)

1. **User Frustration:** ⚠️ HIGH
   - User loads CSV, maps sensors, enters inputs
   - ONE missing sensor → "Missing RPM" → All work wasted
   - Discourages experimentation and learning

2. **Data Loss:** ⚠️ HIGH
   - 91.5% of calculations are valid
   - Throwing them away due to 8.5% missing is wasteful

3. **Debugging Difficulty:** ⚠️ MEDIUM
   - Error doesn't explain how to fix it
   - User doesn't know: "Do I need a sensor? Or a rated input? Or both?"

### 8.2 Risks of Proposed Approach (Graceful Degradation)

1. **User Confusion:** ⚠️ LOW
   - Mitigation: Clear warnings explain what's missing
   - Mitigation: Visual indicators (grayed out, "N/A") show incomplete data

2. **Incorrect Conclusions:** ⚠️ LOW
   - Risk: User might not notice mass flow is missing, draw wrong conclusions
   - Mitigation: Prominent warnings in UI
   - Mitigation: Export includes warnings column

3. **Complex Code:** ⚠️ LOW
   - More if/else branching
   - Mitigation: Clear comments, well-tested

### 8.3 Recommendation

**Proceed with graceful degradation** - the benefits far outweigh the risks.

---

## 9. Questions for User

Before implementation, please clarify:

### Q1: What are the actual 7 required inputs?

You mentioned:
- ✅ 5 currently implemented
- ❓ Rated power (for what calculation?)
- ❓ One more mystery input

**Options:**
- [ ] Rated power (W or HP)
- [ ] Rated cooling capacity (BTU/hr)
- [ ] Rated current draw (A)
- [ ] Condenser water flow rate
- [ ] Motor pole count (for RPM calculation)
- [ ] Other: ___________

### Q2: Fixed-speed vs variable-speed compressor

Is your compressor:
- [ ] Fixed-speed (always runs at same RPM, e.g., 3600 RPM)
- [ ] Variable-speed (RPM varies with load, e.g., 1000-6000 RPM)
- [ ] Mixed (some fixed, some variable)

### Q3: Priority order

Which is more important:
1. [ ] Fix the "Missing RPM" blocker (graceful degradation)
2. [ ] Add the 2 missing rated inputs
3. [ ] Both equally important

---

## 10. Recommended Next Steps

### Immediate (Do First)
1. **User feedback on questions above** ⬅️ START HERE
2. Create detailed implementation plan for graceful degradation
3. Identify exact 7 inputs (if truly 7)

### Short-term (This Week)
1. Implement graceful degradation (Phase 1)
2. Test with missing RPM sensor
3. Verify 43 columns calculate correctly

### Medium-term (Next Week)
1. Add missing rated inputs (Phase 2)
2. Implement calculations that use them
3. Update dialog and validation

### Long-term (Nice to Have)
1. Fixed-speed compressor support
2. Advanced efficiency metrics (COP, EER, etc.)
3. Sensor diagnostics (which sensors are marginal/failing)

---

## 11. Example User Scenarios

### Scenario A: New User, Incomplete Setup

**Current Behavior:**
```
1. User loads CSV
2. User maps SOME sensors (forgets RPM)
3. User clicks "Run"
4. ERROR: "Missing RPM"
5. User frustrated, gives up
```

**Proposed Behavior:**
```
1. User loads CSV
2. User maps SOME sensors (forgets RPM)
3. User clicks "Run"
4. WARNING: "RPM not mapped - mass flow/cooling cap will be blank"
5. User clicks "OK, proceed"
6. Table shows: 43 columns with data, 2 columns blank, warnings column
7. User sees: "Ah, I need to map RPM for those 2 columns"
8. User maps RPM, runs again
9. Now all 47 columns populated!
```

**Result:** User learns incrementally, makes progress

### Scenario B: Fixed-Speed Compressor, No RPM Sensor

**Current Behavior:**
```
System requires RPM sensor
User's compressor has no RPM sensor (it's fixed-speed)
User cannot calculate mass flow or cooling capacity
User must buy and install RPM sensor ($$$)
```

**Proposed Behavior:**
```
User sets compressor type: "Fixed Speed"
User enters rated Hz: 60 Hz
User enters motor poles: 2
System calculates: RPM = 60 * 60 * (2/2) = 3600 RPM
All calculations work without sensor!
```

**Result:** Lower cost, easier deployment

### Scenario C: Temporary Sensor Failure

**Current Behavior:**
```
RPM sensor fails mid-test
All subsequent calculations fail
User must stop test, fix sensor, restart
Hours of data lost
```

**Proposed Behavior:**
```
RPM sensor fails mid-test
Calculations continue with warnings
Mass flow/cooling cap columns show "N/A" for affected rows
Other 43 columns continue to populate
User can identify exact time sensor failed
User can still analyze partial data
```

**Result:** Test continues, partial data preserved

---

## 12. Conclusion

### Summary

1. **Current system is too strict:** Blocking ALL calculations for ONE missing input is bad UX

2. **91.5% of calculations are independent:** They don't need RPM or rated inputs

3. **Graceful degradation is the solution:**
   - Calculate what you can
   - Report what you can't
   - Give user partial results + warnings

4. **Need clarification on "7 inputs":**
   - Code only uses 5
   - User says 7
   - Need to identify the missing 2

5. **Implementation is straightforward:**
   - Remove hard-coded failures
   - Add warning collection
   - Wrap dependent calculations in conditionals

### Recommendation

**Proceed with Phase 1 (Graceful Degradation) immediately**
- This fixes the urgent "Missing RPM" blocker
- Dramatically improves user experience
- Enables incremental sensor mapping
- Low risk, high reward

**Defer Phase 2 & 3 until user clarifies requirements**
- Wait for feedback on "7 inputs" question
- Wait for feedback on fixed/variable compressor question

---

**STATUS: Evaluation Complete - Awaiting User Feedback on Questions**

Next Action: User confirms:
1. What are the actual 7 required inputs?
2. Fixed-speed or variable-speed compressor?
3. Priority: Graceful degradation vs additional inputs?
