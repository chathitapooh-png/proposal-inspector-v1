import streamlit as st
import pandas as pd
import json
import os
import tempfile
import io
from google import genai
from google.genai import types

# 1. การตั้งค่าหน้าจอ
st.set_page_config(
    page_title="Proposal Inspector",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. ปรับแต่งดีไซน์ CSS ให้ตรงตาม UI Mockup
st.markdown("""
<style>
    /* พื้นหลังหลักและฟอนต์ */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* ซ่อนแถบด้านข้าง (Sidebar) อย่างสมบูรณ์ */
    [data-testid="stSidebar"], section[data-testid="stSidebarNav"] {
        display: none !important;
    }

    /* กล่องการ์ดหลัก */
    .main-card {
        background: #111827;
        border: 1px solid #1f293d;
        border-radius: 18px;
        padding: 24px 28px;
        margin-top: 15px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }

    /* Badge หัวเว็บ */
    .badge-status {
        background-color: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #34d399;
        font-size: 13px;
        padding: 6px 14px;
        border-radius: 9999px;
        font-weight: 500;
        display: inline-block;
    }

    /* กล่องอัปโหลดไฟล์จำลอง Dropzone */
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

    /* ตกแต่งกล่อง File Uploader ของ Streamlit */
    [data-testid="stFileUploader"] {
        background-color: #0d1321;
        border: 2px dashed #1e293b;
        border-radius: 12px;
        padding: 10px;
        transition: border-color 0.2s ease;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #38bdf8;
    }
    [data-testid="stFileUploader"] section {
        padding: 0px !important;
    }

    /* ปุ่มประมวลผลสไตล์ Gradient */
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #6366f1 0%, #10b981 100%);
        color: #ffffff;
        font-weight: 600;
        font-size: 16px;
        padding: 12px 24px;
        border: none;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
        transition: all 0.3s ease;
    }
    div.stButton > button:first-child:hover {
        opacity: 0.95;
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
    }

    /* การ์ดสรุปตัวชี้วัด */
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
</style>
""", unsafe_allow_html=True)

# 3. ดึง API Key จาก Secrets โดยตรง (ป้องกันการมองเห็น)
gemini_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

# 4. ฟังก์ชันประมวลผลการตรวจประเมิน
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
        st.info("Gemini AI กำลังอ่านและเปรียบเทียบเอกสารทั้งหมด...")
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[prompt_text, tor_gemini, prop_gemini],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        
        try:
            client.files.delete(name=tor_gemini.name)
            client.files.delete(name=prop_gemini.name)
        except Exception:
            pass

        return json.loads(response.text)

# 5. Header ด้านบน
col_header, col_badge = st.columns([4, 1.2])
with col_header:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="background-color: #2563eb; padding: 10px; border-radius: 10px; display: inline-flex;">
                <span style="font-size: 20px;">📄</span>
            </div>
            <div>
                <h2 style="margin: 0; font-size: 22px; font-weight: 700; color: #ffffff;">Proposal Inspector (Google Workspace Edition)</h2>
                <div style="color: #94a3b8; font-size: 13px; margin-top: 2px;">ระบบตรวจและประเมินข้อเสนอด้านเทคนิคด้วย Gemini AI</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
with col_badge:
    st.markdown('<div style="text-align: right; margin-top: 8px;"><span class="badge-status">Google Apps Script Serverless</span></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# 6. กล่องนำเข้าเอกสาร TOR และ Proposal
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

# กำหนดนามสกุลไฟล์ที่รองรับทั้งหมดตาม Mockup
SUPPORTED_FILE_TYPES = ["pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt", "txt"]

with st.container():
    st.markdown('<div style="background: #111827; border-left: 1px solid #1f293d; border-right: 1px solid #1f293d; border-bottom: 1px solid #1f293d; border-radius: 0 0 18px 18px; padding: 0 28px 24px 28px;">', unsafe_allow_html=True)
    
    col_tor_box, col_prop_box = st.columns(2)
    
    with col_tor_box:
        st.markdown('<div class="dropzone-label"><span class="dot-cyan"></span> ไฟล์ TOR (ข้อกำหนด)</div>', unsafe_allow_html=True)
        tor_file = st.file_uploader(
            "คลิกเพื่อเลือกไฟล์ TOR",
            type=SUPPORTED_FILE_TYPES,
