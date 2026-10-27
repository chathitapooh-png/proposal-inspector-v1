import streamlit as st
import pandas as pd
import json
import os
import tempfile
import io
from google import genai
from google.genai import types

st.set_page_config(
    page_title="Proposal Inspector (Gemini Edition)",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .metric-card {
        background-color: #0c1222;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .metric-title {
        color: #94a3b8;
        font-size: 13px;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

def process_assessment(tor_file, proposal_file, api_key):
    client = genai.Client(api_key=api_key)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        tor_path = os.path.join(temp_dir, tor_file.name)
        prop_path = os.path.join(temp_dir, proposal_file.name)
        
        with open(tor_path, "wb") as f:
            f.write(tor_file.getbuffer())
        with open(prop_path, "wb") as f:
            f.write(proposal_file.getbuffer())

        st.info("กำลังอัปโหลดเล่มเอกสารเข้าสู่ Gemini Files API...")
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
        st.info("Gemini 1.5 Pro กำลังอ่านและเปรียบเทียบเอกสารทั้งเล่ม (กรุณารอประมาณ 30–60 วินาที)...")
        response = client.models.generate_content(
            model="gemini-2.5-pro",
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

# แถบด้านซ้ายสำหรับใส่ Gemini API Key
with st.sidebar:
    st.title("⚙️ ตั้งค่าระบบ")
    default_key = os.environ.get("GEMINI_API_KEY", "")
    gemini_key = st.text_input("Gemini API Key", value=default_key, type="password", placeholder="AIzaSy...")

# ส่วนหัวของแอป
st.title("🛡️ Proposal Inspector")
st.caption("ระบบตรวจและประเมินข้อเสนอด้านเทคนิคเทียบกับ TOR ด้วย Gemini AI")

# อัปโหลดไฟล์ (รองรับได้สูงสุด 200 MB)
st.subheader("📁 นำเข้าเอกสาร TOR และ Proposal")
col_tor, col_prop = st.columns(2)

with col_tor:
    tor_file = st.file_uploader("เลือกหรือลากไฟล์ TOR (ข้อกำหนด)", type=["pdf", "docx", "txt"])

with col_prop:
    prop_file = st.file_uploader("เลือกหรือลากไฟล์ Proposal (ข้อเสนอด้านเทคนิค)", type=["pdf", "docx", "txt"])

if st.button("🚀 เริ่มประมวลผลด้วย Gemini AI", type="primary", use_container_width=True):
    if not gemini_key:
        st.error("กรุณาระบุ Gemini API Key ในแถบด้านซ้ายก่อนเริ่มใช้งาน")
    elif not tor_file or not prop_file:
        st.warning("กรุณาเลือกไฟล์ให้ครบทั้งเล่ม TOR และเล่ม Proposal")
    else:
        try:
            with st.spinner("กำลังดำเนินการ..."):
                result_data = process_assessment(tor_file, prop_file, gemini_key)
                st.session_state["assessment_result"] = result_data
                st.success("ประมวลผลเอกสารสำเร็จเรียบร้อยแล้ว!")
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)}")

# แสดงแดชบอร์ดสรุปผล
if "assessment_result" in st.session_state:
    data = st.session_state["assessment_result"]
    st.markdown("---")
    st.header("📊 ผลการตรวจประเมิน (Assessment Results)")

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

    st.markdown("### 📝 บทสรุปผู้บริหาร (Executive Summary)")
    st.info(data.get("executiveSummary", "-"))

    st.markdown("### 📋 ตารางเปรียบเทียบข้อต่อข้อ (Compliance Table)")
    df = pd.DataFrame(data.get("complianceTable", []))

    if not df.empty:
        column_mapping = {
            "id": "#",
            "torItem": "ข้อกำหนด TOR",
            "proposalItem": "ข้อเสนอ Proposal",
            "status": "สถานะ",
            "gapAnalysis": "Gap Analysis & ข้อเสนอแนะ"
        }
        df_display = df.rename(columns=column_mapping)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        col_exp1, col_exp2 = st.columns(2)
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df_display.to_excel(writer, index=False, sheet_name='Compliance_Evaluation')
        
        with col_exp1:
            st.download_button(
                label="📥 ดาวน์โหลดเป็นไฟล์ Excel (.xlsx)",
                data=excel_buffer.getvalue(),
                file_name="Compliance_Evaluation_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with col_exp2:
            st.download_button(
                label="📥 ดาวน์โหลดเป็นไฟล์ CSV (.csv)",
                data=("\ufeff" + df_display.to_csv(index=False)).encode("utf-8-sig"),
                file_name="Compliance_Evaluation_Report.csv",
                mime="text/csv",
                use_container_width=True
            )
