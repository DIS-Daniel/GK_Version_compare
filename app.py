# app.py
import os
import difflib
import tempfile
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

st.set_page_config(page_title="GK XML Comparison", layout="wide")

# ----------------------------
# Optional GPT4All setup (disabled by default)
# ----------------------------
show_gpt_summary = st.checkbox("Generate GPT Summary (CPU-intensive)", value=False)

try:
    if show_gpt_summary:
        from gpt4all import GPT4All
        MODEL_FILE = "Meta-Llama-3-8B-Instruct.Q4_0.gguf"
        MODEL_DIR = "models"
        MODEL_PATH = os.path.join(MODEL_DIR, MODEL_FILE)
        os.makedirs(MODEL_DIR, exist_ok=True)

        if not os.path.exists(MODEL_PATH):
            st.warning("GPT4All model not found. GPT summary will be skipped.")
            show_gpt_summary = False
        else:
            with st.spinner("Loading GPT4All model (CPU)..."):
                model = GPT4All(MODEL_FILE, model_path=MODEL_DIR)
            st.success("✅ GPT4All model loaded successfully!")
except Exception as e:
    st.warning(f"GPT4All cannot be loaded: {e}")
    show_gpt_summary = False

# ----------------------------
# File upload and comparison
# ----------------------------
st.header("Upload Old and New XML Files")
old_files = st.file_uploader("Old XML files", accept_multiple_files=True, type="xml")
new_files = st.file_uploader("New XML files", accept_multiple_files=True, type="xml")

if old_files and new_files:
    old_files_map = {f.name.lower(): f for f in old_files}
    new_files_map = {f.name.lower(): f for f in new_files}
    common_files = set(old_files_map.keys()).intersection(set(new_files_map.keys()))

    if not common_files:
        st.error("❌ No matching XML filenames found.")
    else:
        st.success(f"✅ Found {len(common_files)} files to compare!")

        old_contents_map = {fname: f.read().decode('utf-8').splitlines() for fname, f in old_files_map.items()}
        new_contents_map = {fname: f.read().decode('utf-8').splitlines() for fname, f in new_files_map.items()}

        diff_map = {}
        context = 2
        for fname in common_files:
            old_content = old_contents_map[fname]
            new_content = new_contents_map[fname]
            diff = list(difflib.ndiff(old_content, new_content))
            change_indices = [i for i, line in enumerate(diff) if line.startswith('- ') or line.startswith('+ ')]
            included_lines = set()
            for idx in change_indices:
                start = max(idx - context, 0)
                end = min(idx + context + 1, len(diff))
                included_lines.update(range(start, end))
            diff_map[fname] = (diff, sorted(included_lines))

        # Display side-by-side
        for fname in common_files:
            st.subheader(f"Comparing: {fname}")
            diff, included_lines = diff_map[fname]
            table_data = [["OLD VERSION", "NEW VERSION"]]

            for i in included_lines:
                line = diff[i]
                if line.startswith('- '):
                    old_cell = f"❌ {line[2:]}"
                    new_cell = ""
                    color_old = "red"
                    color_new = "black"
                elif line.startswith('+ '):
                    old_cell = ""
                    new_cell = f"✅ {line[2:]}"
                    color_old = "black"
                    color_new = "green"
                else:
                    old_cell = new_cell = line[2:]
                    color_old = color_new = "gray"

                table_data.append([
                    f'<font color="{color_old}">{old_cell}</font>',
                    f'<font color="{color_new}">{new_cell}</font>'
                ])

            html_table = "<table style='border-collapse: collapse; width:100%'>"
            html_table += "<tr><th style='border:1px solid black;background-color:#ccc'>OLD VERSION</th>"
            html_table += "<th style='border:1px solid black;background-color:#ccc'>NEW VERSION</th></tr>"

            for row in table_data[1:]:
                html_table += "<tr>"
                for cell in row:
                    html_table += f"<td style='border:1px solid black;padding:2px'>{cell}</td>"
                html_table += "</tr>"
            html_table += "</table>"
            st.markdown(html_table, unsafe_allow_html=True)

            # GPT Summary (optional)
            if show_gpt_summary:
                diff_snippet = "\n".join([diff[i] for i in included_lines if diff[i].startswith('+') or diff[i].startswith('-')])[:4000]
                if diff_snippet:
                    prompt = f"Summarize the following differences in '{fname}':\n{diff_snippet}"
                    try:
                        with model.chat_session():
                            summary = model.generate(prompt, max_tokens=300)
                        st.markdown(f"**GPT Summary:** {summary}")
                    except Exception as e:
                        st.warning(f"GPT summary failed: {e}")

        # PDF report
        if st.button("Generate PDF Report"):
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            doc = SimpleDocTemplate(tmp_file.name, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            cell_style = ParagraphStyle(name='CellStyle', fontSize=8, leading=10, wordWrap='CJK')

            for fname in common_files:
                diff, included_lines = diff_map[fname]
                table_data = [["OLD VERSION", "NEW VERSION"]]

                for i in included_lines:
                    line = diff[i]
                    if line.startswith('- '):
                        old_par = Paragraph(f'<font color="red">{line[2:]}</font>', cell_style)
                        new_par = Paragraph("", cell_style)
                    elif line.startswith('+ '):
                        old_par = Paragraph("", cell_style)
                        new_par = Paragraph(f'<font color="green">{line[2:]}</font>', cell_style)
                    else:
                        old_par = Paragraph(f'<font color="gray">{line[2:]}</font>', cell_style)
                        new_par = Paragraph(f'<font color="gray">{line[2:]}</font>', cell_style)

                    table_data.append([old_par, new_par])

                elements.append(Paragraph(f"<b>{fname}</b>", styles['Heading2']))
                elements.append(Spacer(1, 12))
                t = Table(table_data, colWidths=[270, 270])
                t.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                ]))
                elements.append(t)
                elements.append(PageBreak())

            doc.build(elements)
            st.success("PDF generated!")
            st.download_button("Download PDF", data=open(tmp_file.name, "rb").read(), file_name="comparison_report.pdf")
