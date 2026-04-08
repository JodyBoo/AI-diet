import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import pandas as pd

# --- SETUP & THEMING ---
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="VitalAI", page_icon="🥗", layout="centered")

# Custom CSS for a "Mobile App" feel
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="stMetricValue"] { font-size: 28px; font-weight: 700; color: #2E7D32; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; background-color: #2E7D32; color: white; border: none; }
    .stButton>button:hover { background-color: #1b5e20; color: white; }
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
    .status-warning { color: #d32f2f; font-weight: bold; }
    .status-ok { color: #2E7D32; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- DATA PERSISTENCE ---
if 'total_calories' not in st.session_state: st.session_state.total_calories = 0
if 'water_cups' not in st.session_state: st.session_state.water_cups = 0
if 'macros' not in st.session_state: st.session_state.macros = {"P": 0, "C": 0, "F": 0}
if 'food_history' not in st.session_state: st.session_state.food_history = []

# --- CORE LOGIC ---
def log_food(name, cal, p, c, f, budget):
    is_dense = cal > (budget * 0.4)
    st.session_state.total_calories += cal
    st.session_state.macros["P"] += p
    st.session_state.macros["C"] += c
    st.session_state.macros["F"] += f
    st.session_state.food_history.append({
        "Meal": name, "Calories": cal, "P": p, "C": c, "F": f,
        "Status": "⚠️ High Cal" if is_dense else "✅ Balanced"
    })
    return is_dense

def get_budget(w, h, a, g, act, pace):
    bmr = (10*w + 6.25*h - 5*a + 5) if g == "Male" else (10*w + 6.25*h - 5*a - 161)
    acts = {"Sedentary": 1.2, "Lightly Active": 1.375, "Moderately Active": 1.55, "Very Active": 1.725}
    return int((bmr * acts[act]) - (pace * 500))

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Settings")
    a = st.number_input("Age", 13, 100, 25)
    g = st.selectbox("Gender", ["Female", "Male"])
    w = st.number_input("Weight (kg)", 40.0, 200.0, 70.0)
    h = st.number_input("Height (cm)", 100, 250, 170)
    act = st.selectbox("Activity", ["Sedentary", "Lightly Active", "Moderately Active", "Very Active"])
    pace = st.select_slider("Pace", options=[0, 0.5, 1, 1.5, 2], value=1, help="Lbs per week loss")
    
    budget = get_budget(w, h, a, g, act, pace)
    
    st.divider()
    if st.sidebar.button("🗑️ Reset Day"):
        st.session_state.clear()
        st.rerun()

# --- HEADER SECTION ---
st.title("Good Morning! 👋")
st.subheader(f"Target: {budget} kcal")

# Main Metric "Cards"
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Consumed", f"{st.session_state.total_calories}")
with col2:
    rem = budget - st.session_state.total_calories
    st.metric("Remaining", f"{rem}", delta=rem, delta_color="normal")
with col3:
    st.metric("Hydration", f"{st.session_state.water_cups} 🥤")

# Progress bar with color logic
prog = min(st.session_state.total_calories / budget, 1.0) if budget > 0 else 0
st.progress(prog)

# --- MACRO TILES ---
st.write("### Today's Nutrients")
m_col1, m_col2, m_col3 = st.columns(3)
m_col1.markdown(f"<div class='metric-card'>🍖 <b>Protein</b><br>{st.session_state.macros['P']}g</div>", unsafe_allow_html=True)
m_col2.markdown(f"<div class='metric-card'>🍞 <b>Carbs</b><br>{st.session_state.macros['C']}g</div>", unsafe_allow_html=True)
m_col3.markdown(f"<div class='metric-card'>🥑 <b>Fats</b><br>{st.session_state.macros['F']}g</div>", unsafe_allow_html=True)

st.divider()

# --- ACTION SECTION ---
tab1, tab2, tab3 = st.tabs(["📸 AI Scan", "📝 Manual", "💧 Water"])

with tab1:
    img = st.camera_input("Quick Scan")
    if img:
        with st.spinner("Analyzing Plate..."):
            try:
                raw_img = Image.open(img)
                prompt = "Identify food. Return ONLY JSON: {\"name\":str, \"cal\":int, \"p\":int, \"c\":int, \"f\":int}"
                resp = model.generate_content([prompt, raw_img])
                data = json.loads(resp.text.strip().replace('```json', '').replace('```', ''))
                log_food(data['name'], data['cal'], data['p'], data['c'], data['f'], budget)
                st.rerun()
            except:
                st.error("AI couldn't see the food clearly. Try again!")

with tab2:
    with st.container(border=True):
        name = st.text_input("What did you eat?")
        c1, c2, c3, c4 = st.columns(4)
        kcal = c1.number_input("Kcal", 0, 2000, 250)
        p = c2.number_input("P(g)", 0, 100, 10)
        c = c3.number_input("C(g)", 0, 200, 20)
        f = c4.number_input("F(g)", 0, 100, 5)
        if st.button("Add to Log"):
            log_food(name, kcal, p, c, f, budget)
            st.rerun()

with tab3:
    st.write("Goal: 8+ Cups")
    if st.button("➕ Add 1 Cup of Water"):
        st.session_state.water_cups += 1
        st.rerun()

# --- HISTORY & COACHING ---
if st.session_state.food_history:
    st.divider()
    with st.expander("📜 View Today's Log", expanded=True):
        history_df = pd.DataFrame(st.session_state.food_history)
        st.dataframe(history_df, use_container_width=True, hide_index=True)
        if st.button("Clear Last Entry"):
            st.session_state.food_history.pop()
            st.rerun()

    # Smart Coach Logic
    st.write("### 🤖 AI Coach Advice")
    if rem > 200:
        if st.session_state.macros['P'] < 50:
            st.info("You're low on protein today. Try a Greek yogurt or some grilled chicken for your next snack!")
        else:
            st.info(f"You have {rem} calories left. A light balanced dinner would be perfect.")
    elif rem <= 0:
        st.warning("Daily budget reached! Focus on hydration and fiber-rich greens if you're still hungry.")
