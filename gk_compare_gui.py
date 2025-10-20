import os
import difflib
from gpt4all import GPT4All
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

# ============================
# Paths
# ============================
BASE_DIR = r"C:\Users\105393\OneDrive - Dis-Chem Pharmacies\Documents\GK_Version_compare"
MODEL_PATH = os.path.join(BASE_DIR, "models", "Meta-Llama-3-8B-Instruct.Q4_1.gguf")
OLD_FOLDER = os.path.join(BASE_DIR, "data", "version_1")
NEW_FOLDER = os.path.join(BASE_DIR, "data", "version_2")
REPORTS_FOLDER = os.path.join(BASE_DIR, "results", "reports")
os.makedirs(REPORTS_FOLDER, exist_ok=True)

REPORT_FILE = os.path.join(REPORTS_FOLDER, "side_by_side_report_paginated.pdf")

# ============================
# Load GPT4All
# ============================
print("🔄 Loading GPT4All model...")
model = GPT4All(MODEL_PATH)  # CPU-only
print("✅ Model loaded successfully!")

# ============================
# Compare Files Side by Side
# ============================
def compare_files(file1, file2):
    """Return only the differences between old and new files for PDF."""
    with open(file1, 'r', encoding='utf-8') as f1, open(file2, 'r', encoding='utf-8') as f2:
        text1 = f1.readlines()
        text2 = f2.readlines()

    diff = list(difflib.ndiff(text1, text2))
    old_lines, new_lines, old_types, new_types = [], [], [], []

    for line in diff:
        code = line[:2]
        content = line[2:].rstrip()
        if code == '- ':
            old_lines.append(content)
            new_lines.append('')
            old_types.append('removed')
            new_types.append('unchanged')
        elif code == '+ ':
            old_lines.append('')
            new_lines.append(content)
            old_types.append('unchanged')
            new_types.append('added')
        # skip unchanged lines entirely
    return old_lines, new_lines, old_types, new_types

# ============================
# Summarize Diff
# ============================
def summarize_diff(diff_text, filename):
    diff_lines = [line for line in diff_text.splitlines() if line.startswith('+') or line.startswith('-')]
    diff_snippet = "\n".join(diff_lines)[:4000]

    if not diff_snippet:
        return f"No significant changes detected in {filename}."

    prompt = f"""
Summarize the following differences in GK Software file '{filename}'.
Explain what changed and why it might matter:

{diff_snippet}
""".strip()

    with model.chat_session():
        response = model.generate(prompt, max_tokens=300).strip()
    return response

# ============================
# Build table in pages
# ============================
def build_table_pages(old_lines, new_lines, old_types, new_types, max_rows=40):
    """Split long tables into pages with max_rows per table."""
    pages = []
    headers = [['OLD VERSION', 'NEW VERSION']]

    for i in range(0, len(old_lines), max_rows):
        chunk_old = old_lines[i:i+max_rows]
        chunk_new = new_lines[i:i+max_rows]
        chunk_old_types = old_types[i:i+max_rows]
        chunk_new_types = new_types[i:i+max_rows]

        data = headers + list(zip(chunk_old, chunk_new))
        table = Table(data, colWidths=[270, 270])
        style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN',(0,0),(-1,-1),'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('GRID', (0,0), (-1,-1), 0.25, colors.black),
        ])

        for idx, (o_type, n_type) in enumerate(zip(chunk_old_types, chunk_new_types), start=1):
            if o_type == 'removed':
                style.add('TEXTCOLOR', (0,idx), (0,idx), colors.red)
            if n_type == 'added':
                style.add('TEXTCOLOR', (1,idx), (1,idx), colors.green)

        table.setStyle(style)
        pages.append(table)
    return pages

# ============================
# Main Execution
# ============================
old_files = {f.lower(): f for f in os.listdir(OLD_FOLDER) if f.lower().endswith(".xml")}
new_files = {f.lower(): f for f in os.listdir(NEW_FOLDER) if f.lower().endswith(".xml")}
common_files = set(old_files.keys()).intersection(set(new_files.keys()))

if not common_files:
    print("❌ No matching XML files found in both folders.")
else:
    doc = SimpleDocTemplate(REPORT_FILE, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    for fname_lower in common_files:
        file_old = os.path.join(OLD_FOLDER, old_files[fname_lower])
        file_new = os.path.join(NEW_FOLDER, new_files[fname_lower])

        print(f"\n🔍 Comparing file: {old_files[fname_lower]}")
        old_lines, new_lines, old_types, new_types = compare_files(file_old, file_new)

        # Summarize diff
        diff_text = '\n'.join([f"- {l}" for l in old_lines if l]) + '\n' + '\n'.join([f"+ {l}" for l in new_lines if l])
        summary = summarize_diff(diff_text, old_files[fname_lower])

        # Add file heading & summary
        elements.append(Paragraph(f"<b>{old_files[fname_lower]}</b>", styles['Heading2']))
        elements.append(Paragraph(f"<i>{summary}</i>", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Build tables with pagination
        table_pages = build_table_pages(old_lines, new_lines, old_types, new_types, max_rows=40)
        for table in table_pages:
            elements.append(table)
            elements.append(PageBreak())  # new page per chunk

    doc.build(elements)
    print(f"\n💾 Side-by-side PDF with highlights and pagination saved to: {REPORT_FILE}")
