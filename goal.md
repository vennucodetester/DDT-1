# **Analysis & Migration Plan: Unifying the Calculation Engine**

## **1\. Executive Summary: The Core Challenge**

Your new specifications (Calculations-DDT.txt, .csv, ph diagram-DDT.txt) describe a sophisticated, multi-circuit calculation model. This model is a major evolution from your current codebase.

The core challenge is that your application currently has **two separate, competing, and incomplete calculation systems**:

1. **System A (Current "Calculations" Tab):**  
   * **File:** coolprop\_calculator.py  
   * **Method:** Processes data row-by-row (Good).  
   * **Flaw 1 (Critical):** Uses **hard-coded sensor names** (e.g., row\['Left TXV Bulb'\]) \[cite: coolprop\_calculator.py (line 274)\]. This is brittle and will break.  
   * **Flaw 2 (Critical):** Calculates **incomplete metrics**. It calculates *specific* performance (e.g., q\_evap\_specific in kJ/kg) \[cite: coolprop\_calculator.py (line 364)\] but **does not calculate total Mass flow rate or Cooling cap in Watts/BTU/hr**, which your new layout requires.  
2. **System B (Current "Performance" Tab):**  
   * **Files:** calculation\_orchestrator.py / calculation\_engine.py  
   * **Method:** Uses the flexible **diagram port mappings** (e.g., resolve\_mapped\_sensor(model, 'Compressor', 'SP')) (Good) \[cite: calculation\_orchestrator.py (line 86)\].  
   * **Method:** Correctly calculates **total Mass flow rate and Cooling cap** (Good) \[cite: calculation\_engine.py (lines 284-360)\].  
   * **Flaw (Critical):** It **only works on single, aggregated values** (e.g., the *average* temperature over a time range) \[cite: calculation\_orchestrator.py (line 87)\]. It cannot process a full DataFrame row-by-row to produce the table you want.

**The Goal:** Your new specifications require a **single, unified system** that:

1. Uses the **flexible port mapping** of System B.  
2. Performs the **row-by-row processing** of System A.  
3. Implements the **brand-new calculation logic** (User Inputs, eta\_vol, new mass flow formula) from Calculations-DDT.txt.

The plan is to **retire coolprop\_calculator.py entirely** and evolve System B to meet all these new requirements.

## **2\. Gap Analysis: Current State vs. Target State**

### **Gap 1: User Inputs (New Requirement)**

* **Target:** Calculations-DDT.txt introduces **"User Manual Input"** (Rated Capacity, Rated Power, Compressor Displacement, etc.). These are essential for the new eta\_vol calculation.  
* **Current:** No UI or DataManager fields exist to store these values. The current eta\_vol is just a hard-coded default (0.85) \[cite: calculation\_orchestrator.py (line 167)\].

### **Gap 2: Calculation Logic (The eta\_vol Two-Step)**

* **Target:** Calculations-DDT.txt defines a new two-step process:  
  1. **Step 1 (One-Time):** Use the "User Manual Inputs" to calculate a single, constant **eta\_vol (Volumetric Efficiency)**.  
  2. **Step 2 (Row-by-Row):** Use this eta\_vol to calculate the real-time Mass flow rate and Cooling cap for every timestamp.  
* **Current:** This logic does not exist.  
  * System A (coolprop\_calculator.py) doesn't calculate mass flow or total capacity at all.  
  * System B (calculation\_engine.py) calculates mass flow but uses a simple, hard-coded vol\_eff.

### **Gap 3: Sensor Inputs (Flexibility vs. Rigidity)**

* **Target:** Calculations-DDT.txt lists all required sensor inputs (e.g., T\_1a-lh, T\_2a-LH, P\_suc). The system must be flexible enough to map *any* CSV sensor to these roles.  
* **Current:** The "Calculations" tab (coolprop\_calculator.py) is **rigidly hard-coded** to specific CSV column names (e.g., row\['Right TXV Bulb '\]) and will fail if they change. This is the primary reason it must be retired.

### **Gap 4: "Calculations" Tab UI (Output Format)**

* **Target:** Calculations-DDT.xlsx demands a **hierarchical (nested) table header** (e.g., "AT LH coil" spanning 8 sub-columns like "TXV out", "Coil in", etc.).  
* **Current:** The CalculationsWidget is almost certainly a simple QTableWidget which **cannot** render nested headers. It must be rebuilt.

### **Gap 5: "P-h Interactive" Tab (Visualization)**

* **Target:** ph diagram-DDT.txt requires a **multi-circuit plot** on a single diagram, showing all 3 subcooling points (T\_4b-lh, T\_4b-ctr, T\_4b-rh) and all 3 superheat points (T\_2a-LH, T\_2a-ctr, T\_2a-RH).  
* **Current:** The PhDiagramWidget receives data from the old coolprop\_calculator.py. While it *gets* circuit-specific data, its plotting logic in ph\_diagram\_plotter.py will need to be explicitly updated to read the *new* DataFrame columns and ensure all 7+ points are plotted as specified.

## **3\. Migration Plan: Building the Unified Engine**

This plan retires coolprop\_calculator.py and refactors calculation\_orchestrator.py and calculation\_engine.py to become the new, unified engine.

### **Step 1: Add "User Manual Input" Storage**

1. **Modify data\_manager.py:**  
   * In \_\_init\_\_, add a new dictionary: self.rated\_inputs \= {}.  
   * In load\_session, add: self.rated\_inputs \= session\_data.get('ratedInputs', {}).  
   * In save\_session, add: session\_data\["ratedInputs"\] \= self.rated\_inputs.  
2. **Modify inputs\_widget.py (Recommended):**  
   * Add QLineEdit or QDoubleSpinBox widgets for each "User Manual Input" defined in Calculations-DDT.txt (Rated Capacity, Rated Power, Rated RPM, etc.).  
   * When these values are changed, save them into the DataManager: self.data\_manager.rated\_inputs\['rated\_capacity\_btu'\] \= float(self.rated\_capacity\_edit.text()).  
   * Also, load these values from the DataManager when the tab is shown.

### **Step 2: Implement "Step 1" Logic (Calculate eta\_vol)**

1. **Modify calculation\_engine.py:**  
   * Create a new function to perform the one-time eta\_vol calculation from Calculations-DDT.txt.  
   * This function will take the rated\_inputs dictionary and return the calculated eta\_vol.

\# In calculation\_engine.py  
import CoolProp.CoolProp as CP

def f\_to\_k(temp\_f): ...  
def hz\_to\_rph(hz): return hz \* 3600.0  
def ft3\_to\_m3(ft3): return ft3 \* 0.0283168

def calculate\_volumetric\_efficiency(rated\_inputs: dict) \-\> dict:  
    """  
    Performs the "Step 1" calculation from Calculations-DDT.txt  
    to find the constant volumetric efficiency.  
    """  
    try:  
        \# 1\. Get User Inputs  
        rated\_cap\_btu\_hr \= rated\_inputs.get('rated\_capacity\_btu\_hr', 0\)  
        rated\_power\_w \= rated\_inputs.get('rated\_power\_w', 0\)  
        rated\_evap\_f \= rated\_inputs.get('rated\_evap\_f', 0\)  
        rated\_return\_f \= rated\_inputs.get('rated\_return\_gas\_f', 0\)  
        rated\_disp\_ft3 \= rated\_inputs.get('rated\_displacement\_ft3', 0\)  
        rated\_hz \= rated\_inputs.get('rated\_hz', 0\)  
        refrigerant \= 'R290' \# Or get from DataManager

        \# 2\. Calculate m\_dot\_rated (Rated Mass Flow)  
        rated\_cap\_w \= rated\_cap\_btu\_hr / 3.412  
        q\_evap\_rated\_j\_kg \= (rated\_cap\_w / rated\_power\_w) \* 1000 \# Example, adjust as needed  
        \# THIS IS A PLACEHOLDER. You need the correct formula for q\_evap\_rated.  
        \# Let's assume you get h\_in and h\_out from rated temps  
        rated\_evap\_k \= f\_to\_k(rated\_evap\_f)  
        rated\_return\_k \= f\_to\_k(rated\_return\_f)

        \# This is a simplification; full state points are needed  
        \# P\_rated\_sat \= CP.PropsSI('P', 'T', rated\_evap\_k, 'Q', 0, refrigerant)  
        \# h\_g\_rated \= CP.PropsSI('H', 'T', rated\_evap\_k, 'Q', 1, refrigerant)  
        \# h\_in\_rated \= CP.PropsSI('H', 'T', rated\_return\_k, 'P', P\_rated\_sat, refrigerant)  
        \# ... you need h\_liquid\_rated ...  
        \# m\_dot\_rated\_kgs \= rated\_cap\_w / (h\_in\_rated \- h\_liquid\_rated) \# This is the goal

        \# \--- This logic needs to be fully implemented per your engineering specs \---  
        \# \--- Using placeholder logic from your file for now \---  
        m\_dot\_rated\_lb\_hr \= rated\_inputs.get('m\_dot\_rated\_lb\_hr', 1.0) \# Placeholder

        \# 3\. Calculate m\_dot\_th (Theoretical Mass Flow)  
        P\_rated\_sat \= CP.PropsSI('P', 'T', f\_to\_k(rated\_evap\_f), 'Q', 0, refrigerant)  
        dens\_rated\_kg\_m3 \= CP.PropsSI('D', 'T', f\_to\_k(rated\_return\_f), 'P', P\_rated\_sat, refrigerant)  
        dens\_rated\_lb\_ft3 \= dens\_rated\_kg\_m3 \* 0.062428

        rph \= hz\_to\_rph(rated\_hz)  
        m\_dot\_th\_lb\_hr \= dens\_rated\_lb\_ft3 \* rph \* rated\_disp\_ft3

        \# 4\. Calculate eta\_vol  
        if m\_dot\_th\_lb\_hr \== 0:  
            return {'error': 'Theoretical mass flow is zero'}

        eta\_vol \= m\_dot\_rated\_lb\_hr / m\_dot\_th\_lb\_hr

        return {  
            'eta\_vol': eta\_vol,  
            'm\_dot\_rated\_lb\_hr': m\_dot\_rated\_lb\_hr,  
            'm\_dot\_th\_lb\_hr': m\_dot\_th\_lb\_hr,  
            'dens\_rated\_lb\_ft3': dens\_rated\_lb\_ft3,  
        }  
    except Exception as e:  
        return {'error': str(e)}

### **Step 3: Create the New "Batch Processing" Engine**

This involves creating a new orchestrator function and a new engine function that performs the "Step 2" row-by-row logic.

1. **Modify calculation\_engine.py:**  
   * Add the new "Step 2" function. This will be called *for every row*.

\# In calculation\_engine.py

def calculate\_row\_performance(row: pd.Series, sensor\_map: dict, eta\_vol: float, comp\_specs: dict) \-\> pd.Series:  
    """  
    Performs the "Step 2" calculation from Calculations-DDT.txt  
    on a single row of data.  
    """  
    refrigerant \= 'R290'  
    results \= {}

    try:  
        \# 1\. Get all required sensor values using the map  
        def get\_val(key):  
            return row.get(sensor\_map.get(key))

        p\_suc\_psig \= get\_val('P\_suc')  
        p\_disch\_psig \= get\_val('P\_disch')  
        rpm \= get\_val('RPM')

        t\_2a\_lh\_f \= get\_val('T\_2a-LH')  
        t\_2a\_ctr\_f \= get\_val('T\_2a-ctr')  
        t\_2a\_rh\_f \= get\_val('T\_2a-RH')  
        t\_2b\_f \= get\_val('T\_2b') \# Comp.in

        t\_4b\_lh\_f \= get\_val('T\_4b-lh') \# TXV in-LH  
        t\_4b\_ctr\_f \= get\_val('T\_4b-ctr') \# TXV in-CTR  
        t\_4b\_rh\_f \= get\_val('T\_4b-rh') \# TXV in-RH

        \# ... get all other T\_1a, T\_1b, etc. ...

        \# 2\. Convert units (Pa and K)  
        p\_suc\_pa \= psig\_to\_pa(p\_suc\_psig)  
        p\_disch\_pa \= psig\_to\_pa(p\_disch\_psig)

        t\_2a\_lh\_k \= f\_to\_k(t\_2a\_lh\_f)  
        t\_2a\_ctr\_k \= f\_to\_k(t\_2a\_ctr\_f)  
        t\_2a\_rh\_k \= f\_to\_k(t\_2a\_rh\_f)  
        t\_2b\_k \= f\_to\_k(t\_2b\_f)

        t\_4b\_lh\_k \= f\_to\_k(t\_4b\_lh\_f)  
        t\_4b\_ctr\_k \= f\_to\_k(t\_4b\_ctr\_f)  
        t\_4b\_rh\_k \= f\_to\_k(t\_4b\_rh\_f)

        \# 3\. Get Saturation Temps  
        t\_sat\_suc\_k \= CP.PropsSI('T', 'P', p\_suc\_pa, 'Q', 0, refrigerant)  
        t\_sat\_disch\_k \= CP.PropsSI('T', 'P', p\_disch\_pa, 'Q', 0, refrigerant)

        \# 4\. Get Enthalpy, Density, etc. for all points  
        \# Example for "At compressor inlet" section  
        h\_2b \= CP.PropsSI('H', 'T', t\_2b\_k, 'P', p\_suc\_pa, refrigerant)  
        s\_2b \= CP.PropsSI('S', 'T', t\_2b\_k, 'P', p\_suc\_pa, refrigerant)  
        rho\_2b\_kg\_m3 \= CP.PropsSI('D', 'T', t\_2b\_k, 'P', p\_suc\_pa, refrigerant)

        \# Example for "AT LH coil" section  
        h\_2a\_lh \= CP.PropsSI('H', 'T', t\_2a\_lh\_k, 'P', p\_suc\_pa, refrigerant)  
        \# ... calculate h\_1a\_lh, h\_1b\_lh, etc. ...

        \# Example for "At TXV LH" section  
        h\_4b\_lh \= CP.PropsSI('H', 'T', t\_4b\_lh\_k, 'P', p\_disch\_pa, refrigerant)

        \# ... Repeat for ALL points (LH, CTR, RH, Condenser, etc.) ...

        \# 5\. Store all calculated values in the results dict  
        \# These keys MUST match your Calculations-DDT.csv 3rd row  
        results\['T\_sat.lh'\] \= t\_sat\_suc\_k \- 273.15 \# Convert to C or F as needed  
        results\['S.H\_lh coil'\] \= t\_2a\_lh\_k \- t\_sat\_suc\_k  
        results\['H\_coil lh'\] \= h\_2a\_lh / 1000 \# to kJ/kg

        results\['Press.suc'\] \= p\_suc\_psig  
        results\['Comp.in'\] \= t\_2b\_f  
        results\['T saturation'\] \= t\_sat\_suc\_k \- 273.15  
        results\['Super heat'\] \= t\_2b\_k \- t\_sat\_suc\_k  
        results\['Density'\] \= rho\_2b\_kg\_m3  
        results\['Enthalpy'\] \= h\_2b / 1000  
        results\['Entropy'\] \= s\_2b / 1000

        results\['TXV in-LH'\] \= t\_4b\_lh\_f  
        results\['T\_Saturation'\] \= t\_sat\_disch\_k \- 273.15  
        results\['Subcooling'\] \= t\_sat\_disch\_k \- t\_4b\_lh\_k  
        results\['Enthalpy\_txv\_lh'\] \= h\_4b\_lh / 1000 \# Note: Need unique keys

        \# ... Populate ALL other columns from your CSV ...

        \# 6\. Calculate Final Performance (Step 2 Logic)  
        if rho\_2b\_kg\_m3 \> 0 and eta\_vol \> 0:  
            disp\_m3 \= comp\_specs.get('displacement\_m3', 0\)  
            mass\_flow\_kgs \= rho\_2b\_kg\_m3 \* eta\_vol \* disp\_m3 \* (rpm / 60\)

            \# Average enthalpy at TXV inlet  
            h\_4b\_avg \= np.mean(\[  
                CP.PropsSI('H', 'T', t\_4b\_lh\_k, 'P', p\_disch\_pa, refrigerant),  
                CP.PropsSI('H', 'T', t\_4b\_ctr\_k, 'P', p\_disch\_pa, refrigerant),  
                CP.PropsSI('H', 'T', t\_4b\_rh\_k, 'P', p\_disch\_pa, refrigerant)  
            \])

            \# Cooling cap in Watts  
            cooling\_cap\_w \= mass\_flow\_kgs \* (h\_2b \- h\_4b\_avg)

            results\['Mass flow rate'\] \= mass\_flow\_kgs \* 2.20462 \* 3600 \# to lb/hr  
            results\['Cooling cap'\] \= cooling\_cap\_w \* 3.41214 \# to BTU/hr

        return pd.Series(results)

    except Exception as e:  
        print(f"Error processing row: {e}")  
        return pd.Series(results) \# Return partial results

2. **Modify calculation\_orchestrator.py:**  
   * Create the new orchestrator function that maps sensors and applies the engine function.

\# In calculation\_orchestrator.py  
import pandas as pd  
from port\_resolver import resolve\_mapped\_sensor  
from calculation\_engine import calculate\_row\_performance, calculate\_volumetric\_efficiency, f\_to\_k, psig\_to\_pa, ft3\_to\_m3

\# This is the master list of all roles needed for the new calculation  
\# The key is the internal name, the value is a list of (ComponentType, PortName)  
\# This is a \*simplified\* example. You must build this from Calculations-DDT.txt  
REQUIRED\_SENSOR\_ROLES \= {  
    'P\_suc': \[('Compressor', 'SP')\],  
    'P\_disch': \[('Compressor', 'DP')\],  
    'RPM': \[('Compressor', 'RPM')\],  
    'T\_2b': \[('Compressor', 'inlet')\],  
    'T\_2a-LH': \[('Evaporator', 'outlet\_circuit\_1', {'circuit\_label': 'Left'})\],  
    'T\_2a-ctr': \[('Evaporator', 'outlet\_circuit\_1', {'circuit\_label': 'Center'})\],  
    'T\_2a-RH': \[('Evaporator', 'outlet\_circuit\_1', {'circuit\_label': 'Right'})\],  
    'T\_4b-lh': \[('TXV', 'inlet', {'circuit\_label': 'Left'})\],  
    'T\_4b-ctr': \[('TXV', 'inlet', {'circuit\_label': 'Center'})\],  
    'T\_4b-rh': \[('TXV', 'inlet', {'circuit\_label': 'Right'})\],  
    \# ... YOU MUST COMPLETE THIS LIST FOR ALL SENSORS IN Calculations-DDT.txt ...  
}

def \_find\_sensor\_for\_role(model, role\_def):  
    """Helper to find the first mapped sensor for a given role definition."""  
    components \= model.get('components', {})  
    for comp\_id, comp in components.items():  
        comp\_type \= comp.get('type')  
        props \= comp.get('properties', {})

        role\_comp\_type \= role\_def\[0\]  
        role\_port \= role\_def\[1\]  
        role\_props \= role\_def\[2\] if len(role\_def) \> 2 else {}

        if comp\_type \!= role\_comp\_type:  
            continue

        \# Check if properties match (e.g., circuit\_label)  
        props\_match \= True  
        if role\_props:  
            for key, val in role\_props.items():  
                if props.get(key) \!= val:  
                    props\_match \= False  
                    break

        if props\_match:  
            sensor \= resolve\_mapped\_sensor(model, comp\_type, comp\_id, role\_port)  
            if sensor:  
                return sensor  
    return None

def run\_batch\_processing(data\_manager, input\_dataframe: pd.DataFrame) \-\> pd.DataFrame:  
    """  
    The new main entry point for the "Calculations" tab.  
    Replaces coolprop\_calculator.py  
    """

    \# 1\. Get Rated Inputs and Diagram Model  
    rated\_inputs \= data\_manager.rated\_inputs  
    diagram\_model \= data\_manager.diagram\_model

    \# 2\. Get "Step 1" eta\_vol  
    eta\_vol\_results \= calculate\_volumetric\_efficiency(rated\_inputs)  
    if 'error' in eta\_vol\_results:  
        print(f"Error in Step 1: {eta\_vol\_results\['error'\]}")  
        return pd.DataFrame() \# Return empty  
    eta\_vol \= eta\_vol\_results.get('eta\_vol', 0\)

    \# 3\. Get Compressor Specs  
    comp\_specs \= gather\_compressor\_specs(data\_manager) \# You already have this function  
    \# Convert displacement from user input (ft³) to m³ for the engine  
    rated\_disp\_ft3 \= rated\_inputs.get('rated\_displacement\_ft3', 0\)  
    comp\_specs\['displacement\_m3'\] \= ft3\_to\_m3(rated\_disp\_ft3)

    \# 4\. Build the Sensor Name Map  
    sensor\_map \= {}  
    for key, role\_defs in REQUIRED\_SENSOR\_ROLES.items():  
        for role\_def in role\_defs:  
            sensor\_name \= \_find\_sensor\_for\_role(diagram\_model, role\_def)  
            if sensor\_name:  
                sensor\_map\[key\] \= sensor\_name  
                break \# Found it  
        if key not in sensor\_map:  
            print(f"Warning: No sensor mapped for required role '{key}'")

    print(f"Sensor Map: {sensor\_map}")

    \# 5\. Run "Step 2" (Row-by-Row)  
    results\_df \= input\_dataframe.apply(  
        calculate\_row\_performance,  
        axis=1,  
        sensor\_map=sensor\_map,  
        eta\_vol=eta\_vol,  
        comp\_specs=comp\_specs  
    )

    return results\_df

### **Step 4: Refactor the "Calculations" Tab UI (calculations\_widget.py)**

This file needs a major overhaul to replace its QTableWidget with a QTreeWidget and implement the nested header.

\# In calculations\_widget.py  
\# \--- This is a conceptual rewrite \---

import sys  
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTreeWidget,   
                             QTreeWidgetItem, QHeaderView)  
from PyQt6.QtCore import Qt  
from PyQt6.QtGui import QPainter, QFontMetrics

\# \--- Custom Header Class \---  
class NestedHeaderView(QHeaderView):  
    """  
    A custom QHeaderView that draws nested headers  
    based on the layout in Calculations-DDT.xlsx  
    """  
    def \_\_init\_\_(self, parent=None):  
        super().\_\_init\_\_(Qt.Orientation.Horizontal, parent)  
        self.setStretchLastSection(True)  
          
        \# Define the nested header structure  
        \# (Top Label, Column Span)  
        self.groups \= \[  
            ("AT LH coil", 8),  
            ("AT CTR coil", 8),  
            ("AT RH coil", 8),  
            ("At compressor inlet", 7),  
            ("Comp outlet", 2),  
            ("At Condenser", 7),  
            ("At TXV LH", 4),  
            ("At TXV CTR", 4),  
            ("At TXV RH", 4),  
            ("TOTAL", 2\)  
        \]  
          
        \# Define the sub-header labels (Row 2 from CSV)  
        self.sub\_headers \= \[  
            \# LH Coil  
            "TXV out", "Coil in", "Coil out", "T saturation", "Super heat", "Density", "Enthalpy", "Entropy",  
            \# CTR Coil  
            "TXV out", "Coil in", "Coil out", "T saturation", "Super heat", "Density", "Enthalpy", "Entropy",  
            \# RH Coil  
            "TXV out", "Coil in", "Coil out", "T saturation", "Super heat", "Density", "Enthalpy", "Entropy",  
            \# Compressor Inlet  
            "Press.suc", "Comp.in", "T saturation", "Super heat", "Density", "Enthalpy", "Entropy",  
            \# Comp Outlet  
            "T comp outlet", "Comp. rpm",  
            \# Condenser  
            "T cond inlet", "Press disch", "T cond. Outlet", "T saturation", "Sub cooling", "Cond.water.in", "Cond.water.out",  
            \# TXV LH  
            "TXV in-LH", "T\_Saturation", "Subcooling", "Enthalpy",  
            \# TXV CTR  
            "TXV in-CTR", "T\_Saturation", "Subcooling", "Enthalpy",  
            \# TXV RH  
            "TXV in-LH", "T\_Saturation", "Subcooling", "Enthalpy", \# Note: CSV says TXV in-LH, probably a typo?  
            \# TOTAL  
            "Mass flow rate", "Cooling cap"  
        \]  
          
        \# Define the data keys (Row 3 from CSV)  
        \# This is the crucial link to the DataFrame  
        self.data\_keys \= \[  
            'T\_1a-lh', 'T\_1b-lh', 'T\_2a-LH', 'T\_sat.lh', 'S.H\_lh coil', 'D\_coil lh', 'H\_coil lh', 'S\_coil lh',  
            'T\_1a-ctr', 'T\_1b-ctr', 'T\_2a-ctr', 'T\_sat.ctr', 'S.H\_ctr coil', 'D\_coil ctr', 'H\_coil ctr', 'S\_coil ctr',  
            'T\_1a-rh', 'T\_1c-rh', 'T\_2a-RH', 'T\_sat.rh', 'S.H\_rh coil', 'D\_coil rh', 'H\_coil rh', 'S\_coil rh',  
            'Press.suc', 'Comp.in', 'T saturation', 'Super heat', 'Density', 'Enthalpy', 'Entropy',  
            'T comp outlet', 'Comp. rpm',  
            'T cond inlet', 'Press disch', 'T cond. Outlet', 'T\_sat\_cond', 'Sub cooling\_cond', 'Cond.water.in', 'Cond.water.out',  
            'TXV in-LH', 'T\_Saturation\_txv\_lh', 'Subcooling\_txv\_lh', 'Enthalpy\_txv\_lh',  
            'TXV in-CTR', 'T\_Saturation\_txv\_ctr', 'Subcooling\_txv\_ctr', 'Enthalpy\_txv\_ctr',  
            'TXV in-RH', 'T\_Saturation\_txv\_rh', 'Subcooling\_txv\_rh', 'Enthalpy\_txv\_rh', \# Corrected key  
            'Mass flow rate', 'Cooling cap'  
        \]

    def paintEvent(self, event):  
        \# Draw the base header (sub-headers)  
        super().paintEvent(event)  
          
        painter \= QPainter(self)  
        painter.save()  
          
        \# Set font for group headers  
        font \= self.font()  
        font.setBold(True)  
        painter.setFont(font)  
          
        col\_index \= 0  
        for text, span in self.groups:  
            if span \== 0:  
                continue  
              
            \# Get rectangle for this group  
            first\_col\_rect \= self.sectionViewportPosition(col\_index)  
            last\_col\_rect \= self.sectionViewportPosition(col\_index \+ span \- 1\)  
              
            group\_width \= (last\_col\_rect \+ self.sectionSize(col\_index \+ span \- 1)) \- first\_col\_rect  
            group\_rect \= self.rect()  
            group\_rect.setLeft(first\_col\_rect)  
            group\_rect.setWidth(group\_width)  
            group\_rect.setHeight(self.height() // 2\) \# Top half  
              
            \# Draw border  
            painter.drawRect(group\_rect.adjusted(0, 0, \-1, \-1))  
              
            \# Draw text  
            painter.drawText(group\_rect, Qt.AlignmentFlag.AlignCenter, text)  
              
            col\_index \+= span  
              
        painter.restore()

    def sizeHint(self):  
        size \= super().sizeHint()  
        \# Double the height to make space for the nested groups  
        size.setHeight(size.height() \* 2\)  
        return size

\# \--- Main Widget \---  
class CalculationsWidget(QWidget):  
    \# This signal now sends the new, processed DataFrame  
    filtered\_data\_ready \= pyqtSignal(object) 

    def \_\_init\_\_(self, data\_manager, parent=None):  
        super().\_\_init\_\_(parent)  
        self.data\_manager \= data\_manager  
          
        layout \= QVBoxLayout(self)  
          
        self.run\_button \= QPushButton("Run Full Calculation")  
        self.run\_button.clicked.connect(self.run\_calculation)  
        layout.addWidget(self.run\_button)  
          
        self.tree\_widget \= QTreeWidget()  
        self.header \= NestedHeaderView(self.tree\_widget)  
        self.tree\_widget.setHeader(self.header)  
          
        \# Set the bottom-row (sub-header) labels  
        self.tree\_widget.setHeaderLabels(self.header.sub\_headers)  
          
        layout.addWidget(self.tree\_widget)  
          
    def run\_calculation(self):  
        self.run\_button.setText("Calculating...")  
        self.run\_button.setEnabled(False)  
        QApplication.processEvents() \# Allow UI to update  
          
        try:  
            \# 1\. Get filtered data  
            input\_df \= self.data\_manager.get\_filtered\_data()  
            if input\_df is None or input\_df.empty:  
                print("No data to process.")  
                return

            \# 2\. Call the NEW orchestrator function  
            \# This is the new, flexible, row-by-row engine  
            from calculation\_orchestrator import run\_batch\_processing  
            processed\_df \= run\_batch\_processing(self.data\_manager, input\_df)

            \# 3\. Populate the tree  
            self.populate\_tree(processed\_df)  
              
            \# 4\. Emit signal for P-h Diagram  
            self.filtered\_data\_ready.emit(processed\_df)  
              
        except Exception as e:  
            print(f"Error during calculation: {e}")  
        finally:  
            self.run\_button.setText("Run Full Calculation")  
            self.run\_button.setEnabled(True)

    def populate\_tree(self, df):  
        self.tree\_widget.clear()  
          
        \# Get the data keys from the header  
        data\_keys \= self.header.data\_keys  
          
        items \= \[\]  
        for index, row in df.iterrows():  
            row\_data \= \[\]  
            for key in data\_keys:  
                val \= row.get(key)  
                if isinstance(val, (int, float)):  
                    row\_data.append(f"{val:.2f}") \# Format numbers  
                else:  
                    row\_data.append(str(val) if val is not None else "---")  
              
            item \= QTreeWidgetItem(row\_data)  
            items.append(item)  
              
        self.tree\_widget.addTopLevelItems(items)  
          
        \# Resize columns after adding data  
        for i in range(len(data\_keys)):  
            self.tree\_widget.resizeColumnToContents(i)

### **Step 5: Update "P-h Interactive" Tab (ph\_diagram\_widget.py)**

1. **Modify load\_filtered\_data:** This function in ph\_diagram\_widget.py will now receive the *new* DataFrame.  
2. **Modify ph\_diagram\_plotter.py:** Update its plotting logic to read the new columns as specified in ph diagram-DDT.txt and your new CSV layout.  
   * P\_disch is now row\['Press disch'\] (or its \_pa conversion).  
   * P\_suction is now row\['Press.suc'\] (or its \_pa conversion).  
   * The 3 subcooling enthalpies are row\['Enthalpy\_txv\_lh'\], row\['Enthalpy\_txv\_ctr'\], row\['Enthalpy\_txv\_rh'\].  
   * The 3 superheat enthalpies are row\['H\_coil lh'\], row\['H\_coil ctr'\], row\['H\_coil rh'\].  
   * The compressor inlet enthalpy is row\['Enthalpy'\] (from the "At compressor inlet" group).  
   * The plotter must be modified to average these columns and draw all 7+ state points as requested.