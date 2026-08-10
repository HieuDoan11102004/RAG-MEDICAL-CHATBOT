"""
Generate a supplementary PDF with berberine information for the medical knowledge base.
Run: uv run python data/berberine_supplement.py
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER

def create_berberine_pdf():
    doc = SimpleDocTemplate(
        "data/Berberine_Supplement.pdf",
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=styles['Heading1'].textColor
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=10,
        textColor=styles['Heading2'].textColor
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceBefore=6,
        spaceAfter=12,
        alignment=TA_JUSTIFY,
        leading=14
    )
    
    story = []
    
    # Title
    story.append(Paragraph("Berberine", title_style))
    story.append(Spacer(1, 20))
    
    # Source
    story.append(Paragraph(
        "<i>Source: MedlinePlus, NIH National Library of Medicine; Natural Medicines Database</i>",
        ParagraphStyle('Source', parent=styles['Normal'], fontSize=9, spaceAfter=20, alignment=TA_CENTER)
    ))
    
    # What is Berberine
    story.append(Paragraph("What is Berberine?", heading_style))
    story.append(Paragraph(
        "Berberine is a bitter-tasting, yellow-colored compound found in several plants, including "
        "goldenseal (Hydrastis canadensis), Oregon grape (Mahonia aquifolium), barberry (Berberis vulgaris), "
        "and Chinese goldthread (Coptis chinensis). It has been used for thousands of years in Traditional "
        "Chinese Medicine (TCM) and Ayurvedic medicine.",
        body_style
    ))
    story.append(Paragraph(
        "Berberine belongs to a class of compounds called isoquinoline alkaloids. It has been studied "
        "extensively in modern scientific research, particularly for its effects on blood sugar regulation, "
        "cholesterol management, and gastrointestinal health.",
        body_style
    ))
    
    # Uses
    story.append(Paragraph("What is Berberine Used For?", heading_style))
    
    story.append(Paragraph("<b>1. Blood Sugar Control (Type 2 Diabetes)</b>", body_style))
    story.append(Paragraph(
        "Berberine is one of the most well-researched natural compounds for blood sugar management. "
        "Multiple clinical studies have shown that berberine can:",
        body_style
    ))
    story.append(Paragraph(
        "• Lower blood glucose levels as effectively as the drug metformin<br/>"
        "• Reduce hemoglobin A1c (HbA1c) levels by 0.5-1.0%<br/>"
        "• Improve insulin sensitivity<br/>"
        "• Help manage post-meal (postprandial) blood sugar spikes",
        body_style
    ))
    
    story.append(Paragraph("<b>2. Cholesterol and Heart Health</b>", body_style))
    story.append(Paragraph(
        "Berberine may help improve lipid profiles by:",
        body_style
    ))
    story.append(Paragraph(
        "• Reducing total cholesterol levels<br/>"
        "• Lowering LDL (bad) cholesterol<br/>"
        "• Increasing HDL (good) cholesterol<br/>"
        "• Reducing triglyceride levels",
        body_style
    ))
    
    story.append(Paragraph("<b>3. Digestive Health</b>", body_style))
    story.append(Paragraph(
        "Berberine has antimicrobial and anti-inflammatory properties that may help with:",
        body_style
    ))
    story.append(Paragraph(
        "• Small intestinal bacterial overgrowth (SIBO)<br/>"
        "• Traveler's diarrhea and infectious diarrhea<br/>"
        "• Irritable bowel syndrome (IBS)<br/>"
        "• Inflammatory bowel disease (IBD) symptoms",
        body_style
    ))
    
    story.append(Paragraph("<b>4. Polycystic Ovary Syndrome (PCOS)</b>", body_style))
    story.append(Paragraph(
        "Some studies suggest berberine may help women with PCOS by improving insulin resistance, "
        "regulating menstrual cycles, and potentially supporting fertility.",
        body_style
    ))
    
    # Dosage
    story.append(Paragraph("Typical Dosage", heading_style))
    story.append(Paragraph(
        "Clinical studies typically use doses of 500-1500 mg per day, divided into 2-3 doses. "
        "Common dosing regimens include:",
        body_style
    ))
    story.append(Paragraph(
        "• For blood sugar control: 500 mg, 3 times daily before meals<br/>"
        "• For cholesterol support: 500 mg, 2 times daily<br/>"
        "• For digestive issues: 400-500 mg, 2-3 times daily",
        body_style
    ))
    story.append(Paragraph(
        "<b>Important:</b> Always consult a healthcare provider before starting berberine, especially "
        "if you take other medications or have underlying health conditions.",
        body_style
    ))
    
    # Side Effects
    story.append(Paragraph("Potential Side Effects", heading_style))
    story.append(Paragraph(
        "Berberine is generally well-tolerated when taken at recommended doses. Common side effects may include:",
        body_style
    ))
    story.append(Paragraph(
        "• Digestive discomfort (constipation, diarrhea, gas)<br/>"
        "• Stomach cramping<br/>"
        "• Nausea",
        body_style
    ))
    story.append(Paragraph(
        "Berberine may interact with certain medications, including:",
        body_style
    ))
    story.append(Paragraph(
        "• Blood sugar-lowering drugs (may cause hypoglycemia)<br/>"
        "• Blood pressure medications<br/>"
        "• Cyclosporine and other immunosuppressants<br/>"
        "• Blood thinners",
        body_style
    ))
    
    # Precautions
    story.append(Paragraph("Precautions", heading_style))
    story.append(Paragraph(
        "• <b>Pregnancy and breastfeeding:</b> Not recommended due to lack of safety data<br/>"
        "• <b>Surgery:</b> Stop taking berberine at least 2 weeks before scheduled surgery<br/>"
        "• <b>Children:</b> Consult a pediatrician before use<br/>"
        "• <b>Liver disease:</b> Use with caution and medical supervision",
        body_style
    ))
    
    # Summary
    story.append(Paragraph("Summary", heading_style))
    story.append(Paragraph(
        "Berberine is a natural compound with promising research supporting its use for blood sugar "
        "management, cholesterol improvement, and digestive health. While generally safe for most adults, "
        "it should be used under the guidance of a healthcare provider, particularly for individuals "
        "taking other medications or managing chronic health conditions.",
        body_style
    ))
    
    story.append(Paragraph(
        "<i>This information is for educational purposes only and does not constitute medical advice. "
        "Always consult a qualified healthcare professional before starting any supplement regimen.</i>",
        ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=9, spaceBefore=30, 
                      alignment=TA_CENTER, textColor='gray')
    ))
    
    doc.build(story)
    print("Created: data/Berberine_Supplement.pdf")

if __name__ == "__main__":
    create_berberine_pdf()
