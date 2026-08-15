"""Game/version snapshot helpers used by UI and profile persistence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_STEAM_MANIFEST = "appmanifest_219990.acf"
_HISTORY_FILE = "gdse-db-hash.txt"
_TEXT_EN_SEGMENTS = ("settings", "text_en")
_UNKNOWN = "unknown"
_PATCH_LINE_PATTERN = re.compile(r"^#\s*(patch|hotfix|update)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class GameVersionSnapshot:
    db_hash: str = _UNKNOWN
    steam_build_id: str = _UNKNOWN
    patch_versions: str = _UNKNOWN

    @property
    def has_known_db_hash(self) -> bool:
        return bool(self.db_hash) and self.db_hash.casefold() != _UNKNOWN


def detect_game_snapshot(game_folder: Path | None) -> GameVersionSnapshot:
    """Return best-effort current game snapshot for a configured install."""

    if game_folder is None:
        return GameVersionSnapshot()

    root = Path(game_folder).expanduser().resolve()
    text_en = root.joinpath(*_TEXT_EN_SEGMENTS)
    history = _latest_history_snapshot(text_en / _HISTORY_FILE)
    steam_build_id = _infer_steam_build_id(root)
    patch_versions = _infer_patch_versions(text_en)

    if history is None:
        return GameVersionSnapshot(
            db_hash=_UNKNOWN,
            steam_build_id=steam_build_id,
            patch_versions=patch_versions,
        )

    return GameVersionSnapshot(
        db_hash=history.db_hash,
        steam_build_id=(
            history.steam_build_id
            if history.steam_build_id.casefold() != _UNKNOWN
            else steam_build_id
        ),
        patch_versions=(
            history.patch_versions
            if history.patch_versions.casefold() != _UNKNOWN
            else patch_versions
        ),
    )


def evaluate_profile_snapshot_match(
    current: GameVersionSnapshot,
    profile: GameVersionSnapshot,
) -> str:
    """Classify profile snapshot status against current game snapshot."""

    if not profile.has_known_db_hash:
        return "unknown"
    if not current.has_known_db_hash:
        return "unknown"
    if profile.db_hash != current.db_hash:
        return "mismatch"
    return "match"


def snapshot_from_profile_fields(
    db_hash: str,
    steam_build_id: str,
    patch_versions: str,
) -> GameVersionSnapshot:
    return GameVersionSnapshot(
        db_hash=_normalize_value(db_hash),
        steam_build_id=_normalize_value(steam_build_id),
        patch_versions=_normalize_value(patch_versions),
    )


def _latest_history_snapshot(path: Path) -> GameVersionSnapshot | None:
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    for line in reversed(lines):
        parsed = _parse_history_line(line)
        if parsed is not None:
            return parsed
    return None


def _parse_history_line(line: str) -> GameVersionSnapshot | None:
    tokens = line.split()
    if not tokens:
        return None

    values: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        values[key.strip()] = value.strip()

    db_hash = values.get("hash", "")
    if not db_hash:
        return None

    return GameVersionSnapshot(
        db_hash=_normalize_value(db_hash),
        steam_build_id=_normalize_value(values.get("steam_build_id", "")),
        patch_versions=_normalize_value(values.get("patch_versions", "")),
    )


def _infer_steam_build_id(game_folder: Path) -> str:
    """Best-effort Steam build lookup, matching gdse behavior."""

    candidates: list[Path] = []
    common_dir = game_folder.parent
    if (
        common_dir is not None
        and common_dir.name
        and common_dir.name.casefold() == "common"
        and common_dir.parent is not None
    ):
        candidates.append(common_dir.parent / _STEAM_MANIFEST)

    for ancestor in game_folder.parents:
        if ancestor.name and ancestor.name.casefold() == "steamapps":
            candidates.append(ancestor / _STEAM_MANIFEST)

    for manifest in candidates:
        try:
            text = manifest.read_text(encoding="utf-8")
        except OSError:
            continue
        match = re.search(r'"buildid"\s+"([^\"]+)"', text)
        if match:
            return _normalize_value(match.group(1))
    return _UNKNOWN


def _infer_patch_versions(text_en: Path) -> str:
    """Best-effort patch marker discovery from text files."""

    if not text_en.is_dir():
        return _UNKNOWN

    versions: set[str] = set()
    for path in sorted(text_en.glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if _PATCH_LINE_PATTERN.match(line):
                versions.add(line.lstrip("#").strip())
    if not versions:
        return _UNKNOWN
    return "|".join(sorted(versions, key=str.casefold))


def _normalize_value(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return _UNKNOWN
    return normalized
