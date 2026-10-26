from PIL import Image, ImageDraw

# Create a solid green image
img = Image.new('RGB', (400, 400), color=(0, 255, 0))
draw = ImageDraw.Draw(img)

# Draw a red square (pretend this is you)
draw.rectangle([100, 100, 300, 300], fill=(255, 0, 0))

img.save('test.jpg')
print("Created a fake green screen photo named test.jpg!")
