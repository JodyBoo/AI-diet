import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import pandas as pd

# --- SETUP & THEMING ---
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="VitalAI", page_icon="🥗", layout="centered")

# Custom CSS
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="stMetricValue"] { font-size: 24px; font-weight: 700; color: #2E7D32; }
    .stButton>button { width: 100%; border-radius: 12px; background-color: #2E7D32; color: white; }
    .metric-card {
        background-color: white;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        text-align: center;
        border: 1px solid #eee;
    }
    .weight-text { font-size: 1.2em; font-weight: bold; color: #1B5E20; }
    </style>
    """, unsafe_allow_html=True)

# --- DATA PERSISTENCE ---
if 'total_calories' not in st.session_state: st.session_state.total_calories = 0
if 'water_cups' not in st.session_state: st.session_state.water_cups = 0
if 'macros' not in st.session_state: st.session_state.macros = {"P": 0, "C": 0, "F": 0}
if 'food_history' not in st.session_state: st.session_state.food_history = []

# --- CORE LOGIC ---
def get_budget(w, target_w, h, a, g, act, pace):
    # Mifflin-St Jeor BMR
    bmr = (10*w + 6.25*h - 5*a + 5) if g == "Male" else (10*w + 6.25*h - 5*a - 161)
    acts = {"Sedentary": 1.2, "Lightly Active": 1.375, "Moderately Active": 1.55, "Very Active": 1.725}
    tdee = bmr * acts[act]
    
    # Determine if we are losing, maintaining, or gaining
    if w > target_w:
        adjustment = -(pace * 500) # Deficit
    elif w < target_w:
        adjustment = (pace * 500)  # Surplus
    else:
        adjustment = 0             # Maintenance
        
    return int(tdee + adjustment)

def log_food(name, cal, p, c, f, budget):
    st.session_state.total_calories += cal
    st.session_state.macros["P"] += p
    st.session_state.macros["C"] += c
    st.session_state.macros["F"] += f
    st.session_state.food_history.append({"Meal": name, "Calories": cal, "P": p, "C": c, "F": f})

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Profile")
    a = st.number_input("Age", 13, 100, 25)
    g = st.selectbox("Gender", ["Female", "Male"])
    h = st.number_input("Height (cm)", 100, 250, 170)
    
    st.divider()
    col_w1, col_w2 = st.columns(2)
    curr_w = col_w1.number_input("Current (kg)", 40.0, 200.0, 75.0)
    target_w = col_w2.number_input("Target (kg)", 40.0, 200.0, 70.0)
    
    act = st.selectbox("Activity", ["Sedentary", "Lightly Active", "Moderately Active", "Very Active"])
    pace = st.select_slider("Pace (lb/week)", options=[0, 0.5, 1.0, 1.5, 2.0], value=1.0)
    
    budget = get_budget(curr_w, target_w, h, a, g, act, pace)
    
    if st.button("🗑️ Reset Day"):
        st.session_state.clear()
        st.rerun()

# --- DASHBOARD HEADER ---
st.title("VitalAI Dashboard")

# Weight Progress Card
weight_diff = abs(curr_w - target_w)
weeks_left = (weight_diff / (pace * 0.45)) if pace > 0 else 0 # Converting lbs pace to kg approx

with st.container():
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.markdown(f"<div class='metric-card'>Current<br><span class='weight-text'>{curr_w} kg</span></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='metric-card'>Target<br><span class='weight-text'>{target_w} kg</span></div>", unsafe_allow_html=True)
    with c3:
        status_text = "to lose" if curr_w > target_w else "to gain"
        st.markdown(f"<div class='metric-card'>{weight_diff:.1f} kg {status_text}<br><b>~{int(weeks_left)} weeks</b></div>", unsafe_allow_html=True)

st.write("") # Spacer

# Calorie Metrics
m1, m2, m3 = st.columns(3)
m1.metric("Daily Goal", f"{budget} kcal")
m2.metric("Consumed", f"{st.session_state.total_calories}")
rem = budget - st.session_state.total_calories
m3.metric("Remaining", f"{rem}", delta=rem)

prog = min(st.session_state.total_calories / budget, 1.0) if budget > 0 else 0
st.progress(prog, text=f"{int(prog*100)}% of daily budget used")

# --- MACRO TILES ---
st.write("### Today's Nutrients")
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
m_col1.markdown(f"<div class='metric-card'>🍖 <b>Protein</b><br>{st.session_state.macros['P']}g</div>", unsafe_allow_html=True)
m_col2.markdown(f"<div class='metric-card'>🍞 <b>Carbs</b><br>{st.session_state.macros['C']}g</div>", unsafe_allow_html=True)
m_col3.markdown(f"<div class='metric-card'>🥑 <b>Fats</b><br>{st.session_state.macros['F']}g</div>", unsafe_allow_html=True)
m_col4.markdown(f"<div class='metric-card'>🥤 <b>Water</b><br>{st.session_state.water_cups} Cups</div>", unsafe_allow_html=True)

st.divider()

# --- ACTION TABS ---
tab1, tab2, tab3 = st.tabs(["📸 AI Photo Scan", "📝 Manual Entry", "💧 Add Water"])

with tab1:
    img = st.camera_input("Scan Meal")
    if img:
        with st.spinner("Analyzing..."):
            try:
                raw_img = Image.open(img)
                prompt = "Identify food. Return ONLY JSON: {\"name\":str, \"cal\":int, \"p\":int, \"c\":int, \"f\":int}"
                resp = model.generate_content([prompt, raw_img])
                data = json.loads(resp.text.strip().replace('```json', '').replace('```', ''))
                log_food(data['name'], data['cal'], data['p'], data['c'], data['f'], budget)
                st.rerun()
            except:
                st.error("AI Error. Please use manual entry.")

with tab2:
    with st.form("manual"):
        name = st.text_input("Food Name")
        c1, c2, c3, c4 = st.columns(4)
        kcal = c1.number_input("Kcal", 0, 2000, 250)
        p = c2.number_input("P", 0, 100, 10)
        c = c3.number_input("C", 0, 200, 20)
        f = c4.number_input("F", 0, 100, 5)
        if st.form_submit_button("Log Food"):
            log_food(name, kcal, p, c, f, budget)
            st.rerun()

with tab3:
    if st.button("🥤 Log 1 Cup (250ml)"):
        st.session_state.water_cups += 1
        st.rerun()

# --- HISTORY ---
if st.session_state.food_history:
    with st.expander("📜 Log History"):
        st.table(pd.DataFrame(st.session_state.food_history))
        if st.button("Remove Last Item"):
            st.session_state.food_history.pop()
            st.rerun()
