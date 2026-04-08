import streamlit as st
import google.generativeai as genai
from PIL import Image
import json

# --- SETUP ---
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"]) # Use Streamlit Secrets for security
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="AI Health Coach", page_icon="⚖️")

# --- DATA PERSISTENCE ---
if 'total_calories' not in st.session_state: st.session_state.total_calories = 0
if 'water_cups' not in st.session_state: st.session_state.water_cups = 0
if 'macros' not in st.session_state: st.session_state.macros = {"P": 0, "C": 0, "F": 0}

# --- CALCULATOR LOGIC ---
def get_budget(w, h, a, g, act, pace):
    bmr = (10*w + 6.25*h - 5*a + 5) if g == "Male" else (10*w + 6.25*h - 5*a - 161)
    acts = {"Sedentary": 1.2, "Active": 1.5}
    return int((bmr * acts[act]) - (pace * 500))

# --- SIDEBAR & GOALS ---
st.sidebar.header("👤 Profile")
w = st.sidebar.number_input("Weight (kg)", 70)
h = st.sidebar.number_input("Height (cm)", 170)
a = st.sidebar.number_input("Age", 25)
g = st.sidebar.selectbox("Gender", ["Male", "Female"])
pace = st.sidebar.slider("Pace (lb/week)", 0.0, 2.0, 1.0)
budget = get_budget(w, h, a, g, "Active", pace)

# --- DASHBOARD ---
st.title("My Daily Stats")
c1, c2, c3 = st.columns(3)
c1.metric("Budget", f"{budget}")
c2.metric("Left", f"{budget - st.session_state.total_calories}")
c3.metric("Water", f"{st.session_state.water_cups} 🥤")

# Water Button
if st.button("+ Add Water Cup"):
    st.session_state.water_cups += 1
    st.rerun()

# Macro Breakdown
p, c, f = st.session_state.macros["P"], st.session_state.macros["C"], st.session_state.macros["F"]
st.write(f"**Macros:** 🍖 {p}g | 🍞 {c}g | 🥑 {f}g")

# --- AI SCANNER ---
st.divider()
img_file = st.camera_input("Take a photo of your meal") # Uses phone camera directly!
portion = st.text_input("Portion?", "1 serving")

if img_file:
    with st.spinner("Analyzing..."):
        img = Image.open(img_file)
        prompt = f"Identify food. Portion: {portion}. Return JSON only: {{\"name\":str, \"cal\":int, \"p\":int, \"c\":int, \"f\":int}}"
        resp = model.generate_content([prompt, img])
        data = json.loads(resp.text.replace('```json', '').replace('```', ''))
        
        # Log it
        st.session_state.total_calories += data['cal']
        st.session_state.macros["P"] += data['p']
        st.session_state.macros["C"] += data['c']
        st.session_state.macros["F"] += data['f']
        st.success(f"Logged {data['name']}!")
        st.rerun()
