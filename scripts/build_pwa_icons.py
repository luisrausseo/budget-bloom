"""Resize the supplied logo without redrawing it. Requires Pillow (dev only)."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
source = Image.open(ROOT / 'assets' / 'Heartleaf coin sprout logo.png').convert('RGB')
target = ROOT / 'static' / 'icons'
target.mkdir(exist_ok=True)
for name, size in [('icon-192.png', 192), ('icon-512.png', 512), ('apple-touch-icon.png', 180)]:
    source.resize((size, size), Image.Resampling.LANCZOS).save(target / name)
# The source includes generous padding. An extra 10% inset keeps the complete
# sprout and coin inside the maskable icon's central 80%-diameter safe circle.
canvas = Image.new('RGB', (512, 512), source.getpixel((0, 0)))
mark = source.resize((460, 460), Image.Resampling.LANCZOS)
canvas.paste(mark, (26, 26))
canvas.save(target / 'maskable-512.png')
