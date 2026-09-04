"""Minimal CAMEO / QuadClass reference for human-readable labels."""

QUAD_CLASS = {
    1: "Verbal Cooperation",
    2: "Material Cooperation",
    3: "Verbal Conflict",
    4: "Material Conflict",
}

# CAMEO root event codes (01-20) -> label
EVENT_ROOT = {
    "01": "Make public statement",
    "02": "Appeal",
    "03": "Express intent to cooperate",
    "04": "Consult",
    "05": "Engage in diplomatic cooperation",
    "06": "Engage in material cooperation",
    "07": "Provide aid",
    "08": "Yield",
    "09": "Investigate",
    "10": "Demand",
    "11": "Disapprove",
    "12": "Reject",
    "13": "Threaten",
    "14": "Protest",
    "15": "Exhibit force posture",
    "16": "Reduce relations",
    "17": "Coerce",
    "18": "Assault",
    "19": "Fight",
    "20": "Use unconventional mass violence",
}


def quad_label(q):
    return QUAD_CLASS.get(q, "Unknown")


def root_label(code):
    return EVENT_ROOT.get((code or "").zfill(2), code or "")
