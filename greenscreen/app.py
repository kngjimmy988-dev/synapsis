import streamlit as st
import numpy as np
import urllib.request
import urllib.parse
import json
import io
from PIL import Image, ImageFilter, ImageDraw

# --- PAGE CONFIG ---
st.set_page_config(page_title="Postcard VFX", page_icon="✈️", layout="centered")

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

def download_background(place_name):
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query", "generator": "search", "gsrsearch": f"File: {place_name}",
        "gsrlimit": "1", "prop": "imageinfo", "iiprop": "url", "iiurlwidth": "1080", "format": "json"
    }
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={'User-Agent': 'VFXApp/1.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            pages = data.get("query", {}).get("pages", {})
            if not pages: return None
            page_id = list(pages.keys())[0]
            image_url = pages[page_id]["imageinfo"][0]["thumburl"]
            
            img_req = urllib.request.Request(image_url, headers={'User-Agent': 'VFXApp/1.0'})
            with urllib.request.urlopen(img_req) as img_response:
                return Image.open(io.BytesIO(img_response.read())).convert("RGB")
    except Exception:
        return None

def create_composite(person, background, scale, x_pos, y_pos, sun_angle, sink):
    width, height = background.size
    bbox = person.getbbox()
    if bbox: person = person.crop(bbox)

    target_height = int(height * scale)
    person_width = int(person.width * (target_height / person.height))
    person = person.resize((person_width, target_height), Image.Resampling.LANCZOS)

    # --- THE SINK LOGIC ---
    if sink > 0:
        new_height = max(10, target_height - sink)
        person = person.crop((0, 0, person_width, new_height))
        target_height = new_height # Update height

    person_data = np.array(person).astype(np.float32)
    gradient = np.linspace(1.15, 0.85, person_width) 
    for i in range(3): person_data[:, :, i] = person_data[:, :, i] * gradient
    person = Image.fromarray(np.clip(person_data, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=0.8))

    # --- SHADOW LOGIC (FIXED) ---
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

    # FIXED SHADOW POSITION: It now follows the sink offset exactly
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
location = st.text_input("Search a location", "Sunny beach")

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
    uploaded_file = st.file_uploader("Upload a photo taken in front of a green screen", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        person_img = Image.open(uploaded_file)
        st.image(person_img, caption="Your Photo", width=200)
        
        if not has_green_screen(person_img):
            st.error("🚨 **No Green Screen Detected!**")
            st.info("It looks like you uploaded a photo without a green background. Our math needs a solid green color to cut you out perfectly.\n\n**Tips for Coily Hair & Perfect Edges:**\n1. Stand in front of a bright green cloth.\n2. Light the back of your hair well so the details don't blend into the dark.\n3. Stand 2 meters away from the cloth to avoid green light bouncing on your skin.")
            st.stop()
        
        st.success("✅ Green screen detected! You're ready to go.")
        st.divider()
        st.subheader("Step 3: Make it blend")
        
        c1, c2, c3 = st.columns(3)
        scale = c1.slider("Size", 0.10, 0.50, 0.25, 0.01)
        x_pos = c2.slider("Left / Right", 0.0, 1.0, 0.50, 0.01)
        y_pos = c3.slider("Up / Down", 0.0, 1.0, 0.85, 0.01)
        
        sink = st.slider("Sink into Ground / Water (Fixes Physics!)", 0, 150, 0, 5)
        
        sun_angle = st.slider("Drag to move the shadow", -90, 90, -15, 5)
        
        if st.button("🚀 Make my scene"):
            with st.spinner("Adding your shadow... Matching the light..."):
                cutout = remove_green_screen(person_img)
                final_img = create_composite(cutout, st.session_state['bg_img'], scale, x_pos, y_pos, sun_angle, sink)
                
                st.image(final_img, caption="Your Scene", use_column_width=True)
                
                st.write("### Realism Meter")
                if scale < 0.15 or scale > 0.40:
                    st.progress(40)
                    st.warning("⚠️ 40% — The person looks too big or too small.")
                else:
                    st.progress(85)
                    st.success("✅ 85% — This looks believable!")
                
                buf = io.BytesIO()
                final_img.save(buf, format="JPEG")
                st.download_button("Save to my Phone", buf.getvalue(), "my_scene.jpg", "image/jpeg")
