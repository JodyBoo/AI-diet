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

# Connect to Supabase
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.set_page_config(page_title="VitalAI Pro", page_icon="🥗", layout="centered")

# --- 2. DATABASE FUNCTIONS ---
def load_today_data():
    """Checks DB for today's entry and loads into session state"""
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
    except Exception as e:
        print(f"Empty or Error: {e}")
    return False

def save_to_db():
    """Saves current state to DB (Upsert)"""
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

# --- 3. DATA PERSISTENCE INITIALIZATION ---
if 'db_loaded' not in st.session_state:
    if not load_today_data():
        st.session_state.total_calories = 0
        st.session_state.water_cups = 0
        st.session_state.macros = {"P": 0, "C": 0, "F": 0}
        st.session_state.food_history = []
    st.session_state.db_loaded = True

# --- 4. CUSTOM CSS ---
st.markdown("""
    <style>
    html, body, [class*="st-"] { color: #2E7D32 !important; }
    h1, h2, h3 { color: #1B5E20 !important; }
    .stButton>button { border-radius: 20px; background-color: #2E7D32; color: white !important; font-weight: bold; border: none; }
    .metric-card { background-color: #F1F8E9; padding: 15px; border-radius: 12px; text-align: center; border: 1px solid #C8E6C9; }
    </style>
    """, unsafe_allow_html=True)

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
    save_to_db() # PERSISTENCE!

# --- 6. SIDEBAR ---
with st.sidebar:
    st.title("🍏 Profile")
    a = st.number_input("Age", 13, 100, 25)
    g = st.selectbox("Gender", ["Female", "Male"])
    h = st.number_input("Height (cm)", 100, 250, 170)
    curr_w = st.number_input("Current Weight (kg)", 40.0, 200.0, 75.0)
    target_w = st.number_input("Target Weight (kg)", 40.0, 200.0, 70.0)
    act = st.selectbox("Activity Level", ["Sedentary", "Lightly Active", "Moderately Active", "Very Active"])
    pace = st.select_slider("Pace (lb/week)", options=[0, 0.5, 1.0, 1.5, 2.0], value=1.0)
    
    budget, bmi, bmi_cat = get_health_stats(curr_w, target_w, h, a, g, act, pace)
    
    if st.button("🔄 Clear Today's Log"):
        # This deletes the row in the DB for today
        supabase.table("health_logs").delete().eq("log_date", str(date.today())).execute()
        st.session_state.clear()
        st.rerun()

# --- 7. MAIN DASHBOARD ---
st.title("VitalAI Pro 🌿")

c1, c2, c3 = st.columns(3)
with c1: st.markdown(f"<div class='metric-card'><b>BMI: {bmi:.1f}</b><br><small>{bmi_cat}</small></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div class='metric-card'><b>Budget: {budget}</b><br><small>Goal</small></div>", unsafe_allow_html=True)
with c3:
    rem = budget - st.session_state.total_calories
    st.markdown(f"<div class='metric-card'><b>Left: {rem}</b><br><small>kcal</small></div>", unsafe_allow_html=True)

# --- 8. ACTION TABS ---
t1, t2, t3, t4 = st.tabs(["📸 Photo", "📝 Manual", "🏃 Exercise", "🤖 Coach"])

with t1:
    img = st.camera_input("Scan Plate", key="plate")
    if img:
        with st.spinner("AI analyzing..."):
            try:
                raw_img = Image.open(img)
                prompt = "Identify food. Return JSON: {\"name\":str, \"cal\":int, \"p\":int, \"c\":int, \"f\":int}"
                resp = model.generate_content([prompt, raw_img])
                data = json.loads(resp.text.strip().replace('```json', '').replace('```', ''))
                log_food(data['name'], data['cal'], data['p'], data['c'], data['f'])
                st.rerun()
            except: st.error("Scanning failed.")

with t2:
    with st.form("manual"):
        name = st.text_input("Meal Name")
        ca, cb, cc, cd = st.columns(4)
        kcal = ca.number_input("Kcal", 0, 2000, 250)
        if st.form_submit_button("Log"):
            log_food(name, kcal, 10, 20, 5) # Default macros for brevity
            st.rerun()

with t3:
    burn = st.number_input("Burned calories", 0, 2000, 200)
    if st.button("Log Workout"):
        st.session_state.total_calories -= burn # Exercise adds back to budget
        save_to_db()
        st.rerun()

with t4:
    if st.button("Get AI Advice"):
        advice = model.generate_content(f"I have {rem} cals left. Suggest a snack.")
        st.info(advice.text)

# --- 9. VISUALS ---
st.divider()
v1, v2 = st.columns([2, 1])
with v1:
    st.write("**Macro Balance**")
    if st.session_state.total_calories > 0:
        st.bar_chart(pd.DataFrame({'G': [st.session_state.macros["P"], st.session_state.macros["C"], st.session_state.macros["F"]]}, index=['P', 'C', 'F']))
with v2:
    st.write("**Water**")
    st.markdown(f"<h2>💧 {st.session_state.water_cups}</h2>", unsafe_allow_html=True)
    if st.button("🥤 +1"):
        st.session_state.water_cups += 1
        save_to_db()
        st.rerun()

if st.session_state.food_history:
    with st.expander("📜 Today's Log"):
        st.table(pd.DataFrame(st.session_state.food_history))
