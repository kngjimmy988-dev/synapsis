import streamlit as st
import numpy as np
import urllib.request
import urllib.parse
import json
import io
from PIL import Image, ImageFilter, ImageDraw
import requests 

# --- PAGE CONFIG ---
st.set_page_config(page_title="Postcard VFX", page_icon="✈️", layout="centered")

# --- SECURE API KEY LOADING ---
# Try to get the key from Streamlit Secrets first (for the live app)
try:
    REMOVEBG_API_KEY = st.secrets["REMOVEBG_API_KEY"]
except Exception:
    # If running locally, fall back to the placeholder
    REMOVEBG_API_KEY = "YOUR_REMOVEBG_API_KEY"

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

# --- HELPER FUNCTIONS ---

def has_green_screen(img):
    img = img.convert("RGB")
    data = np.array(img)
    r = data[:, :, 0].astype(int)
    g = data[:, :, 1].astype(int)
    b = data[:, :, 2].astype(int)
    green_mask = (g > r + 40) & (g > b + 40)
    green_ratio = np.sum(green_mask) / (img.width * img.height)
    return green_ratio > 0.05

def remove_green_screen(img):
    img = img.convert("RGBA")
    data = np.array(img)
    r = data[:, :, 0].astype(int)
    g = data[:, :, 1].astype(int)
    b = data[:, :, 2].astype(int)
    
    threshold = 60
    green_mask = (g > r + threshold) & (g > b + threshold)
    mask_data = np.where(green_mask, 0, 255).astype(np.uint8)
    mask_img = Image.fromarray(mask_data).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(radius=1))
    data[:, :, 3] = np.array(mask_img)
    
    semi_green = (g > r) & (g > b) & (data[:, :, 3] > 0)
    avg_rb = (r + b) // 2
    data[:, :, 1] = np.where(semi_green, avg_rb, data[:, :, 1])
    return Image.fromarray(data)

# --- THE NEW AI FUNCTION ---
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
            if not results:
                return None
            
            image_url = results[0]["url"]
            
            img_req = urllib.request.Request(image_url, headers={'User-Agent': 'VFXApp/1.0'})
            with urllib.request.urlopen(img_req) as img_response:
                return Image.open(io.BytesIO(img_response.read())).convert("RGB")
    except Exception as e:
        st.error(f"Search error: {e}")
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
st.title("✈️ Where do you want to be?")
st.write("Make it look like you were there. No editing skills needed.")
st.divider()

st.subheader("Step 1: Pick a place")
location = st.text_input("Search a location", "Cyberpunk city")

if st.button("Find this place"):
    with st.spinner("Finding your light..."):
        bg_img = download_background(location)
        if bg_img:
            st.session_state['bg_img'] = bg_img
            st.image(bg_img, use_column_width=True)
        else:
            st.error("Place not found. Try another search.")

if 'bg_img' in st.session_state:
    st.divider()
    st.subheader("Step 2: Add yourself")
    uploaded_file = st.file_uploader("Upload a photo", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        person_img = Image.open(uploaded_file)
        st.image(person_img, caption="Your Original Photo", width=200)
        
        cutout_method = st.radio(
            "How should we cut you out?",
            ("Green Screen Math (Fast, Free)", "AI Cutout (Perfect Hair, Uses API Credit)")
        )
        
        cutout = None
        if st.button("Cut me out"):
            with st.spinner("Removing background..."):
                if cutout_method == "Green Screen Math (Fast, Free)":
                    cutout = remove_green_screen(person_img)
                    st.session_state['cutout'] = cutout
                    st.success("✅ Green screen math applied!")
                else:
                    uploaded_file.seek(0) 
                    cutout = remove_bg_ai(uploaded_file.read())
                    if cutout:
                        st.session_state['cutout'] = cutout
                        st.success("✅ AI cutout complete! Look at that hair.")
        
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
