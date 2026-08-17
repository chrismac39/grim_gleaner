"""Palette parsing and defaults for Grim Dawn color-code letters."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PALETTE: dict[str, str] = {
    "rarity.common": "w",
    "rarity.magical": "y",
    "rarity.rare": "g",
    # Keep Epic/Legendary unset by default to preserve engine defaults.
    "damage.physical": "k",
    "damage.pierce": "f",
    "damage.bleeding": "r",
    "damage.fire": "o",
    "damage.cold": "c",
    "damage.lightning": "z",
    "damage.poison": "l",
    "damage.vitality": "m",
    "damage.life": "m",
    "damage.aether": "a",
    "damage.chaos": "p",
    "damage.elemental": "y",
    "nondamage.attribute0": "h",
    "nondamage.mastery_increment": "t",
    "nondamage.all_skill_increment": "t",
    # Export-only controls for grade marker insertion.
    "marker.generated": "c",
    "marker.default": "e",
    # Grade-specific marker colors.
    "grade.f": "r",
    "grade.d": "o",
    "grade.c": "y",
    "grade.b": "g",
    "grade.a": "t",
    "grade.s": "c",
    "grade.s_plus": "b",
    "grade.s_plusplus": "p",
}

KNOWN_KEYS = frozenset(
    {
        "rarity.common",
        "rarity.magical",
        "rarity.rare",
        "rarity.epic",
        "rarity.legendary",
        "damage.physical",
        "damage.pierce",
        "damage.bleeding",
        "damage.fire",
        "damage.cold",
        "damage.lightning",
        "damage.poison",
        "damage.vitality",
        "damage.life",
        "damage.aether",
        "damage.chaos",
        "damage.elemental",
        "nondamage.attribute0",
        "nondamage.mastery_increment",
        "nondamage.all_skill_increment",
        "nondamage.run_speed",
        "nondamage.cast_speed",
        "nondamage.attack_speed",
        "nondamage.total_speed",
        "nondamage.run_speed_modifier",
        "nondamage.offensive_ability",
        "nondamage.defensive_ability",
        "nondamage.crit_damage",
        "nondamage.damage_mult",
        "nondamage.total_damage",
        "marker.generated",
        "marker.default",
        "grade.f",
        "grade.d",
        "grade.c",
        "grade.b",
        "grade.a",
        "grade.s",
        "grade.s_plus",
        "grade.s_plusplus",
    }
)


@dataclass(frozen=True, slots=True)
class PaletteLoadResult:
    values: dict[str, str]
    source: Path | None
    overrides: dict[str, str]


class PaletteParseError(ValueError):
    """Raised when a palette file cannot be parsed."""


def default_palette() -> dict[str, str]:
    return dict(DEFAULT_PALETTE)


def palette_fingerprint(values: Mapping[str, str]) -> str:
    payload = json.dumps(dict(sorted(values.items())), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_palette(path: Path | None = None) -> PaletteLoadResult:
    if path is None:
        default_path = Path("grim-gleaner-palette.txt")
        if not default_path.is_file():
            return PaletteLoadResult(
                values=default_palette(), source=None, overrides={}
            )
        path = default_path

    resolved = Path(path).expanduser().resolve()
    overrides = _parse_palette_text(
        resolved.read_text(encoding="utf-8"), resolved
    )
    values = default_palette()
    values.update(overrides)
    return PaletteLoadResult(values=values, source=resolved, overrides=overrides)


def _parse_palette_text(text: str, source: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise PaletteParseError(
                f"Invalid palette line {line_no} in {source}: expected key=value"
            )
        key_raw, value_raw = line.split("=", 1)
        key = key_raw.strip().lower()
        if key not in KNOWN_KEYS:
            raise PaletteParseError(
                f"Unknown palette key '{key}' on line {line_no} in {source}"
            )
        code = _parse_color_code(value_raw.strip())
        if code is None:
            raise PaletteParseError(
                "Invalid color code "
                f"'{value_raw.strip()}' on line {line_no} in {source}. "
                "Use one letter such as w, y, g, f, r."
            )
        parsed[key] = code
    return parsed


def _parse_color_code(value: str) -> str | None:
    if len(value) != 1:
        return None
    if not value.isalpha():
        return None
    return value.lower()
