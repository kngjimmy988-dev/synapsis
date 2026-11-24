import streamlit as st
import numpy as np
import urllib.request
import urllib.parse
import json
import io
from PIL import Image, ImageFilter, ImageDraw
import requests 
from groq import Groq

# --- PAGE CONFIG ---
st.set_page_config(page_title="Virtual Studio", page_icon="🎬", layout="wide") # Using WIDE layout for a studio feel

# --- SECURE API KEY LOADING ---
try:
    REMOVEBG_API_KEY = st.secrets["REMOVEBG_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    REMOVEBG_API_KEY = "YOUR_REMOVEBG_API_KEY"
    GROQ_API_KEY = "YOUR_GROQ_API_KEY"

# --- CUSTOM CSS FOR STUDIO UI ---
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        background-color: #00E5FF; /* Electric Cyan */
        color: black;
        font-size: 18px;
        border-radius: 8px;
        height: 45px;
        font-weight: bold;
    }
    h1, h2, h3 { color: #FFFFFF; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 18px;
        color: #A0A0A0;
    }
    .stTabs [aria-selected="true"] {
        color: #00E5FF;
    }
    </style>
    """, unsafe_allow_html=True)

# --- THE AI DIRECTOR (GROQ) ---
def direct_prompt(user_idea):
    if GROQ_API_KEY == "YOUR_GROQ_API_KEY": return user_idea 
    try:
        client = Groq(api_key=GROQ_API_KEY)
        prompt = f"""
        You are an expert Hollywood VFX director. Rewrite the user's idea into a highly detailed, cinematic image generation prompt.
        You MUST include: Photorealistic, 8k resolution, cinematic lighting, eye-level camera angle, clear flat empty ground in the lower foreground, no text, no watermarks.
        User's idea: "{user_idea}"
        Return ONLY the detailed prompt text.
        """
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-oss-20b",
            temperature=0.7,
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"Director Error: {e}")
        return user_idea

# --- HELPER FUNCTIONS ---
def remove_green_screen(img):
    img = img.convert("RGBA")
    data = np.array(img)
    r, g, b = data[:, :, 0].astype(int), data[:, :, 1].astype(int), data[:, :, 2].astype(int)
    green_mask = (g > r + 60) & (g > b + 60)
    mask_data = np.where(green_mask, 0, 255).astype(np.uint8)
    mask_img = Image.fromarray(mask_data).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(radius=1))
    data[:, :, 3] = np.array(mask_img)
    semi_green = (g > r) & (g > b) & (data[:, :, 3] > 0)
    avg_rb = (r + b) // 2
    data[:, :, 1] = np.where(semi_green, avg_rb, data[:, :, 1])
    return Image.fromarray(data)

def remove_bg_ai(image_bytes):
    if REMOVEBG_API_KEY == "YOUR_REMOVEBG_API_KEY" or not REMOVEBG_API_KEY: return None
    try:
        response = requests.post(
            'https://api.remove.bg/v1.0/removebg',
            files={'image_file': image_bytes},
            data={'size': 'auto'},
            headers={'X-Api-Key': REMOVEBG_API_KEY},
        )
        if response.status_code == requests.codes.ok:
            return Image.open(io.BytesIO(response.content)).convert("RGBA")
        return None
    except Exception:
        return None

def generate_ai_background(prompt):
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1080&nologo=true"
        req = urllib.request.Request(url, headers={'User-Agent': 'VFXApp/1.0'})
        with urllib.request.urlopen(req) as img_response:
            img = Image.open(io.BytesIO(img_response.read())).convert("RGB")
            img = img.crop((0, 0, img.width, img.height - 40)) # Watermark killer
            return img
    except Exception:
        return None

def create_composite(person, background, scale, x_pos, y_pos, sun_angle, sink):
    width, height = background.size
    bbox = person.getbbox()
    if bbox: person = person.crop(bbox)
    target_height = int(height * scale)
    person_width = int(person.width * (target_height / person.height))
    person = person.resize((person_width, target_height), Image.Resampling.LANCZOS)
    if sink > 0:
        new_height = max(10, target_height - sink)
        person = person.crop((0, 0, person_width, new_height))
        target_height = new_height 
    person_data = np.array(person).astype(np.float32)
    gradient = np.linspace(1.15, 0.85, person_width) 
    for i in range(3): person_data[:, :, i] = person_data[:, :, i] * gradient
    person = Image.fromarray(np.clip(person_data, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=0.8))
    cast_shadow = Image.new("RGBA", person.size, (0, 0, 0, 0))
    cast_shadow.putalpha(person.split()[3]) 
    cast_shadow = cast_shadow.resize((int(person_width * 1.5), int(target_height * 0.2)), Image.Resampling.LANCZOS)
    cast_shadow = cast_shadow.rotate(sun_angle, expand=True, resample=Image.BICUBIC).filter(ImageFilter.GaussianBlur(radius=8))
    shadow_data = np.array(cast_shadow)
    shadow_data[:, :, 0:3] = [10, 20, 40]
    shadow_data[:, :, 3] = np.where(np.clip(shadow_data[:, :, 3] * 0.4, 0, 255) < 15, 0, np.clip(shadow_data[:, :, 3] * 0.4, 0, 255))
    cast_shadow = Image.fromarray(shadow_data)
    contact_shadow = Image.new("RGBA", (person_width, 40), (0, 0, 0, 0))
    ImageDraw.Draw(contact_shadow).ellipse([10, 10, person_width-10, 35], fill=(0, 0, 0, 200))
    contact_shadow = contact_shadow.filter(ImageFilter.GaussianBlur(radius=3))
    background = background.filter(ImageFilter.GaussianBlur(radius=1.5))
    bg_data = np.array(background).astype(np.float32)
    vignette = Image.new('L', (width, height), 0)
    ImageDraw.Draw(vignette).ellipse([-width//4, -height//4, width + width//4, height + height//4], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=100))
    vig_data = np.array(vignette).astype(np.float32) / 255.0
    for i in range(3): bg_data[:, :, i] = bg_data[:, :, i] * (0.7 + (0.3 * vig_data))
    background = Image.fromarray(np.clip(bg_data, 0, 255).astype(np.uint8))
    x_offset = int((width * x_pos) - (person_width / 2))
    y_offset = int((height * y_pos) - target_height) + sink
    background.paste(cast_shadow, (x_offset - int(cast_shadow.width * 0.4), y_offset + target_height - int(cast_shadow.height * 0.8) + sink), cast_shadow)
    background.paste(contact_shadow, (x_offset, y_offset + target_height - 20), contact_shadow)
    background.paste(person, (x_offset, y_offset), person)
    return background

# --- V3 UI: THE VIRTUAL STUDIO ---
st.title("🎬 Virtual Studio")
st.markdown("*A mobile-first creative production environment.*")

# Use columns to create a dominant Canvas area
col_canvas, col_controls = st.columns([2, 1])

# Initialize session states
if 'bg_img' not in st.session_state: st.session_state['bg_img'] = None
if 'cutout' not in st.session_state: st.session_state['cutout'] = None

with col_canvas:
    st.subheader("Scene Canvas")
    if st.session_state['bg_img'] and st.session_state['cutout']:
        # If both exist, show a placeholder for the final render
        st.info("✅ Subject and Environment loaded. Adjust tools on the right, then click 'Render Scene'.")
        # Show a stacked preview
        preview = st.session_state['bg_img'].copy()
        st.image(preview, caption="Environment Preview (Subject will be rendered here)", use_column_width=True)
    elif st.session_state['bg_img']:
        st.image(st.session_state['bg_img'], caption="Environment", use_column_width=True)
    else:
        st.info("👈 Start by generating an environment or uploading your subject.")

with col_controls:
    st.subheader("Studio Tools")
    
    # THE TABS (Contextual Tools)
    tab_env, tab_subject, tab_lighting = st.tabs(["🌍 Environment", "🧑 Subject", "💡 Lighting & Physics"])
    
    with tab_env:
        st.caption("Generate a world or search for a real location.")
        location = st.text_area("Describe the scene", "a futuristic sci-fi space station", height=80)
        if st.button("Generate Environment"):
            with st.spinner("Director is designing the shot..."):
                cinematic_prompt = direct_prompt(location)
                bg_img = generate_ai_background(cinematic_prompt)
                if bg_img:
                    st.session_state['bg_img'] = bg_img
                    st.rerun()

    with tab_subject:
        st.caption("Upload yourself and remove the background.")
        uploaded_file = st.file_uploader("Upload a photo", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            cutout_method = st.radio("Cutout Engine:", ("AI Cutout (Perfect Hair)", "Green Screen Math"))
            if st.button("Process Subject"):
                with st.spinner("Cutting you out..."):
                    if cutout_method == "Green Screen Math":
                        cutout = remove_green_screen(Image.open(uploaded_file))
                    else:
                        uploaded_file.seek(0) 
                        cutout = remove_bg_ai(uploaded_file.read())
                    if cutout:
                        st.session_state['cutout'] = cutout
                        st.success("Subject isolated!")
                        st.image(cutout, caption="Cutout Preview", width=150)

    with tab_lighting:
        st.caption("Match physics, scale, and shadows.")
        scale = st.slider("Subject Scale", 0.10, 0.60, 0.25, 0.01)
        x_pos = st.slider("Horizontal Position", 0.0, 1.0, 0.50, 0.01)
        y_pos = st.slider("Vertical Position", 0.0, 1.0, 0.85, 0.01)
        sink = st.slider("Sink (Physics)", 0, 150, 0, 5)
        sun_angle = st.slider("Sun Direction", -90, 90, -15, 5)
        
        if st.button("🚀 Render Scene"):
            if st.session_state['bg_img'] and st.session_state['cutout']:
                with st.spinner("Compositing..."):
                    final_img = create_composite(st.session_state['cutout'], st.session_state['bg_img'], scale, x_pos, y_pos, sun_angle, sink)
                    st.image(final_img, caption="Final Render", use_column_width=True)
                    
                    buf = io.BytesIO()
                    final_img.save(buf, format="JPEG")
                    st.download_button("Save to my Phone", buf.getvalue(), "my_scene.jpg", "image/jpeg")
            else:
                st.error("Missing Environment or Subject. Please complete the other tabs.")
