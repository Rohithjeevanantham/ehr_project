import plotly.graph_objects as go
import pandas as pd
import plotly.io as pio

# Medical tests categories and acceptable ranges (as defined earlier)
medical_tests = {
    'Complete Blood Count': ['WBC', 'RBC', 'Hemoglobin', 'Platelets'],
    'Urine Routine': ['pH', 'Protein', 'Glucose'],
    'Liver Function Test': ['ALT', 'AST', 'Bilirubin'],
    'Renal Function Test': ['Creatinine', 'Urea', 'Electrolytes'],
    'Diabetic Profile': ['Fasting Blood Sugar', 'Postprandial Blood Sugar', 'HbA1c'],
    'Thyroid Function Test': ['TSH', 'T3', 'T4'],
    'Lipid Profile': ['Cholesterol', 'Triglycerides', 'HDL', 'LDL']
}

acceptable_ranges = {
    'WBC': (4.0, 11.0),
    'RBC': (4.7, 6.1),
    'Hemoglobin': (13.8, 17.2),
    'Platelets': (150, 450),
    'pH': (4.5, 8.0),
    'Protein': (0, 0.2),
    'Glucose': (0, 0.8),
    'ALT': (7, 56),
    'AST': (10, 40),
    'Bilirubin': (0.1, 1.2),
    'Creatinine': (0.6, 1.2),
    'Urea': (7, 20),
    'Electrolytes': (135, 145),
    'Fasting Blood Sugar': (70, 100),
    'Postprandial Blood Sugar': (70, 140),
    'HbA1c': (4.0, 5.6),
    'TSH': (0.4, 4.0),
    'T3': (80, 200),
    'T4': (4.5, 11.2),
    'Cholesterol': (125, 200),
    'Triglycerides': (0, 150),
    'HDL': (40, 60),
    'LDL': (0, 100)
}

def generate_lab_plots(ehr):
    """
    Generate a Plotly graph for each defined test by aggregating data
    from all patient reports.
    The function is robust and uses a case-insensitive containment check.
    Returns a list of HTML div strings.
    """
    charts = []
    for category, tests in medical_tests.items():
        for test in tests:
            dates = []
            values = []
            # Loop through each report in the aggregated EHR record.
            for report in ehr.get("Reports", []):
                report_date = report.get("Report Generated On")
                if report_date:
                    try:
                        date_parsed = pd.to_datetime(report_date)
                    except:
                        continue
                else:
                    continue
                # For each lab result, if the category matches...
                for lab_result in report.get("Lab Results", []):
                    if lab_result.get("Test Category") == category:
                        # Check each test component.
                        for comp in lab_result.get("Test Components", []):
                            found = False
                            # Check each subtest.
                            for sub in comp.get("SubTests", []):
                                # Use a case-insensitive check if test is in parameter.
                                if test.lower() in sub.get("Parameter", "").lower():
                                    try:
                                        value = float(sub.get("Value"))
                                    except:
                                        value = None
                                    if value is not None:
                                        dates.append(date_parsed)
                                        values.append(value)
                                        found = True
                                        break
                            # Fallback: if no subtest found but component directly has a "Value"
                            if not found and comp.get("Value"):
                                try:
                                    value = float(comp.get("Value"))
                                except:
                                    value = None
                                if value is not None:
                                    dates.append(date_parsed)
                                    values.append(value)
            if dates and values:
                df = pd.DataFrame({"Date": dates, test: values})
                df.sort_values("Date", inplace=True)
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['Date'], y=df[test], mode='lines+markers', name=test))
                if test in acceptable_ranges:
                    lower_bound, upper_bound = acceptable_ranges[test]
                    fig.add_shape(type="line", x0=df['Date'].min(), x1=df['Date'].max(),
                                  y0=lower_bound, y1=lower_bound, line=dict(color="green", dash="dash"))
                    fig.add_shape(type="line", x0=df['Date'].min(), x1=df['Date'].max(),
                                  y0=upper_bound, y1=upper_bound, line=dict(color="red", dash="dash"))
                fig.update_layout(
                    title=f"{test} Levels Over Time",
                    xaxis_title="Date",
                    yaxis_title=f"{test} Value",
                    template="plotly_dark"
                )
                chart_html = pio.to_html(fig, include_plotlyjs=False, full_html=False)
                charts.append(chart_html)
    return charts
