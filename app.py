import streamlit as st
import pandas as pd
import json
import os
import tempfile
import io
import time
import streamlit.components.v1 as components
from google import genai
from google.genai import types

# 1. ตั้งค่าหน้าเว็บ
st.set_page_config(
    page_title="Proposal Inspector",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. ตกแต่ง Dark Theme, Badge สถานะ และปุ่มต่างๆ
st.markdown("""
<style>
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    [data-testid="stSidebar"], section[data-testid="stSidebarNav"] {
        display: none !important;
    }
    .dropzone-label {
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .dot-cyan {
        height: 8px;
        width: 8px;
        background-color: #38bdf8;
        border-radius: 50%;
        display: inline-block;
    }
    .dot-green {
        height: 8px;
        width: 8px;
        background-color: #34d399;
        border-radius: 50%;
        display: inline-block;
    }
    [data-testid="stFileUploader"] {
        background-color: #0d1321;
        border: 2px dashed #1e293b;
        border-radius: 12px;
        padding: 10px;
    }
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1 0%, #10b981 100%) !important;
        color: #ffffff !important;
        font-weight: 600;
        font-size: 15px;
        padding: 10px 20px;
        border: none !important;
        border-radius: 12px;
    }
    div[data-testid="stButton"] > button[kind="secondary"] {
        background-color: #1e293b !important;
        color: #cbd5e1 !important;
        border: 1px solid #334155 !important;
        font-weight: 600;
        font-size: 15px;
        padding: 10px 16px;
        border-radius: 12px;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover {
        background-color: #334155 !important;
        color: #ffffff !important;
    }
    .metric-card {
        background-color: #111827;
        border: 1px solid #1f293d;
        border-radius: 14px;
        padding: 16px;
        text-align: center;
    }
    .metric-title {
        color: #94a3b8;
        font-size: 13px;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
    }

    /* ตารางผลการตรวจประเมิน */
    .custom-table-container {
        width: 100%;
        overflow-x: auto;
        background-color: #0b1120;
        border: 1px solid #1e293b;
        border-radius: 12px;
        margin-bottom: 28px;
    }
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        color: #e2e8f0;
        font-size: 14px;
        line-height: 1.6;
    }
    .custom-table th {
        background-color: #0d1527;
        color: #94a3b8;
        font-weight: 600;
        text-align: center !important;
        padding: 14px 16px;
        border-bottom: 1px solid #1e293b;
        white-space: nowrap;
    }
    .custom-table td {
        padding: 14px 16px;
        border-bottom: 1px solid #172238;
        vertical-align: middle;
    }
    .custom-table tr:hover {
        background-color: #0f1a30;
    }

    /* Badge สถานะแบบ Pill Box */
    .status-badge-container {
        display: flex;
        justify-content: center;
        align-items: center;
    }
    .badge-pill-compliant {
        background-color: rgba(52, 211, 153, 0.12);
        color: #34d399;
        border: 1px solid #059669;
        padding: 4px 14px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 600;
        display: inline-block;
        text-align: center;
        min-width: 65px;
    }
    .badge-pill-partial {
        background-color: rgba(251, 191, 36, 0.12);
        color: #fbbf24;
        border: 1px solid #d97706;
        padding: 4px 14px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 600;
        display: inline-block;
        text-align: center;
        min-width: 65px;
    }
    .badge-pill-noncompliant {
        background-color: rgba(244, 63, 94, 0.14);
        color: #fb7185;
        border: 1px solid #be123c;
        padding: 4px 14px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 600;
        display: inline-block;
        text-align: center;
        min-width: 65px;
    }
</style>
""", unsafe_allow_html=True)

# 3. ดึง API Key จาก Secrets
gemini_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

# รายชื่อโมเดลสำรองเรียงตามลำดับความเสถียร (Auto-Fallback)
CANDIDATE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-3.8-flash",
    "gemini-2.0-flash-lite"
]

# 4. ฟังก์ชันประมวลผลพร้อมระบบ Auto-Fallback
def process_assessment(tor_file, proposal_file, api_key):
    client = genai.Client(api_key=api_key)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        tor_ext = os.path.splitext(tor_file.name)[1] or ".pdf"
        prop_ext = os.path.splitext(proposal_file.name)[1] or ".pdf"
        
        tor_path = os.path.join(temp_dir, f"tor_doc{tor_ext}")
        prop_path = os.path.join(temp_dir, f"proposal_doc{prop_ext}")
        
        with open(tor_path, "wb") as f:
            f.write(tor_file.getbuffer())
        with open(prop_path, "wb") as f:
            f.write(proposal_file.getbuffer())

        st.info("กำลังอัปโหลดเอกสารเข้าสู่ระบบประมวลผล...")
        tor_gemini = client.files.upload(file=tor_path)
        prop_gemini = client.files.upload(file=prop_path)

        prompt_text = """
คุณเป็นผู้เชี่ยวชาญด้านการจัดซื้อจัดจ้างและการตรวจประเมินข้อเสนอทางเทคนิค (Technical Proposal Inspector)
หน้าที่ของคุณคือ: เปรียบเทียบข้อกำหนดในเอกสาร TOR กับเอกสาร Proposal เล่มข้อเสนออย่างละเอียดถี่ถ้วนแบบข้อต่อข้อ

จงวิเคราะห์และตอบกลับในรูปแบบ JSON Schema ดังนี้เท่านั้น:
{
  "totalTorItems": <จำนวนข้อกำหนด TOR ทั้งหมดที่ตรวจพบ>,
  "compliantCount": <จำนวนข้อที่ ครบถ้วน (Compliant)>,
  "partialCount": <จำนวนข้อที่ บางส่วน (Partial)>,
  "nonCompliantCount": <จำนวนข้อที่ ขาดตก (Non-Compliant)>,
  "complianceScore": <คะแนนรวมเป็นตัวเลข % เช่น 92>,
  "executiveSummary": "<บทสรุปผู้บริหาร สรุปภาพรวมความสอดคล้อง จุดเด่น และข้อสังเกต>",
  "complianceTable": [
    {
      "id": 1,
      "torItem": "<ระบุรายละเอียดข้อกำหนด TOR แต่ละข้อ>",
      "proposalItem": "<ระบุข้อเสนอของ Proposal ที่ตรงกับข้อกำหนดนี้อย่างกระชับ>",
      "status": "ครบถ้วน" | "บางส่วน" | "ขาดตก",
      "gapAnalysis": "<ระบุการวิเคราะห์ข้อดี ข้อสังเกต หรือ Gap Analysis และข้อเสนอแนะเชิงลึก>"
    }
  ]
}
"""
        response = None
        last_error = None
        status_placeholder = st.empty()

        for model_name in CANDIDATE_MODELS:
            try:
                status_placeholder.info(f"⚡ กำลังส่งเอกสารให้โมเดล: {model_name} วิเคราะห์และเปรียบเทียบ...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt_text, tor_gemini, prop_gemini],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )
                if response and response.text:
                    status_placeholder.empty()
                    break
            except Exception as err:
                last_error = err
                status_placeholder.warning(f"⚠️ โมเดล {model_name} มีผู้ใช้งานหนาแน่น (ติดข้อผิดพลาด) -> กำลังสลับไปใช้โมเดลถัดไป...")
                time.sleep(1.5)

        try:
            client.files.delete(name=tor_gemini.name)
            client.files.delete(name=prop_gemini.name)
        except Exception:
            pass

        if not response or not response.text:
            raise Exception(f"ระบบไม่สามารถประมวลผลได้เนื่องจากทุกโมเดลสำรองมีผู้ใช้งานหนาแน่น: {str(last_error)}")

        return json.loads(response.text)

# 5. ส่วนหัวหน้าเว็บ
st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
        <div style="background-color: #2563eb; padding: 10px; border-radius: 10px; display: inline-flex;">
            <span style="font-size: 20px;">📄</span>
        </div>
        <div>
            <h2 style="margin: 0; font-size: 22px; font-weight: 700; color: #ffffff;">Proposal Inspector</h2>
            <div style="color: #94a3b8; font-size: 13px; margin-top: 2px;">ระบบตรวจและประเมินข้อเสนอด้านเทคนิคด้วย Gemini AI</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# 6. จัดการ Key รีเฟรชไฟล์
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

# 7. กล่องรับไฟล์
st.markdown("""
    <div style="background: #111827; border: 1px solid #1f293d; border-radius: 18px 18px 0 0; padding: 22px 28px 0px 28px;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 20px;">📁</span>
            <span style="font-size: 18px; font-weight: 700; color: #ffffff;">นำเข้าเอกสาร TOR และ Proposal</span>
        </div>
        <div style="color: #94a3b8; font-size: 13px; margin-top: 4px; margin-bottom: 16px;">
            รองรับไฟล์ PDF, Word (.docx/.doc), Excel (.xlsx/.xls), PPT (.pptx/.ppt) และ Text (.txt)
        </div>
    </div>
""", unsafe_allow_html=True)

SUPPORTED_TYPES = ["pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt", "txt"]

st.markdown('<div style="background: #111827; border-left: 1px solid #1f293d; border-right: 1px solid #1f293d; border-bottom: 1px solid #1f293d; border-radius: 0 0 18px 18px; padding: 0 28px 24px 28px;">', unsafe_allow_html=True)

col_tor_box, col_prop_box = st.columns(2)

with col_tor_box:
    st.markdown('<div class="dropzone-label"><span class="dot-cyan"></span> ไฟล์ TOR (ข้อกำหนด)</div>', unsafe_allow_html=True)
    tor_file = st.file_uploader(
        "อัปโหลดไฟล์ TOR",
        type=SUPPORTED_TYPES,
        key=f"tor_upload_{st.session_state['uploader_key']}",
        label_visibility="collapsed"
    )

with col_prop_box:
    st.markdown('<div class="dropzone-label"><span class="dot-green"></span> ไฟล์ Proposal (ข้อเสนอด้านเทคนิค)</div>', unsafe_allow_html=True)
    prop_file = st.file_uploader(
        "อัปโหลดไฟล์ Proposal",
        type=SUPPORTED_TYPES,
        key=f"prop_upload_{st.session_state['uploader_key']}",
        label_visibility="collapsed"
    )

st.markdown("<br>", unsafe_allow_html=True)

# ปุ่มควบคุม
b_col_space, b_col_refresh, b_col_start = st.columns([2.5, 0.8, 1.3])

with b_col_refresh:
    reset_btn = st.button("🔄 รีเฟรช", use_container_width=True, type="secondary")

with b_col_start:
    start_btn = st
