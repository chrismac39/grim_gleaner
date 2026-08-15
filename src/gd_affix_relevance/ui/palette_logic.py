"""In-application reference for item color palette logic."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPixmap
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
from gd_affix_relevance.game_version import (
    detect_game_snapshot,
    evaluate_profile_snapshot_match,
    snapshot_from_profile_fields,
)
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
        "Grade marker",
        (
            "marker.generated",
            "marker.default",
        ),
    ),
    (
        "Grade colors",
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


def _swatch_icon(hex_color: str) -> QIcon:
    pixmap = QPixmap(10, 10)
    pixmap.fill(QColor(hex_color))
    return QIcon(pixmap)


def _letter_options() -> Iterable[tuple[str, str]]:
    for code in sorted(_COLOR_NAMES):
        yield code, f"{code} ({_COLOR_NAMES[code]})"


class _ClickSelectComboBox(QComboBox):
    """Allow changes only through explicit open-and-click selection."""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()


class PaletteLogicPage(QWidget):
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
        layout.setSpacing(14)

        heading = QLabel("Color Palette", self)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        introduction = QLabel(
            "Choose color letters for each category below. These selectors write "
            "a local palette file used by Export Grades.",
            self,
        )
        introduction.setObjectName("pageHint")
        introduction.setWordWrap(True)
        layout.addWidget(introduction)

        tip = QLabel(
            "Tip: dropdowns show color letters with names. Example: damage.chaos = "
            "p (Purple). Use Save Palette after making changes.",
            self,
        )
        tip.setObjectName("pageHint")
        tip.setWordWrap(True)
        layout.addWidget(tip)

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
        self.refresh_version_blurb()

    def set_profile(self, profile: BuildProfile) -> None:
        self.profile = profile
        self.refresh_version_blurb()

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
            self.current_badge.setText("Current: folder not set")
            self._set_sync_badge("unknown", "? Unknown")
            self.version_blurb.setText(
                "Set Grim Dawn folder in Settings, then save profile to stamp hash/build/patch metadata."
            )
            return

        match_state = evaluate_profile_snapshot_match(snapshot, profile_snapshot)
        if match_state == "match":
            summary = "Profile snapshot matches current install."
            status_text = "✓ In Sync"
        elif match_state == "mismatch":
            summary = "Profile snapshot differs from current install."
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
            "Current "
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
            "Current install snapshot: "
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
        self.palette_path.setText(f"Active palette file: {target}")

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
        self.palette_path.setText(f"Active palette file: {target}")

    def _add_selector_section(
        self,
        layout: QVBoxLayout,
        title: str,
        keys: tuple[str, ...],
        parent: QWidget,
    ) -> None:
        section_title = QLabel(title, parent)
        section_title.setObjectName("guideSectionTitle")
        layout.addWidget(section_title)

        section_frame = QFrame(parent)
        section_frame.setObjectName("paletteSection")
        form = QFormLayout(section_frame)
        form.setContentsMargins(10, 8, 10, 8)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        defaults = default_palette()
        for key in keys:
            label = QLabel(key, section_frame)
            label.setObjectName("fieldLabel")
            label.setFixedWidth(self._label_width)

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

            form.addRow(label, selector)
            self._selectors[key] = selector

        layout.addWidget(section_frame)

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
