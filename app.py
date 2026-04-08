import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import pandas as pd

# --- SETUP ---
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="AI Health Coach", page_icon="🥗", layout="wide")

# --- DATA PERSISTENCE ---
if 'total_calories' not in st.session_state: st.session_state.total_calories = 0
if 'water_cups' not in st.session_state: st.session_state.water_cups = 0
if 'macros' not in st.session_state: st.session_state.macros = {"P": 0, "C": 0, "F": 0}
if 'food_history' not in st.session_state: st.session_state.food_history = []

# --- CALCULATOR LOGIC ---
def get_budget(w, h, a, g, act, pace):
    # Mifflin-St Jeor
    bmr = (10*w + 6.25*h - 5*a + 5) if g == "Male" else (10*w + 6.25*h - 5*a - 161)
    # Activity Multipliers
    acts = {
        "Sedentary (Little to no exercise)": 1.2,
        "Lightly Active (1-3 days/week)": 1.375,
        "Moderately Active (3-5 days/week)": 1.55,
        "Very Active (6-7 days/week)": 1.725
    }
    tdee = bmr * acts[act]
    # Pace: 1lb/week is roughly 500 calorie deficit
    return int(tdee - (pace * 500))

# --- SIDEBAR & GOALS ---
with st.sidebar:
    st.header("👤 Profile Settings")
    w = st.number_input("Weight (kg)", 40, 200, 70)
    h = st.number_input("Height (cm)", 100, 250, 170)
    a = st.number_input("Age", 15, 100, 25)
    g = st.selectbox("Gender", ["Male", "Female"])
    act = st.selectbox("Activity Level", [
        "Sedentary (Little to no exercise)", 
        "Lightly Active (1-3 days/week)", 
        "Moderately Active (3-5 days/week)", 
        "Very Active (6-7 days/week)"
    ])
    pace = st.slider("Weight Loss Pace (lb/week)", 0.0, 2.0, 1.0)
    
    budget = get_budget(w, h, a, g, act, pace)
    
    st.divider()
    if st.button("Reset Daily Progress", type="primary"):
        st.session_state.total_calories = 0
        st.session_state.water_cups = 0
        st.session_state.macros = {"P": 0, "C": 0, "F": 0}
        st.session_state.food_history = []
        st.rerun()

# --- DASHBOARD ---
st.title("🍎 My Daily Dashboard")

# Top Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Goal", f"{budget} kcal")
m2.metric("Consumed", f"{st.session_state.total_calories} kcal")
remaining = budget - st.session_state.total_calories
m3.metric("Remaining", f"{remaining} kcal", delta=remaining, delta_color="normal")
m4.metric("Water", f"{st.session_state.water_cups} 🥤")

# Progress Bar
progress_per = min(st.session_state.total_calories / budget, 1.0) if budget > 0 else 0
st.progress(progress_per, text=f"Daily Budget Used: {int(progress_per*100)}%")

# Water & Macro UI
col_a, col_b = st.columns([1, 2])

with col_a:
    st.subheader("Hydration")
    if st.button("🥤 Drink 1 Cup (250ml)", use_container_width=True):
        st.session_state.water_cups += 1
        st.rerun()

with col_b:
    st.subheader("Macro Breakdown")
    p, c, f = st.session_state.macros["P"], st.session_state.macros["C"], st.session_state.macros["F"]
    
    # Calculate a simple target (e.g., 30% P, 40% C, 30% F)
    mc1, mc2, mc3 = st.columns(3)
    mc1.write(f"🍖 **Protein**\n{p}g")
    mc2.write(f"🍞 **Carbs**\n{c}g")
    mc3.write(f"🥑 **Fats**\n{f}g")

# --- AI SCANNER ---
st.divider()
st.subheader("📸 Log a Meal")
img_file = st.camera_input("Scan your plate")
portion = st.text_input("Portion size? (e.g., 'half a plate', 'large bowl', '2 slices')", "1 standard serving")

if img_file:
    with st.spinner("Gemini is analyzing your meal..."):
        try:
            img = Image.open(img_file)
            # Instruct Gemini clearly to ensure valid JSON
            prompt = f"""
            Act as a nutritionist. Analyze this image for a {portion} portion.
            Identify the food and estimate calories and macros.
            Return ONLY a JSON object with this exact structure:
            {{"name": "food name", "cal": 0, "p": 0, "c": 0, "f": 0}}
            """
            
            resp = model.generate_content([prompt, img])
            # Cleaning the response text to handle potential markdown formatting
            clean_json = resp.text.strip().replace('```json', '').replace('```', '')
            data = json.loads(clean_json)
            
            # Log to state
            st.session_state.total_calories += data['cal']
            st.session_state.macros["P"] += data['p']
            st.session_state.macros["C"] += data['c']
            st.session_state.macros["F"] += data['f']
            
            # Save to history
            st.session_state.food_history.append({
                "Food": data['name'],
                "Calories": data['cal'],
                "P": data['p'], "C": data['c'], "F": data['f']
            })
            
            st.success(f"Logged {data['name']} ({data['cal']} kcal)!")
            st.rerun()
        except Exception as e:
            st.error(f"Could not analyze image. Please try again. Error: {e}")

# --- HISTORY TABLE ---
if st.session_state.food_history:
    st.divider()
    st.subheader("📜 Today's Log")
    df = pd.DataFrame(st.session_state.food_history)
    st.table(df)
