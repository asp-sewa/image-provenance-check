"""Generate sample images for tests (run: python tests/make_fixtures.py <outdir>)."""
import sys, os
from PIL import Image, ImageDraw, ImageFont

out = sys.argv[1]; os.makedirs(out, exist_ok=True)
def font(sz):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf", "arial.ttf"):
        try: return ImageFont.truetype(f, sz)
        except Exception: pass
    return ImageFont.load_default()
def base(color=(90, 140, 200)):
    im = Image.new("RGB", (1200, 800), color); d = ImageDraw.Draw(im)
    for i in range(0, 1200, 60): d.line([(i, 0), (1200 - i, 800)], fill=(255, 255, 255), width=3)
    return im, d

im, _ = base(); im.save(os.path.join(out, "gettyimages-2299925682-612x612.jpg"))                 # filename block
im, d = base((120, 160, 90)); d.text((60, 700), "Photo: Ravi Kumar / Reuters  © 2025", font=font(48), fill=(255, 255, 255))
im.save(os.path.join(out, "flood_relief.jpg"))                                                      # OCR block
im, _ = base((200, 120, 80))
ex = im.getexif(); ex[315] = "Jane Photographer"; ex[33432] = "© 2024 Jane Photographer"
im.save(os.path.join(out, "meta_owned.jpg"), exif=ex)                                               # metadata soft flag
im, _ = base((60, 60, 120)); im.save(os.path.join(out, "clean_unknown.jpg"))                       # nothing found
im, _ = base((60, 60, 120)); im.save(os.path.join(out, "clean_unknown_copy.png"))
