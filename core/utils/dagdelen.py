# core/utils/dagdelen.py
from __future__ import annotations

from datetime import time
from typing import Dict, Tuple

from core.models import Dagdeel

# Shift.period -> Dagdeel.code
PERIOD_TO_DAGDEEL_CODE = {
    "morning": Dagdeel.CODE_MORNING,
    "afternoon": Dagdeel.CODE_AFTERNOON,
    "evening": Dagdeel.CODE_PRE_EVENING,  # Shift 'evening' = Dagdeel 'pre_evening'
}

# Fallback als Dagdeel records (nog) niet bestaan
FALLBACK = {
    "morning":    {"label": "Ochtend",   "start": time(8, 0),  "end": time(12, 30)},
    "afternoon":  {"label": "Middag",    "start": time(13, 0), "end": time(17, 30)},
    "evening":    {"label": "Vooravond", "start": time(18, 0), "end": time(20, 0)},
}

def get_period_meta(period: str) -> Dict:
    """
    Return:
      {
        "label": "Ochtend/Middag/Vooravond",
        "start": time,
        "end": time,
        "time_str": "HH:MM - HH:MM",
        "dagdeel_code": "...",
      }
    """
    dagdeel_code = PERIOD_TO_DAGDEEL_CODE.get(period)

    if not dagdeel_code:
        fb = FALLBACK.get(period, {"label": period, "start": time(9, 0), "end": time(13, 0)})
        return {
            "label": fb["label"],
            "start": fb["start"],
            "end": fb["end"],
            "time_str": f"{fb['start'].strftime('%H:%M')} - {fb['end'].strftime('%H:%M')}",
            "dagdeel_code": None,
        }

    dd = Dagdeel.objects.filter(code=dagdeel_code).only("start_time", "end_time", "name", "code").first()
    if not dd or not dd.start_time or not dd.end_time:
        fb = FALLBACK.get(period)
        return {
            "label": fb["label"],
            "start": fb["start"],
            "end": fb["end"],
            "time_str": f"{fb['start'].strftime('%H:%M')} - {fb['end'].strftime('%H:%M')}",
            "dagdeel_code": dagdeel_code,
        }

    label = dd.get_code_display()  # "Vooravond" bij pre_evening
    start_t = dd.start_time
    end_t = dd.end_time
    return {
        "label": label,
        "start": start_t,
        "end": end_t,
        "time_str": f"{start_t.strftime('%H:%M')} - {end_t.strftime('%H:%M')}",
        "dagdeel_code": dagdeel_code,
    }
