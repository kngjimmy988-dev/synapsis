import numpy as np
from PIL import Image, ImageFilter

def remove_green_screen(input_path, output_path, threshold=60):
    print(f"Loading {input_path}...")
    img = Image.open(input_path).convert("RGBA")
    data = np.array(img)
    
    r = data[:, :, 0].astype(int)
    g = data[:, :, 1].astype(int)
    b = data[:, :, 2].astype(int)
    
    # 1. Find the green pixels
    green_mask = (g > r + threshold) & (g > b + threshold)
    
    # Create a black and white image of the mask (255 = white/opaque, 0 = black/transparent)
    mask_data = np.where(green_mask, 0, 255).astype(np.uint8)
    mask_img = Image.fromarray(mask_data)
    
    # 2. THE FIX: Shrink the mask by 1 pixel (MinFilter removes the outer green edge)
    print("Cleaning edges...")
    mask_img = mask_img.filter(ImageFilter.MinFilter(3))
    
    # 3. THE FIX: Soften the mask so it's not a jagged line
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=1))
    
    # Apply the new clean mask to the image
    data[:, :, 3] = np.array(mask_img)
    
    # 4. Color Spill Suppression (kills the remaining green tint on the skin)
    # If green is higher than red or blue on the remaining visible pixels, pull it down.
    semi_green = (g > r) & (g > b) & (data[:, :, 3] > 0)
    avg_rb = (r + b) // 2
    data[:, :, 1] = np.where(semi_green, avg_rb, data[:, :, 1])
    
    result_img = Image.fromarray(data)
    result_img.save(output_path, "PNG")
    print(f"Saved clean image to {output_path}")

if __name__ == "__main__":
    remove_green_screen("test.jpg", "cutout.png")
