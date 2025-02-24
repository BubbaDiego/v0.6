from PIL import Image, ImageEnhance, ImageOps
import sys

def make_nightscape(input_path, output_path):
    # 1) Open the original image and ensure it's in RGB mode
    img = Image.open(input_path).convert("RGB")

    # 2) Darken the image - but not too much
    #    Increase darken_factor for a darker scene, decrease for brighter.
    darken_factor = 0.6  # Instead of 0.3
    enhancer = ImageEnhance.Brightness(img)
    img_dark = enhancer.enhance(darken_factor)

    # 3) Add a bluish/purple tint
    r, g, b = img_dark.split()
    r = r.point(lambda i: i * 0.8)
    g = g.point(lambda i: i * 0.9)
    b = b.point(lambda i: i * 1.2)
    img_tinted = Image.merge("RGB", (r, g, b))

    # 4) Convert tinted to grayscale, then threshold for a silhouette
    gray = img_tinted.convert("L")
    threshold = 130
    silhouette = gray.point(lambda x: 0 if x < threshold else 255, 'L')
    silhouette_rgb = silhouette.convert("RGB")

    # 5) Blend tinted with silhouette
    #    Lower alpha => more of tinted sky is visible (less silhouette).
    blend_alpha = 0.5  # Instead of 0.8
    img_night = Image.blend(img_tinted, silhouette_rgb, alpha=blend_alpha)

    # 6) Save the final result
    img_night.save(output_path)
    print(f"Nightscape saved to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python nightscape.py <input_image> <output_image>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    make_nightscape(input_file, output_file)
