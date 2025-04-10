import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from openai import OpenAI
from dotenv import load_dotenv
import os
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="تقرير مشروع ", layout="centered")

# تحميل المفاتيح من .env
load_dotenv()
ASANA_TOKEN = os.getenv("ASANA_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

headers = {"Authorization": f"Bearer {ASANA_TOKEN}"}

# --------- تخصيص الستايل --------- #
st.markdown("""
    <style>
        body {
            background-color: #f9fafb;
            direction: rtl;
            padding: 10px;
            font-size: 15px;
        }
        .report-title {
            color: #1d4ed8;
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 20px;
        }
        .section-header {
            color: #1f2937;
            font-size: 24px;
            font-weight: bold;
            margin-top: 40px;
            margin-bottom: 15px;
        }
        .gpt-summary-box {
            background-color: #f3f4f6;
            padding: 20px;
            border-radius: 10px;
            font-weight: 500;
        }
        .dataframe th {
            background-color: #1d4ed8;
            text-align: right;
        }
        .stButton button {
            background-color: #861d1d;
            color: white;
            font-weight: bold;
            border-radius: 8px;
            padding: 10px 20px;
        }
        .stButton button:hover {
            background-color: #861d1d;
        }
        .print-button {
            margin-top: 40px;
            text-align: center;
        }
    </style>
""", unsafe_allow_html=True)

# --------- وظائف --------- #
def get_project_name(project_id):
    url = f"https://app.asana.com/api/1.0/projects/{project_id}"
    response = requests.get(url, headers=headers)
    return response.json()['data']['name']

def get_asana_tasks(project_id):
    url = f"https://app.asana.com/api/1.0/projects/{project_id}/tasks?opt_fields=name,assignee.name,completed,due_on"
    response = requests.get(url, headers=headers)
    return response.json()['data']

def process_tasks_to_df(tasks):
    data = []
    for task in tasks:
        completed = task.get("completed")
        data.append({
            "Task Name": task.get("name"),
            "Assignee": task["assignee"]["name"] if task.get("assignee") else "غير مسند",
            "Completed": "✅" if completed else "❌",
            "Due Date": task.get("due_on")
        })
    df = pd.DataFrame(data)
    df["Due Date"] = pd.to_datetime(df["Due Date"], errors='coerce')
    return df

def generate_user_stats(df):
    df_copy = df.copy()
    df_copy["Delayed"] = (df_copy["Completed"] == "❌") & (df_copy["Due Date"] < pd.Timestamp.today())
    grouped = df_copy.groupby("Assignee").agg({
        "Task Name": "count",
        "Completed": lambda x: (x == "✅").sum(),
        "Delayed": "sum"
    }).reset_index()
    grouped.columns = ["Assignee", "Total Tasks", "Completed Tasks", "Delayed Tasks"]
    return grouped

def generate_summary_with_gpt(df, user_stats):
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"""
أنت مساعد إداري ذكي. هذا تقرير بيانات مهام مشروع في Asana:

أول 10 مهام:
{df.head(10).to_string(index=False)}

تحليل الموظفين:
{user_stats.to_string(index=False)}

- عدد المهام: {len(df)}
- مكتملة: {(df['Completed'] == '✅').sum()}
- غير مكتملة: {(df['Completed'] == '❌').sum()}
- متأخرة: {(df['Completed'] == '❌') & (df['Due Date'] < pd.Timestamp.today()).sum()}

ابدأ بملخص عام عن المشروع.
ثم افصل بين:
- نقاط القوة
- نقاط الضعف
- التوصيات
واكتب عنوان واضح قبل كل قسم.
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    return response.choices[0].message.content

def generate_chart(df):
    counts = {
        "Completed": (df["Completed"] == "✅").sum(),
        "Not Completed ": (df["Completed"] == "❌").sum(),
        "Delayed": ((df["Completed"] == "❌") & (df["Due Date"] < pd.Timestamp.today())).sum()
    }
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.bar(counts.keys(), counts.values(), color=['green', 'orange', 'red'])
    ax.set_title("Task Completion Status")
    ax.set_ylabel("Total Tasks")
    st.pyplot(fig)

# --------- واجهة المستخدم --------- #
st.markdown("<div class='report-title'>📋 مولد تقرير Asana</div>", unsafe_allow_html=True)
st.write("أدخل معرف (ID) المشروع للحصول على تقرير شامل:")

project_id_input = st.text_input("🔢 معرّف المشروع (Project ID)", "")

if st.button("توليد التقرير") and project_id_input:
    with st.spinner("📡 جاري تحميل البيانات من Asana..."):
        try:
            project_name = get_project_name(project_id_input)
            tasks = get_asana_tasks(project_id_input)
            df = process_tasks_to_df(tasks)
            user_stats_df = generate_user_stats(df)
            summary = generate_summary_with_gpt(df, user_stats_df)

            st.markdown(f"<div class='section-header'>📌 تقرير المشروع: {project_name}</div>", unsafe_allow_html=True)
            st.markdown(f"<p class='text-gray-600'>🕒 تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d')}</p>", unsafe_allow_html=True)

            st.markdown("<div class='section-header'>🧠 التحليل العام للمشروع</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='gpt-summary-box'>{summary}</div>", unsafe_allow_html=True)

            st.markdown("<div class='section-header'>📈 الرسم البياني لحالة المهام</div>", unsafe_allow_html=True)
            generate_chart(df)

            st.markdown("<div class='section-header'>📊 جدول المهام</div>", unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True)

            st.markdown("<div class='section-header'>👥 تحليل الموظفين</div>", unsafe_allow_html=True)
            st.dataframe(user_stats_df, use_container_width=True)

            st.markdown("""
<div style="text-align:center; margin-top:40px;">
    <p style="color:#374151;font-size:16px;font-weight:bold;">
        💡 لحفظ التقرير كـ PDF، استخدم اختصار الطباعة في متصفحك: <br>
        <span style="color:#1d4ed8;">Ctrl + P</span> أو من القائمة > طباعة > حفظ كـ PDF
    </p>
</div>
""", unsafe_allow_html=True)


        except Exception as e:
            st.error(f"حدث خطأ: {e}")
