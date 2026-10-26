import numpy as np
from PIL import Image, ImageFilter, ImageDraw

def create_v3_composite(person_path, bg_path, output_path):
    print("Loading cutout and background...")
    person = Image.open(person_path).convert("RGBA")
    background = Image.open(bg_path).convert("RGB")
    
    width, height = background.size

    # 1. Crop and Scale
    bbox = person.getbbox()
    if bbox:
        person = person.crop(bbox)

    x_position = 0.50      
    y_position = 0.85      
    scale_percent = 0.25   

    target_height = int(height * scale_percent)
    person_width = int(person.width * (target_height / person.height))
    person = person.resize((person_width, target_height), Image.Resampling.LANCZOS)

    # --- 2. DIRECTIONAL LIGHTING ---
    person_data = np.array(person).astype(np.float32)
    gradient = np.linspace(1.15, 0.85, person_width) 
    for i in range(3):
        person_data[:, :, i] = person_data[:, :, i] * gradient
    person = Image.fromarray(np.clip(person_data, 0, 255).astype(np.uint8))

    # --- 3. MATCH SHARPNESS ---
    person = person.filter(ImageFilter.GaussianBlur(radius=0.8))

    # --- 4. CAST SHADOW & CONTACT SHADOW ---
    print("Generating shadows...")
    
    # Cast Shadow
    cast_shadow = Image.new("RGBA", person.size, (0, 0, 0, 0))
    cast_shadow.putalpha(person.split()[3]) 
    
    # Squash and stretch
    new_shadow_height = int(target_height * 0.2)
    new_shadow_width = int(person_width * 1.5)
    cast_shadow = cast_shadow.resize((new_shadow_width, new_shadow_height), Image.Resampling.LANCZOS)
    
    # Rotate slightly
    cast_shadow = cast_shadow.rotate(-15, expand=True, resample=Image.BICUBIC)
    cast_shadow = cast_shadow.filter(ImageFilter.GaussianBlur(radius=8))
    
    # Tint and opacity
    shadow_data = np.array(cast_shadow)
    shadow_data[:, :, 0] = 10 
    shadow_data[:, :, 1] = 20
    shadow_data[:, :, 2] = 40
    
    # THE FIX: Multiply alpha, but force anything below 10 to be completely 0
    shadow_data[:, :, 3] = np.clip(shadow_data[:, :, 3] * 0.4, 0, 255)
    shadow_data[:, :, 3] = np.where(shadow_data[:, :, 3] < 15, 0, shadow_data[:, :, 3])
    
    cast_shadow = Image.fromarray(shadow_data)

    # Contact Shadow (Small dark oval under shoes)
    contact_shadow = Image.new("RGBA", (person_width, 40), (0, 0, 0, 0))
    draw_contact = ImageDraw.Draw(contact_shadow)
    draw_contact.ellipse([10, 10, person_width-10, 35], fill=(0, 0, 0, 200))
    contact_shadow = contact_shadow.filter(ImageFilter.GaussianBlur(radius=3))
    
    # THE FIX for contact shadow box
    contact_data = np.array(contact_shadow)
    contact_data[:, :, 3] = np.where(contact_data[:, :, 3] < 15, 0, contact_data[:, :, 3])
    contact_shadow = Image.fromarray(contact_data)

    # --- 5. BACKGROUND MATCHING & GRADE ---
    background = background.filter(ImageFilter.GaussianBlur(radius=1.5))
    
    # Cinematic Vignette
    vignette = Image.new('L', (width, height), 0)
    draw_v = ImageDraw.Draw(vignette)
    draw_v.ellipse([-width//4, -height//4, width + width//4, height + height//4], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=100))
    
    bg_data = np.array(background).astype(np.float32)
    vig_data = np.array(vignette).astype(np.float32) / 255.0
    vig_multiplier = 0.7 + (0.3 * vig_data)
    
    for i in range(3):
        bg_data[:, :, i] = bg_data[:, :, i] * vig_multiplier
    background = Image.fromarray(np.clip(bg_data, 0, 255).astype(np.uint8))

    # --- 6. COMBINE EVERYTHING ---
    x_offset = int((width * x_position) - (person_width / 2))
    y_offset = int((height * y_position) - target_height)

    # Paste Cast Shadow
    shadow_x = x_offset - int(cast_shadow.width * 0.4) 
    shadow_y = y_offset + target_height - int(cast_shadow.height * 0.8)
    background.paste(cast_shadow, (shadow_x, shadow_y), cast_shadow)
    
    # Paste Contact Shadow
    contact_x = x_offset
    contact_y = y_offset + target_height - 20
    background.paste(contact_shadow, (contact_x, contact_y), contact_shadow)
    
    # Paste Person
    background.paste(person, (x_offset, y_offset), person)

    background.save(output_path)
    print(f"Success! V3 invisible box destroyed. Saved to {output_path}")

if __name__ == "__main__":
    create_v3_composite("cutout.png", "background.jpg", "final_result.jpg")
