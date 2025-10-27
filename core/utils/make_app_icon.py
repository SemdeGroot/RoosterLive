#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
App-icoon met gelijke verticale afstanden:
- 'Apotheek' gecentreerd boven
- Slang + lichtblauwe ring gecentreerd in het midden
- 'Jansen' gecentreerd onder
- Vierkant canvas; alle vier verticale tussenruimtes exact gelijk.

Gebruik:
  python make_app_icon.py --input core/static/img/logo.jpg --output core/static/img/app_icon.png \
      --scale_text 0.9 --scale_snake 1.15 --gap_ratio 0.08
"""

import argparse
import cv2
import numpy as np
from PIL import Image

# ---------- MASKS ----------
def mask_blue_text(hsv):
    # Donkerblauwe tekst (ring uitfilteren met hogere S)
    return cv2.inRange(hsv, (95, 110, 50), (140, 255, 255))

def mask_red(hsv):
    m1 = cv2.inRange(hsv, (0, 120, 90),  (10, 255, 255))
    m2 = cv2.inRange(hsv, (160, 120, 90), (179, 255, 255))
    return cv2.bitwise_or(m1, m2)

def mask_ring_lightblue(hsv):
    # Lichtblauwe/grijze ring (lagere S)
    return cv2.inRange(hsv, (95, 20, 120), (135, 110, 255))

# ---------- HELPERS ----------
def merge_bboxes(boxes):
    x0 = min(x for x, y, w, h in boxes)
    y0 = min(y for x, y, w, h in boxes)
    x1 = max(x + w for x, y, w, h in boxes)
    y1 = max(y + h for x, y, w, h in boxes)
    return (x0, y0, x1 - x0, y1 - y0)

def crop(img, box):
    x, y, w, h = box
    return img[y:y+h, x:x+w]

def paste(canvas, img, x, y):
    h, w = img.shape[:2]
    canvas[y:y+h, x:x+w] = img

def resize_rel(img, factor):
    if factor == 1.0:
        return img
    h, w = img.shape[:2]
    return cv2.resize(img, (int(round(w*factor)), int(round(h*factor))), interpolation=cv2.INTER_AREA)

# ---------- DETECTIE ----------
def find_text_boxes(img_bgr):
    """Vind blauw en splits in links (Apotheek) en rechts (Jansen)."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mb = mask_blue_text(hsv)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mb = cv2.morphologyEx(mb, cv2.MORPH_OPEN, k, iterations=1)
    mb = cv2.morphologyEx(mb, cv2.MORPH_CLOSE, k, iterations=2)

    cnts, _ = cv2.findContours(mb, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) > 50]
    if not cnts:
        return None, None

    centers = np.array([[cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2] / 2.0] for c in cnts], dtype=np.float32)
    if len(centers) == 1:
        x, y, w, h = cv2.boundingRect(cnts[0])
        return (x, y, w, h), None

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.1)
    _, labels, _ = cv2.kmeans(centers, 2, None, criteria, 10, cv2.KMEANS_PP_CENTERS)
    group0 = [cv2.boundingRect(cnts[i]) for i in range(len(cnts)) if labels[i] == 0]
    group1 = [cv2.boundingRect(cnts[i]) for i in range(len(cnts)) if labels[i] == 1]

    box0 = merge_bboxes(group0)
    box1 = merge_bboxes(group1)
    left_box, right_box = (box0, box1) if box0[0] < box1[0] else (box1, box0)
    return left_box, right_box

def find_snake_with_ring_box(img_bgr):
    """Voeg rode slang en lichtblauwe ring samen als één element."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    combo = cv2.bitwise_or(mask_red(hsv), mask_ring_lightblue(hsv))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    combo = cv2.morphologyEx(combo, cv2.MORPH_CLOSE, k, iterations=2)
    combo = cv2.morphologyEx(combo, cv2.MORPH_OPEN,  k, iterations=1)

    cnts, _ = cv2.findContours(combo, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) > 80]
    if not cnts:
        return None
    return merge_bboxes([cv2.boundingRect(c) for c in cnts])

# ---------- MAIN ----------
def make_square_icon(
    input_path="core/static/img/logo.jpg",
    output_path="core/static/img/app_icon.png",
    scale_text=0.9,
    scale_snake=1.15,
    gap_ratio=0.08,   # basis-gap als fractie van grootste brondimensie
    force_size=None   # bv. 1024 om exact 1024x1024 te erztten (zonder elementen schalen)
):
    img = cv2.imread(input_path)
    if img is None:
        raise FileNotFoundError(f"Niet gevonden: {input_path}")

    # Detecteer elementen
    left_box, right_box = find_text_boxes(img)
    snake_box = find_snake_with_ring_box(img)
    if left_box is None or right_box is None or snake_box is None:
        raise ValueError("Kon elementen niet detecteren.")

    # Crops
    im_top = crop(img, left_box)     # 'Apotheek'
    im_bottom = crop(img, right_box) # 'Jansen'
    im_snake = crop(img, snake_box)  # slang + ring

    # Zachte schaal zoals je eerder koos
    im_top    = resize_rel(im_top, scale_text)
    im_bottom = resize_rel(im_bottom, scale_text)
    im_snake  = resize_rel(im_snake, scale_snake)

    # --- GELIJKE VERTICALE GAPS ---
    # Start-gap op basis van input (zonder elementen te schalen)
    base_gap = int(round(gap_ratio * max(img.shape[:2])))

    # Minimale canvas-hoogte met gelijke gaps: H = top + snake + bottom + 4*gap
    min_height = im_top.shape[0] + im_snake.shape[0] + im_bottom.shape[0] + 4 * base_gap

    # Minimale benodigde breedte
    min_width = max(im_top.shape[1], im_snake.shape[1], im_bottom.shape[1]) + 2 * base_gap

    # Vierkante canvasgrootte bepalen
    size = max(min_height, min_width)
    if force_size:
        size = max(size, int(force_size))  # garandeer minstens dit formaat

    # Als het canvas groter is dan min_height, verdeel de extra ruimte eerlijk over 4 gaps
    extra_h = size - min_height
    gap = base_gap + extra_h // 4  # integer pixels
    # Voor het geval er 1-3 restpixels zijn, die komen onderaan terecht; visueel verschil is onzichtbaar.

    # Canvas
    canvas = np.full((size, size, 3), 255, dtype=np.uint8)

    # --- POSITIES met gelijke gaps ---
    # y-posities: gap | top | gap | snake | gap | bottom | gap
    y_top = gap
    x_top = (size - im_top.shape[1]) // 2
    paste(canvas, im_top, x_top, y_top)

    y_snake = y_top + im_top.shape[0] + gap
    x_snake = (size - im_snake.shape[1]) // 2
    paste(canvas, im_snake, x_snake, y_snake)

    y_bottom = y_snake + im_snake.shape[0] + gap
    x_bottom = (size - im_bottom.shape[1]) // 2
    paste(canvas, im_bottom, x_bottom, y_bottom)

    # Optioneel exact naar force_size schalen (zonder inhoudsverhoudingen te wijzigen)
    if force_size:
        size = int(force_size)
        canvas = cv2.resize(canvas, (size, size), interpolation=cv2.INTER_AREA)

    Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)).save(output_path)
    print(f"✅ Vierkant logo met gelijke marges opgeslagen als: {output_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="core/static/img/logo.jpg")
    ap.add_argument("--output", default="core/static/img/app_icon.png")
    ap.add_argument("--scale_text", type=float, default=1.0)
    ap.add_argument("--scale_snake", type=float, default=1.0)
    ap.add_argument("--gap_ratio", type=float, default=0.04)
    ap.add_argument("--force_size", type=int, default=1024)  # bv. 1024
    args = ap.parse_args()

    make_square_icon(
        input_path=args.input,
        output_path=args.output,
        scale_text=args.scale_text,
        scale_snake=args.scale_snake,
        gap_ratio=args.gap_ratio,
        force_size=args.force_size,
    )
