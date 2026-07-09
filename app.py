import streamlit as st
import fitz
from groq import Groq
import os
import json
import html
import re
import tempfile
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF

HISTORY_FILE = "resume_history.json"
MAX_HISTORY = 25

st.set_page_config(
    page_title="AI Career Assistant",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { font-family: 'Inter', sans-serif; }
    h1 { font-weight: 700; }
    .subtitle { color: #9ca3af; font-size: 1rem; margin-bottom: 1.5rem; }
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .section-card {
        background-color: #1e1e2e; padding: 18px 20px; border-radius: 12px;
        border: 1px solid #333; margin-bottom: 16px;
        animation: fadeInUp 0.5s ease-out;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .section-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(79, 70, 229, 0.25);
        border-color: #4f46e5;
    }
    .section-title {
        font-size: 1.05rem; font-weight: 700; margin-bottom: 10px;
        display: flex; align-items: center; gap: 8px;
    }
    .skill-tag {
        display: inline-block; background-color: #312e81; color: #c7d2fe;
        padding: 5px 12px; border-radius: 20px; font-size: 0.8rem;
        margin: 3px; font-weight: 500; transition: all 0.2s ease;
    }
    .skill-tag:hover { background-color: #4338ca; transform: scale(1.08); }
    .missing-tag {
        display: inline-block; background-color: #7f1d1d; color: #fecaca;
        padding: 5px 12px; border-radius: 20px; font-size: 0.8rem;
        margin: 3px; font-weight: 500; transition: all 0.2s ease;
    }
    .missing-tag:hover { background-color: #991b1b; transform: scale(1.08); }
    .job-tag {
        display: inline-block; background: linear-gradient(135deg, #059669, #10b981);
        color: white; padding: 7px 16px; border-radius: 20px; font-size: 0.85rem;
        margin: 4px; font-weight: 600; transition: all 0.2s ease;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
    }
    .job-tag:hover { transform: translateY(-2px) scale(1.05); }
    .list-item {
        padding: 8px 0; border-bottom: 1px solid #2a2a3a; font-size: 0.92rem;
    }
    .strength-item { color: #86efac; }
    .weakness-item { color: #fca5a5; }
    .question-item {
        background-color: #262637; padding: 10px 14px; border-radius: 8px;
        margin: 6px 0; font-size: 0.88rem; border-left: 3px solid #4f46e5;
        transition: all 0.2s ease;
    }
    .question-item:hover { border-left-color: #a78bfa; background-color: #2d2d44; padding-left: 18px; }
    .hero-banner {
        background: linear-gradient(135deg, #4f46e5, #7c3aed, #db2777);
        background-size: 200% 200%;
        animation: gradientShift 6s ease infinite;
        padding: 32px; border-radius: 20px; margin-bottom: 24px; text-align: center;
    }
    .hero-title { font-size: 2.2rem; font-weight: 800; color: white; margin: 0; }
    .hero-subtitle { color: rgba(255,255,255,0.9); font-size: 1rem; margin-top: 8px; }
    .history-item {
        background-color: #1e1e2e; padding: 10px 12px; border-radius: 8px;
        margin: 6px 0; border: 1px solid #333; font-size: 0.82rem;
        transition: all 0.2s ease;
    }
    .history-item:hover { border-color: #4f46e5; background-color: #262637; }
    .history-score {
        font-weight: 700; font-size: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def esc(value):
    """Escape any AI-generated or user-provided text before it goes into raw HTML.
    Without this, a resume containing '<', '>' or '&' (e.g. 'C++ & C#', or a
    stray HTML-like string in a skill name) can break layout or inject markup."""
    return html.escape(str(value), quote=False)


def dedent_html(s):
    """Streamlit's markdown renderer treats any line starting with 4+ spaces
    of indentation as a literal code block, not HTML — even inside an
    unsafe_allow_html=True call. Multi-line HTML built from indented
    triple-quoted Python strings trips this every time (that's why the
    Category Breakdown bars were rendering as raw <div> text). Strip
    leading whitespace from every line before it reaches st.markdown."""
    return re.sub(r'(?m)^[ \t]+', '', s)


def md(html_str):
    """Shortcut: dedent then render as HTML."""
    st.markdown(dedent_html(html_str), unsafe_allow_html=True)


def get_groq_key():
    try:
        return st.secrets["GROQ_API_KEY"]
    except Exception:
        return os.environ.get("GROQ_API_KEY")


GROQ_API_KEY = get_groq_key()
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


# ---- Persistence: history ----
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history):
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history[:MAX_HISTORY], f)
    except Exception as e:
        st.warning(f"Couldn't save history: {e}")


def add_to_history(filename, target_role, analysis):
    history = load_history()
    entry = {
        "id": f"{datetime.now().timestamp()}",
        "filename": filename,
        "target_role": target_role or "General",
        "timestamp": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "analysis": analysis
    }
    history.insert(0, entry)
    save_history(history)
    return entry


def delete_history_entry(entry_id):
    history = load_history()
    history = [h for h in history if h["id"] != entry_id]
    save_history(history)


# ---- Backend functions ----
def extract_resume_text(path):
    try:
        doc = fitz.open(path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text.strip()
    except Exception as e:
        st.error(f"Couldn't read that PDF: {e}")
        return ""


def build_prompt(resume_text, target_role):
    role_line = ""
    if target_role:
        role_line = "The candidate is targeting this specific role: " + target_role + \
            ". Tailor the ats_score, missing_skills, recommended_jobs, and interview_questions specifically toward this role.\n\n"

    instructions = """You are an experienced Technical Recruiter and Career Coach with 15 years of experience reviewing resumes for AI/ML, Software Engineering, and Data roles.

""" + role_line + """Analyze the following resume and return ONLY valid JSON. Do not include any text before or after the JSON. Do not use markdown code fences.

The JSON must have exactly this structure:
{
  "summary": "2-3 sentence professional summary of the candidate",
  "technical_skills": ["skill1", "skill2"],
  "soft_skills": ["skill1", "skill2"],
  "education": ["degree - institution - year"],
  "experience": ["role at company - key achievement"],
  "projects": ["project name - brief description"],
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1", "weakness2"],
  "ats_score": 0,
  "missing_skills": ["skill1", "skill2"],
  "recommended_jobs": ["job title 1", "job title 2"],
  "improved_summary": "a rewritten, stronger version of the professional summary",
  "category_scores": {
    "technical_skills": 0,
    "experience": 0,
    "education": 0,
    "projects": 0,
    "presentation": 0
  },
  "interview_questions": {
    "hr_questions": ["question1", "question2"],
    "technical_questions": ["question1", "question2"],
    "coding_questions": ["question1", "question2"]
  }
}

Resume:
"""
    return instructions + resume_text


def analyze_resume(resume_text, target_role):
    if client is None:
        st.error(
            "⚠️ GROQ_API_KEY is not configured. Add it to your Streamlit "
            "secrets (`.streamlit/secrets.toml`) or as an environment variable."
        )
        return None

    if not resume_text:
        st.error("Couldn't extract any text from that PDF — it may be scanned/image-based.")
        return None

    prompt = build_prompt(resume_text, target_role)
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
    except Exception as e:
        st.error(f"Error contacting the AI service: {e}")
        return None

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json", "", 1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        st.error("The AI response wasn't valid JSON. Please try again.")
        return None


def score_color(score):
    if score < 50:
        return "#ef4444"
    elif score < 75:
        return "#f59e0b"
    else:
        return "#10b981"


def render_score_ring(score):
    """Custom circular progress ring built with pure CSS conic-gradient — no chart library."""
    color = score_color(score)
    angle = int(score / 100 * 360)
    label = "Needs Work" if score < 50 else "Good" if score < 75 else "Excellent"

    html_out = f"""
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:12px 0;">
        <div style="
            position:relative; width:200px; height:200px; border-radius:50%;
            background: conic-gradient({color} {angle}deg, #262637 {angle}deg 360deg);
            display:flex; align-items:center; justify-content:center;
            animation: ringFadeIn 0.8s ease-out;
            box-shadow: 0 0 30px {color}33;
        ">
            <div style="
                width:158px; height:158px; border-radius:50%; background:#14141f;
                display:flex; flex-direction:column; align-items:center; justify-content:center;
            ">
                <span style="font-size:2.6rem; font-weight:800; color:{color}; line-height:1;">{score}</span>
                <span style="font-size:0.72rem; color:#9ca3af; margin-top:4px; letter-spacing:0.05em;">OUT OF 100</span>
            </div>
        </div>
        <div style="
            margin-top:14px; padding:5px 16px; border-radius:20px; font-size:0.82rem; font-weight:600;
            background:{color}22; color:{color}; border:1px solid {color}55;
        ">{label}</div>
    </div>
    <style>
    @keyframes ringFadeIn {{
        from {{ opacity: 0; transform: scale(0.85) rotate(-90deg); }}
        to {{ opacity: 1; transform: scale(1) rotate(0deg); }}
    }}
    </style>
    """
    return dedent_html(html_out)


def render_category_bars(category_scores):
    """Animated horizontal progress bars replacing the radar chart."""
    rows = ""
    for i, (key, value) in enumerate(category_scores.items()):
        label = esc(key.replace("_", " ").title())
        color = score_color(value)
        delay = i * 0.08
        rows += f"""
        <div style="margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                <span style="font-size:0.85rem; color:#d1d5db; font-weight:500;">{label}</span>
                <span style="font-size:0.85rem; color:{color}; font-weight:700;">{value}</span>
            </div>
            <div style="background:#262637; border-radius:8px; height:10px; overflow:hidden;">
                <div style="
                    width:{value}%; height:100%; border-radius:8px;
                    background:linear-gradient(90deg, {color}aa, {color});
                    animation: barGrow_{i} 0.9s ease-out {delay}s both;
                "></div>
            </div>
        </div>
        <style>
        @keyframes barGrow_{i} {{
            from {{ width: 0%; }}
            to {{ width: {value}%; }}
        }}
        </style>
        """
    return dedent_html(f'<div style="padding:8px 4px;">{rows}</div>')


def render_trend(history):
    if len(history) < 2:
        return None
    ordered = list(reversed(history))
    scores = [h["analysis"].get("ats_score", 0) for h in ordered]
    labels = [h["timestamp"].split(",")[0] for h in ordered]
    names = [h["filename"] for h in ordered]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels, y=scores, mode="lines+markers",
        line=dict(color="#a78bfa", width=3),
        marker=dict(size=9, color="#7c3aed", line=dict(width=2, color="white")),
        text=names,
        hovertemplate="%{text}<br>ATS Score: %{y}<extra></extra>"
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=260,
        margin=dict(l=30, r=30, t=20, b=30),
        font={'color': "white"},
        xaxis=dict(gridcolor="#333", color="white"),
        yaxis=dict(gridcolor="#333", color="white", range=[0, 100])
    )
    return fig


def clean_for_pdf(text):
    """Strip characters FPDF's core fonts can't render (emoji, curly quotes, etc.)"""
    if not isinstance(text, str):
        text = str(text)
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "ignore").decode("latin-1")


def generate_pdf_report(data, filename, target_role):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(79, 70, 229)
    pdf.cell(0, 12, "AI Career Assistant - Resume Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, clean_for_pdf(f"File: {filename}   |   Target Role: {target_role or 'General'}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    def section(title, body_lines):
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(30, 30, 46)
        pdf.cell(0, 9, clean_for_pdf(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(40, 40, 40)
        for line in body_lines:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 6, clean_for_pdf("- " + line))
        pdf.ln(3)

    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(16, 185, 129)
    pdf.cell(0, 10, clean_for_pdf(f"ATS Score: {data.get('ats_score', 'N/A')} / 100"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    section("Professional Summary", [data.get("summary", "")])
    section("AI-Improved Summary", [data.get("improved_summary", "")])
    section("Technical Skills", data.get("technical_skills", []))
    section("Soft Skills", data.get("soft_skills", []))
    section("Missing Skills", data.get("missing_skills", []))
    section("Recommended Job Roles", data.get("recommended_jobs", []))
    section("Strengths", data.get("strengths", []))
    section("Areas to Improve", data.get("weaknesses", []))
    section("Education", data.get("education", []))
    section("Experience", data.get("experience", []))
    section("Projects", data.get("projects", []))

    iq = data.get("interview_questions", {})
    section("HR Interview Questions", iq.get("hr_questions", []))
    section("Technical Interview Questions", iq.get("technical_questions", []))
    section("Coding Interview Questions", iq.get("coding_questions", []))

    # fpdf2's output() returns a bytearray directly; the old dest="S" kwarg
    # is deprecated and triggers warnings on newer fpdf2 versions.
    return bytes(pdf.output())


# ---- Session state ----
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "filename" not in st.session_state:
    st.session_state.filename = None
if "target_role" not in st.session_state:
    st.session_state.target_role = ""

# ---- Sidebar ----
with st.sidebar:
    st.markdown("## 🎯 AI Career Assistant")
    st.caption("Upload your resume for an AI-powered breakdown: ATS score, skill gaps, and tailored interview prep.")
    st.markdown("---")

    if client is None:
        st.warning("⚠️ GROQ_API_KEY is not set — analysis is disabled until it's configured.")

    target_role_input = st.text_input(
        "🎯 Target job role (optional)",
        placeholder="e.g. Machine Learning Engineer",
        help="Tailors the ATS score, missing skills, and interview questions to this specific role."
    )

    uploaded_file = st.file_uploader("Upload Resume (PDF)", type="pdf", label_visibility="collapsed")

    if uploaded_file is not None:
        if st.button("🔍 Analyze Resume", use_container_width=True, disabled=(client is None)):
            with st.spinner("Analyzing your resume..."):
                tmp_path = None
                try:
                    # Use a unique temp file instead of a fixed name so
                    # concurrent users/sessions can't clobber each other's upload.
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(uploaded_file.getbuffer())
                        tmp_path = tmp.name

                    resume_text = extract_resume_text(tmp_path)
                    result = analyze_resume(resume_text, target_role_input.strip())
                    if result:
                        st.session_state.analysis = result
                        st.session_state.filename = uploaded_file.name
                        st.session_state.target_role = target_role_input.strip()
                        add_to_history(uploaded_file.name, target_role_input.strip(), result)
                        st.success("Analysis complete!")
                    else:
                        st.error("Couldn't parse the analysis. Try again.")
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.remove(tmp_path)

    if st.session_state.analysis:
        st.markdown("---")
        if st.button("🔄 Analyze New Resume", use_container_width=True):
            st.session_state.analysis = None
            st.session_state.filename = None
            st.session_state.target_role = ""
            st.rerun()

    # ---- History panel ----
    st.markdown("---")
    st.markdown("### 🕒 Resume History")
    history = load_history()
    if not history:
        st.caption("No past analyses yet.")
    else:
        for h in history[:10]:
            score = h["analysis"].get("ats_score", 0)
            hex_color = "#10b981" if score >= 75 else "#f59e0b" if score >= 50 else "#ef4444"
            col_a, col_b = st.columns([5, 1])
            with col_a:
                md(f"""
                <div class="history-item">
                    <span class="history-score" style="color:{hex_color}">{score}</span> /100 &nbsp;
                    <b>{esc(h['filename'][:20])}</b><br>
                    <span style="color:#9ca3af;font-size:0.75rem;">{esc(h['target_role'])} · {esc(h['timestamp'])}</span>
                </div>
                """)
                if st.button("View", key=f"view_{h['id']}", use_container_width=True):
                    st.session_state.analysis = h["analysis"]
                    st.session_state.filename = h["filename"]
                    st.session_state.target_role = h["target_role"]
                    st.rerun()
            with col_b:
                if st.button("🗑️", key=f"del_{h['id']}"):
                    delete_history_entry(h["id"])
                    st.rerun()

        if st.button("🧹 Clear All History", use_container_width=True):
            save_history([])
            st.rerun()

    st.markdown("---")
    st.caption("Built with PyMuPDF · Groq (Llama 3.3) · Streamlit · Plotly")

# ---- Main area ----
data = st.session_state.analysis
history = load_history()

if data is None:
    md("""
    <div class="hero-banner">
        <p class="hero-title">🎯 AI Career Assistant</p>
        <p class="hero-subtitle">AI-powered resume analysis — ATS scoring, skill gaps, and interview prep, generated in seconds.</p>
    </div>
    """)

    trend_fig = render_trend(history)
    if trend_fig:
        st.markdown('<div class="section-card"><div class="section-title">📈 Your ATS Score Trend</div>', unsafe_allow_html=True)
        st.plotly_chart(trend_fig, use_container_width=True, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    st.info("👈 Upload your resume in the sidebar and click 'Analyze Resume' to get started.")
else:
    score = data.get('ats_score', 0)

    if score >= 80:
        st.balloons()

    role_display = f" · Targeting: {esc(st.session_state.target_role)}" if st.session_state.target_role else ""
    md(f"""
    <div class="hero-banner">
        <p class="hero-title">🎯 Analysis Complete</p>
        <p class="hero-subtitle">{esc(st.session_state.filename)}{role_display}</p>
    </div>
    """)

    # ---- Download PDF button ----
    try:
        pdf_bytes = generate_pdf_report(data, st.session_state.filename, st.session_state.target_role)
        st.download_button(
            label="📄 Download Full Report (PDF)",
            data=pdf_bytes,
            file_name=f"resume_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except Exception as e:
        st.warning(f"Couldn't generate the PDF report: {e}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            '<div class="section-card"><div class="section-title">📊 ATS Score</div>'
            + render_score_ring(score) + '</div>',
            unsafe_allow_html=True
        )
    with col2:
        cat_scores = data.get('category_scores', {})
        if cat_scores:
            st.markdown(
                '<div class="section-card"><div class="section-title">📈 Category Breakdown</div>'
                + render_category_bars(cat_scores) + '</div>',
                unsafe_allow_html=True
            )

    trend_fig = render_trend(history)
    if trend_fig:
        st.markdown('<div class="section-card"><div class="section-title">📈 Your ATS Score Trend</div>', unsafe_allow_html=True)
        st.plotly_chart(trend_fig, use_container_width=True, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    md(f"""
    <div class="section-card">
        <div class="section-title">📝 Professional Summary</div>
        <p>{esc(data.get('summary', ''))}</p>
    </div>
    """)

    md(f"""
    <div class="section-card">
        <div class="section-title">✨ AI-Improved Summary</div>
        <p>{esc(data.get('improved_summary', ''))}</p>
    </div>
    """)

    col1, col2 = st.columns(2)
    with col1:
        tags = "".join([f'<span class="skill-tag">{esc(s)}</span>' for s in data.get('technical_skills', [])])
        md(f"""
        <div class="section-card">
            <div class="section-title">💻 Technical Skills</div>
            {tags}
        </div>
        """)
    with col2:
        tags = "".join([f'<span class="skill-tag">{esc(s)}</span>' for s in data.get('soft_skills', [])])
        md(f"""
        <div class="section-card">
            <div class="section-title">🤝 Soft Skills</div>
            {tags}
        </div>
        """)

    col1, col2 = st.columns(2)
    with col1:
        tags = "".join([f'<span class="missing-tag">{esc(s)}</span>' for s in data.get('missing_skills', [])])
        md(f"""
        <div class="section-card">
            <div class="section-title">⚠️ Missing Skills</div>
            {tags}
        </div>
        """)
    with col2:
        tags = "".join([f'<span class="job-tag">{esc(s)}</span>' for s in data.get('recommended_jobs', [])])
        md(f"""
        <div class="section-card">
            <div class="section-title">💼 Recommended Job Roles</div>
            {tags}
        </div>
        """)

    col1, col2 = st.columns(2)
    with col1:
        items = "".join([f'<div class="list-item strength-item">✅ {esc(s)}</div>' for s in data.get('strengths', [])])
        md(f"""
        <div class="section-card">
            <div class="section-title">💪 Strengths</div>
            {items}
        </div>
        """)
    with col2:
        items = "".join([f'<div class="list-item weakness-item">⚠️ {esc(s)}</div>' for s in data.get('weaknesses', [])])
        md(f"""
        <div class="section-card">
            <div class="section-title">📉 Areas to Improve</div>
            {items}
        </div>
        """)

    col1, col2 = st.columns(2)
    with col1:
        items = "".join([f'<div class="list-item">🎓 {esc(s)}</div>' for s in data.get('education', [])])
        md(f"""
        <div class="section-card">
            <div class="section-title">🎓 Education</div>
            {items}
        </div>
        """)
    with col2:
        items = "".join([f'<div class="list-item">💼 {esc(s)}</div>' for s in data.get('experience', [])])
        md(f"""
        <div class="section-card">
            <div class="section-title">💼 Experience</div>
            {items}
        </div>
        """)

    items = "".join([f'<div class="list-item">🚀 {esc(s)}</div>' for s in data.get('projects', [])])
    md(f"""
    <div class="section-card">
        <div class="section-title">🚀 Projects</div>
        {items}
    </div>
    """)

    st.markdown("## 🎤 Personalized Interview Prep")
    iq = data.get('interview_questions', {})

    tab1, tab2, tab3 = st.tabs(["🗣️ HR Questions", "🧠 Technical Questions", "💻 Coding Questions"])
    with tab1:
        for q in iq.get('hr_questions', []):
            st.markdown(f'<div class="question-item">{esc(q)}</div>', unsafe_allow_html=True)
    with tab2:
        for q in iq.get('technical_questions', []):
            st.markdown(f'<div class="question-item">{esc(q)}</div>', unsafe_allow_html=True)
    with tab3:
        for q in iq.get('coding_questions', []):
            st.markdown(f'<div class="question-item">{esc(q)}</div>', unsafe_allow_html=True)
