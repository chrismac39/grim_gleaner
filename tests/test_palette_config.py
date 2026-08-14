from pathlib import Path

import pytest

from gd_affix_relevance.palette_config import (
    PaletteParseError,
    default_palette,
    load_palette,
)


def test_load_palette_applies_overrides(tmp_path: Path) -> None:
    palette_file = tmp_path / "grim-gleaner-palette.txt"
    palette_file.write_text(
        "# sample overrides\n"
        "damage.pierce=r\n"
        "marker.generated=h\n",
        encoding="utf-8",
    )

    loaded = load_palette(palette_file)

    assert loaded.source == palette_file.resolve()
    assert loaded.values["damage.pierce"] == "r"
    assert loaded.values["marker.generated"] == "h"
    assert loaded.values["rarity.common"] == default_palette()["rarity.common"]


def test_load_palette_rejects_unknown_key(tmp_path: Path) -> None:
    palette_file = tmp_path / "bad.txt"
    palette_file.write_text("unknown.key=w\n", encoding="utf-8")

    with pytest.raises(PaletteParseError, match="Unknown palette key"):
        load_palette(palette_file)


def test_load_palette_rejects_invalid_value(tmp_path: Path) -> None:
    palette_file = tmp_path / "bad-value.txt"
    palette_file.write_text("damage.fire=zz\n", encoding="utf-8")

    with pytest.raises(PaletteParseError, match="Invalid color code"):
        load_palette(palette_file)
