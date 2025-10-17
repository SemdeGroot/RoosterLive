from PIL import Image
import numpy as np
from pathlib import Path

def hex_to_rgb(hex_color):
    """Converteer een hexkleur (#rrggbb) naar een RGB-tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def make_vertical_gradient(h, w, top='#1f4ba0', mid='#ffffff', bottom=None):
    """
    Maak een (h,w,3) RGB-gradient:
      boven (top) -> midden (mid) -> onder (bottom).
    Hier krijgt wit een breder middengebied (meer wit oppervlak).
    """
    if bottom is None:
        bottom = top

    top = np.array(hex_to_rgb(top), dtype=float)
    mid = np.array(hex_to_rgb(mid), dtype=float)
    bottom = np.array(hex_to_rgb(bottom), dtype=float)

    y = np.linspace(0, 1, h)  # 0 = boven, 1 = onder
    grad_rows = np.empty((h, 3), dtype=float)

    # Definieer overgangspunten:
    top_to_white_end = 0.25   # tot 35%: blauw -> wit
    white_hold_end   = 0.75   # 35–65%: wit blijft dominant

    # 1️⃣ bovenste deel: blauw -> wit
    upper_idx = np.where(y <= top_to_white_end)[0]
    if upper_idx.size > 0:
        t = (y[upper_idx] / top_to_white_end)[:, None]
        grad_rows[upper_idx] = (1 - t) * top + t * mid

    # 2️⃣ middelste deel: blijft wit
    mid_idx = np.where((y > top_to_white_end) & (y <= white_hold_end))[0]
    if mid_idx.size > 0:
        grad_rows[mid_idx] = mid

    # 3️⃣ onderste deel: wit -> blauw
    lower_idx = np.where(y > white_hold_end)[0]
    if lower_idx.size > 0:
        t = ((y[lower_idx] - white_hold_end) / (1 - white_hold_end))[:, None]
        grad_rows[lower_idx] = (1 - t) * mid + t * bottom

    grad = np.repeat(grad_rows[:, None, :], w, axis=1)
    return grad.astype(np.uint8)

def recolor_icon(input_path, output_path=None,
                 top='#1f4ba0', mid='#ffffff', bottom=None,
                 alpha_threshold=1):
    """
    Kleur alle niet-transparante pixels van een PNG met een verticale gradient.
    Transparantie (alpha) blijft behouden.
    Standaard: blauw (#1f4ba0) -> wit -> blauw (met meer wit oppervlak).
    """
    img = Image.open(input_path).convert('RGBA')
    w, h = img.size
    rgba = np.array(img, dtype=np.uint8)
    a = rgba[..., 3:]  # alpha (H,W,1)

    grad = make_vertical_gradient(h, w, top=top, mid=mid, bottom=bottom)

    mask = (a[..., 0] > alpha_threshold)[..., None]
    new_rgb = np.where(mask, grad, 0)

    out = np.concatenate([new_rgb, a], axis=-1).astype(np.uint8)
    out_img = Image.fromarray(out, mode='RGBA')

    if output_path is None:
        output_path = Path(input_path).with_name(Path(input_path).stem + '.png')

    out_img.save(output_path)
    print(f"✅  Opgeslagen: {output_path}")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(
        description="Recolor transparante PNG-iconen met een zachtere blauw→wit→blauw gradient (meer wit in het midden)."
    )
    p.add_argument("inputs", nargs="+", help="Input PNG-bestanden")
    p.add_argument("--top", default="#1f4ba0", help="Bovenkleur (default: #1f4ba0)")
    p.add_argument("--mid", default="#ffffff", help="Middelkleur (default: #ffffff)")
    p.add_argument("--bottom", default=None, help="Onderkleur (default: zelfde als top voor blauw→wit→blauw)")
    p.add_argument("--suffix", default="", help="Suffix voor uitvoerbestanden")
    args = p.parse_args()

    for inp in args.inputs:
        inp_path = Path(inp)
        out_path = inp_path.with_name(inp_path.stem + args.suffix + inp_path.suffix)
        recolor_icon(inp_path, out_path, top=args.top, mid=args.mid, bottom=args.bottom)