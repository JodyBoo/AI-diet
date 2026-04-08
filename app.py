import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import pandas as pd
import plotly.express as px

# --- SETUP & THEMING ---
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="VitalAI Pro", page_icon="🥗", layout="centered")

# --- CUSTOM GREEN CSS ---
st.markdown("""
    <style>
    html, body, [class*="st-"] { color: #2E7D32; font-family: 'Helvetica Neue', Arial, sans-serif; }
    h1, h2, h3 { color: #1B5E20 !important; }
    .stButton>button { border-radius: 20px; background-color: #2E7D32; color: white !important; font-weight: bold; }
    .metric-card { background-color: #F1F8E9; padding: 20px; border-radius: 15px; text-align: center; border: 1px solid #C8E6C9; }
    .label-box { background-color: #ffffff; border: 2px dashed #2E7D32; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- DATA PERSISTENCE ---
if 'total_calories' not in st.session_state: st.session_state.total_calories = 0
if 'burned_calories' not in st.session_state: st.session_state.burned_calories = 0
if 'water_cups' not in st.session_state: st.session_state.water_cups = 0
if 'macros' not in st.session_state: st.session_state.macros = {"P": 0, "C": 0, "F": 0}
if 'food_history' not in st.session_state: st.session_state.food_history = []

# --- CORE LOGIC ---
def get_health_stats(w, target_w, h, a, g, act, pace):
    bmi = w / ((h/100)**2)
    bmi_cat = "Normal" if 18.5 <= bmi <= 24.9 else "Underweight" if bmi < 18.5 else "Overweight"
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

# --- SIDEBAR ---
with st.sidebar:
    st.title("🍏 VitalAI Profile")
    a = st.number_input("Age", 13, 100, 25)
    g = st.selectbox("Gender", ["Female", "Male"])
    h = st.number_input("Height (cm)", 100, 250, 170)
    curr_w = st.number_input("Current Weight (kg)", 40.0, 200.0, 75.0)
    target_w = st.number_input("Target Weight (kg)", 40.0, 200.0, 70.0)
    act = st.selectbox("Activity Level", ["Sedentary", "Lightly Active", "Moderately Active", "Very Active"])
    pace = st.select_slider("Pace (lb/week)", options=[0, 0.5, 1.0, 1.5, 2.0], value=1.0)
    
    budget, bmi, bmi_cat = get_health_stats(curr_w, target_w, h, a, g, act, pace)
    
    if st.button("🔄 Reset Daily Log"):
        st.session_state.clear()
        st.rerun()

# --- MAIN DASHBOARD ---
st.title("VitalAI Coach Pro 🌿")

# Status Cards
c1, c2, c3 = st.columns(3)
with c1: st.markdown(f"<div class='metric-card'><b>BMI: {bmi:.1f}</b><br><small>{bmi_cat}</small></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div class='metric-card'><b>Budget: {budget}</b><br><small>kcal/day</small></div>", unsafe_allow_html=True)
with c3:
    net = st.session_state.total_calories - st.session_state.burned_calories
    rem = budget - net
    st.markdown(f"<div class='metric-card'><b>Left: {rem}</b><br><small>kcal</small></div>", unsafe_allow_html=True)

st.divider()

# --- INTERACTIVE TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📸 Photo", "🏷️ Label Scan", "📝 Manual", "🏃 Exercise", "🤖 Coach"])

with tab1:
    st.write("### AI Plate Scanner")
    img = st.camera_input("Take a photo of your food", key="plate_cam")
    if img:
        with st.spinner("AI analyzing plate..."):
            raw_img = Image.open(img)
            prompt = "Identify food. Return JSON: {\"name\":str, \"cal\":int, \"p\":int, \"c\":int, \"f\":int}"
            resp = model.generate_content([prompt, raw_img])
            data = json.loads(resp.text.strip().replace('```json', '').replace('```', ''))
            log_food(data['name'], data['cal'], data['p'], data['c'], data['f'])
            st.rerun()

with tab2:
    st.write("### Nutrition Label AI")
    st.info("Point camera at the 'Nutrition Facts' table on any package.")
    label_img = st.camera_input("Scan Nutrition Label", key="label_cam")
    servings = st.number_input("How many servings did you eat?", 1.0, 10.0, 1.0)
    
    if label_img:
        with st.spinner("Reading Nutrition Label..."):
            raw_label = Image.open(label_img)
            # Refined prompt for label OCR
            label_prompt = f"""
            Extract information from this Nutrition Facts label. 
            Multiply all values by {servings} servings.
            Return ONLY a JSON object: 
            {{"name": "Product Name", "cal": total_calories, "p": total_protein, "c": total_carbs, "f": total_fat}}
            """
            resp = model.generate_content([label_prompt, raw_label])
            try:
                data = json.loads(resp.text.strip().replace('```json', '').replace('```', ''))
                log_food(data['name'], data['cal'], data['p'], data['c'], data['f'])
                st.success(f"Successfully logged {data['name']}!")
                st.rerun()
            except:
                st.error("Could not read label. Please ensure the 'Nutrition Facts' table is clear.")

with tab3:
    with st.form("manual_entry"):
        f_name = st.text_input("Meal Name")
        c_a, c_b, c_c, c_d = st.columns(4)
        f_cal = c_a.number_input("Kcal", 0, 2000, 250)
        f_p = c_b.number_input("P(g)", 0, 100, 10)
        f_c = c_c.number_input("C(g)", 0, 200, 20)
        f_f = c_d.number_input("F(g)", 0, 100, 5)
        if st.form_submit_button("Log Meal"):
            log_food(f_name, f_cal, f_p, f_c, f_f)
            st.rerun()

with tab4:
    ex_name = st.text_input("Workout Type")
    ex_burn = st.number_input("Kcal Burned", 0, 2000, 200)
    if st.button("Log Workout"):
        st.session_state.burned_calories += ex_burn
        st.rerun()

with tab5:
    query = st.text_input("Ask about your diet:")
    if st.button("Get AI Advice"):
        advice = model.generate_content(f"Current Status: {rem} cals left, BMI {bmi:.1f}. User asks: {query}")
        st.info(advice.text)

# --- VISUALS (Native Streamlit Version - No Plotly Required) ---
st.divider()
col_left, col_right = st.columns([1, 1])

with col_left:
    st.write("### Macros")
    if st.session_state.total_calories > 0:
        # Create a simple vertical bar chart using native Streamlit
        macro_counts = {
            "Protein": [st.session_state.macros["P"]],
            "Carbs": [st.session_state.macros["C"]],
            "Fats": [st.session_state.macros["F"]]
        }
        st.bar_chart(pd.DataFrame(macro_counts), height=200)
    else:
        st.info("Log food to see balance")

with col_right:
    st.markdown(f"<div class='metric-card'>💧 <b>Hydration</b><br>{st.session_state.water_cups}/8 Cups</div>", unsafe_allow_html=True)
    if st.button("🥤 Drink Water"):
        st.session_state.water_cups += 1
        st.rerun()
