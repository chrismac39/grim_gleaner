"""In-application reference for item color palette logic."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class PaletteLogicPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        heading = QLabel("Palette Logic", self)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        introduction = QLabel(
            "This page documents the default color choices used by Grim Gleaner "
            "when composing grade-aware item labels. The implementation is now "
            "Python-native, while keeping compatibility with existing gdse-style "
            "palette key conventions.",
            self,
        )
        introduction.setObjectName("pageHint")
        introduction.setWordWrap(True)
        layout.addWidget(introduction)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 8, 12, 8)
        content_layout.setSpacing(18)

        _add_section(
            content_layout,
            "Design goals",
            "1. Keep labels readable on Grim Dawn's dark tooltip background.\n"
            "2. Preserve player-installed color files when present.\n"
            "3. Keep palette keys stable so custom override files stay useful.\n"
            "4. Keep defaults opinionated but allow narrow, one-line overrides.",
            content,
        )

        _add_section(
            content_layout,
            "Rarity defaults",
            "rarity.common = w (White)\n"
            "rarity.magical = y (Yellow)\n"
            "rarity.rare = g (Green)\n"
            "rarity.epic = engine default blue unless explicitly overridden\n"
            "rarity.legendary = engine default indigo unless explicitly overridden",
            content,
        )

        _add_section(
            content_layout,
            "Damage defaults",
            "damage.physical = k (Khaki)\n"
            "damage.pierce = f (Fuchsia/Pink)\n"
            "damage.bleeding = r (Red)\n"
            "damage.fire = o (Orange)\n"
            "damage.cold = c (Cyan)\n"
            "damage.lightning = z (Cobalt)\n"
            "damage.poison = l (Olive)\n"
            "damage.vitality = m (Maroon)\n"
            "damage.life = m (Maroon)\n"
            "damage.aether = a (Aqua)\n"
            "damage.chaos = p (Purple)\n"
            "damage.elemental = y (Yellow)",
            content,
        )

        _add_section(
            content_layout,
            "Non-damage defaults",
            "nondamage.attribute0 = h (Grayish Orange highlight)\n"
            "nondamage.mastery_increment = t (Teal)\n"
            "nondamage.all_skill_increment = t (Teal)\n"
            "Most speed, OA/DA, crit, and total-damage categories remain uncolored "
            "by default unless overridden.",
            content,
        )

        _add_section(
            content_layout,
            "Why Pierce is pink",
            "The default separates Pierce from Bleeding at a glance. "
            "If you prefer the classic red Pierce look, set damage.pierce=r in "
            "your custom palette file.",
            content,
        )

        _add_section(
            content_layout,
            "Custom palette format",
            "Use one key=value line per override. Blank lines and # comments are "
            "allowed. Example:\n"
            "damage.chaos=f\n"
            "Only keys you provide are changed; all others keep defaults.",
            content,
        )

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)


def _add_section(
    layout: QVBoxLayout,
    title: str,
    text: str,
    parent: QWidget,
) -> None:
    title_label = QLabel(title, parent)
    title_label.setObjectName("guideSectionTitle")
    layout.addWidget(title_label)

    body = QLabel(text, parent)
    body.setObjectName("guideBody")
    body.setWordWrap(True)
    layout.addWidget(body)
