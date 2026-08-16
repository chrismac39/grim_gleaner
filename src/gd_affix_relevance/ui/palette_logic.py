"""In-application reference for item color palette logic."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QSettings, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.palette_config import default_palette, load_palette
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.domain.profile import (
    GRADE_DISPLAY_STYLE_AFFIX_ONLY,
    GRADE_DISPLAY_STYLE_FULL,
    GRADE_DISPLAY_STYLE_ITEM_ONLY,
)
from gd_affix_relevance.game_version import (
    detect_game_snapshot,
    evaluate_profile_snapshot_match,
    snapshot_from_profile_fields,
)
from gd_affix_relevance.output import marker_palette_from_values
from gd_affix_relevance.ui.settings import PALETTE_FILE_SETTING
from gd_affix_relevance.ui.settings import GAME_FOLDER_SETTING

_DEFAULT_FILE_NAME = "grim-gleaner-palette.txt"
_NO_OVERRIDE = "__none__"

_COLOR_NAMES: dict[str, str] = {
    "a": "Aqua",
    "b": "Blue",
    "c": "Cyan",
    "d": "Dark Gray",
    "e": "Brown",
    "f": "Fuchsia/Pink",
    "g": "Green",
    "h": "Grayish Orange",
    "i": "Indigo",
    "j": "Disabled",
    "k": "Khaki",
    "l": "Olive",
    "m": "Maroon",
    "n": "Disabled",
    "o": "Orange",
    "p": "Purple",
    "q": "Grayish Magenta",
    "r": "Red",
    "s": "Silver",
    "t": "Teal",
    "u": "Disabled",
    "v": "Disabled",
    "w": "White",
    "x": "Dark Green",
    "y": "Yellow",
    "z": "Cobalt",
}

_COLOR_HEX: dict[str, str] = {
    "a": "#80ffd5",
    "b": "#4e7bd6",
    "c": "#00ffff",
    "d": "#4d4d4d",
    "e": "#8f6b24",
    "f": "#ff69b5",
    "g": "#10eb5d",
    "h": "#f1b56a",
    "i": "#6c6fe5",
    "j": "#4b4b4b",
    "k": "#f1e78c",
    "l": "#92cc00",
    "m": "#800000",
    "n": "#4b4b4b",
    "o": "#f3a44d",
    "p": "#bd94c6",
    "q": "#9d6b92",
    "r": "#ff4200",
    "s": "#c0c0c0",
    "t": "#00ffd2",
    "u": "#4b4b4b",
    "v": "#4b4b4b",
    "w": "#ffffff",
    "x": "#1f6b3a",
    "y": "#fff62c",
    "z": "#6a91e0",
}

_SECTION_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Rarity",
        (
            "rarity.common",
            "rarity.magical",
            "rarity.rare",
            "rarity.epic",
            "rarity.legendary",
        ),
    ),
    (
        "Damage",
        (
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
        ),
    ),
    (
        "Non-damage",
        (
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
        ),
    ),
    (
        "Gear Grade marker",
        (
            "marker.generated",
            "marker.default",
        ),
    ),
    (
        "Gear Grade colors",
        (
            "grade.f",
            "grade.d",
            "grade.c",
            "grade.b",
            "grade.a",
            "grade.s",
            "grade.s_plus",
            "grade.s_plusplus",
        ),
    ),
)

_ENGINE_DEFAULT_CODES: dict[str, str] = {
    "rarity.epic": "b",
    "rarity.legendary": "i",
    "nondamage.run_speed": "e",
    "nondamage.cast_speed": "e",
    "nondamage.attack_speed": "e",
    "nondamage.total_speed": "e",
    "nondamage.run_speed_modifier": "e",
    "nondamage.offensive_ability": "e",
    "nondamage.defensive_ability": "e",
    "nondamage.crit_damage": "e",
    "nondamage.damage_mult": "e",
    "nondamage.total_damage": "e",
}

_SECTION_HELP: dict[str, str] = {
    "Gear Grade colors": (
        "Per-grade annotation colors used for [GRADE]: and trailing (grade) tags. "
        "Any grade without an explicit override falls back to marker.generated."
    ),
}

_FIELD_HELP: dict[str, str] = {
    "marker.generated": (
        "Fallback annotation color for generated Gear Grade tags. "
        "Used whenever a specific grade color is not overridden."
    ),
    "marker.default": (
        "Default/base text color inserted before item names when needed. "
        "Also used when normalizing Rainbow set marker color."
    ),
}

GRADE_STYLE_OPTIONS: tuple[tuple[str, str], ...] = (
    (
        GRADE_DISPLAY_STYLE_FULL,
        "Full (EG: [A6]: Stonehide (f0) Stoneplate Greaves of Kings (b3))",
    ),
    (
        GRADE_DISPLAY_STYLE_ITEM_ONLY,
        "Item Only (EG: [A6]: Stonehide Stoneplate Greaves of Kings)",
    ),
    (
        GRADE_DISPLAY_STYLE_AFFIX_ONLY,
        "Affix/Suffix Only (EG: Stonehide (f0) Stoneplate Greaves of Kings (b3))",
    ),
)


def _swatch_icon(hex_color: str) -> QIcon:
    pixmap = QPixmap(10, 10)
    pixmap.fill(QColor(hex_color))
    return QIcon(pixmap)


def _swatch_strip_icon(colors: tuple[str, ...]) -> QIcon:
    if not colors:
        return _swatch_icon("#d7dde8")
    width = 12
    height = 10
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor("#00000000"))
    painter = QPainter(pixmap)
    stripe_count = len(colors)
    for index, color in enumerate(colors):
        start = (index * width) // stripe_count
        end = ((index + 1) * width) // stripe_count
        painter.fillRect(start, 0, max(1, end - start), height, QColor(color))
    painter.end()
    return QIcon(pixmap)


def _letter_options() -> Iterable[tuple[str, str]]:
    for code in sorted(_COLOR_NAMES):
        yield code, f"{code} ({_COLOR_NAMES[code]})"


class _ClickSelectComboBox(QComboBox):
    """Allow changes only through explicit open-and-click selection."""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()


class PaletteLogicPage(QWidget):
    profile_state_changed = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        settings: QSettings | None = None,
        profile: BuildProfile | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.profile = profile
        self._selectors: dict[str, QComboBox] = {}
        self._label_width = self._compute_label_width()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(10)

        heading = QLabel("Color Palette", self)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        badge_row = QWidget(self)
        badge_row.setObjectName("versionBadgeRow")
        badge_layout = QHBoxLayout(badge_row)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setSpacing(8)
        self.profile_badge = QLabel(badge_row)
        self.profile_badge.setObjectName("versionBadge")
        self.profile_badge.setProperty("kind", "profile")
        badge_layout.addWidget(self.profile_badge)
        self.current_badge = QLabel(badge_row)
        self.current_badge.setObjectName("versionBadge")
        self.current_badge.setProperty("kind", "current")
        badge_layout.addWidget(self.current_badge)
        self.sync_badge = QLabel(badge_row)
        self.sync_badge.setObjectName("versionStatusBadge")
        self.sync_badge.setProperty("syncState", "unknown")
        badge_layout.addWidget(self.sync_badge)
        badge_layout.addStretch()
        layout.addWidget(badge_row)

        self.version_blurb = QLabel(self)
        self.version_blurb.setObjectName("versionBadgeDetail")
        self.version_blurb.setWordWrap(True)
        layout.addWidget(self.version_blurb)

        introduction = QLabel(
            "Choose color letters for each category below. Export Grades uses this "
            "active palette to write the exact rarity, grade & damage type colors you see in-game.",
            self,
        )
        introduction.setObjectName("pageHint")
        introduction.setWordWrap(True)
        layout.addWidget(introduction)

        style_row = QHBoxLayout()
        style_row.setSpacing(8)
        style_label = QLabel("Gear Grade style", self)
        style_label.setObjectName("fieldLabel")
        style_label.setFixedWidth(self._label_width)
        style_row.addWidget(style_label)
        self.grade_style_selector = QComboBox(self)
        self.grade_style_selector.setObjectName("profileSwapSelector")
        for style_id, display in GRADE_STYLE_OPTIONS:
            self.grade_style_selector.addItem(display, style_id)
        self.grade_style_selector.currentIndexChanged.connect(
            self._grade_style_changed
        )
        style_row.addWidget(self.grade_style_selector, 1)
        self.applied_style_pill = QLabel(self)
        self.applied_style_pill.setObjectName("profileStatusPill")
        style_row.addWidget(self.applied_style_pill)
        layout.addLayout(style_row)

        self.style_example = QLabel(self)
        self.style_example.setObjectName("matchHighlightLegend")
        self.style_example.setTextFormat(Qt.TextFormat.RichText)
        self.style_example.setWordWrap(True)
        layout.addWidget(self.style_example)

        self.palette_path = QLabel(self)
        self.palette_path.setObjectName("pageHint")
        self.palette_path.setWordWrap(True)
        layout.addWidget(self.palette_path)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.save_button = QPushButton("Save Palette", self)
        self.save_button.setObjectName("primaryAction")
        self.save_button.clicked.connect(self._save_palette)
        actions.addWidget(self.save_button)

        self.reset_button = QPushButton("Reset to Defaults", self)
        self.reset_button.setObjectName("profileAction")
        self.reset_button.clicked.connect(self._reset_to_defaults)
        actions.addWidget(self.reset_button)

        self.reload_button = QPushButton("Reload File", self)
        self.reload_button.setObjectName("profileAction")
        self.reload_button.clicked.connect(self._reload_palette)
        actions.addWidget(self.reload_button)
        actions.addStretch()
        layout.addLayout(actions)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 8, 12, 8)
        content_layout.setSpacing(18)

        for section_title, keys in _SECTION_KEYS:
            self._add_selector_section(content_layout, section_title, keys, content)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        self._reload_palette()
        self._sync_grade_style_controls()
        self._refresh_style_examples_from_palette()
        self.refresh_version_blurb()

    def set_profile(self, profile: BuildProfile) -> None:
        self.profile = profile
        self._sync_grade_style_controls()
        self._refresh_style_examples_from_palette()
        self.refresh_version_blurb()

    def refresh_profile_state(self) -> None:
        self._sync_grade_style_controls()
        self._refresh_style_examples_from_palette()

    def refresh_version_blurb(self) -> None:
        raw_game_folder = ""
        if self.settings is not None:
            raw_game_folder = self.settings.value(
                GAME_FOLDER_SETTING,
                "",
                type=str,
            ).strip()
        snapshot = detect_game_snapshot(Path(raw_game_folder)) if raw_game_folder else None
        profile_snapshot = (
            snapshot_from_profile_fields(
                self.profile.saved_db_hash,
                self.profile.saved_steam_build_id,
                self.profile.saved_patch_versions,
            )
            if self.profile is not None
            else snapshot_from_profile_fields("", "", "")
        )
        if snapshot is None:
            self.profile_badge.setText("Profile: not stamped")
            self.current_badge.setText("Game: folder not set")
            self._set_sync_badge("unknown", "? Unknown")
            self.version_blurb.setText(
                "Set Grim Dawn folder in Settings, then save profile to stamp hash/build/patch metadata."
            )
            return

        match_state = evaluate_profile_snapshot_match(snapshot, profile_snapshot)
        if match_state == "match":
            summary = ""
            status_text = "✓ In Sync"
        elif match_state == "mismatch":
            summary = ""
            status_text = "✕ Out of Sync"
        else:
            summary = (
                "Profile snapshot unavailable; save profile to stamp version metadata."
            )
            status_text = "? Unknown"

        self.profile_badge.setText(
            "Profile "
            f"hash {self._short_hash(profile_snapshot.db_hash)}  "
            f"patch {profile_snapshot.patch_versions}"
        )
        self.current_badge.setText(
            "Game "
            f"hash {self._short_hash(snapshot.db_hash)}  "
            f"patch {snapshot.patch_versions}"
        )
        self._set_sync_badge(match_state, status_text)
        self.profile_badge.setToolTip(
            "Profile snapshot: "
            f"hash={profile_snapshot.db_hash}, "
            f"steam_build_id={profile_snapshot.steam_build_id}, "
            f"patch_versions={profile_snapshot.patch_versions}"
        )
        self.current_badge.setToolTip(
            "Game install snapshot: "
            f"hash={snapshot.db_hash}, "
            f"steam_build_id={snapshot.steam_build_id}, "
            f"patch_versions={snapshot.patch_versions}"
        )

        self.version_blurb.setText(summary)

    def _short_hash(self, value: str) -> str:
        normalized = value.strip().casefold()
        if not normalized or normalized == "unknown":
            return "unknown"
        return value[:8]

    def _set_sync_badge(self, state: str, text: str) -> None:
        self.sync_badge.setText(text)
        self.sync_badge.setProperty("syncState", state)
        self.sync_badge.style().unpolish(self.sync_badge)
        self.sync_badge.style().polish(self.sync_badge)

    def _compute_label_width(self) -> int:
        keys = [key for _, section_keys in _SECTION_KEYS for key in section_keys]
        metrics = self.fontMetrics()
        widest = max(metrics.horizontalAdvance(key) for key in keys)
        return widest + 14

    def _palette_path(self) -> Path:
        raw = ""
        if self.settings is not None:
            raw = self.settings.value(PALETTE_FILE_SETTING, "", type=str).strip()
        if raw:
            return Path(raw).expanduser().resolve()
        return (Path.cwd() / _DEFAULT_FILE_NAME).resolve()

    def _set_selector_value(self, key: str, value: str | None) -> None:
        selector = self._selectors[key]
        target = value.lower() if value else _NO_OVERRIDE
        index = selector.findData(target)
        if index < 0:
            index = selector.findData(_NO_OVERRIDE)
        selector.setCurrentIndex(index)
        self._apply_selector_tint(selector)

    def _effective_values_from_ui(self) -> dict[str, str]:
        values: dict[str, str] = {}
        defaults = default_palette()
        for key, selector in self._selectors.items():
            choice = selector.currentData()
            if not isinstance(choice, str):
                continue
            if choice == _NO_OVERRIDE:
                continue
            default_choice = defaults.get(key) or _ENGINE_DEFAULT_CODES.get(key)
            if default_choice is not None and choice == default_choice:
                continue
            values[key] = choice
        return values

    def _reload_palette(self) -> None:
        defaults = default_palette()
        target = self._palette_path()
        overrides: dict[str, str] = {}
        if target.is_file():
            try:
                loaded = load_palette(target)
                for key, value in loaded.values.items():
                    if defaults.get(key) != value:
                        overrides[key] = value
            except (OSError, ValueError) as error:
                QMessageBox.warning(
                    self,
                    "Palette File Error",
                    f"Could not read {target}: {error}",
                )

        for key in self._selectors:
            if key in overrides:
                self._set_selector_value(key, overrides[key])
            elif key in defaults or key in _ENGINE_DEFAULT_CODES:
                self._set_selector_value(
                    key,
                    defaults.get(key) or _ENGINE_DEFAULT_CODES.get(key),
                )
            else:
                self._set_selector_value(key, None)
        self.palette_path.setText(
            "Active palette file (used by Export Grades for in-game colors): "
            f"{target}"
        )
        self._refresh_style_examples_from_palette()

    def _reset_to_defaults(self) -> None:
        defaults = default_palette()
        for key in self._selectors:
            if key in defaults or key in _ENGINE_DEFAULT_CODES:
                self._set_selector_value(
                    key,
                    defaults.get(key) or _ENGINE_DEFAULT_CODES.get(key),
                )
            else:
                self._set_selector_value(key, None)
        self._refresh_style_examples_from_palette()

    def _save_palette(self) -> None:
        target = self._palette_path()
        target.parent.mkdir(parents=True, exist_ok=True)

        if self.settings is not None:
            self.settings.setValue(PALETTE_FILE_SETTING, str(target))
            self.settings.sync()

        payload = self._effective_values_from_ui()
        lines = [
            "# Grim Gleaner palette overrides",
            "# Auto-generated from the Color Palette page",
            "",
        ]
        for key in sorted(payload):
            lines.append(f"{key}={payload[key]}")
        if len(lines) == 3:
            lines.append("# No overrides; built-in defaults will be used.")
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.palette_path.setText(
            "Active palette file (used by Export Grades for in-game colors): "
            f"{target}"
        )
        self._refresh_style_examples_from_palette()

    def _grade_style_changed(self, index: int) -> None:
        if index < 0 or self.profile is None:
            return
        value = self.grade_style_selector.itemData(index)
        if not isinstance(value, str):
            return
        normalized = value.strip().casefold()
        if self.profile.grade_display_style == normalized:
            self._sync_grade_style_controls()
            return
        self.profile.grade_display_style = normalized
        self._sync_grade_style_controls()
        self._refresh_style_examples_from_palette()
        self.profile_state_changed.emit()

    def _sync_grade_style_controls(self) -> None:
        if self.profile is None:
            return
        normalized = self.profile.grade_display_style.strip().casefold()
        for index in range(self.grade_style_selector.count()):
            value = self.grade_style_selector.itemData(index)
            if isinstance(value, str) and value.strip().casefold() == normalized:
                blocker = QSignalBlocker(self.grade_style_selector)
                self.grade_style_selector.setCurrentIndex(index)
                del blocker
                break
        label = "Full"
        if normalized == GRADE_DISPLAY_STYLE_ITEM_ONLY:
            label = "Item Only"
        elif normalized == GRADE_DISPLAY_STYLE_AFFIX_ONLY:
            label = "Affix/Suffix Only"
        self.applied_style_pill.setText(f"Applied: {label}")

    def _preview_palette_values(self) -> dict[str, str]:
        values = default_palette()
        for key, selector in self._selectors.items():
            code = selector.currentData()
            if isinstance(code, str) and code != _NO_OVERRIDE:
                values[key] = code
        return values

    def _refresh_style_examples_from_palette(self) -> None:
        if self.profile is None:
            return
        marker_hex, affix_hex, item_hex, grade_hex, rarity_hex = self._active_palette_hex()
        style = self.profile.grade_display_style.strip().casefold()
        self.style_example.setText(
            "Style EG: "
            f"{self._style_example_html(style, affix_hex, item_hex, grade_hex)}"
            "<br/>"
            f"{self._style_rarity_legend_html(rarity_hex)}"
            "<br/>"
            f"{self._style_palette_legend_html(grade_hex)}"
        )
        for index in range(self.grade_style_selector.count()):
            style_id = self.grade_style_selector.itemData(index)
            if not isinstance(style_id, str):
                continue
            color = self._selector_item_color()
            self.grade_style_selector.setItemData(
                index,
                QBrush(QColor(color)),
                Qt.ItemDataRole.ForegroundRole,
            )
            self.grade_style_selector.setItemIcon(
                index,
                self._selector_item_icon(style_id, grade_hex, affix_hex, item_hex),
            )

        selected_color = self._selector_item_color()
        self.grade_style_selector.setStyleSheet(
            "QComboBox#profileSwapSelector {"
            "background: #242932;"
            "border: 1px solid #3a414d;"
            "border-radius: 5px;"
            "padding: 4px 9px;"
            "min-width: 260px;"
            f"color: {selected_color};"
            "}"
            "QComboBox#profileSwapSelector QAbstractItemView {"
            "background: #20242b;"
            "border: 1px solid #3a414d;"
            "selection-background-color: #3a4454;"
            "}"
        )

    def _active_palette_hex(self) -> tuple[str, str, str, dict[str, str], dict[str, str]]:
        values = self._preview_palette_values()
        palette = marker_palette_from_values(values)
        marker_code = palette.grade_color_codes.get("S", palette.generated_color_code)
        marker_hex = self._code_to_hex(marker_code, "#00ffff")

        rarity_hex = {
            "common": self._code_to_hex(values.get("rarity.common", "w"), "#ffffff"),
            "magical": self._code_to_hex(values.get("rarity.magical", "y"), "#fff62c"),
            "rare": self._code_to_hex(values.get("rarity.rare", "g"), "#10eb5d"),
            "epic": self._code_to_hex(values.get("rarity.epic", "b"), "#4e7bd6"),
            "legendary": self._code_to_hex(values.get("rarity.legendary", "p"), "#bd94c6"),
        }

        affix_hex = rarity_hex["rare"]
        item_hex = self._code_to_hex(values.get("marker.default", "e"), "#8f6b24")
        grade_hex = {
            "F0": self._code_to_hex(
                palette.grade_color_codes.get("F", palette.generated_color_code),
                "#ff4200",
            ),
            "D1": self._code_to_hex(
                palette.grade_color_codes.get("D", palette.generated_color_code),
                "#f3a44d",
            ),
            "C1": self._code_to_hex(
                palette.grade_color_codes.get("C", palette.generated_color_code),
                "#fff62c",
            ),
            "B3": self._code_to_hex(
                palette.grade_color_codes.get("B", palette.generated_color_code),
                "#10eb5d",
            ),
            "A6": self._code_to_hex(
                palette.grade_color_codes.get("A", palette.generated_color_code),
                "#00ffd2",
            ),
            "S6": self._code_to_hex(
                palette.grade_color_codes.get("S", palette.generated_color_code),
                "#00ffff",
            ),
            "S+7": self._code_to_hex(
                palette.grade_color_codes.get("S+", palette.generated_color_code),
                "#4e7bd6",
            ),
            "S++8": self._code_to_hex(
                palette.grade_color_codes.get("S++", palette.generated_color_code),
                "#bd94c6",
            ),
        }
        return marker_hex, affix_hex, item_hex, grade_hex, rarity_hex

    def _code_to_hex(self, code: str, fallback_hex: str) -> str:
        normalized = str(code).strip().casefold()
        if not normalized:
            return fallback_hex
        return _COLOR_HEX.get(normalized, fallback_hex)

    def _style_palette_legend_html(self, grade_hex: dict[str, str]) -> str:
        order = ("F0", "D1", "C1", "B3", "A6", "S6", "S+7", "S++8")
        parts = [
            f"<span style='color: {grade_hex[token]}; font-weight: 700;'>{token}</span>"
            for token in order
        ]
        return "Palette grade colors: " + " ".join(parts)

    def _selector_item_color(self) -> str:
        return "#d7dde8"

    def _selector_item_icon(
        self,
        style: str,
        grade_hex: dict[str, str],
        affix_hex: str,
        item_hex: str,
    ) -> QIcon:
        lead_hex = grade_hex.get("A6", "#00ffd2")
        low_hex = grade_hex.get("F0", "#ff4200")
        suffix_hex = grade_hex.get("B3", "#10eb5d")
        normalized = style.strip().casefold()
        if normalized == GRADE_DISPLAY_STYLE_ITEM_ONLY:
            return _swatch_strip_icon((lead_hex, affix_hex, item_hex, affix_hex))
        if normalized == GRADE_DISPLAY_STYLE_AFFIX_ONLY:
            return _swatch_strip_icon((affix_hex, low_hex, suffix_hex))
        return _swatch_strip_icon((lead_hex, affix_hex, item_hex, suffix_hex))

    def _style_rarity_legend_html(self, rarity_hex: dict[str, str]) -> str:
        return (
            "Rarity colors: "
            f"<span style='color: {rarity_hex['common']}; font-weight: 700;'>common</span> "
            f"<span style='color: {rarity_hex['magical']}; font-weight: 700;'>magical</span> "
            f"<span style='color: {rarity_hex['rare']}; font-weight: 700;'>rare</span> "
            f"<span style='color: {rarity_hex['epic']}; font-weight: 700;'>epic</span> "
            f"<span style='color: {rarity_hex['legendary']}; font-weight: 700;'>legendary</span>"
        )

    def _style_example_html(
        self,
        style: str,
        affix_hex: str,
        item_hex: str,
        grade_hex: dict[str, str],
    ) -> str:
        leading_style = (
            f"color: {grade_hex.get('A6', '#00ffd2')}; font-weight: 700;"
        )
        prefix_grade_style = (
            f"color: {grade_hex.get('F0', '#ff4200')}; font-weight: 700;"
        )
        suffix_grade_style = (
            f"color: {grade_hex.get('B3', '#10eb5d')}; font-weight: 700;"
        )
        affix_style = f"color: {affix_hex};"
        item_style = f"color: {item_hex};"
        if style == GRADE_DISPLAY_STYLE_ITEM_ONLY:
            return (
                f"<span style='{leading_style}'>[A6]: </span>"
                f"<span style='{affix_style}'>Stonehide </span>"
                f"<span style='{item_style}'>Stoneplate Greaves</span>"
                f"<span style='{affix_style}'> of Kings</span>"
            )
        if style == GRADE_DISPLAY_STYLE_AFFIX_ONLY:
            return (
                f"<span style='{affix_style}'>Stonehide </span>"
                f"<span style='{prefix_grade_style}'>(f0)</span>"
                f"<span style='{item_style}'> Stoneplate Greaves </span>"
                f"<span style='{affix_style}'>of Kings </span>"
                f"<span style='{suffix_grade_style}'>(b3)</span>"
            )
        return (
            f"<span style='{leading_style}'>[A6]: </span>"
            f"<span style='{affix_style}'>Stonehide </span>"
            f"<span style='{prefix_grade_style}'>(f0)</span>"
            f"<span style='{item_style}'> Stoneplate Greaves </span>"
            f"<span style='{affix_style}'>of Kings </span>"
            f"<span style='{suffix_grade_style}'>(b3)</span>"
        )

    def _add_selector_section(
        self,
        layout: QVBoxLayout,
        title: str,
        keys: tuple[str, ...],
        parent: QWidget,
    ) -> None:
        section_title_row = QWidget(parent)
        section_title_layout = QHBoxLayout(section_title_row)
        section_title_layout.setContentsMargins(0, 0, 0, 0)
        section_title_layout.setSpacing(6)

        section_title = QLabel(title, section_title_row)
        section_title.setObjectName("guideSectionTitle")
        section_title_layout.addWidget(section_title)
        section_help = _SECTION_HELP.get(title)
        if section_help:
            section_title_layout.addWidget(self._build_info_icon(section_help, section_title_row))
        section_title_layout.addStretch()
        layout.addWidget(section_title_row)

        section_frame = QFrame(parent)
        section_frame.setObjectName("paletteSection")
        form = QFormLayout(section_frame)
        form.setContentsMargins(10, 8, 10, 8)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        defaults = default_palette()
        for key in keys:
            label_host = QWidget(section_frame)
            label_layout = QHBoxLayout(label_host)
            label_layout.setContentsMargins(0, 0, 0, 0)
            label_layout.setSpacing(6)

            label = QLabel(key, label_host)
            label.setObjectName("fieldLabel")
            label.setFixedWidth(self._label_width)
            label_layout.addWidget(label)
            field_help = _FIELD_HELP.get(key)
            if field_help:
                label_layout.addWidget(self._build_info_icon(field_help, label_host))
            label_layout.addStretch()

            selector = _ClickSelectComboBox(section_frame)
            selector.setObjectName("paletteSelector")
            fallback = "engine/default" if key not in defaults else "built-in default"
            selector.addItem(f"No override ({fallback})", _NO_OVERRIDE)
            for code, display in _letter_options():
                swatch = _COLOR_HEX.get(code)
                if swatch:
                    selector.addItem(_swatch_icon(swatch), display, code)
                else:
                    selector.addItem(display, code)
                row_index = selector.count() - 1
                if swatch:
                    swatch_color = QColor(swatch)
                    selector.setItemData(
                        row_index,
                        QBrush(swatch_color),
                        Qt.ItemDataRole.ForegroundRole,
                    )
            selector.currentIndexChanged.connect(
                lambda _index, combo=selector: self._apply_selector_tint(combo)
            )

            form.addRow(label_host, selector)
            self._selectors[key] = selector

        layout.addWidget(section_frame)

    def _build_info_icon(self, tooltip: str, parent: QWidget) -> QLabel:
        badge = QLabel("i", parent)
        badge.setObjectName("infoIcon")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setToolTip(tooltip)
        badge.setCursor(Qt.CursorShape.ArrowCursor)
        badge.setFixedSize(16, 16)
        return badge

    def _apply_selector_tint(self, selector: QComboBox) -> None:
        code = selector.currentData()
        if not isinstance(code, str) or code == _NO_OVERRIDE:
            selector.setStyleSheet("")
            return
        hex_color = _COLOR_HEX.get(code)
        if not hex_color:
            selector.setStyleSheet("")
            return

        selector.setStyleSheet(
            "QComboBox#paletteSelector {"
            "background: #242932;"
            f"color: {hex_color};"
            "border: 1px solid #3a414d;"
            "border-radius: 5px;"
            "padding: 6px 10px;"
            "min-width: 102px;"
            "}"
            "QComboBox#paletteSelector QAbstractItemView {"
            "background: #20242b;"
            "border: 1px solid #3a414d;"
            "selection-background-color: #3a4454;"
            "}"
        )
