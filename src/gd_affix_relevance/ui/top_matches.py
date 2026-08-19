"""Per-slot affix and unique-equipment recommendations."""

from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSettings, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.catalog import (
    AffixCatalog,
    ItemCatalog,
    ItemContainerSource,
    ItemMonsterSource,
    ItemVariantDefinition,
    SkillCatalog,
)
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
from gd_affix_relevance.scoring import (
    ADDON_AUGMENT,
    ADDON_COMPONENT,
    ADDON_TYPE_LABELS,
    RankedAffixVariant,
    RankedAddonVariant,
    RankedItemVariant,
    UNIQUE_ITEM_TYPES,
    UNIQUE_TYPE_LABELS,
    canonical_skill_reference,
    profile_weight_for_semantic_id,
    rank_addons_for_slot,
    rank_affixes_for_slot,
    rank_unique_items_for_slot,
    semantic_stat_id,
)
from gd_affix_relevance.slots import (
    FILTER_LABELS,
    SLOT_FILTERS,
    SLOT_GROUPS,
    SLOT_LABELS,
    WEAPON_SLOTS,
)
from gd_affix_relevance.ui.catalog import RESISTANCE_STATS
from gd_affix_relevance.stats import registered_stat_definitions
from gd_affix_relevance.ui.settings import (
    GAME_FOLDER_SETTING,
)
from gd_affix_relevance.ui.widgets import StatRow
from gd_affix_relevance.output import marker_palette_from_values
from gd_affix_relevance.palette_config import default_palette, load_palette

STAT_LABELS = {
    definition.stat_id: definition.label
    for definition in registered_stat_definitions()
}
RESULTS_PER_AFFIX_TABLE = 5
SKILL_RANK_HIGHLIGHT = QColor("#f1b56a")
SKILL_MODIFIER_HIGHLIGHT = QColor("#6a91e0")
SKILL_BOTH_HIGHLIGHT = QColor("#bd94c6")
HIGHLIGHT_TEXT = QColor("#102528")
MATCHED_STAT_COLOR = "#82d99b"
UNMATCHED_STAT_COLOR = "#b7bec9"
SKILL_RANK_STAT_COLOR = "#f1b56a"
SKILL_MODIFIER_STAT_COLOR = "#6a91e0"
SKILL_BOTH_STAT_COLOR = "#bd94c6"
PALETTE_CODE_HEX = {
    "a": "#80ffd5", "b": "#4e7bd6", "c": "#00ffff", "d": "#4d4d4d",
    "e": "#8f6b24", "f": "#ff69b5", "g": "#10eb5d", "h": "#f1b56a",
    "i": "#6c6fe5", "j": "#4b4b4b", "k": "#f1e78c", "l": "#92cc00",
    "m": "#800000", "n": "#4b4b4b", "o": "#f3a44d", "p": "#bd94c6",
    "q": "#9d6b92", "r": "#ff4200", "s": "#c0c0c0", "t": "#00ffd2",
    "u": "#4b4b4b", "v": "#4b4b4b", "w": "#ffffff", "x": "#1f6b3a",
    "y": "#fff62c", "z": "#6a91e0",
}
STAT_CATEGORY_COLORS = {
    "elemental": "#f2d64b",
    "fire": "#ef922f",
    "acid": "#64e34b",
    "aether": "#42c7bd",
    "bleeding": "#c05b5b",
    "pierce": "#e47878",
    "chaos": "#e56acb",
    "cold": "#5ee8eb",
    "lightning": "#65bff2",
    "physical": "#cfaa79",
    "vitality": "#b987d6",
    "attribute": "#ed91c5",
    "ability": "#b8d85f",
    "health": "#f06b6b",
    "energy": "#319d98",
}
DETAIL_TITLE_COLORS = {
    "monster_infrequent": "#28613a",
    "epic": "#315b88",
    "legendary": "#60427f",
    "affix_rare": "#28613a",
    "affix_magical": "#786019",
    "affix": "#3a404b",
    "component": "#786019",
    "augment": "#25676b",
}


def _format_score(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


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


def _item_source_label(variant: ItemVariantDefinition) -> str:
    if (
        variant.acquisition_source == "Specific Monster Drop"
        and variant.monster_sources
    ):
        return _compact_named_source(variant.monster_sources)
    if (
        variant.acquisition_source == "Lootable Container"
        and variant.container_sources
    ):
        return "Lootable Container: " + _compact_named_source(
            variant.container_sources
        )
    return variant.acquisition_source


def _compact_named_source(
    sources: tuple[ItemMonsterSource | ItemContainerSource, ...],
) -> str:
    first = sources[0].name
    remaining = len(sources) - 1
    if not remaining:
        return first
    noun = "other" if remaining == 1 else "others"
    return f"{first} +{remaining} {noun}"


def _granted_skill_section(names: tuple[str, ...]) -> tuple[str, ...]:
    distinct_names = tuple(dict.fromkeys(name for name in names if name))
    if not distinct_names:
        return ()
    heading = (
        "Granted skill (not evaluated):"
        if len(distinct_names) == 1
        else "Granted skills (not evaluated):"
    )
    return (
        _html_line(""),
        _html_line(heading, bold=True),
        *(
            _html_line(f"- {name}", color=SKILL_RANK_STAT_COLOR)
            for name in distinct_names
        ),
    )


def _has_selected_skill_bonus(
    semantic_stat_ids: tuple[str, ...], profile: BuildProfile
) -> bool:
    selected_skills = {
        canonical_skill_reference(skill_id) for skill_id in profile.skill_weights
    }
    selected_masteries = {mastery for mastery in profile.masteries if mastery}
    return any(
        (
            stat_id.startswith("skill_bonus:")
            and canonical_skill_reference(
                stat_id.removeprefix("skill_bonus:")
            )
            in selected_skills
        )
        or (
            bool(selected_skills)
            and stat_id.startswith("mastery_bonus:")
            and stat_id.removeprefix("mastery_bonus:") in selected_masteries
        )
        for stat_id in semantic_stat_ids
    )


def _highlight_item(
    item: QTableWidgetItem,
    kind: str,
    *,
    rank_highlight: QColor = SKILL_RANK_HIGHLIGHT,
    modifier_highlight: QColor = SKILL_MODIFIER_HIGHLIGHT,
    both_highlight: QColor = SKILL_BOTH_HIGHLIGHT,
) -> None:
    if kind == "both":
        item.setBackground(both_highlight)
        item.setToolTip(
            "Includes bonus ranks for an active build skill and modifies that "
            "active skill."
        )
    elif kind == "modifier":
        item.setBackground(modifier_highlight)
        item.setToolTip(
            "Modifies an active build skill."
        )
    elif kind == "rank":
        item.setBackground(rank_highlight)
        item.setToolTip("Includes bonus ranks for an active build skill.")
    if kind:
        item.setForeground(HIGHLIGHT_TEXT)


def _grade_color(marker: str, colors: dict[str, QColor]) -> QColor | None:
    upper = marker.upper()
    for token in ("S++", "S+", "S", "A", "B", "C", "D", "F"):
        if token in upper:
            return colors.get(token)
    return None


def _set_table_item_color(
    item: QTableWidgetItem,
    column: int,
    marker: str,
    grade_colors: dict[str, QColor] | None,
) -> None:
    if column == 0 and grade_colors:
        color = _grade_color(marker, grade_colors)
        if color is not None:
            item.setForeground(color)


def _html_line(text: str, *, color: str = "", bold: bool = False) -> str:
    if not text:
        return "<div><br></div>"
    style = []
    if color:
        style.append(f"color: {color}")
    if bold:
        style.append("font-weight: 600")
    style_attr = f' style="{"; ".join(style)}"' if style else ""
    return f"<div{style_attr}>{escape(text)}</div>"


def _semantic_stat_color(stat_id: str, *, matched: bool) -> str:
    """Return a Rainbow-inspired color without changing semantic scoring data."""

    if stat_id.startswith("skill_modifier:"):
        return SKILL_MODIFIER_STAT_COLOR
    if stat_id.startswith(("skill_bonus:", "mastery_bonus:")):
        return SKILL_RANK_STAT_COLOR

    # Specific damage families take precedence over broad core categories. This
    # also colors conversions, base weapon damage, retaliation, and resistances.
    damage_families = (
        (("elemental",), "elemental"),
        # Frostburn must be tested before the shorter "burn" token.
        (("cold", "frostburn"), "cold"),
        (("fire", "burn"), "fire"),
        (("acid", "poison"), "acid"),
        (("aether",), "aether"),
        (("bleeding",), "bleeding"),
        (("pierce",), "pierce"),
        (("chaos",), "chaos"),
        (("lightning", "electrocute"), "lightning"),
        (("physical", "internal_trauma"), "physical"),
        (("vitality", "vitality_decay"), "vitality"),
    )
    for tokens, family in damage_families:
        if any(token in stat_id for token in tokens):
            return STAT_CATEGORY_COLORS[family]

    if "offensive_ability" in stat_id or "defensive_ability" in stat_id:
        return STAT_CATEGORY_COLORS["ability"]
    if "health" in stat_id or "healing" in stat_id:
        return STAT_CATEGORY_COLORS["health"]
    if "energy" in stat_id or "mana" in stat_id:
        return STAT_CATEGORY_COLORS["energy"]
    if any(token in stat_id for token in ("physique", "cunning", "spirit")):
        return STAT_CATEGORY_COLORS["attribute"]
    return MATCHED_STAT_COLOR if matched else UNMATCHED_STAT_COLOR


def _stat_html(stat_id: str, label: str, *, matched: bool) -> str:
    color = _semantic_stat_color(stat_id, matched=matched)
    return _html_line(f"- {label}", color=color)


class MatchDetailPane(QFrame):
    """Fixed title bar over an independently scrolling rich-text body."""

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("matchDetailPane")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.title = QLabel(self)
        self.title.setObjectName("matchDetailTitle")
        self.title.setWordWrap(False)
        self.title.hide()
        layout.addWidget(self.title)
        self.body = QTextEdit(self)
        self.body.setObjectName("matchDetails")
        self.body.setReadOnly(True)
        self.body.setPlaceholderText(placeholder)
        layout.addWidget(self.body, 1)

    def clear(self) -> None:
        self.title.clear()
        self.title.hide()
        self.body.clear()

    def set_title(self, text: str, color: str) -> None:
        self.title.setText(text)
        self.title.setStyleSheet(
            f"background-color: {color}; color: #ffffff;"
        )
        self.title.show()


def _configure_table(table: QTableWidget, stretch_column: int) -> None:
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(26)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)


class AffixSlotTable(QTableWidget):
    match_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 4, parent)
        self.matches: tuple[RankedAffixVariant, ...] = ()
        self._updating = False
        self.setObjectName("affixSlotTable")
        self.setHorizontalHeaderLabels(("Grade", "Affix", "Score", "Coverage"))
        _configure_table(self, 1)
        self.setMinimumHeight(190)
        self.setMaximumHeight(205)
        self.currentCellChanged.connect(self._selection_changed)

    def set_matches(
        self,
        matches: tuple[RankedAffixVariant, ...],
        profile: BuildProfile | None = None,
        grade_colors: dict[str, QColor] | None = None,
        rank_highlight: QColor = SKILL_RANK_HIGHLIGHT,
        modifier_highlight: QColor = SKILL_MODIFIER_HIGHLIGHT,
        both_highlight: QColor = SKILL_BOTH_HIGHLIGHT,
    ) -> None:
        self._updating = True
        self.matches = matches
        self.clearContents()
        self.setRowCount(len(matches))
        for row, match in enumerate(matches):
            score = match.score
            highlight = (
                "rank"
                if profile is not None
                and _has_selected_skill_bonus(match.semantic_stat_ids, profile)
                else ""
            )
            values = (
                match.marker,
                match.affix.display_name,
                _format_score(score.effective_score),
                f"{score.matched_count}/{score.total_category_count}",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column != 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column != 0:
                    _highlight_item(
                        item,
                        highlight,
                        rank_highlight=rank_highlight,
                        modifier_highlight=modifier_highlight,
                        both_highlight=both_highlight,
                    )
                _set_table_item_color(item, column, match.marker, grade_colors)
                self.setItem(row, column, item)
        self._updating = False

    def _selection_changed(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if not self._updating and 0 <= current_row < len(self.matches):
            self.match_selected.emit(self.matches[current_row])


class AffixSlotRow(QFrame):
    def __init__(self, slot_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slot_id = slot_id
        self.setObjectName("affixSlotRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 10)
        layout.setSpacing(10)

        slot_label = QLabel(SLOT_LABELS[slot_id], self)
        slot_label.setObjectName("affixSlotName")
        slot_label.setFixedWidth(100)
        layout.addWidget(slot_label)

        self.tables: dict[str, AffixSlotTable] = {}
        for kind in ("prefix", "suffix"):
            section = QWidget(self)
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(5)
            title = QLabel("Prefixes" if kind == "prefix" else "Suffixes")
            title.setObjectName("affixTableTitle")
            section_layout.addWidget(title)
            table = AffixSlotTable(section)
            section_layout.addWidget(table)
            layout.addWidget(section, 1)
            self.tables[kind] = table


class AddonSlotTable(QTableWidget):
    match_selected = Signal(object)

    def __init__(
        self, addon_type: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(0, 5, parent)
        self.addon_type = addon_type
        self.matches: tuple[RankedAddonVariant, ...] = ()
        self._updating = False
        self.setObjectName("addonSlotTable")
        metadata_label = (
            "Faction / Source" if addon_type == ADDON_COMPONENT else "Faction"
        )
        self.setHorizontalHeaderLabels(
            (
                "Grade",
                ADDON_TYPE_LABELS[addon_type],
                metadata_label,
                "Score",
                "Coverage",
            )
        )
        _configure_table(self, 1)
        self.setMinimumHeight(190)
        self.setMaximumHeight(205)
        self.currentCellChanged.connect(self._selection_changed)

    def set_matches(
        self,
        matches: tuple[RankedAddonVariant, ...],
        profile: BuildProfile | None = None,
        grade_colors: dict[str, QColor] | None = None,
        rank_highlight: QColor = SKILL_RANK_HIGHLIGHT,
        modifier_highlight: QColor = SKILL_MODIFIER_HIGHLIGHT,
        both_highlight: QColor = SKILL_BOTH_HIGHLIGHT,
    ) -> None:
        self._updating = True
        self.matches = matches
        self.clearContents()
        self.setRowCount(len(matches))
        for row, match in enumerate(matches):
            score = match.score
            has_rank_bonus = profile is not None and _has_selected_skill_bonus(
                match.semantic_stat_ids, profile
            )
            highlight = (
                "both"
                if has_rank_bonus and match.has_selected_skill_modifier
                else "modifier"
                if match.has_selected_skill_modifier
                else "rank" if has_rank_bonus else ""
            )
            if match.addon_type == ADDON_COMPONENT:
                factions = tuple(
                    dict.fromkeys(
                        source.faction_name or source.faction_source
                        for source in match.variant.vendor_sources
                        if source.faction_name or source.faction_source
                    )
                )
                faction_text = ", ".join(factions)
                source = match.variant.acquisition_source
                if faction_text and "Random Blueprint" in source:
                    extras = ["Random Blueprint"]
                    if "Special Vendor" in source:
                        extras.append("Special Vendor")
                    metadata = f"{faction_text} / {' / '.join(extras)}"
                else:
                    metadata = faction_text or source
            else:
                metadata = (
                    match.variant.faction_name
                    or match.variant.faction_source
                    or "Unknown"
                )
            values = (
                match.marker,
                match.item.display_name,
                metadata,
                _format_score(score.effective_score),
                f"{score.matched_count}/{score.total_category_count}",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column != 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column != 0:
                    _highlight_item(
                        item,
                        highlight,
                        rank_highlight=rank_highlight,
                        modifier_highlight=modifier_highlight,
                        both_highlight=both_highlight,
                    )
                _set_table_item_color(item, column, match.marker, grade_colors)
                self.setItem(row, column, item)
        self._updating = False

    def _selection_changed(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if not self._updating and 0 <= current_row < len(self.matches):
            self.match_selected.emit(self.matches[current_row])


class AddonSlotRow(QFrame):
    def __init__(self, slot_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slot_id = slot_id
        self.setObjectName("addonSlotRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 10)
        layout.setSpacing(10)

        slot_label = QLabel(SLOT_LABELS[slot_id], self)
        slot_label.setObjectName("affixSlotName")
        slot_label.setFixedWidth(100)
        layout.addWidget(slot_label)

        self.tables: dict[str, AddonSlotTable] = {}
        for addon_type in (ADDON_COMPONENT, ADDON_AUGMENT):
            section = QWidget(self)
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(5)
            title = QLabel(
                "Components"
                if addon_type == ADDON_COMPONENT
                else "Augments"
            )
            title.setObjectName("affixTableTitle")
            section_layout.addWidget(title)
            table = AddonSlotTable(addon_type, section)
            section_layout.addWidget(table)
            layout.addWidget(section, 1)
            self.tables[addon_type] = table


class UniqueSlotTable(QTableWidget):
    match_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 6, parent)
        self.matches: tuple[RankedItemVariant, ...] = ()
        self._updating = False
        self.setObjectName("uniqueSlotTable")
        self.setHorizontalHeaderLabels(
            ("Grade", "Item", "Type", "Source", "Score", "Coverage")
        )
        _configure_table(self, 1)
        self.setMinimumHeight(84)
        self.setMaximumHeight(420)
        self.currentCellChanged.connect(self._selection_changed)

    def set_matches(
        self,
        matches: tuple[RankedItemVariant, ...],
        profile: BuildProfile | None = None,
        grade_colors: dict[str, QColor] | None = None,
        rank_highlight: QColor = SKILL_RANK_HIGHLIGHT,
        modifier_highlight: QColor = SKILL_MODIFIER_HIGHLIGHT,
        both_highlight: QColor = SKILL_BOTH_HIGHLIGHT,
    ) -> None:
        self._updating = True
        self.matches = matches
        self.clearContents()
        self.setRowCount(len(matches))
        for row, match in enumerate(matches):
            score = match.score
            has_rank_bonus = profile is not None and _has_selected_skill_bonus(
                match.semantic_stat_ids, profile
            )
            highlight = (
                "both"
                if has_rank_bonus and match.has_selected_skill_modifier
                else "modifier"
                if match.has_selected_skill_modifier
                else "rank" if has_rank_bonus else ""
            )
            values = (
                match.marker,
                match.item.display_name,
                UNIQUE_TYPE_LABELS[match.item_type],
                _item_source_label(match.variant),
                _format_score(score.effective_score),
                f"{score.matched_count}/{score.total_category_count}",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column != 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column != 0:
                    _highlight_item(
                        item,
                        highlight,
                        rank_highlight=rank_highlight,
                        modifier_highlight=modifier_highlight,
                        both_highlight=both_highlight,
                    )
                _set_table_item_color(item, column, match.marker, grade_colors)
                self.setItem(row, column, item)
        visible_rows = max(1, min(len(matches), 12))
        self.setFixedHeight(58 + visible_rows * 26)
        self._updating = False

    def _selection_changed(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if not self._updating and 0 <= current_row < len(self.matches):
            self.match_selected.emit(self.matches[current_row])


class UniqueSlotRow(QFrame):
    def __init__(self, slot_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slot_id = slot_id
        self.setObjectName("uniqueSlotRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 10)
        layout.setSpacing(10)
        slot_label = QLabel(SLOT_LABELS[slot_id], self)
        slot_label.setObjectName("affixSlotName")
        slot_label.setFixedWidth(100)
        layout.addWidget(slot_label)
        self.table = UniqueSlotTable(self)
        layout.addWidget(self.table, 1)


class TopMatchesPage(QWidget):
    profile_state_changed = Signal()

    def __init__(
        self,
        catalog: AffixCatalog | None,
        profile: BuildProfile,
        *,
        catalog_status: str = "",
        skills: SkillCatalog | None = None,
        items: ItemCatalog | None = None,
        settings: QSettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.items = items or ItemCatalog((), (), (), (), (), ())
        self.profile = profile
        self.catalog_status = catalog_status
        self.settings = settings
        self.grade_colors: dict[str, QColor] = {}
        self.skill_rank_highlight = SKILL_RANK_HIGHLIGHT
        self.skill_modifier_highlight = SKILL_MODIFIER_HIGHLIGHT
        self.skill_both_highlight = SKILL_BOTH_HIGHLIGHT
        skill_catalog = skills or SkillCatalog(())
        self.skill_labels = {
            skill.skill_id: skill.display_name
            for skill in skill_catalog.skills
            if skill.display_name
        }
        self.canonical_skill_labels = {
            canonical_skill_reference(skill.skill_id): skill.display_name
            for skill in skill_catalog.skills
            if skill.display_name
        }
        self.mastery_labels = {
            skill.mastery_id: skill.mastery_name
            for skill in skill_catalog.skills
            if skill.mastery_id and skill.mastery_name
        }
        self.matches: tuple[RankedAffixVariant, ...] = ()
        self.unique_matches: tuple[RankedItemVariant, ...] = ()
        self.addon_matches: tuple[RankedAddonVariant, ...] = ()
        self.tables: dict[tuple[str, str], AffixSlotTable] = {}
        self.slot_rows: dict[str, AffixSlotRow] = {}
        self.unique_tables: dict[str, UniqueSlotTable] = {}
        self.unique_slot_rows: dict[str, UniqueSlotRow] = {}
        self.addon_tables: dict[tuple[str, str], AddonSlotTable] = {}
        self.addon_slot_rows: dict[str, AddonSlotRow] = {}
        self.category_widgets: list[tuple[QLabel, tuple[str, ...]]] = []
        self.unique_category_widgets: list[tuple[QLabel, tuple[str, ...]]] = []
        self.addon_category_widgets: list[tuple[QLabel, tuple[str, ...]]] = []
        self.weapon_filter_warnings: list[QLabel] = []
        self._selected_table: AffixSlotTable | None = None
        self._selected_unique_table: UniqueSlotTable | None = None
        self._selected_addon_table: AddonSlotTable | None = None
        self.resistance_cap_enabled = profile.resistance_cap_enabled
        self.resistance_cap_weights = {
            definition.stat_id: profile.resistance_cap_weight_for(
                definition.stat_id
            )
            for definition in RESISTANCE_STATS
        }
        self.resistance_cap_rows: dict[str, StatRow] = {}
        self.current_profile_path: Path | None = None
        self._control_row_labels: list[QLabel] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        heading_row = QHBoxLayout()
        heading = QLabel("Gear Grades", self)
        heading.setObjectName("pageTitle")
        heading_row.addWidget(heading)
        heading_row.addStretch()
        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setObjectName("profileAction")
        self.refresh_button.clicked.connect(self.refresh)
        heading_row.addWidget(self.refresh_button)
        layout.addLayout(heading_row)

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

        profile_row = QHBoxLayout()
        profile_row.setSpacing(8)
        profile_label = QLabel("Loaded", self)
        profile_label.setObjectName("fieldLabel")
        self._control_row_labels.append(profile_label)
        profile_row.addWidget(profile_label)
        self.loaded_profile_badge = QLabel(self)
        self.loaded_profile_badge.setObjectName("profileStatusPill")
        profile_row.addWidget(self.loaded_profile_badge)
        profile_row.addStretch()
        layout.addLayout(profile_row)

        self.status = QLabel(self)
        self.status.setObjectName("pageHint")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.highlight_legend = QLabel(
            self,
        )
        self.highlight_legend.setTextFormat(Qt.TextFormat.RichText)
        self.highlight_legend.setText(
            "<span style='color: #f1b56a;'>+Ranks to active skills</span>    "
            "<span style='color: #6a91e0;'>Active-skill modifier</span>    "
            "<span style='color: #bd94c6;'>Both</span>"
        )
        self.highlight_legend.setObjectName("matchHighlightLegend")
        layout.addWidget(self.highlight_legend)

        filter_frame = QFrame(self)
        filter_frame.setObjectName("slotFilterBar")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(10, 7, 10, 7)
        filter_layout.addWidget(QLabel("Show item slots:", filter_frame))
        self.slot_filters: dict[str, QCheckBox] = {}
        for filter_id, label in FILTER_LABELS:
            checkbox = QCheckBox(label, filter_frame)
            checkbox.setObjectName(f"slotFilter_{filter_id}")
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._slot_filter_changed)
            filter_layout.addWidget(checkbox)
            self.slot_filters[filter_id] = checkbox
            if filter_id == "two_handed":
                self.slot_filter_divider = QFrame(filter_frame)
                self.slot_filter_divider.setObjectName("slotFilterDivider")
                self.slot_filter_divider.setFrameShape(QFrame.Shape.VLine)
                self.slot_filter_divider.setFrameShadow(QFrame.Shadow.Sunken)
                filter_layout.addWidget(self.slot_filter_divider)
        filter_layout.addStretch()
        layout.addWidget(filter_frame)

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("recommendationTabs")
        self.tabs.addTab(self._build_affix_tab(), "Affixes")
        self.tabs.addTab(self._build_unique_tab(), "Uniques")
        self.tabs.addTab(self._build_addon_tab(), "Add-ons")
        layout.addWidget(self.tabs, 1)
        self._align_control_row_labels()
        self._update_loaded_profile_pill()
        self.refresh_version_blurb()
        self.refresh_palette_colors()
        self.refresh()

    def refresh_palette_colors(self) -> None:
        values = default_palette()
        if self.settings is not None:
            raw = self.settings.value("paths/palette_file", "", type=str).strip()
            if raw:
                try:
                    values = load_palette(Path(raw)).values
                except (OSError, ValueError):
                    pass
        palette = marker_palette_from_values(values)
        self.grade_colors = {
            token: QColor(PALETTE_CODE_HEX.get(code, "#ffffff"))
            for token, code in palette.grade_color_codes.items()
        }
        self.skill_rank_highlight = QColor(
            PALETTE_CODE_HEX.get(values.get("ui.skill_rank", "h"), "#f1b56a")
        )
        self.skill_modifier_highlight = QColor(
            PALETTE_CODE_HEX.get(values.get("ui.skill_modifier", "z"), "#6a91e0")
        )
        self.skill_both_highlight = QColor(
            PALETTE_CODE_HEX.get(values.get("ui.skill_both", "p"), "#bd94c6")
        )
        if hasattr(self, "highlight_legend"):
            self.highlight_legend.setText(
                f"<span style='color: {self.skill_rank_highlight.name()};'>"
                "+Ranks to active skills</span>    "
                f"<span style='color: {self.skill_modifier_highlight.name()};'>"
                "Active-skill modifier</span>    "
                f"<span style='color: {self.skill_both_highlight.name()};'>"
                "Both</span>"
            )

    def refresh_palette(self) -> None:
        self.refresh_palette_colors()
        self.refresh()

    def _align_control_row_labels(self) -> None:
        if not self._control_row_labels:
            return
        width = max(label.sizeHint().width() for label in self._control_row_labels)
        for label in self._control_row_labels:
            label.setFixedWidth(width)

    def set_profile_path(self, path: Path | None) -> None:
        self.current_profile_path = (
            Path(path).expanduser().resolve() if path is not None else None
        )
        self._update_loaded_profile_pill()

    def refresh_version_blurb(self) -> None:
        if self.settings is None:
            self.profile_badge.setText("Profile: not stamped")
            self.current_badge.setText("Game: settings unavailable")
            self._set_sync_badge("unknown", "? Unknown")
            self.version_blurb.setText("Game folder settings unavailable.")
            return
        raw_game_folder = self.settings.value(
            GAME_FOLDER_SETTING,
            "",
            type=str,
        ).strip()
        if not raw_game_folder:
            self.profile_badge.setText("Profile: not stamped")
            self.current_badge.setText("Game: folder not set")
            self._set_sync_badge("unknown", "? Unknown")
            self.version_blurb.setText(
                "Set Grim Dawn folder in Settings, then save profile to stamp version metadata."
            )
            return

        current = detect_game_snapshot(Path(raw_game_folder))
        profile_snapshot = snapshot_from_profile_fields(
            self.profile.saved_db_hash,
            self.profile.saved_steam_build_id,
            self.profile.saved_patch_versions,
        )
        state = evaluate_profile_snapshot_match(current, profile_snapshot)
        if state == "match":
            summary = ""
            status_text = "✓ In Sync"
        elif state == "mismatch":
            summary = ""
            status_text = "✕ Out of Sync"
        else:
            summary = (
                "Profile snapshot unavailable; save profile to record game metadata."
            )
            status_text = "? Unknown"

        self.profile_badge.setText(
            "Profile "
            f"hash {self._short_hash(profile_snapshot.db_hash)}  "
            f"patch {profile_snapshot.patch_versions}"
        )
        self.current_badge.setText(
            "Game "
            f"hash {self._short_hash(current.db_hash)}  "
            f"patch {current.patch_versions}"
        )
        self._set_sync_badge(state, status_text)
        self.profile_badge.setToolTip(
            "Profile snapshot: "
            f"hash={profile_snapshot.db_hash}, "
            f"steam_build_id={profile_snapshot.steam_build_id}, "
            f"patch_versions={profile_snapshot.patch_versions}"
        )
        self.current_badge.setToolTip(
            "Game install snapshot: "
            f"hash={current.db_hash}, "
            f"steam_build_id={current.steam_build_id}, "
            f"patch_versions={current.patch_versions}"
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

    def _build_affix_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Orientation.Vertical, tab)
        scroll = QScrollArea(splitter)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 4, 8, 8)
        content_layout.setSpacing(10)
        for category_label, slot_ids in SLOT_GROUPS:
            category = QLabel(category_label, content)
            category.setObjectName("affixCategoryTitle")
            content_layout.addWidget(category)
            self.category_widgets.append((category, slot_ids))
            if category_label == "Weapons":
                warning = self._weapon_filter_warning(content)
                self.weapon_filter_warnings.append(warning)
                content_layout.addWidget(warning)
            for slot_id in slot_ids:
                row = AffixSlotRow(slot_id, content)
                for kind, table in row.tables.items():
                    table.match_selected.connect(
                        lambda match, selected=table, slot=slot_id: self._show_match(
                            selected, slot, match
                        )
                    )
                    self.tables[(slot_id, kind)] = table
                self.slot_rows[slot_id] = row
                content_layout.addWidget(row)
        content_layout.addStretch()
        scroll.setWidget(content)
        splitter.addWidget(scroll)
        self.affix_detail_pane = MatchDetailPane(
            "Select an affix to inspect its matched stats.", splitter
        )
        self.details = self.affix_detail_pane.body
        splitter.addWidget(self.affix_detail_pane)
        splitter.setSizes((570, 230))
        layout.addWidget(splitter)
        return tab

    def _build_unique_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Orientation.Vertical, tab)
        upper = QWidget(splitter)
        upper_layout = QVBoxLayout(upper)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(8)

        type_frame = QFrame(upper)
        type_frame.setObjectName("typeFilterBar")
        type_layout = QHBoxLayout(type_frame)
        type_layout.setContentsMargins(10, 7, 10, 7)
        type_layout.addWidget(QLabel("Show types:", type_frame))
        self.type_filters: dict[str, QCheckBox] = {}
        for type_id in UNIQUE_ITEM_TYPES:
            checkbox = QCheckBox(UNIQUE_TYPE_LABELS[type_id], type_frame)
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._type_filter_changed)
            type_layout.addWidget(checkbox)
            self.type_filters[type_id] = checkbox
        type_layout.addSpacing(14)
        type_layout.addWidget(QLabel("Minimum grade:", type_frame))
        self.minimum_grade = QComboBox(type_frame)
        self.minimum_grade.setObjectName("minimumGradeSelector")
        self.minimum_grade.addItems(("S++", "S+", "S", "A", "B"))
        self.minimum_grade.setCurrentText("A")
        self.minimum_grade.currentTextChanged.connect(
            self._minimum_grade_changed
        )
        type_layout.addWidget(self.minimum_grade)
        type_layout.addStretch()
        upper_layout.addWidget(type_frame)

        scroll = QScrollArea(upper)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 4, 8, 8)
        content_layout.setSpacing(10)
        for category_label, slot_ids in SLOT_GROUPS:
            category = QLabel(category_label, content)
            category.setObjectName("affixCategoryTitle")
            content_layout.addWidget(category)
            self.unique_category_widgets.append((category, slot_ids))
            if category_label == "Weapons":
                warning = self._weapon_filter_warning(content)
                self.weapon_filter_warnings.append(warning)
                content_layout.addWidget(warning)
            for slot_id in slot_ids:
                row = UniqueSlotRow(slot_id, content)
                row.table.match_selected.connect(
                    lambda match, selected=row.table, slot=slot_id: self._show_unique(
                        selected, slot, match
                    )
                )
                self.unique_tables[slot_id] = row.table
                self.unique_slot_rows[slot_id] = row
                content_layout.addWidget(row)
        content_layout.addStretch()
        scroll.setWidget(content)
        upper_layout.addWidget(scroll, 1)
        splitter.addWidget(upper)

        self.unique_detail_pane = MatchDetailPane(
            "Select an item to inspect its matched stats.", splitter
        )
        self.unique_details = self.unique_detail_pane.body
        splitter.addWidget(self.unique_detail_pane)
        splitter.setSizes((570, 230))
        layout.addWidget(splitter)
        return tab

    def _build_addon_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        mode_button_row = QHBoxLayout()
        mode_button_row.addStretch()
        self.resistance_cap_button = QToolButton(tab)
        self.resistance_cap_button.setObjectName("resistanceCapButton")
        self.resistance_cap_button.setCheckable(True)
        self.resistance_cap_button.toggled.connect(
            self._set_resistance_cap_expanded
        )
        mode_button_row.addWidget(self.resistance_cap_button)
        mode_button_row.addStretch()
        layout.addLayout(mode_button_row)

        mode_body_row = QHBoxLayout()
        mode_body_row.addStretch()
        self.resistance_cap_body = QFrame(tab)
        self.resistance_cap_body.setObjectName("resistanceCapBody")
        self.resistance_cap_body.setMaximumWidth(980)
        mode_layout = QVBoxLayout(self.resistance_cap_body)
        mode_layout.setContentsMargins(12, 10, 12, 12)
        mode_layout.setSpacing(7)
        self.resistance_cap_toggle = QCheckBox(
            "Enable Resistance Cap Mode", self.resistance_cap_body
        )
        self.resistance_cap_toggle.setObjectName("resistanceCapToggle")
        self.resistance_cap_toggle.setChecked(self.resistance_cap_enabled)
        self.resistance_cap_toggle.toggled.connect(
            self._resistance_cap_toggled
        )
        mode_layout.addWidget(self.resistance_cap_toggle)
        self.resistance_cap_hint = QLabel(
            "Overrides profile resistance weights for Add-ons only. "
            "Two stars score like an ordinary four-star weight; higher "
            "ratings are strongly amplified."
            "\nUntouched weights inherit from the main profile. Changes here "
            "are saved separately and never write back to the main weights.",
            self.resistance_cap_body,
        )
        self.resistance_cap_hint.setObjectName("resistanceCapHint")
        self.resistance_cap_hint.setWordWrap(True)
        mode_layout.addWidget(self.resistance_cap_hint)
        self.resistance_cap_rows_widget = QWidget(self.resistance_cap_body)
        rows_layout = QGridLayout(self.resistance_cap_rows_widget)
        rows_layout.setContentsMargins(0, 2, 0, 0)
        rows_layout.setHorizontalSpacing(12)
        rows_layout.setVerticalSpacing(0)
        for index, definition in enumerate(RESISTANCE_STATS):
            row = StatRow(
                definition,
                self.resistance_cap_weights[definition.stat_id],
                self.resistance_cap_rows_widget,
            )
            row.value_changed.connect(self._resistance_cap_weight_changed)
            rows_layout.addWidget(row, index // 2, index % 2)
            self.resistance_cap_rows[definition.stat_id] = row
        self.resistance_cap_rows_widget.setEnabled(
            self.resistance_cap_enabled
        )
        mode_layout.addWidget(self.resistance_cap_rows_widget)
        self.resistance_cap_body.installEventFilter(self)
        for child in self.resistance_cap_body.findChildren(QWidget):
            child.installEventFilter(self)
        mode_body_row.addWidget(self.resistance_cap_body, 1)
        mode_body_row.addStretch()
        layout.addLayout(mode_body_row)
        self._set_resistance_cap_expanded(False)

        splitter = QSplitter(Qt.Orientation.Vertical, tab)
        self.addon_scroll = QScrollArea(splitter)
        self.addon_scroll.setWidgetResizable(True)
        self.addon_scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(self.addon_scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 4, 8, 8)
        content_layout.setSpacing(10)
        for category_label, slot_ids in SLOT_GROUPS:
            category = QLabel(category_label, content)
            category.setObjectName("affixCategoryTitle")
            content_layout.addWidget(category)
            self.addon_category_widgets.append((category, slot_ids))
            if category_label == "Weapons":
                warning = self._weapon_filter_warning(content)
                self.weapon_filter_warnings.append(warning)
                content_layout.addWidget(warning)
            for slot_id in slot_ids:
                row = AddonSlotRow(slot_id, content)
                for addon_type, table in row.tables.items():
                    table.match_selected.connect(
                        lambda match, selected=table, slot=slot_id: (
                            self._show_addon(selected, slot, match)
                        )
                    )
                    self.addon_tables[(slot_id, addon_type)] = table
                self.addon_slot_rows[slot_id] = row
                content_layout.addWidget(row)
        content_layout.addStretch()
        self.addon_scroll.setWidget(content)
        splitter.addWidget(self.addon_scroll)
        self.addon_detail_pane = MatchDetailPane(
            "Select a component or augment to inspect its matched stats.",
            splitter,
        )
        self.addon_details = self.addon_detail_pane.body
        splitter.addWidget(self.addon_detail_pane)
        splitter.setSizes((570, 230))
        layout.addWidget(splitter)
        return tab

    def _set_resistance_cap_expanded(self, expanded: bool) -> None:
        self.resistance_cap_button.setChecked(expanded)
        self.resistance_cap_body.setVisible(expanded)
        indicator = "\u25be" if expanded else "\u25b8"
        active = " (On)" if self.resistance_cap_enabled else ""
        self.resistance_cap_button.setText(
            f"{indicator} Resistance Cap Mode{active}"
        )
        self.resistance_cap_button.setProperty(
            "active", self.resistance_cap_enabled
        )
        self.resistance_cap_button.style().unpolish(
            self.resistance_cap_button
        )
        self.resistance_cap_button.style().polish(
            self.resistance_cap_button
        )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.Wheel
            and (
                watched is self.resistance_cap_body
                or self.resistance_cap_body.isAncestorOf(watched)
            )
        ):
            pixel_delta = event.pixelDelta().y()
            angle_delta = event.angleDelta().y()
            delta = pixel_delta
            if not delta and angle_delta:
                steps = angle_delta / 120
                delta = round(
                    steps
                    * self.addon_scroll.verticalScrollBar().singleStep()
                    * 3
                )
            if delta:
                scrollbar = self.addon_scroll.verticalScrollBar()
                scrollbar.setValue(scrollbar.value() - delta)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _resistance_cap_toggled(self, enabled: bool) -> None:
        self.resistance_cap_enabled = enabled
        self.profile.resistance_cap_enabled = enabled
        self.resistance_cap_rows_widget.setEnabled(enabled)
        self._set_resistance_cap_expanded(
            self.resistance_cap_button.isChecked()
        )
        self.addon_detail_pane.clear()
        self._selected_addon_table = None
        self._refresh_addons()
        self._update_status()
        self._select_first_visible_addon()
        self.profile_state_changed.emit()

    def _resistance_cap_weight_changed(
        self, stat_id: str, weight: int
    ) -> None:
        self.resistance_cap_weights[stat_id] = weight
        self.profile.set_resistance_cap_weight(stat_id, weight)
        self.profile_state_changed.emit()
        if not self.resistance_cap_enabled:
            return
        self.addon_detail_pane.clear()
        self._selected_addon_table = None
        self._refresh_addons()
        self._update_status()
        self._select_first_visible_addon()

    @staticmethod
    def _weapon_filter_warning(parent: QWidget) -> QLabel:
        warning = QLabel(
            "1H or 2H, and at least one weapon type must be selected to view "
            "weapons.",
            parent,
        )
        warning.setObjectName("weaponFilterWarning")
        warning.setWordWrap(True)
        warning.hide()
        return warning

    def set_catalog(self, catalog: AffixCatalog | None, status: str = "") -> None:
        self.catalog = catalog
        self.catalog_status = status
        self.refresh()

    def refresh(self, _value: int | bool = False) -> None:
        self._sync_resistance_cap_from_profile()
        self.affix_detail_pane.clear()
        self.unique_detail_pane.clear()
        self.addon_detail_pane.clear()
        self.matches = ()
        self.unique_matches = ()
        self.addon_matches = ()
        self._selected_table = None
        self._selected_unique_table = None
        self._selected_addon_table = None
        for table in self.tables.values():
            table.set_matches(())
        for table in self.unique_tables.values():
            table.set_matches(())
        for table in self.addon_tables.values():
            table.set_matches(())
        if self.catalog is None:
            self.status.setText(
                self.catalog_status
                or "No compiled gear catalog is available for ranking."
            )
            return
        has_cap_weight = self.resistance_cap_enabled and any(
            self.resistance_cap_weights.values()
        )
        if not has_cap_weight and not self.profile.weights and not any(
            weight > 0 for weight in self.profile.skill_weights.values()
        ):
            self.status.setText(
                "Set at least one nonzero build-profile weight to rank gear."
            )
            return

        all_affixes: list[RankedAffixVariant] = []
        for (slot_id, kind), table in self.tables.items():
            matches = rank_affixes_for_slot(
                self.catalog,
                self.profile,
                slot_id=slot_id,
                kind=kind,
                limit=RESULTS_PER_AFFIX_TABLE,
            )
            table.set_matches(
                matches,
                self.profile,
                self.grade_colors,
                self.skill_rank_highlight,
                self.skill_modifier_highlight,
                self.skill_both_highlight,
            )
            all_affixes.extend(matches)
        self.matches = tuple(all_affixes)
        self._refresh_uniques()
        self._refresh_addons()
        self._apply_slot_filters()
        self._update_status()
        self._select_first_visible_match()
        self._select_first_visible_unique()
        self._select_first_visible_addon()

    def _sync_resistance_cap_from_profile(self) -> None:
        """Refresh saved cap-mode state without writing into main weights."""

        self.resistance_cap_enabled = self.profile.resistance_cap_enabled
        toggle_blocker = QSignalBlocker(self.resistance_cap_toggle)
        self.resistance_cap_toggle.setChecked(self.resistance_cap_enabled)
        del toggle_blocker
        self.resistance_cap_rows_widget.setEnabled(
            self.resistance_cap_enabled
        )
        for definition in RESISTANCE_STATS:
            stat_id = definition.stat_id
            weight = self.profile.resistance_cap_weight_for(stat_id)
            self.resistance_cap_weights[stat_id] = weight
            self.resistance_cap_rows[stat_id].weight_control.set_value(
                weight, emit=False
            )
        self._set_resistance_cap_expanded(
            self.resistance_cap_button.isChecked()
        )

    def _refresh_uniques(self) -> None:
        enabled_types = frozenset(
            type_id
            for type_id, checkbox in self.type_filters.items()
            if checkbox.isChecked()
        )
        all_matches: list[RankedItemVariant] = []
        for slot_id, table in self.unique_tables.items():
            matches = rank_unique_items_for_slot(
                self.items,
                self.profile,
                slot_id=slot_id,
                enabled_types=enabled_types,
                minimum_grade=self.minimum_grade.currentText(),
            )
            table.set_matches(
                matches,
                self.profile,
                self.grade_colors,
                self.skill_rank_highlight,
                self.skill_modifier_highlight,
                self.skill_both_highlight,
            )
            all_matches.extend(matches)
        self.unique_matches = tuple(all_matches)

    def _refresh_addons(self) -> None:
        all_matches: list[RankedAddonVariant] = []
        for (slot_id, addon_type), table in self.addon_tables.items():
            matches = rank_addons_for_slot(
                self.items,
                self.profile,
                slot_id=slot_id,
                addon_type=addon_type,
                limit=RESULTS_PER_AFFIX_TABLE,
                resistance_cap_weights=(
                    self.resistance_cap_weights
                    if self.resistance_cap_enabled
                    else None
                ),
            )
            table.set_matches(
                matches,
                self.profile,
                self.grade_colors,
                self.skill_rank_highlight,
                self.skill_modifier_highlight,
                self.skill_both_highlight,
            )
            all_matches.extend(matches)
        self.addon_matches = tuple(all_matches)

    def _slot_filter_changed(self, _checked: bool) -> None:
        self._apply_slot_filters()
        self._update_status()
        self._select_first_visible_match()
        self._select_first_visible_unique()
        self._select_first_visible_addon()

    def _type_filter_changed(self, _checked: bool) -> None:
        self.unique_detail_pane.clear()
        self._selected_unique_table = None
        self._refresh_uniques()
        self._update_status()
        self._select_first_visible_unique()

    def _minimum_grade_changed(self, _grade: str) -> None:
        self._type_filter_changed(False)

    def _update_loaded_profile_pill(self) -> None:
        if self.current_profile_path is None:
            display = self.profile.name.strip() or "New Build Profile"
            self.loaded_profile_badge.setText(f"Unsaved ({display})")
            self.loaded_profile_badge.setToolTip("")
            return
        self.loaded_profile_badge.setText(self.current_profile_path.name)
        self.loaded_profile_badge.setToolTip(str(self.current_profile_path))

    def _apply_slot_filters(self) -> None:
        enabled = {
            filter_id
            for filter_id, checkbox in self.slot_filters.items()
            if checkbox.isChecked()
        }
        has_handedness = bool(enabled & {"one_handed", "two_handed"})
        has_weapon_type = bool(enabled & {"melee", "caster", "ranged"})
        invalid_weapon_filters = not has_handedness or not has_weapon_type
        for warning in self.weapon_filter_warnings:
            warning.setVisible(invalid_weapon_filters)
        for slot_id in self.slot_rows:
            required = SLOT_FILTERS.get(slot_id, frozenset())
            visible = required <= enabled
            self.slot_rows[slot_id].setVisible(visible)
            self.unique_slot_rows[slot_id].setVisible(visible)
            self.addon_slot_rows[slot_id].setVisible(visible)
        for headings, rows in (
            (self.category_widgets, self.slot_rows),
            (self.unique_category_widgets, self.unique_slot_rows),
            (self.addon_category_widgets, self.addon_slot_rows),
        ):
            for heading, slot_ids in headings:
                is_weapon_heading = bool(set(slot_ids) & set(WEAPON_SLOTS))
                heading.setVisible(
                    (is_weapon_heading and invalid_weapon_filters)
                    or any(not rows[slot].isHidden() for slot in slot_ids)
                )

    def _update_status(self) -> None:
        visible_affixes = sum(
            len(table.matches)
            for (slot_id, _), table in self.tables.items()
            if not self.slot_rows[slot_id].isHidden()
        )
        visible_uniques = sum(
            len(table.matches)
            for slot_id, table in self.unique_tables.items()
            if not self.unique_slot_rows[slot_id].isHidden()
        )
        visible_addons = sum(
            len(table.matches)
            for (slot_id, _), table in self.addon_tables.items()
            if not self.addon_slot_rows[slot_id].isHidden()
        )
        source_note = f" {self.catalog_status}" if self.catalog_status else ""
        cap_note = (
            " Resistance Cap Mode is enabled for Add-ons."
            if self.resistance_cap_enabled
            else ""
        )
        self.status.setText(
            f"{self.profile.name}: {visible_affixes} ranked affix entries and "
            f"{visible_uniques} {self.minimum_grade.currentText()}-or-better "
            f"unique-item entries, and {visible_addons} add-on entries. "
            "Grades assume "
            f"the highest-level stat layout.{cap_note}{source_note}"
        )

    def _select_first_visible_match(self) -> None:
        for _, slot_ids in SLOT_GROUPS:
            for slot_id in slot_ids:
                if self.slot_rows[slot_id].isHidden():
                    continue
                for kind in ("prefix", "suffix"):
                    table = self.tables[(slot_id, kind)]
                    if table.matches:
                        table.selectRow(0)
                        return
        self.affix_detail_pane.clear()

    def _select_first_visible_unique(self) -> None:
        for _, slot_ids in SLOT_GROUPS:
            for slot_id in slot_ids:
                if self.unique_slot_rows[slot_id].isHidden():
                    continue
                table = self.unique_tables[slot_id]
                if table.matches:
                    table.selectRow(0)
                    return
        self.unique_detail_pane.clear()

    def _select_first_visible_addon(self) -> None:
        for _, slot_ids in SLOT_GROUPS:
            for slot_id in slot_ids:
                if self.addon_slot_rows[slot_id].isHidden():
                    continue
                for addon_type in (ADDON_COMPONENT, ADDON_AUGMENT):
                    table = self.addon_tables[(slot_id, addon_type)]
                    if table.matches:
                        table.selectRow(0)
                        return
        self.addon_detail_pane.clear()

    def _show_match(
        self,
        table: AffixSlotTable,
        slot_id: str,
        match: RankedAffixVariant,
    ) -> None:
        if self._selected_table is not table:
            for other in self.tables.values():
                if other is not table:
                    other.clearSelection()
            self._selected_table = table
        score = match.score
        matched_ids = set(score.matched_stat_ids)
        unmatched_ids = [
            stat_id
            for stat_id in match.semantic_stat_ids
            if stat_id not in matched_ids
        ]
        rarity = match.affix.rarity.strip()
        affix_type = " ".join(
            part for part in (rarity, match.affix.kind.title()) if part
        )
        rarity_color = DETAIL_TITLE_COLORS.get(
            f"affix_{rarity.casefold()}", DETAIL_TITLE_COLORS["affix"]
        )
        self.affix_detail_pane.set_title(
            f"{match.marker}{match.affix.display_name} · "
            f"{SLOT_LABELS[slot_id]} · {affix_type}",
            rarity_color,
        )
        html = [
            _html_line(
                f"Effective score: {_format_score(score.effective_score)} "
                f"· Base score: {_format_score(score.base_effective_score)} "
                f"(profile x{score.profile_adjustment:.3f}) "
                f"· Raw weight total: {score.weighted_match} "
                f"· Coverage: "
                f"{score.matched_count}/{score.total_category_count} "
                f"({score.coverage_ratio:.0%})"
            ),
            _html_line(""),
            _html_line("Matched stats:", bold=True),
        ]
        if score.matched_stat_ids:
            html.extend(
                _stat_html(
                    stat_id,
                    f"{self._label_for(stat_id, match.variant.properties)}: "
                    "weight "
                    f"{profile_weight_for_semantic_id(self.profile, stat_id)}",
                    matched=True,
                )
                for stat_id in score.matched_stat_ids
            )
        else:
            html.append(_stat_html("", "None", matched=True))
        html.extend(
            (_html_line(""), _html_line("Remaining unmatched stats:", bold=True))
        )
        if unmatched_ids:
            html.extend(
                _stat_html(
                    stat_id,
                    self._label_for(stat_id, match.variant.properties),
                    matched=False,
                )
                for stat_id in unmatched_ids
            )
        else:
            html.append(_stat_html("", "None", matched=False))
        html.extend(
            _granted_skill_section(
                tuple(
                    property_.attributes.get("display_name", "").strip()
                    for property_ in match.variant.properties
                    if property_.property_id == "granted_item_skill"
                )
            )
        )
        if match.variant.level_requirements:
            html.extend(
                (
                    _html_line(""),
                    _html_line(
                        "Level requirements for this layout: "
                        + ", ".join(map(str, match.variant.level_requirements))
                    ),
                )
            )
        html.extend(
            (
                _html_line(""),
                _html_line("Grades assume the highest-level stat layout."),
                _html_line(f"Full applicability: {match.variant.gear_slot}"),
                _html_line(f"Localization tag: {match.affix.localization_tag}"),
                _html_line(
                    f"Representative: {match.variant.representative_source}"
                ),
            )
        )
        self.details.setHtml("".join(html))

    def _show_unique(
        self,
        table: UniqueSlotTable,
        slot_id: str,
        match: RankedItemVariant,
    ) -> None:
        if self._selected_unique_table is not table:
            for other in self.unique_tables.values():
                if other is not table:
                    other.clearSelection()
            self._selected_unique_table = table
        score = match.score
        matched_ids = set(score.matched_stat_ids)
        unmatched_ids = [
            stat_id
            for stat_id in match.semantic_stat_ids
            if stat_id not in matched_ids
        ]
        self.unique_detail_pane.set_title(
            f"{match.marker}{match.item.display_name} · {SLOT_LABELS[slot_id]} · "
            f"{UNIQUE_TYPE_LABELS[match.item_type]}",
            DETAIL_TITLE_COLORS[match.item_type],
        )
        html = [
            _html_line(
                f"Effective score: {_format_score(score.effective_score)} "
                f"· Base score: {_format_score(score.base_effective_score)} "
                f"(profile x{score.profile_adjustment:.3f}) "
                f"· Raw weight total: {score.weighted_match} "
                f"· Coverage: "
                f"{score.matched_count}/{score.total_category_count} "
                f"({score.coverage_ratio:.0%})"
            ),
            _html_line(""),
            _html_line("Matched stats:", bold=True),
        ]
        if score.matched_stat_ids:
            html.extend(
                _stat_html(
                    stat_id,
                    f"{self._label_for(stat_id, match.variant.properties)}: "
                    "weight "
                    f"{profile_weight_for_semantic_id(self.profile, stat_id)}",
                    matched=True,
                )
                for stat_id in score.matched_stat_ids
            )
        else:
            html.append(_stat_html("", "None", matched=True))
        html.extend(
            (_html_line(""), _html_line("Remaining unmatched stats:", bold=True))
        )
        if unmatched_ids:
            html.extend(
                _stat_html(
                    stat_id,
                    self._label_for(stat_id, match.variant.properties),
                    matched=False,
                )
                for stat_id in unmatched_ids
            )
        else:
            html.append(_stat_html("", "None", matched=False))
        if match.variant.set_name:
            html.extend((_html_line(""), _html_line(f"Set: {match.variant.set_name}")))
        html.extend(
            _granted_skill_section((match.variant.granted_skill_name,))
        )
        if match.variant.skill_modifiers:
            html.extend((_html_line(""), _html_line("Skill modifiers:", bold=True)))
            for modifier in match.variant.skill_modifiers:
                html.append(
                    _html_line(
                        f"- {modifier.modified_skill_name}",
                        color=SKILL_MODIFIER_STAT_COLOR,
                    )
                )
                html.extend(
                    _html_line(f"  - {line}", color=SKILL_MODIFIER_STAT_COLOR)
                    for line in modifier.stat_lines
                )
        if match.has_selected_skill_modifier:
            selected_modifiers = sorted(
                {
                    modifier.modified_skill_name
                    for modifier in match.variant.skill_modifiers
                    if canonical_skill_reference(
                        modifier.modified_skill_reference
                    )
                    in {
                        canonical_skill_reference(skill_id)
                        for skill_id in self.profile.skill_weights
                    }
                }
            )
            html.extend(
                (
                    _html_line(""),
                    _html_line(
                        "!: Modifies selected build skill(s): "
                        + ", ".join(selected_modifiers),
                        color=SKILL_MODIFIER_STAT_COLOR,
                    ),
                    _html_line(
                        "The selected skill's profile weight is included once for "
                        "each modified skill. The modifier's actual effects, values, "
                        "and conversions are not yet evaluated."
                    ),
                )
            )
        html.extend(
            (
                _html_line(""),
                _html_line(f"Source: {_item_source_label(match.variant)}"),
            )
        )
        if (
            match.variant.acquisition_source == "Specific Monster Drop"
            and len(match.variant.monster_sources) > 1
        ):
            html.append(
                _html_line(
                    f"Drops from {len(match.variant.monster_sources)} enemies:",
                    bold=True,
                )
            )
            html.extend(
                _html_line(f"- {source.name}")
                for source in match.variant.monster_sources
            )
        if (
            match.variant.acquisition_source == "Lootable Container"
            and len(match.variant.container_sources) > 1
        ):
            html.append(
                _html_line(
                    "Found in "
                    f"{len(match.variant.container_sources)} lootable containers:",
                    bold=True,
                )
            )
            html.extend(
                _html_line(f"- {source.name}")
                for source in match.variant.container_sources
            )
        html.extend(
            (
                _html_line(f"Required level: {match.variant.level_requirement}"),
                _html_line("Grades assume the highest-level item variant."),
                _html_line(f"Localization tag: {match.item.localization_tag}"),
                _html_line(
                    f"Record: {match.variant.source}:{match.variant.record_path}"
                ),
            )
        )
        self.unique_details.setHtml("".join(html))

    def _show_addon(
        self,
        table: AddonSlotTable,
        slot_id: str,
        match: RankedAddonVariant,
    ) -> None:
        if self._selected_addon_table is not table:
            for other in self.addon_tables.values():
                if other is not table:
                    other.clearSelection()
                    other.setCurrentCell(-1, -1)
            self._selected_addon_table = table
        score = match.score
        matched_ids = set(score.matched_stat_ids)
        unmatched_ids = [
            stat_id
            for stat_id in match.semantic_stat_ids
            if stat_id not in matched_ids
        ]
        type_label = ADDON_TYPE_LABELS[match.addon_type]
        self.addon_detail_pane.set_title(
            f"{match.marker}{match.item.display_name} \u00b7 "
            f"{SLOT_LABELS[slot_id]} \u00b7 {type_label}",
            DETAIL_TITLE_COLORS[match.addon_type],
        )
        html = [
            _html_line(
                f"Effective score: {_format_score(score.effective_score)} "
                f"\u00b7 Base score: {_format_score(score.base_effective_score)} "
                f"(profile x{score.profile_adjustment:.3f}) "
                f"\u00b7 "
                f"{'Amplified' if self.resistance_cap_enabled else 'Raw'} "
                f"weight total: {score.weighted_match} "
                f"\u00b7 Coverage: "
                f"{score.matched_count}/{score.total_category_count} "
                f"({score.coverage_ratio:.0%})"
            ),
            _html_line(""),
            _html_line("Matched stats:", bold=True),
        ]
        if score.matched_stat_ids:
            html.extend(
                _stat_html(
                    stat_id,
                    f"{self._label_for(stat_id, match.variant.properties)}: "
                    f"{self._addon_weight_description(stat_id)}",
                    matched=True,
                )
                for stat_id in score.matched_stat_ids
            )
        else:
            html.append(_stat_html("", "None", matched=True))
        html.extend(
            (_html_line(""), _html_line("Remaining unmatched stats:", bold=True))
        )
        if unmatched_ids:
            html.extend(
                _stat_html(
                    stat_id,
                    self._label_for(stat_id, match.variant.properties),
                    matched=False,
                )
                for stat_id in unmatched_ids
            )
        else:
            html.append(_stat_html("", "None", matched=False))
        html.extend(
            _granted_skill_section((match.variant.granted_skill_name,))
        )
        html.append(_html_line(""))
        if match.addon_type == ADDON_AUGMENT:
            faction = (
                match.variant.faction_name
                or match.variant.faction_source
                or "Unknown"
            )
            html.append(_html_line(f"Faction: {faction}"))
        if match.variant.vendor_sources:
            vendors = ", ".join(
                f"{source.faction_name} ({source.reputation})"
                for source in match.variant.vendor_sources
            )
            html.append(_html_line(f"Recipe sold by: {vendors}"))
        html.extend(
            (
                _html_line(f"Source: {match.variant.acquisition_source}"),
                _html_line(
                    f"Required level: {match.variant.level_requirement}"
                ),
                _html_line("Grades assume the highest-level item variant."),
                _html_line(f"Localization tag: {match.item.localization_tag}"),
                _html_line(
                    f"Record: {match.variant.source}:"
                    f"{match.variant.record_path}"
                ),
            )
        )
        self.addon_details.setHtml("".join(html))

    def _addon_weight_description(self, stat_id: str) -> str:
        if self.resistance_cap_enabled and stat_id in self.resistance_cap_weights:
            weight = self.resistance_cap_weights[stat_id]
            return f"cap weight {weight} (amplified to {weight * 2})"
        return (
            "weight "
            f"{profile_weight_for_semantic_id(self.profile, stat_id)}"
        )

    def _label_for(
        self, stat_id: str, properties: tuple[object, ...] = ()
    ) -> str:
        rank = _skill_rank_for_stat(properties, stat_id)
        property_display_name = _property_display_name_for_stat(
            properties, stat_id
        )
        for prefix, label in (
            ("skill_bonus:", "+Ranks to"),
            ("skill_modifier:", "Skill modifier for"),
            ("mastery_bonus:", "+Ranks to all skills in"),
            ("granted_item_skill:", "Granted Skill:"),
        ):
            if stat_id.startswith(prefix):
                reference = stat_id[len(prefix) :]
                if prefix in {
                    "skill_bonus:",
                    "skill_modifier:",
                    "granted_item_skill:",
                }:
                    reference = self.skill_labels.get(
                        reference,
                        self.canonical_skill_labels.get(
                            canonical_skill_reference(reference),
                            property_display_name or reference,
                        ),
                    )
                else:
                    reference = self.mastery_labels.get(
                        reference, property_display_name or reference
                    )
                if rank and prefix not in {
                    "skill_modifier:",
                    "granted_item_skill:",
                }:
                    label = (
                        f"+{rank} to"
                        if prefix == "skill_bonus:"
                        else f"+{rank} to All Skills in"
                    )
                return f"{label} {reference}"
        return STAT_LABELS.get(stat_id, stat_id)


def _skill_rank_for_stat(
    properties: tuple[object, ...], stat_id: str
) -> str:
    ranks: list[int] = []
    for property_ in properties:
        if semantic_stat_id(property_) != stat_id:
            continue
        raw_rank = getattr(property_, "attributes", {}).get("skill_level", "")
        try:
            ranks.append(int(float(raw_rank)))
        except (TypeError, ValueError):
            continue
    return str(max(ranks)) if ranks else ""


def _property_display_name_for_stat(
    properties: tuple[object, ...], stat_id: str
) -> str:
    for property_ in properties:
        if semantic_stat_id(property_) != stat_id:
            continue
        display_name = getattr(property_, "attributes", {}).get(
            "display_name", ""
        )
        if isinstance(display_name, str) and display_name.strip():
            return display_name.strip()
    return ""
