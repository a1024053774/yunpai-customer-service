from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PATH = Path(__file__).with_name("domain_profiles.json")
_INTENTS = frozenset(("product_inquiry", "after_sales", "complaint", "chitchat"))


def load_domain_profiles(path: str | Path = _PATH) -> dict[str, dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload:
        raise ValueError("domain profiles must be a non-empty object")
    profiles: dict[str, dict[str, Any]] = {}
    for domain, profile in payload.items():
        if not isinstance(domain, str) or not domain.strip() or not isinstance(profile, dict):
            raise ValueError("invalid domain profile")
        intents = profile.get("intents")
        if not isinstance(intents, dict) or set(intents) != _INTENTS:
            raise ValueError(f"domain profile {domain} must map all controlled intents")
        if not isinstance(profile.get("label"), str) or not isinstance(profile.get("description"), str):
            raise ValueError(f"domain profile {domain} is missing label or description")
        if any(not isinstance(value, str) or not value.strip() for value in intents.values()):
            raise ValueError(f"domain profile {domain} has empty intent description")
        profiles[domain.strip()] = {
            "label": profile["label"].strip(),
            "description": profile["description"].strip(),
            "intents": {key: str(intents[key]).strip() for key in _INTENTS},
        }
    return profiles


DOMAIN_PROFILES = load_domain_profiles()


def profile_for_domain(domain: str) -> dict[str, Any]:
    try:
        profile = DOMAIN_PROFILES[domain.strip().lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported business domain: {domain}") from exc
    return {
        "label": profile["label"],
        "description": profile["description"],
        "intents": dict(profile["intents"]),
    }
