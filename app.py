import streamlit as st
import pandas as pd
import json
import os
import tempfile
import io
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

# 2. ตกแต่ง Dark Theme และ Badge สถานะตามแบบตัวอย่าง
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

    /* Badge สถานะแบบ Pill Box ตามรูปตัวอย่าง */
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
        letter-spacing: 0.3px;
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
        letter-spacing: 0.3px;
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
        letter-spacing: 0.3px;
        display: inline-block;
        text-align: center;
        min-width: 65px;
    }
</style>
""", unsafe_allow_html=True)

# 3. ดึง API Key จาก Secrets
gemini_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

# 4. ฟังก์ชันประมวลผล
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

# 5. ส่วนหัวหน้าเว็บ
st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px;">
        <div style="background-color: #2563eb; padding: 10px; border-radius: 10px; display: inline-flex;">
            <span style="font-size: 20px;">📄</span>
        </div>
        <div>
            <h2 style="margin: 0; font-size: 22px; font-weight: 700; color: #ffffff;">Proposal Inspector</h2>
            <div style="color: #94a3b8; font-size: 13px; margin-top: 2px;">ระบบตรวจและประเมินข้อเสนอด้านเทคนิคด้วย Gemini AI</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# 6. จัดการ Key เพื่อให้ปุ่มรีเฟรชล้างไฟล์ได้จริง
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
    start_btn = st.button("✨ เริ่มประมวลผลด้วย Gemini AI", use_container_width=True, type="primary")

st.markdown('</div>', unsafe_allow_html=True)

# ฟังก์ชันรีเฟรช
if reset_btn:
    if "assessment_result" in st.session_state:
        del st.session_state["assessment_result"]
    st.session_state["uploader_key"] += 1
    st.rerun()

# 8. กดประมวลผล
if start_btn:
    if not gemini_key:
        st.error("⚠️ ไม่พบคีย์ GEMINI_API_KEY ใน Settings > Secrets กรุณาตั้งค่าก่อนเริ่มใช้งาน")
    elif not tor_file or not prop_file:
        st.warning("⚠️ กรุณานำเข้าไฟล์ให้ครบทั้ง 2 เล่มก่อนเริ่มประมวลผล")
    else:
        try:
            with st.spinner("ระบบกำลังเริ่มกระบวนการวิเคราะห์เอกสาร..."):
                result_data = process_assessment(tor_file, prop_file, gemini_key)
                st.session_state["assessment_result"] = result_data
                st.success("ประมวลผลเสร็จสิ้นเรียบร้อยแล้ว!")
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)}")

# 9. ส่วนแสดงผลลัพธ์
if "assessment_result" in st.session_state:
    data = st.session_state["assessment_result"]
    st.markdown("<br><hr style='border: 1px solid #1e293b;'><br>", unsafe_allow_html=True)
    st.markdown("### 📊 ผลการตรวจประเมิน (Assessment Results)")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-title">Compliance Score</div><div class="metric-value" style="color: #38bdf8;">{data.get("complianceScore", 0)}%</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card" style="border-left: 3px solid #3b82f6;"><div class="metric-title">จำนวนข้อกำหนด TOR</div><div class="metric-value" style="color: #60a5fa;">{data.get("totalTorItems", 0)}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-title">ครบถ้วน (Compliant)</div><div class="metric-value" style="color: #34d399;">{data.get("compliantCount", 0)}</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-title">บางส่วน (Partial)</div><div class="metric-value" style="color: #fbbf24;">{data.get("partialCount", 0)}</div></div>', unsafe_allow_html=True)
    with c5:
        st.markdown(f'<div class="metric-card"><div class="metric-title">ขาดตก (Non-Compliant)</div><div class="metric-value" style="color: #f87171;">{data.get("nonCompliantCount", 0)}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📝 บทสรุปผู้บริหาร (Executive Summary)")
    st.info(data.get("executiveSummary", "-"))

    st.markdown("#### 📋 ตารางเปรียบเทียบข้อต่อข้อ (Compliance Table)")
    items = data.get("complianceTable", [])
    
    if items:
        table_html = """
        <div class="custom-table-container">
            <table class="custom-table">
                <thead>
                    <tr>
                        <th style="width: 5%;">#</th>
                        <th style="width: 30%;">ข้อกำหนด TOR</th>
                        <th style="width: 30%;">ข้อเสนอ Proposal</th>
                        <th style="width: 12%;">สถานะ</th>
                        <th style="width: 23%;">Gap Analysis & ข้อเสนอแนะ</th>
                    </tr>
                </thead>
                <tbody>
        """
        for item in items:
            status_text = str(item.get("status", "")).strip()
            if status_text == "ครบถ้วน":
                status_badge = f'<div class="status-badge-container"><span class="badge-pill-compliant">{status_text}</span></div>'
            elif status_text == "บางส่วน":
                status_badge = f'<div class="status-badge-container"><span class="badge-pill-partial">{status_text}</span></div>'
            else:
                status_badge = f'<div class="status-badge-container"><span class="badge-pill-noncompliant">{status_text}</span></div>'

            table_html += f"""
                <tr>
                    <td style="text-align: center; color: #94a3b8; font-weight: 600;">{item.get('id', '')}</td>
                    <td>{item.get('torItem', '')}</td>
                    <td>{item.get('proposalItem', '')}</td>
                    <td>{status_badge}</td>
                    <td>{item.get('gapAnalysis', '')}</td>
                </tr>
            """
        table_html += """
                </tbody>
            </table>
        </div>
        """
        st.markdown(table_html, unsafe_allow_html=True)

        # เตรียมข้อมูลสำหรับดาวน์โหลดเป็น Excel
        df = pd.DataFrame(items)
        column_mapping = {
            "id": "#",
            "torItem": "ข้อกำหนด TOR",
            "proposalItem": "ข้อเสนอ Proposal",
            "status": "สถานะ",
            "gapAnalysis": "Gap Analysis & ข้อเสนอแนะ"
        }
        df_display = df.rename(columns=column_mapping)
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df_display.to_excel(writer, index=False, sheet_name='Compliance_Evaluation')

        col_down1, col_down2 = st.columns(2)
        with col_down1:
            st.download_button(
                label="📥 ดาวน์โหลดเป็นไฟล์ Excel",
                data=excel_buffer.getvalue(),
                file_name="Compliance_Evaluation_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with col_down2:
            print_btn = st.button("🖨️ พิมพ์รายงาน / บันทึกเป็น PDF", use_container_width=True)
            if print_btn:
                components.html("<script>window.parent.print();</script>", height=0, width=0)
