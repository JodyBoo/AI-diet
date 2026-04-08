import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import pandas as pd
from datetime import date
from supabase import create_client, Client

# --- 1. SETUP & DB CONNECTION ---
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.set_page_config(page_title="VitalAI", page_icon="🥗", layout="centered")

# --- 2. FORCED HIGH-CONTRAST UI (FIXES INVISIBLE TEXT) ---
st.markdown("""
    <style>
    /* 1. Force Global Background to White */
    .stApp, [data-testid="stSidebar"], [data-testid="stSidebarContent"] {
        background-color: #FFFFFF !important;
    }

    /* 2. Force ALL text elements to Black */
    html, body, [class*="st-"], p, h1, h2, h3, label, span, div, small {
        color: #000000 !important;
    }

    /* 3. FIX INPUT BOXES (Number input, Select, Text) */
    /* This makes the boxes light grey so the black text is visible */
    input, div[data-baseweb="select"], div[data-baseweb="input"] {
        background-color: #F0F2F6 !important;
        color: #000000 !important;
        border-radius: 10px !important;
    }

    /* 4. FIX SIDEBAR INPUTS SPECIFICALLY */
    [data-testid="stSidebar"] input, [data-testid="stSidebar"] div[data-baseweb="select"] {
        background-color: #F0F2F6 !important;
        color: #000000 !important;
    }

    /* 5. FIX FILE UPLOADER (The black box issue) */
    [data-testid="stFileUploader"] {
        background-color: #F0F2F6 !important;
        border: 2px dashed #CCCCCC !important;
        border-radius: 15px !important;
        padding: 10px !important;
    }
    
    [data-testid="stFileUploader"] section {
        color: #000000 !important;
    }
    
    /* Small text inside uploader */
    [data-testid="stFileUploader"]  div div div div {
        color: #000000 !important;
    }

    /* 6. STYLE DASHBOARD CARDS */
    .metric-card {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        border: 1px solid #EEEEEE;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.05);
        color: #000000;
    }

    /* 7. BLACK BUTTONS */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        background-color: #000000 !important;
        color: #FFFFFF !important;
        height: 3.5rem;
        font-size: 18px;
        font-weight: 600;
        border: none !important;
    }

    /* Hide Streamlit Header/Footer */
    header, footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE FUNCTIONS ---
def load_today_data():
    today = str(date.today())
    try:
        response = supabase.table("health_logs").select("*").eq("log_date", today).execute()
        if response.data:
            data = response.data[0]
            st.session_state.total_calories = data['calories']
            st.session_state.water_cups = data['water']
            st.session_state.macros = {"P": data['protein'], "C": data['carbs'], "F": data['fats']}
            st.session_state.food_history = data['food_history']
            return True
    except: return False
    return False

def save_to_db():
    today = str(date.today())
    payload = {
        "log_date": today,
        "calories": st.session_state.total_calories,
        "protein": st.session_state.macros["P"],
        "carbs": st.session_state.macros["C"],
        "fats": st.session_state.macros["F"],
        "water": st.session_state.water_cups,
        "food_history": st.session_state.food_history
    }
    supabase.table("health_logs").upsert(payload, on_conflict="log_date").execute()

# --- 4. DATA INITIALIZATION ---
if 'db_loaded' not in st.session_state:
    if not load_today_data():
        st.session_state.total_calories = 0
        st.session_state.water_cups = 0
        st.session_state.macros = {"P": 0, "C": 0, "F": 0}
        st.session_state.food_history = []
    st.session_state.db_loaded = True

# --- 5. CORE LOGIC ---
def get_health_stats(w, target_w, h, a, g, act, pace):
    bmi = w / ((h/100)**2)
    if bmi < 18.5: bmi_cat = "Underweight"
    elif 18.5 <= bmi < 25: bmi_cat = "Healthy"
    elif 25 <= bmi < 30: bmi_cat = "Overweight"
    else: bmi_cat = "Obese"
    
    bmr = (10*w + 6.25*h - 5*a + 5) if g == "Male" else (10*w + 6.25*h - 5*a - 161)
    acts = {"Sedentary": 1.2, "Lightly Active": 1.375, "Moderately Active": 1.55, "Very Active": 1.725}
    tdee = bmr * acts[act]
    adj = -(pace * 500) if w > target_w else (pace * 500) if w < target_w else 0
    return int(tdee + adj), bmi, bmi_cat

def log_food(name, cal, p, c, f):
    st.session_state.total_calories += cal
    st.session_state.macros["P"] += p
    st.session_state.macros["C"] += c
    st.session_state.macros["F"] += f
    st.session_state.food_history.append({"Meal": name, "Kcal": cal, "P": p, "C": c, "F": f})
    save_to_db()

# --- 6. SIDEBAR SETTINGS ---
with st.sidebar:
    st.markdown("<h2>👤 Profile</h2>", unsafe_allow_html=True)
    a = st.number_input("Age", 13, 100, 25)
    g = st.selectbox("Gender", ["Female", "Male"])
    h = st.number_input("Height (cm)", 100, 250, 170)
    curr_w = st.number_input("Current Weight (kg)", 40.0, 200.0, 75.0)
    target_w = st.number_input("Target Weight (kg)", 40.0, 200.0, 70.0)
    act = st.selectbox("Activity Level", ["Sedentary", "Lightly Active", "Moderately Active", "Very Active"])
    pace = st.select_slider("Pace (lb/week)", options=[0, 0.5, 1.0, 1.5, 2.0], value=1.0)
    
    budget, bmi, bmi_cat = get_health_stats(curr_w, target_w, h, a, g, act, pace)
    
    if st.button("🔄 Reset Daily Log"):
        supabase.table("health_logs").delete().eq("log_date", str(date.today())).execute()
        st.session_state.total_calories = 0
        st.session_state.water_cups = 0
        st.session_state.macros = {"P": 0, "C": 0, "F": 0}
        st.session_state.food_history = []
        st.rerun()

# --- 7. DASHBOARD ---
st.title("VitalAI Coach")

col1, col2 = st.columns(2)
with col1:
    st.markdown(f"<div class='metric-card'><b>BMI</b><br><span style='font-size:24px;'>{bmi:.1f}</span><br><small>{bmi_cat}</small></div>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='metric-card'><b>Budget</b><br><span style='font-size:24px;'>{budget}</span><br><small>kcal</small></div>", unsafe_allow_html=True)

rem = budget - st.session_state.total_calories
st.write("")
st.markdown(f"<h3 style='text-align: center;'>{rem} kcal remaining</h3>", unsafe_allow_html=True)
st.progress(min(st.session_state.total_calories / budget, 1.0) if budget > 0 else 0)

# --- 8. LOGGING ACTIONS ---
st.write("### Log Activity")
t1, t2, t3, t4, t5 = st.tabs(["📸 Scan", "🏷️ Label", "📝 Manual", "💧 Water", "🤖 Coach"])

with t1:
    up_file = st.file_uploader("Take Photo of Meal", type=['jpg','png','jpeg'], key="plate")
    if up_file:
        st.image(up_file, use_container_width=True)
        if st.button("Confirm AI Scan"):
            with st.spinner("Analyzing..."):
                try:
                    img = Image.open(up_file)
                    prompt = "Identify food. Return JSON: {\"name\":str, \"cal\":int, \"p\":int, \"c\":int, \"f\":int}"
                    resp = model.generate_content([prompt, img])
                    data = json.loads(resp.text.strip().replace('```json', '').replace('```', ''))
                    log_food(data['name'], data['cal'], data['p'], data['c'], data['f'])
                    st.rerun()
                except: st.error("AI couldn't see clearly.")

with t2:
    lab_file = st.file_uploader("Scan Nutrition Label", type=['jpg','png','jpeg'], key="label")
    if lab_file:
        st.image(lab_file, use_container_width=True)
        if st.button("Extract Label Data"):
            with st.spinner("Reading Label..."):
                try:
                    img = Image.open(lab_file)
                    prompt = "Extract nutrition from label. Return JSON: {\"name\":str, \"cal\":int, \"p\":int, \"c\":int, \"f\":int}"
                    resp = model.generate_content([prompt, img])
                    data = json.loads(resp.text.strip().replace('```json', '').replace('```', ''))
                    log_food(data['name'], data['cal'], data['p'], data['c'], data['f'])
                    st.rerun()
                except: st.error("Label scanning failed.")

with t3:
    with st.form("man"):
        m_name = st.text_input("Food Name")
        m_cal = st.number_input("Calories", 0, 2000, 250)
        if st.form_submit_button("Add to Log"):
            log_food(m_name, m_cal, 10, 20, 5)
            st.rerun()

with t4:
    st.markdown(f"<div class='metric-card'><span style='font-size:30px;'>💧 {st.session_state.water_cups}</span><br>Cups Today</div>", unsafe_allow_html=True)
    if st.button("🥤 Log Water (+1 Cup)"):
        st.session_state.water_cups += 1
        save_to_db()
        st.rerun()

with t5:
    if st.button("Get Next Meal Advice"):
        with st.spinner("Thinking..."):
            advice = model.generate_content(f"I have {rem} cals left. Suggest a snack.")
            st.info(advice.text)

# --- 9. HISTORY ---
st.divider()
if st.session_state.food_history:
    with st.expander("📜 Today's History"):
        st.dataframe(pd.DataFrame(st.session_state.food_history), hide_index=True, use_container_width=True)
        if st.button("🗑️ Delete Last Item"):
            last = st.session_state.food_history.pop()
            st.session_state.total_calories -= last['Kcal']
            save_to_db()
            st.rerun()
