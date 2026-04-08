import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import pandas as pd

# --- SETUP & THEME ---
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="VitalAI Pro", page_icon="🥗", layout="centered")

# --- CUSTOM CSS (Consolidated Green Theme) ---
st.markdown("""
    <style>
    html, body, [class*="st-"] { color: #2E7D32 !important; }
    h1, h2, h3 { color: #1B5E20 !important; }
    .stButton>button { border-radius: 20px; background-color: #2E7D32; color: white !important; font-weight: bold; border: none; width: 100%; }
    .stButton>button:hover { background-color: #1B5E20; color: white !important; }
    .metric-card { background-color: #F1F8E9; padding: 15px; border-radius: 12px; text-align: center; border: 1px solid #C8E6C9; height: 100%; }
    .label-box { background-color: #ffffff; border: 2px dashed #2E7D32; padding: 15px; border-radius: 10px; }
    div[data-testid="stMetricValue"] { color: #1B5E20 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- DATA PERSISTENCE (Safe initialization) ---
if 'total_calories' not in st.session_state: st.session_state.total_calories = 0
if 'burned_calories' not in st.session_state: st.session_state.burned_calories = 0
if 'water_cups' not in st.session_state: st.session_state.water_cups = 0
if 'macros' not in st.session_state: st.session_state.macros = {"P": 0, "C": 0, "F": 0}
if 'food_history' not in st.session_state: st.session_state.food_history = []

# --- CORE LOGIC ---
def get_health_stats(w, target_w, h, a, g, act, pace):
    # BMI FIX: More granular categories
    bmi = w / ((h/100)**2)
    if bmi < 18.5: bmi_cat = "Underweight"
    elif 18.5 <= bmi < 25: bmi_cat = "Healthy Weight"
    elif 25 <= bmi < 30: bmi_cat = "Overweight"
    else: bmi_cat = "Obese"
    
    # Budget Logic (Mifflin-St Jeor)
    bmr = (10*w + 6.25*h - 5*a + 5) if g == "Male" else (10*w + 6.25*h - 5*a - 161)
    acts = {"Sedentary": 1.2, "Lightly Active": 1.375, "Moderately Active": 1.55, "Very Active": 1.725}
    tdee = bmr * acts[act]
    
    # Calculate Adjustment based on Target
    if w > target_w: # Loss
        adj = -(pace * 500)
    elif w < target_w: # Gain
        adj = (pace * 500)
    else:
        adj = 0
        
    return int(tdee + adj), bmi, bmi_cat

def log_food(name, cal, p, c, f):
    st.session_state.total_calories += cal
    st.session_state.macros["P"] += p
    st.session_state.macros["C"] += c
    st.session_state.macros["F"] += f
    st.session_state.food_history.append({"Meal": name, "Kcal": cal, "P": p, "C": c, "F": f})

# --- SIDEBAR ---
with st.sidebar:
    st.title("🍏 Your Profile")
    a = st.number_input("Age", 13, 100, 25)
    g = st.selectbox("Gender", ["Female", "Male"])
    h = st.number_input("Height (cm)", 100, 250, 170)
    curr_w = st.number_input("Current Weight (kg)", 40.0, 200.0, 75.0)
    target_w = st.number_input("Target Weight (kg)", 40.0, 200.0, 70.0)
    act = st.selectbox("Activity Level", ["Sedentary", "Lightly Active", "Moderately Active", "Very Active"])
    pace = st.select_slider("Pace (lb/week)", options=[0, 0.5, 1.0, 1.5, 2.0], value=1.0)
    
    budget, bmi, bmi_cat = get_health_stats(curr_w, target_w, h, a, g, act, pace)
    
    st.divider()
    if st.button("🔄 Reset Daily Progress"):
        # We only clear the daily stats, not the profile settings
        st.session_state.total_calories = 0
        st.session_state.burned_calories = 0
        st.session_state.water_cups = 0
        st.session_state.macros = {"P": 0, "C": 0, "F": 0}
        st.session_state.food_history = []
        st.rerun()

# --- MAIN DASHBOARD ---
st.title("VitalAI Coach 🌿")

# Status Cards
c1, c2, c3 = st.columns(3)
with c1: 
    st.markdown(f"<div class='metric-card'><b>BMI: {bmi:.1f}</b><br><small>{bmi_cat}</small></div>", unsafe_allow_html=True)
with c2: 
    st.markdown(f"<div class='metric-card'><b>Budget: {budget}</b><br><small>Goal kcal</small></div>", unsafe_allow_html=True)
with c3:
    net = st.session_state.total_calories - st.session_state.burned_calories
    rem = budget - net
    st.markdown(f"<div class='metric-card'><b>Remaining: {rem}</b><br><small>kcal</small></div>", unsafe_allow_html=True)

st.write("") # Spacer

# --- ACTION TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📸 Photo Scan", "🏷️ Label Scan", "📝 Manual", "🏃 Exercise", "🤖 Advice"])

with tab1:
    img = st.camera_input("Scan Plate", key="plate")
    if img:
        with st.spinner("AI analyzing..."):
            try:
                raw_img = Image.open(img)
                prompt = "Identify food. Return ONLY valid JSON: {\"name\":str, \"cal\":int, \"p\":int, \"c\":int, \"f\":int}"
                resp = model.generate_content([prompt, raw_img])
                # Clean AI output
                clean_text = resp.text.strip().replace('```json', '').replace('```', '')
                data = json.loads(clean_text)
                log_food(data['name'], data['cal'], data['p'], data['c'], data['f'])
                st.rerun()
            except: st.error("Scanning failed. Try again or use manual.")

with tab2:
    label_img = st.camera_input("Scan Nutrition Label", key="label")
    serving_mult = st.number_input("How many servings?", 0.5, 10.0, 1.0, step=0.5)
    if label_img:
        with st.spinner("Reading label..."):
            try:
                raw_label = Image.open(label_img)
                label_prompt = f"Extract nutrition info. Multiply by {serving_mult}. Return JSON: {{\"name\":str, \"cal\":int, \"p\":int, \"c\":int, \"f\":int}}"
                resp = model.generate_content([label_prompt, raw_label])
                clean_label = resp.text.strip().replace('```json', '').replace('```', '')
                data = json.loads(clean_label)
                log_food(data['name'], data['cal'], data['p'], data['c'], data['f'])
                st.rerun()
            except: st.error("Couldn't read label.")

with tab3:
    with st.form("manual"):
        name = st.text_input("Meal Name")
        ca, cb, cc, cd = st.columns(4)
        kcal = ca.number_input("Kcal", 0, 2000, 250)
        p = cb.number_input("P", 0, 100, 10)
        c = cc.number_input("C", 0, 200, 20)
        f = cd.number_input("F", 0, 100, 5)
        if st.form_submit_button("Log"):
            log_food(name, kcal, p, c, f)
            st.rerun()

with tab4:
    ex_name = st.text_input("Activity Name")
    ex_burn = st.number_input("Calories Burned", 0, 2000, 200)
    if st.button("Log Workout"):
        st.session_state.burned_calories += ex_burn
        st.rerun()

with tab5:
    st.write("### AI Coach Advice")
    if st.button("Get advice for my next meal"):
        advice_p = f"User has {rem} cals left, current macros: {st.session_state.macros}. Suggest a meal."
        advice = model.generate_content(advice_p)
        st.info(advice.text)

# --- VISUALS (Native Streamlit Version - BUG FIX) ---
st.divider()
v1, v2 = st.columns([2, 1])

with v1:
    st.write("**Macro Balance (Grams)**")
    if st.session_state.total_calories > 0:
        # Native Bar Chart (No Plotly needed)
        chart_data = pd.DataFrame({
            'Macros': ['Protein', 'Carbs', 'Fats'],
            'Grams': [st.session_state.macros["P"], st.session_state.macros["C"], st.session_state.macros["F"]]
        }).set_index('Macros')
        st.bar_chart(chart_data, color="#2E7D32")
    else:
        st.caption("No food logged yet.")

with v2:
    st.write("**Hydration**")
    st.markdown(f"<h2>💧 {st.session_state.water_cups} <small>Cups</small></h2>", unsafe_allow_html=True)
    if st.button("🥤 +1 Cup"):
        st.session_state.water_cups += 1
        st.rerun()

# --- HISTORY ---
if st.session_state.food_history:
    with st.expander("📜 View Log History"):
        st.dataframe(pd.DataFrame(st.session_state.food_history), use_container_width=True, hide_index=True)
        if st.button("🗑️ Remove Last Item"):
            last = st.session_state.food_history.pop()
            st.session_state.total_calories -= last['Kcal']
            st.session_state.macros["P"] -= last['P']
            st.session_state.macros["C"] -= last['C']
            st.session_state.macros["F"] -= last['F']
            st.rerun()
