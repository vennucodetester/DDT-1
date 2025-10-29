# Goal-2 Implementation Plan: Input Dialog Refactoring

**Created:** 2025-10-29
**Branch:** `claude/refactor-calculation-engine-011CUap9sd3nSiYRE7M2b2iL`
**Status:** Analysis Complete - Ready for Implementation

---

## 1. Problem Analysis

### 1.1 Current Error (from error-1.txt and input tab.png)

**Error Message:**
```
Calculation error: unsupported operand type(s) for +: 'NoneType' and 'float'

Please ensure:
1. Rated inputs are entered in the Inputs tab
2. All required sensors are mapped in the Diagram tab
```

**Error Location:**
- Line 468 in error-1.txt: `[BATCH PROCESSING] ERROR in Step 1 (eta_vol): Calculation error: unsupported operand type(s) for +: 'NoneType' and 'float'`
- Line 469: `[BATCH PROCESSING] Please enter rated inputs in the Inputs tab.`

**Root Cause:**
The unified calculation engine (implemented in the previous session) requires 7 rated performance inputs to calculate volumetric efficiency (eta_vol). When users click "Run" in the Calculations tab without entering these values:
1. `data_manager.rated_inputs` contains `None` values
2. `calculate_volumetric_efficiency()` attempts arithmetic operations with `None`
3. Python throws `TypeError: unsupported operand type(s) for +: 'NoneType' and 'float'`

### 1.2 User Experience Problem

The error message says "Rated inputs are entered in the Inputs tab", but:
1. The current `inputs_widget.py` is confusing and poorly designed
2. There are multiple calculation-related tabs that create confusion
3. The tab structure doesn't match user expectations

**Evidence from input tab.png:**
The error dialog appears when calculations fail, directing users to an "Inputs tab" that may or may not exist or be properly integrated.

---

## 2. Current State Analysis

### 2.1 Existing Files (Obsolete/Problematic)

1. **`inputs_widget.py` (14 KB)**
   - Purpose: Presumably for entering rated inputs
   - Problem: Confusing, unnecessary as a separate tab
   - Action: **DELETE**

2. **`live_calculation_widget.py` (15 KB)**
   - Purpose: Unknown "Performance" or "Live Calculation" tab
   - Problem: Creates confusion, not in Goal-2.txt requirements
   - Currently imported in app.py line 15
   - Currently instantiated in app.py line 46
   - Currently referenced in update_active_tab() method
   - Action: **DELETE + CLEAN UP REFERENCES**

3. **`simple_calculation_widget.py` (25 KB)**
   - Purpose: Old calculation widget (before unified engine)
   - Problem: Replaced by new `calculations_widget.py`
   - Action: **DELETE**

### 2.2 Current Tab Structure (app.py lines 91-95)

```python
self.tabs.addTab(self.diagram_widget, "Diagram")
self.tabs.addTab(self.graph_widget, "Graph")
self.tabs.addTab(self.comparison_widget, "Comparison")
self.tabs.addTab(self.calculations_widget, "Calculations")
self.tabs.addTab(self.ph_diagram_interactive_widget, "P-h Interactive")
```

**Analysis:**
- ✅ Tabs are already clean (no "Inputs", "Performance", or old calculation tabs)
- ✅ Tab naming is correct ("P-h Interactive" already matches Goal-2.txt)
- ⚠️ BUT: `live_calc_widget` is still instantiated and referenced in code (not added to tabs)

### 2.3 Required Inputs (from goal.md - previous session)

The unified calculation engine needs **7 rated performance inputs**:

1. `m_dot_rated_lbhr` - Rated mass flow rate (lbm/hr)
2. `hz_rated` - Rated compressor speed (Hz)
3. `disp_ft3` - Compressor displacement (ft³)
4. `rated_evap_temp_f` - Rated evaporator temperature (°F)
5. `rated_return_gas_temp_f` - Rated return gas temperature (°F)
6. **[NEED TO VERIFY 2 MORE FROM CODE]**

**Note:** Goal-2.txt mentions "7 required inputs" but doesn't list them all. I need to check the actual calculation_engine.py to verify all 7 fields.

---

## 3. Goal-2.txt Requirements Summary

### Phase 1: Create New Input Dialog
**Deliverable:** New file `input_dialog.py`

**Requirements:**
- Class: `InputDialog` (inherits from `QDialog`)
- Layout: `QFormLayout`
- Fields: 7 `QLineEdit` widgets for rated performance inputs
- Buttons: "OK" and "Cancel" (QDialogButtonBox)
- Methods:
  - `get_data()` → Returns dict of 7 values (converted to float)
  - `set_data(data)` → Pre-fills fields from existing data

### Phase 2: Clean Up app.py
**Deliverable:** Modified `app.py`

**Actions:**
1. ✅ Remove import: `from live_calculation_widget import LiveCalculationWidget`
2. ✅ Remove instantiation: `self.live_calc_widget = ...`
3. ✅ Remove references in `update_active_tab()` method
4. ✅ Verify tab naming (already correct)
5. ✅ Ensure only 5 tabs exist

### Phase 3: Modify calculations_widget.py
**Deliverable:** Modified `calculations_widget.py`

**Actions:**
1. Add "Enter Rated Inputs" button at top of layout
2. Create `open_input_dialog()` method:
   - Import InputDialog
   - Create instance
   - Pre-fill with `self.data_manager.rated_inputs`
   - On OK: Save to `self.data_manager.rated_inputs`
   - Optionally re-run calculations
3. Add guard clause to `run_calculations()`:
   - Check if all 7 rated inputs are filled
   - If missing: Show `QMessageBox.warning()` with helpful message
   - Do NOT proceed with calculation if inputs missing

### Phase 4: Modify ph_diagram_widget.py
**Deliverable:** Modified `ph_diagram_widget.py`

**Actions:**
1. In `load_filtered_data()`: Check if rated inputs are filled
2. If not filled: Return early (don't plot)
3. Rely on Calculations tab to show the error message

---

## 4. Implementation Plan (Detailed Steps)

### Step 1: Verify Required Inputs
**Before coding, confirm the exact 7 fields needed**

- [ ] Read `calculation_engine.py` → `calculate_volumetric_efficiency()` function
- [ ] Document exact field names and descriptions
- [ ] Update this document with definitive list

### Step 2: Create input_dialog.py
**New file with QDialog for entering rated inputs**

```python
# Pseudocode structure:
class InputDialog(QDialog):
    def __init__(self, parent=None):
        - Set up QFormLayout
        - Create 7 QLineEdit fields with labels
        - Add QDialogButtonBox (OK/Cancel)
        - Connect signals

    def get_data(self) -> dict:
        - Read all 7 QLineEdit values
        - Convert to float (with error handling)
        - Return dict

    def set_data(self, data: dict):
        - Pre-fill all 7 QLineEdit fields
        - Handle missing/None values gracefully
```

**Validation considerations:**
- Should we validate on OK click?
- Should we show errors for invalid floats?
- Should we allow empty fields (treat as None)?

### Step 3: Clean Up app.py

**3.1 Remove Imports**
```python
# DELETE LINE 15:
from live_calculation_widget import LiveCalculationWidget
```

**3.2 Remove Instantiation**
```python
# DELETE LINE 46 (approximately):
self.live_calc_widget = LiveCalculationWidget(self.data_manager)
```

**3.3 Clean Up update_active_tab() Method**
Find and remove references to `self.live_calc_widget` in the method around line 178-181.

**3.4 Verify Tab Setup**
- Confirm only 5 tabs are added
- Confirm "P-h Interactive" naming (already correct)

### Step 4: Modify calculations_widget.py

**4.1 Add Import**
```python
from input_dialog import InputDialog
```

**4.2 Add Button to Layout**
In `__init__` or `setup_ui()`:
```python
# Create button
self.btn_enter_inputs = QPushButton("Enter Rated Inputs")
self.btn_enter_inputs.clicked.connect(self.open_input_dialog)

# Add to top of layout (before existing widgets)
top_layout = QHBoxLayout()
top_layout.addWidget(self.btn_enter_inputs)
top_layout.addStretch()
main_layout.insertLayout(0, top_layout)
```

**4.3 Create open_input_dialog() Method**
```python
def open_input_dialog(self):
    dialog = InputDialog(self)
    dialog.set_data(self.data_manager.rated_inputs)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        data = dialog.get_data()
        self.data_manager.rated_inputs = data
        # Optional: self.run_calculations()
        QMessageBox.information(self, "Success", "Rated inputs saved successfully.")
```

**4.4 Add Guard Clause to run_calculations()**
```python
def run_calculations(self):
    # GUARD CLAUSE: Check for rated inputs
    rated_inputs = self.data_manager.rated_inputs

    # Check if all 7 required fields are present and not None
    required_fields = [
        'm_dot_rated_lbhr',
        'hz_rated',
        'disp_ft3',
        'rated_evap_temp_f',
        'rated_return_gas_temp_f',
        # ... add 2 more
    ]

    missing_fields = []
    for field in required_fields:
        if rated_inputs.get(field) is None:
            missing_fields.append(field)

    if missing_fields:
        QMessageBox.warning(
            self,
            "Missing Inputs",
            "Please click the 'Enter Rated Inputs' button and fill in all 7 "
            "'Rated Performance Inputs' fields before running calculations.\n\n"
            f"Missing fields: {', '.join(missing_fields)}"
        )
        return  # EXIT - do not proceed

    # ... rest of existing calculation code
```

### Step 5: Modify ph_diagram_widget.py

**5.1 Add Input Check to load_filtered_data()**
```python
def load_filtered_data(self, filtered_df, circuit_data=None):
    # Check if rated inputs are filled
    rated_inputs = self.data_manager.rated_inputs
    required_fields = [...]  # Same 7 fields

    missing = any(rated_inputs.get(f) is None for f in required_fields)

    if missing:
        # Don't show error here - Calculations tab already did
        # Just return early without plotting
        return

    # ... rest of existing plotting code
```

### Step 6: Delete Obsolete Files

**Files to DELETE:**
1. `inputs_widget.py`
2. `live_calculation_widget.py`
3. `simple_calculation_widget.py`

**Method:**
```bash
git rm inputs_widget.py
git rm live_calculation_widget.py
git rm simple_calculation_widget.py
```

### Step 7: Testing Plan

**Test Case 1: First Run (No Inputs)**
1. Open application
2. Load CSV data
3. Go to Calculations tab
4. Click "Run"
5. **Expected:** Warning dialog appears listing missing inputs

**Test Case 2: Enter Inputs**
1. Click "Enter Rated Inputs" button
2. **Expected:** Dialog opens with 7 empty fields
3. Fill in all 7 fields with valid numbers
4. Click OK
5. **Expected:** Success message, dialog closes

**Test Case 3: Run with Inputs**
1. Click "Run" in Calculations tab
2. **Expected:** Calculations execute successfully, table populates

**Test Case 4: Persistence**
1. Save session (File → Save)
2. Close application
3. Reopen and load session
4. Click "Enter Rated Inputs"
5. **Expected:** Dialog shows previously entered values

**Test Case 5: P-h Diagram**
1. With valid inputs, run calculations
2. Go to "P-h Interactive" tab
3. **Expected:** Diagram plots correctly with all state points

---

## 5. Technical Considerations

### 5.1 Field Validation in InputDialog

**Options:**
1. **Lenient:** Allow empty fields, treat as None
2. **Strict:** Require all fields before allowing OK

**Recommendation:** Lenient approach
- Users may want to save partial data
- Validation happens in `run_calculations()` anyway
- Better UX (don't block dialog closing)

**Implementation:**
```python
def get_data(self):
    data = {}
    for field_name, line_edit in self.fields.items():
        text = line_edit.text().strip()
        if text:
            try:
                data[field_name] = float(text)
            except ValueError:
                data[field_name] = None
        else:
            data[field_name] = None
    return data
```

### 5.2 Data Manager Integration

**Verify data_manager.py has:**
- `rated_inputs` dictionary initialized
- Session save/load support

From previous session (MIGRATION_COMPLETE.md), this should already exist:
```python
self.rated_inputs = {
    'm_dot_rated_lbhr': None,
    'hz_rated': None,
    'disp_ft3': None,
    'rated_evap_temp_f': None,
    'rated_return_gas_temp_f': None,
    # ... potentially 2 more
}
```

### 5.3 Auto-Run After Input Entry

**Question:** Should we automatically run calculations after user enters inputs?

**Pros:**
- Faster workflow
- Immediate feedback

**Cons:**
- May be unexpected
- User might want to review/edit first

**Recommendation:** Don't auto-run, but show success message
- User retains control
- Clear feedback that data was saved
- User can click "Run" when ready

---

## 6. Definition of Done

### Code Deliverables
- [ ] `input_dialog.py` created with full functionality
- [ ] `app.py` cleaned up (no dead code)
- [ ] `calculations_widget.py` modified with button + guard clause
- [ ] `ph_diagram_widget.py` modified with input check
- [ ] 3 obsolete files deleted

### Testing
- [ ] All 5 test cases pass
- [ ] No console errors on startup
- [ ] No crashes when clicking "Enter Rated Inputs"
- [ ] Calculations work with valid inputs
- [ ] Calculations blocked with missing inputs
- [ ] Session save/load preserves input values

### Documentation
- [ ] Update MIGRATION_COMPLETE.md with Goal-2 changes
- [ ] Clear commit messages
- [ ] This implementation plan document complete

---

## 7. Open Questions (To Resolve Before Coding)

### Q1: What are the exact required inputs? ✅ RESOLVED

**VERIFIED FROM CODE:**

The actual implementation in `calculation_engine.py` uses **5 inputs**:
1. `m_dot_rated_lbhr` - Rated Mass Flow Rate (lbm/hr)
2. `hz_rated` - Rated Compressor Speed (Hz)
3. `disp_ft3` - Compressor Displacement (ft³)
4. `rated_evap_temp_f` - Rated Evaporator Temperature (°F)
5. `rated_return_gas_temp_f` - Rated Return Gas Temperature (°F)

**DISCREPANCY RESOLUTION:**

Goal-2.txt mentions "7 required inputs" but:
- Current `data_manager.py` has only 5 fields
- Current `calculation_engine.py` uses only 5 fields
- `Calculations-DDT.txt` specification requires only 5 user manual inputs

**DECISION:** Implement with 5 inputs (what's actually used)
- This matches the working calculation engine
- This matches the specification
- If user truly needs 7 fields, they can be added later

**Note:** The original goal.md mentioned "Rated Capacity" and "Rated Power" as additional inputs, but these were not implemented because they're not needed for the thermodynamic calculations.

### Q2: Field Labels for InputDialog ✅ RESOLVED

**DECISION:** Use user-friendly labels with units

```python
FIELD_DEFINITIONS = [
    ('m_dot_rated_lbhr', 'Rated Mass Flow Rate (lbm/hr)'),
    ('hz_rated', 'Rated Compressor Speed (Hz)'),
    ('disp_ft3', 'Compressor Displacement (ft³)'),
    ('rated_evap_temp_f', 'Rated Evaporator Temperature (°F)'),
    ('rated_return_gas_temp_f', 'Rated Return Gas Temperature (°F)'),
]
```

These labels are:
- Clear and descriptive for users
- Include units for guidance
- Match the manufacturer's data sheet terminology

### Q3: Input Validation Strictness ✅ RESOLVED

**DECISION:** Use `QDoubleSpinBox` for all fields

**Rationale:**
- Automatically constrains to numeric input (can't enter text)
- Better UX with increment/decrement arrows
- Built-in range validation (can set min/max)
- No need for try/except in get_data()
- Professional appearance

**Configuration:**
```python
spinbox.setRange(0.0, 999999.0)  # Allow large values
spinbox.setDecimals(2)  # 2 decimal places
spinbox.setSuffix('')  # No suffix (units in label)
spinbox.setSpecialValueText('')  # Show 0.00 instead of special text
```

---

## 8. Risk Assessment

### Low Risk
- Creating `input_dialog.py` (new file, no dependencies)
- Adding button to `calculations_widget.py` (additive change)
- Deleting obsolete files (git can recover if needed)

### Medium Risk
- Modifying `run_calculations()` guard clause (could break existing flow)
- Cleaning up `app.py` references (must find all references to live_calc_widget)

### Mitigation Strategies
1. **Test incrementally** - Don't change everything at once
2. **Git commits** - Commit after each phase
3. **Backup** - Current state is already committed
4. **Rollback plan** - Can revert any commit if issues arise

---

## 9. Implementation Order (Recommended)

**Day 1 (Setup & Verification):**
1. ✅ Read error-1.txt and analyze (DONE)
2. ✅ Read Goal-2.txt (DONE)
3. ✅ View input tab.png (DONE)
4. ✅ Create this implementation plan (IN PROGRESS)
5. ⏳ Verify 7 required inputs from calculation_engine.py
6. ⏳ Update this document with definitive input list

**Day 1 (Phase 1 - Input Dialog):**
7. Create `input_dialog.py` skeleton
8. Test dialog opens/closes
9. Add all 7 fields with proper labels
10. Implement `get_data()` and `set_data()` methods
11. Test standalone dialog

**Day 1 (Phase 3 - Calculations Widget):**
12. Add "Enter Rated Inputs" button
13. Wire up `open_input_dialog()` method
14. Test dialog opens from Calculations tab
15. Add guard clause to `run_calculations()`
16. Test error message shows when inputs missing

**Day 2 (Phase 2 & 4 - Cleanup):**
17. Clean up `app.py` (remove dead code)
18. Test application starts without errors
19. Modify `ph_diagram_widget.py` input check
20. Delete 3 obsolete files

**Day 2 (Testing & Finalization):**
21. Run all 5 test cases
22. Fix any bugs found
23. Update documentation
24. Commit and push

---

## 10. Success Criteria

This implementation will be considered successful when:

1. ✅ Users can enter 7 rated inputs via a clean dialog
2. ✅ Dialog is accessible from Calculations tab
3. ✅ Calculations are BLOCKED when inputs are missing
4. ✅ Clear, helpful error message guides users
5. ✅ No confusing/unnecessary tabs remain
6. ✅ Application structure is clean and maintainable
7. ✅ All tests pass without errors
8. ✅ Previous calculation functionality still works

---

**STATUS: Analysis Complete - Awaiting Input Verification Before Implementation**

Next Action: Read `calculation_engine.py` to verify all 7 required input fields.
