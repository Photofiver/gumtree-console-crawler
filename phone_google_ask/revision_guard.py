"""Conservative, auditable review edits. Reviewer text is untrusted input."""
import json
import re

PRICE_RE = re.compile(r"(?:£|GBP\s*)(\d+(?:[.,]\d{1,2})?)", re.IGNORECASE)
BAD_TOPIC = re.compile(r"\b(?:beton|cement|concrete|wapienny|prawie\s+za\s+darmo)\b", re.I)
FOREIGN_S700 = re.compile(r"\b(?:ALLPOWERS\s+)?(?:R600|S300|S500|S1500|S2000|S3000)\b", re.I)
BARE_VERDICT = re.compile(r"\s*(?:PASS|REVISE|DO POPRAWY|SPRAWDZONE|POTWIERDZONE|NIEPOTWIERDZONE)(?:\s+[a-f0-9]{16})?\s*", re.I)
WRONG_VOC = re.compile(
    r"25[.,]2\s*V\s*(?:<|<=|jest\s+mniejsze\s+niż|miesci\s+sie\s+w|mieści\s+się\s+w)\s*24\s*V",
    re.I,
)


def prices(text):
    return {m.group(1).replace(",", ".") for m in PRICE_RE.finditer(text)}


def guarded_patch(data, old, new):
    """Apply only an exact, local patch; never accept a new shopping recommendation."""
    original = data["draft"]
    if not isinstance(old, str) or not isinstance(new, str):
        raise ValueError("Patch old/new must be strings")
    if not 5 <= len(old) <= 480 or not 1 <= len(new) <= 480:
        raise ValueError("Patch length out of bounds")
    if original.count(old) != 1:
        raise ValueError("Patch old is not a unique exact span of the original draft")
    patched = original.replace(old, new, 1)
    if patched == original:
        raise ValueError("No change in patched draft")
    if BARE_VERDICT.fullmatch(patched):
        raise ValueError("Bare reviewer verdict is not a substantive answer")
    if "S700" in data.get("question", "").upper():
        for token in ("S700", "606", "48", "Amazon", "Argos", "Belfa"):
            if token.casefold() in original.casefold() and token.casefold() not in patched.casefold():
                raise ValueError("Correction dropped original constraint: " + token)
    if "S700" in data["question"].upper():
        if FOREIGN_S700.search(patched) and not FOREIGN_S700.search(original):
            raise ValueError("Patch changed or introduced a different power station")
        if BAD_TOPIC.search(new):
            raise ValueError("Unrelated topic in proposed correction")
    if prices(patched) - prices(original):
        raise ValueError("Patch inserted a new unverified price")
    if WRONG_VOC.search(patched) and not WRONG_VOC.search(original):
        raise ValueError("Patch introduced a false voltage comparison")
    return patched


def tagged_json(page_text, tag):
    """Google AI WebView sometimes wraps JSON strings across multiple lines."""
    decoder = json.JSONDecoder(strict=False)
    for match in re.finditer(r"\{", page_text):
        try:
            obj, _ = decoder.raw_decode(page_text[match.start():])
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and obj.get("tag") == tag:
            if isinstance(obj.get("old"), str) and isinstance(obj.get("new"), str):
                return obj
    return None


def safe_arithmetic_patch(data):
    """Only repair the explicit 25.2V < 24V test defect; do not invent sources."""
    original = data["draft"]
    variants = [
        r"25[.,]2\s*V\s*(?:<|<=)\s*24\s*V",
        r"25[.,]2\s*V\s+jest\s+mniejsze\s+niż\s+24\s*V",
        r"25[.,]2\s*V\s+mieści\s+się\s+w\s+(?:limicie\s+)?24\s*V",
    ]
    for variant in variants:
        m = re.search(variant, original, re.I)
        if m:
            return dict(data, draft=guarded_patch(
                data, m.group(0), "25,2 V przekracza limit 24 V"))
    return None


def validate_revision(before, after):
    """Prevent side effects on requirements, and prevent unverified facts entering drafts."""
    if not isinstance(after, dict) or not isinstance(after.get("draft"), str):
        raise ValueError("Research returned invalid data")
    if after.get("question") != before.get("question"):
        raise ValueError("Research changed the original question")
    if [c.get("requirement") for c in after.get("checks", [])] != [
            c.get("requirement") for c in before.get("checks", [])]:
        raise ValueError("Research changed the original requirements")
    for original, revised in zip(before["checks"], after["checks"]):
        if revised.get("status") == "met" and original.get("status") != "met":
            raise ValueError("AI cannot independently promote missing evidence to verified")
    previous, candidate = before["draft"], after["draft"]
    if "S700" in before.get("question", "").upper():
        for token in ("S700", "606", "48", "Amazon", "Argos", "Belfa"):
            if token.casefold() in previous.casefold() and token.casefold() not in candidate.casefold():
                raise ValueError("Correction dropped original constraint: " + token)
    if candidate == previous or not candidate.strip():
        raise ValueError("No valid change")
    if BARE_VERDICT.fullmatch(candidate):
        raise ValueError("Bare reviewer verdict is not a substantive answer")
    if "S700" in before.get("question", "").upper():
        if FOREIGN_S700.search(candidate) and not FOREIGN_S700.search(previous):
            raise ValueError("Research changed the model of the user's existing station")
        if BAD_TOPIC.search(candidate) and not BAD_TOPIC.search(previous):
            raise ValueError("Unrelated correction")
    if prices(candidate) - prices(previous):
        raise ValueError("Research inserted unsupported new prices")
    if WRONG_VOC.search(candidate) and not WRONG_VOC.search(previous):
        raise ValueError("Research introduced a false voltage comparison")
    return after
