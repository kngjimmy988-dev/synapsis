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
st.set_page_config(page_title="Postcard VFX", page_icon="✈️", layout="centered")

# --- SECURE API KEY LOADING ---
try:
    REMOVEBG_API_KEY = st.secrets["REMOVEBG_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    REMOVEBG_API_KEY = "YOUR_REMOVEBG_API_KEY"
    GROQ_API_KEY = "YOUR_GROQ_API_KEY"

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        background-color: #FFC107; 
        color: black;
        font-size: 20px;
        border-radius: 10px;
        height: 50px;
    }
    h1, h2, h3 { color: #005662; }
    </style>
    """, unsafe_allow_html=True)

# --- THE AI DIRECTOR (GROQ) ---
def direct_prompt(user_idea):
    if GROQ_API_KEY == "YOUR_GROQ_API_KEY":
        return user_idea # Fallback if no key
        
    try:
        client = Groq(api_key=GROQ_API_KEY)
        prompt = f"""
        You are an expert Hollywood VFX director. 
        The user wants to generate a background image for a scene where they will place a real person.
        Take their simple idea and rewrite it into a highly detailed, cinematic image generation prompt.
        
        You MUST include these keywords in your prompt:
        - Photorealistic, 8k resolution, cinematic lighting.
        - Eye-level camera angle.
        - Clear, flat, empty ground in the lower foreground where a person can stand.
        - No text, no watermarks, no logos.
        
        User's idea: "{user_idea}"
        
        Return ONLY the detailed prompt text. Do not say "Here is your prompt".
        """
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"Director Error: {e}")
        return user_idea

# --- HELPER FUNCTIONS ---

def has_green_screen(img):
    img = img.convert("RGB")
    data = np.array(img)
    r, g, b = data[:, :, 0].astype(int), data[:, :, 1].astype(int), data[:, :, 2].astype(int)
    green_mask = (g > r + 40) & (g > b + 40)
    return (np.sum(green_mask) / (img.width * img.height)) > 0.05

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
    if REMOVEBG_API_KEY == "YOUR_REMOVEBG_API_KEY" or not REMOVEBG_API_KEY:
        st.error("Please add your Remove.bg API key to Streamlit Secrets first!")
        return None
    try:
        response = requests.post(
            'https://api.remove.bg/v1.0/removebg',
            files={'image_file': image_bytes},
            data={'size': 'auto'},
            headers={'X-Api-Key': REMOVEBG_API_KEY},
        )
        if response.status_code == requests.codes.ok:
            return Image.open(io.BytesIO(response.content)).convert("RGBA")
        else:
            st.error(f"AI Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Network Error: {e}")
        return None

def download_background(place_name):
    try:
        url = f"https://api.openverse.org/v1/images/?q={urllib.parse.quote(place_name)}&page_size=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'VFXApp/1.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            results = data.get("results", [])
            if not results: return None
            image_url = results[0]["url"]
            img_req = urllib.request.Request(image_url, headers={'User-Agent': 'VFXApp/1.0'})
            with urllib.request.urlopen(img_req) as img_response:
                return Image.open(io.BytesIO(img_response.read())).convert("RGB")
    except Exception:
        return None

def generate_ai_background(prompt):
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1080&nologo=true"
        req = urllib.request.Request(url, headers={'User-Agent': 'VFXApp/1.0'})
        with urllib.request.urlopen(req) as img_response:
            return Image.open(io.BytesIO(img_response.read())).convert("RGB")
    except Exception as e:
        st.error(f"Generation Error: {e}")
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
    cast_shadow = cast_shadow.rotate(sun_angle, expand=True, resample=Image.BICUBIC)
    cast_shadow = cast_shadow.filter(ImageFilter.GaussianBlur(radius=8))
    
    shadow_data = np.array(cast_shadow)
    shadow_data[:, :, 0:3] = [10, 20, 40]
    shadow_data[:, :, 3] = np.clip(shadow_data[:, :, 3] * 0.4, 0, 255)
    shadow_data[:, :, 3] = np.where(shadow_data[:, :, 3] < 15, 0, shadow_data[:, :, 3])
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

    shadow_x = x_offset - int(cast_shadow.width * 0.4) 
    shadow_y = y_offset + target_height - int(cast_shadow.height * 0.8) + sink
    
    background.paste(cast_shadow, (shadow_x, shadow_y), cast_shadow)
    background.paste(contact_shadow, (x_offset, y_offset + target_height - 20), contact_shadow)
    background.paste(person, (x_offset, y_offset), person)

    return background

# --- UI FLOW ---
st.title("✈️ Full CGI Experience")
st.write("Generate a world, add yourself, make it real.")
st.divider()

st.subheader("Step 1: Create your background")
bg_method = st.radio("How do you want your background?", ("Search Stock Photos", "Generate with AI (CGI)"))

location = st.text_input("Describe your scene", "a futuristic sci-fi space station")

if st.button("Get Background"):
    with st.spinner("Creating your world..."):
        if bg_method == "Search Stock Photos":
            bg_img = download_background(location)
        else:
            # THE DIRECTOR IS CALLED HERE
            st.info("🎬 Director is designing the shot...")
            cinematic_prompt = direct_prompt(location)
            
            # Show the user what the Director did (Optional, but cool)
            with st.expander("See Director's Prompt"):
                st.write(cinematic_prompt)
                
            bg_img = generate_ai_background(cinematic_prompt)
            
        if bg_img:
            st.session_state['bg_img'] = bg_img
            st.image(bg_img, use_column_width=True)
        else:
            st.error("Failed to get background. Try another description.")

if 'bg_img' in st.session_state:
    # ... [Rest of the UI remains the same: Upload, Cutout, Blend] ...
    st.divider()
    st.subheader("Step 2: Add yourself")
    uploaded_file = st.file_uploader("Upload a photo", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        person_img = Image.open(uploaded_file)
        st.image(person_img, caption="Your Original Photo", width=200)
        
        cutout_method = st.radio("How should we cut you out?", ("Green Screen Math", "AI Cutout (Perfect Hair)"))
        
        if st.button("Cut me out"):
            with st.spinner("Removing background..."):
                if cutout_method == "Green Screen Math":
                    cutout = remove_green_screen(person_img)
                else:
                    uploaded_file.seek(0) 
                    cutout = remove_bg_ai(uploaded_file.read())
                
                if cutout:
                    st.session_state['cutout'] = cutout
                    st.success("✅ Cutout complete!")
        
        if 'cutout' in st.session_state:
            st.image(st.session_state['cutout'], caption="Cutout Preview", width=200)
            st.divider()
            st.subheader("Step 3: Make it blend")
            
            c1, c2, c3 = st.columns(3)
            scale = c1.slider("Size", 0.10, 0.50, 0.25, 0.01)
            x_pos = c2.slider("Left / Right", 0.0, 1.0, 0.50, 0.01)
            y_pos = c3.slider("Up / Down", 0.0, 1.0, 0.85, 0.01)
            
            sink = st.slider("Sink into Ground / Water", 0, 150, 0, 5)
            sun_angle = st.slider("Drag to move the shadow", -90, 90, -15, 5)
            
            if st.button("🚀 Make my scene"):
                with st.spinner("Adding your shadow... Matching the light..."):
                    final_img = create_composite(st.session_state['cutout'], st.session_state['bg_img'], scale, x_pos, y_pos, sun_angle, sink)
                    st.image(final_img, caption="Your Scene", use_column_width=True)
                    
                    buf = io.BytesIO()
                    final_img.save(buf, format="JPEG")
                    st.download_button("Save to my Phone", buf.getvalue(), "my_scene.jpg", "image/jpeg")
