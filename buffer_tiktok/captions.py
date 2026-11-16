"""Content-aware, truthful TikTok captions for original AI videos.

Prefer an optional, reviewed sidecar with source video's prompt/concept.
Without sidecar metadata, use filename keywords or a neutral caption. Never
invent claims about the finished video and never remove AI disclosure.
"""
import hashlib
import json
from pathlib import Path

DEFAULT_TAGS = "#AIGenerated #AICat #CatTok #FunnyCats"


def make_caption(source: Path) -> str:
    source = Path(source)
    details = {}
    sidecar = source.with_suffix(".json")
    if sidecar.is_file():
        details = json.loads(sidecar.read_text(encoding="utf-8"))
        if not isinstance(details, dict):
            details = {}
    explicit = str(details.get("caption") or "").strip()
    if explicit:
        # Consent to use the human-reviewed caption comes from its committed metadata.
        text = explicit[:1900]
    else:
        concept = (str(details.get("concept") or "") + " " + source.stem).lower()
        if "coffee" in concept or "espresso" in concept:
            hooks = [
                "POV: Your cat has a Monday morning coffee routine. ☕ Who can relate?",
                "When the coffee is more important than the morning meeting. ☕",
                "This tiny coffee lover has better mornings than I do. ☕"
            ]
            tags = "#AICat #CatTok #CoffeeCat #AIGenerated"
        elif "office" in concept or "boss" in concept or "work" in concept:
            hooks = [
                "POV: Your new manager has paws. Would you take the job?",
                "This boss works hard... at finding snacks. Sound familiar?",
                "Corporate life, but make it cats. Who's your office cat?"
            ]
            tags = "#AICat #FunnyCats #OfficeHumor #AIGenerated"
        else:
            hooks = [
                "A tiny moment from an AI cat's world. What should happen next?",
                "What would you name this AI cat? Tell me below.",
                "This is your daily dose of imaginary cat chaos. What's next?"
            ]
            tags = DEFAULT_TAGS
        digest = hashlib.sha256(source.stem.encode("utf-8")).digest()
        text = hooks[int.from_bytes(digest[:2], "big") % len(hooks)] + " " + tags
    if "ai-generated" not in text.lower() and "#aigenerated" not in text.lower():
        text += " #AIGenerated"
    # Human-approved original prompt-based text, no misleading commercial offers.
    if len(text) > 2200:
        raise ValueError("Caption exceeds TikTok limit")
    return text
