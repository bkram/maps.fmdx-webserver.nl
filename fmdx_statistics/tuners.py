# tuners.py
import re
from typing import Optional

# (pattern, label) pairs — order matters (first match wins)
_TUNER_FAMILIES = [
    (r"(?:^|\W)rtl[-_ ]?sdr(?:$|\W)|\br820t2?\b|\brtl2832\b", "RTL-SDR"),
    (r"\bairspy(?:\s+mini|\s+hf\+)?\b", "Airspy"),
    (r"\bsdrplay|rsp1(?:a)?\b|\brsp2\b|\brspdx\b|\brspduo\b", "SDRplay"),
    (r"\bhackrf\b", "HackRF"),
    (r"\blimesdr(?:-mini)?\b", "LimeSDR"),
    (r"\bmiri(?:ics)?\b|\bmsi2500\b", "Mirics/MSI"),
    (r"\bblade[-_ ]?rf\b", "BladeRF"),
    (r"\busrp\b|\bb2xx\b|\bn2xx\b|\bx3xx\b", "USRP"),
    (r"\bsoapysdr\b", "SoapySDR (generic)"),
    (r"\btef66(?:86|87)\b|\b(?:^|[^a-z])tef(?:$|[^a-z])", "TEF66xx"),
    (r"\bsi473(?:2|4|5)\b|\bsi47xx\b", "Si47xx"),
]


def tuner_family(tuner_str: Optional[str]) -> str:
    """
    Map a free-form tuner string to a coarse family bucket.
    Returns 'Unknown' when empty, 'Other/Unknown' when not matched.
    """
    s = (tuner_str or "").strip()
    if not s:
        return "Unknown"
    low = s.lower()
    for pat, label in _TUNER_FAMILIES:
        if re.search(pat, low):
            return label
    # Common loose aliases
    if low in {"tef", "tef6686", "tef6687"}:
        return "TEF66xx"
    if low in {"sdr", "rtl", "rtlsdr"}:
        return "RTL-SDR"
    return "Other/Unknown"
