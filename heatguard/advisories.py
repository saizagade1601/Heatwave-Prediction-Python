"""
advisories.py  -  Phase V: Stakeholder-specific advisories & early warning
==========================================================================
Turns technical numbers into plain-language advice for each beneficiary
named in the use case: citizens, farmers, health departments, and
disaster-management authorities.  (String handling - Exp 3)
"""
from .text_tools import short_date

STAKEHOLDERS = ("Citizens", "Farmers", "Health Dept.", "Authorities")

_ADVICE = {
    "SEVERE HEATWAVE": {
        "Citizens": "Stay indoors 11 AM-4 PM. Drink water every 20 minutes even if not thirsty. Never leave children or pets in parked vehicles.",
        "Farmers": "Irrigate at dawn/dusk only. Shift field work to before 10 AM. Provide shade and extra water to livestock.",
        "Health Dept.": "Activate heat-stroke wards and cold rooms. Stock ORS & IV fluids. Alert ambulances for heat emergencies.",
        "Authorities": "Issue RED alert. Open cooling shelters, run water kiosks, reschedule outdoor labour and school hours.",
    },
    "HEATWAVE": {
        "Citizens": "Avoid direct sun 12-4 PM. Wear light cotton clothes and a cap. Carry water and ORS.",
        "Farmers": "Use mulching to save soil moisture. Increase irrigation frequency. Keep livestock in shade.",
        "Health Dept.": "Prepare for heat-exhaustion cases. Issue public hydration advisories.",
        "Authorities": "Issue ORANGE alert. Set up drinking-water points and shaded rest areas.",
    },
    "HOT DAY": {
        "Citizens": "Hot day ahead - stay hydrated and limit long exposure to the afternoon sun.",
        "Farmers": "Plan irrigation for the early morning to cut evaporation losses.",
        "Health Dept.": "Monitor vulnerable groups (elderly, outdoor workers).",
        "Authorities": "Issue YELLOW watch. Keep heat-action plan ready.",
    },
    "COLD WAVE": {
        "Citizens": "Wear layered woollen clothing. Avoid prolonged exposure at night and early morning.",
        "Farmers": "Light irrigation in the evening protects crops from frost. Cover nurseries.",
        "Health Dept.": "Watch for hypothermia and respiratory cases.",
        "Authorities": "Open night shelters and distribute blankets.",
    },
    "NORMAL": {
        "Citizens": "No weather stress expected. Normal routine is fine.",
        "Farmers": "Normal agricultural operations can continue.",
        "Health Dept.": "Routine surveillance.",
        "Authorities": "No warning required - continue monitoring.",
    },
}
_ADVICE["SEVERE COLD"] = _ADVICE["COLD WAVE"]
_ADVICE["CHILLY"] = _ADVICE["NORMAL"]


def worst_label(labels):
    order = ["SEVERE HEATWAVE", "HEATWAVE", "SEVERE COLD", "COLD WAVE", "HOT DAY", "CHILLY", "NORMAL"]
    for lab in order:
        if lab in labels:
            return lab
    return "NORMAL"


def build_advisory(result):
    """Return (headline, colour level, {stakeholder: advice}) for a forecast."""
    label = worst_label(result.risk_label)
    days = [short_date(d) for d, lab in zip(result.dates, result.risk_label) if lab == label]
    wet = [short_date(d) for d, p in zip(result.dates, result.rain_prob) if p >= 0.6]
    if label in ("SEVERE HEATWAVE", "HEATWAVE"):
        headline = f"{label.title()} early warning for {result.country}: {', '.join(days[:4])}"
        level = 3 if label.startswith("SEVERE") else 2
    elif label in ("COLD WAVE", "SEVERE COLD"):
        headline = f"{label.title()} warning for {result.country}: {', '.join(days[:4])}"
        level = 2
    elif label == "HOT DAY":
        headline = f"Heat watch for {result.country}: {len(days)} hot day(s) ahead"
        level = 1
    else:
        headline = f"No heatwave expected in {result.country} for the next {result.horizon} days"
        level = 0
    advice = dict(_ADVICE.get(label, _ADVICE["NORMAL"]))
    if wet:
        advice["Citizens"] += f" Rain likely on {', '.join(wet[:3])} - carry an umbrella."
        advice["Farmers"] += " Postpone pesticide spraying on rainy days."
    return headline, level, advice
