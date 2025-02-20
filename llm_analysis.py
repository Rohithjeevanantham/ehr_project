import cohere
import json

# You may reuse your API keys or configure a dedicated one.
COHERE_API_KEY = "RBOlmQ7eZaKsnY2dvR6tNquLQ7eICYzOrcSGlCM2"  # Replace with your key

def analyze_patient_report(ehr):
    """
    Generate a Markdown‑formatted analysis for the aggregated patient EHR.
    Aggregates all lab results and report notes from all reports.
    """
    client = cohere.Client(COHERE_API_KEY)
    aggregated_text = ""
    reports = ehr.get("Reports", [])
    if not reports:
        aggregated_text = "No reports available."
    else:
        for report in reports:
            date = report.get("Report Generated On", "Unknown Date")
            aggregated_text += f"**Report Date:** {date}\n\n"
            for test in report.get("Lab Results", []):
                category = test.get("Test Category", "Unknown Category")
                aggregated_text += f"- **Test Category:** {category}\n"
                for comp in test.get("Test Components", []):
                    comp_name = comp.get("Name", "Unnamed Test")
                    aggregated_text += f"  - **{comp_name}:** "
                    subs = comp.get("SubTests", [])
                    if subs:
                        sub_details = []
                        for sub in subs:
                            param = sub.get("Parameter", "N/A")
                            value = sub.get("Value", "N/A")
                            unit = sub.get("Unit", "")
                            ref = sub.get("Reference Range", "")
                            sub_details.append(f"{param} = {value} {unit} (Ref: {ref})")
                        aggregated_text += "; ".join(sub_details) + "\n"
                    else:
                        aggregated_text += "No subtests available.\n"
            # Append report notes.
            notes = report.get("Report Notes", {})
            for key, note_list in notes.items():
                if note_list:
                    aggregated_text += f"- **{key}:** " + "; ".join(note_list) + "\n"
            aggregated_text += "\n"
    
    prompt = f"""You are a highly experienced medical data analyst. Based on the following aggregated patient lab report data in Markdown, provide a concise, bullet‐point analysis.
Your analysis should include:
- Summary of trends across the reports.
- Identification of abnormal values or anomalies.
- Diagnostic insights and recommendations.
Keep your analysis under 250 words. Format your response in Markdown.
    
Patient Data:
{aggregated_text}
"""
    try:
        response = client.chat(
            model="command-r",
            message=f"System: {prompt}\nUser: Provide analysis in Markdown.",
            max_tokens=300,
            temperature=0.2,
        )
        analysis_text = response.text.strip()
        if not analysis_text:
            analysis_text = "No analysis could be generated."
    except Exception as e:
        analysis_text = f"Error generating analysis: {str(e)}"
    
    return analysis_text

def stream_analysis(patient_ehr):
    """
    Stream the analysis response as SSE (Server Sent Events).
    Splits the final analysis into lines and yields each line as an SSE event.
    """
    analysis_text = analyze_patient_report(patient_ehr)
    # Split into lines.
    for line in analysis_text.splitlines():
        yield f"data: {line}\n\n"
