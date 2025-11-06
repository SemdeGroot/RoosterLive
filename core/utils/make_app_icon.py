#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# import argparse
# import cv2
# import numpy as np
# from PIL import Image

# # ---------------- Detectie: rood + lichtblauwe ring ----------------
# def mask_red(hsv):
#     m1 = cv2.inRange(hsv, (0,   120, 90), (10,  255, 255))
#     m2 = cv2.inRange(hsv, (160, 120, 90), (179, 255, 255))
#     return cv2.bitwise_or(m1, m2)

# def mask_ring_lightblue(hsv):
#     # lager S dan donkerblauwe tekst, hoger V om grijs-achtige ring te pakken
#     return cv2.inRange(hsv, (95, 20, 120), (135, 110, 255))

# def find_snake_with_ring_box(img_bgr):
#     hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
#     combo = cv2.bitwise_or(mask_red(hsv), mask_ring_lightblue(hsv))
#     k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
#     combo = cv2.morphologyEx(combo, cv2.MORPH_CLOSE, k, iterations=2)
#     combo = cv2.morphologyEx(combo, cv2.MORPH_OPEN,  k, iterations=1)

#     cnts, _ = cv2.findContours(combo, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
#     cnts = [c for c in cnts if cv2.contourArea(c) > 80]
#     if not cnts:
#         return None
#     # 1 box die slang + ring omvat
#     x0 = min(cv2.boundingRect(c)[0] for c in cnts)
#     y0 = min(cv2.boundingRect(c)[1] for c in cnts)
#     x1 = max(cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2] for c in cnts)
#     y1 = max(cv2.boundingRect(c)[1] + cv2.boundingRect(c)[3] for c in cnts)
#     return (x0, y0, x1 - x0, y1 - y0)

# # ---------------- Helpers ----------------
# def crop(img, box):
#     x, y, w, h = box
#     return img[y:y+h, x:x+w]

# def resize_fit(img, target_w, target_h, allow_upscale=True):
#     h, w = img.shape[:2]
#     scale = min(target_w / float(w), target_h / float(h))
#     if not allow_upscale:
#         scale = min(1.0, scale)
#     new_w = max(1, int(round(w * scale)))
#     new_h = max(1, int(round(h * scale)))
#     return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

# def paste_center(canvas, img):
#     H, W = canvas.shape[:2]
#     h, w = img.shape[:2]
#     x = (W - w) // 2
#     y = (H - h) // 2
#     canvas[y:y+h, x:x+w] = img

# # ---------------- Main ----------------
# def make_snake_icon(
#     input_path="core/static/img/logo.jpg",
#     output_path="core/static/img/app_icon.png",
#     force_size=1024,       # eindformaat (vierkant), bv. 1024
#     gap_ratio=0.08,        # buitenmarge t.o.v. grootste dimensie van het BRON-logo
#     allow_upscale=True     # slang+ring uitvergroten tot het mooi vult
# ):
#     img = cv2.imread(input_path)
#     if img is None:
#         raise FileNotFoundError(input_path)

#     box = find_snake_with_ring_box(img)
#     if box is None:
#         raise ValueError("Slang + ring niet gedetecteerd. Pas evt. de HSV-ranges aan.")
#     snake = crop(img, box)

#     # Canvas (vierkant, wit)
#     size = int(force_size)
#     canvas = np.full((size, size, 3), 255, dtype=np.uint8)

#     # Bepaal buitenmarge in pixels en beschikbare ruimte voor het element
#     G = int(round(gap_ratio * max(img.shape[:2])))   # marge rondom
#     avail = max(1, size - 2 * G)

#     # Schaal slang+ring proportioneel in de beschikbare ruimte
#     snake_fit = resize_fit(snake, avail, avail, allow_upscale=allow_upscale)

#     # Plaats gecentreerd
#     paste_center(canvas, snake_fit)

#     # Opslaan
#     Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)).save(output_path)
#     print(f"✅ Alleen slangenlogo opgeslagen als vierkant: {output_path}")
#     print(f"   size={size}px | outer margin G={G}px | placed size={snake_fit.shape[1]}×{snake_fit.shape[0]}")

# if __name__ == "__main__":
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--input", default="core/static/img/logo.jpg")
#     ap.add_argument("--output", default="core/static/img/app_icon.png")
#     ap.add_argument("--force_size", type=int, default=1024)
#     ap.add_argument("--gap_ratio", type=float, default=0.07)
#     ap.add_argument("--allow_upscale", type=int, default=1, help="1 = groter maken toegestaan, 0 = niet")
#     args = ap.parse_args()

#     make_snake_icon(
#         input_path=args.input,
#         output_path=args.output,
#         force_size=args.force_size,
#         gap_ratio=args.gap_ratio,
#         allow_upscale=bool(args.allow_upscale),
#     )
