"""Build-profile editing view."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.catalog import SkillCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.game_version import detect_game_snapshot
from gd_affix_relevance.profile_store import load_profile, save_profile
from gd_affix_relevance.ui.catalog import PROFILE_TABS, TabDefinition
from gd_affix_relevance.ui.settings import GAME_FOLDER_SETTING
from gd_affix_relevance.ui.widgets import PackageAccordion
from gd_affix_relevance.ui.skills_editor import SkillsEditor


class ProfileEditor(QWidget):
    profile_changed = Signal()
    profile_path_changed = Signal(object)
    view_matches_requested = Signal()

    def __init__(
        self,
        profile: BuildProfile | None = None,
        parent: QWidget | None = None,
        *,
        skills: SkillCatalog | None = None,
        profile_path: Path | None = None,
        profiles_root: Path | None = None,
        startup_notice: str = "",
        settings: QSettings | None = None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile or BuildProfile()
        self.settings = settings
        self.accordions: dict[str, PackageAccordion] = {}
        self.current_profile_path = Path(profile_path) if profile_path else None
        self.profiles_root = (
            Path(profiles_root).expanduser().resolve()
            if profiles_root is not None
            else Path.cwd()
        )
        self.profiles_root.mkdir(parents=True, exist_ok=True)
        self.custom_profiles_root = self.profiles_root / "custom"
        self.custom_profiles_root.mkdir(parents=True, exist_ok=True)
        self._default_profile_paths = self._discover_default_profile_paths()
        self._default_selector_paths: list[Path] = []
        self._custom_selector_paths: list[Path] = []
        self._profile_row_labels: list[QLabel] = []
        self._profile_row_spacing = 8
        self.is_dirty = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        heading_row = QHBoxLayout()
        heading = QLabel("Build Profile", self)
        heading.setObjectName("pageTitle")
        heading_row.addWidget(heading)
        heading_row.addStretch()
        legend = QLabel(
            "☆ Ignored   ★ Incidental   ★★ Useful   ★★★ Emphasized   ★★★★ Core",
            self,
        )
        legend.setObjectName("weightLegend")
        heading_row.addWidget(legend)
        layout.addLayout(heading_row)

        name_row = QHBoxLayout()
        name_row.setSpacing(self._profile_row_spacing)
        name_label = QLabel("Profile name", self)
        name_label.setText("Profile")
        name_label.setObjectName("fieldLabel")
        self._profile_row_labels.append(name_label)
        name_row.addWidget(name_label)
        self.name_edit = QLineEdit(self.profile.name, self)
        self.name_edit.setObjectName("profileInput")
        self.name_edit.textChanged.connect(self._name_changed)
        name_row.addWidget(self.name_edit, 1)
        self.new_button = QPushButton("New Profile", self)
        self.new_button.setObjectName("profileAction")
        self.new_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_FileDialogNewFolder
            )
        )
        self.new_button.setToolTip("Start a blank build profile")
        self.new_button.clicked.connect(self.new_profile)
        name_row.addWidget(self.new_button)
        self.save_button = QPushButton("Save Profile", self)
        self.save_button.setObjectName("profileAction")
        self.save_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_DialogSaveButton
            )
        )
        self.save_button.setToolTip("Save this profile into your custom profile list")
        self.save_button.clicked.connect(self._save_current_profile)
        name_row.addWidget(self.save_button)
        layout.addLayout(name_row)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(self._profile_row_spacing)
        default_label = QLabel("Defaults", self)
        default_label.setObjectName("fieldLabel")
        self._profile_row_labels.append(default_label)
        selector_row.addWidget(default_label)
        self.default_profile_selector = QComboBox(self)
        self.default_profile_selector.setObjectName("profilePicker")
        selector_row.addWidget(self.default_profile_selector, 1)
        self.load_default_button = QPushButton("Apply Default", self)
        self.load_default_button.setObjectName("profileAction")
        self.load_default_button.clicked.connect(self._apply_selected_default_profile)
        selector_row.addWidget(self.load_default_button)
        layout.addLayout(selector_row)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(self._profile_row_spacing)
        custom_label = QLabel("Custom", self)
        custom_label.setObjectName("fieldLabel")
        self._profile_row_labels.append(custom_label)
        custom_row.addWidget(custom_label)
        self.custom_profile_selector = QComboBox(self)
        self.custom_profile_selector.setObjectName("profilePicker")
        custom_row.addWidget(self.custom_profile_selector, 1)
        self.load_custom_button = QPushButton("Apply Custom", self)
        self.load_custom_button.setObjectName("profileAction")
        self.load_custom_button.clicked.connect(self._apply_selected_custom_profile)
        custom_row.addWidget(self.load_custom_button)
        layout.addLayout(custom_row)

        self.status_indent = QWidget(self)
        self.status_indent.setFixedWidth(0)
        status_row = QHBoxLayout()
        status_row.setSpacing(self._profile_row_spacing)
        status_row.addWidget(self.status_indent)

        initial_status = (
            f"Loaded {self.current_profile_path.name}"
            if self.current_profile_path is not None
            else startup_notice or "Not saved"
        )
        self.file_status = QLabel(initial_status, self)
        self.file_status.setObjectName("profileStatusPill")
        if self.current_profile_path is not None:
            self.file_status.setToolTip(str(self.current_profile_path))
        status_row.addWidget(self.file_status)
        status_row.addStretch()
        layout.addLayout(status_row)

        self._align_profile_row_labels()
        self._align_action_buttons()

        hint_row = QHBoxLayout()
        hint = QLabel(
            "All packages remain visible. Optional packages start collapsed and stay "
            "open whenever they contain a nonzero weight.",
            self,
        )
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        hint_row.addWidget(hint, 1)
        self.view_matches_button = QPushButton("View Matches", self)
        self.view_matches_button.setObjectName("primaryAction")
        self.view_matches_button.clicked.connect(self.view_matches_requested)
        hint_row.addWidget(self.view_matches_button)
        layout.addLayout(hint_row)

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("profileTabs")
        for definition in PROFILE_TABS:
            self.tabs.addTab(self._build_tab(definition), definition.label)
        self.skills_editor = SkillsEditor(
            self.profile, skills or SkillCatalog(()), self
        )
        self.skills_editor.changed.connect(self._skills_changed)
        self.tabs.addTab(self.skills_editor, "Skills")
        layout.addWidget(self.tabs, 1)
        self._refresh_profile_selectors()

    def set_profiles_root(self, profiles_root: Path) -> None:
        previous_root = self.profiles_root
        previous_current = self.current_profile_path
        self.profiles_root = Path(profiles_root).expanduser().resolve()
        self.profiles_root.mkdir(parents=True, exist_ok=True)
        self.custom_profiles_root = self.profiles_root / "custom"
        self.custom_profiles_root.mkdir(parents=True, exist_ok=True)
        self._default_profile_paths = self._discover_default_profile_paths()

        if (
            previous_current is not None
            and previous_current.is_relative_to(previous_root)
        ):
            migrated = self.profiles_root / previous_current.relative_to(
                previous_root
            )
            if migrated.exists():
                self.current_profile_path = migrated.resolve()
                self.file_status.setToolTip(str(self.current_profile_path))
        self._refresh_profile_selectors(selected_path=self.current_profile_path)

    def _build_tab(self, definition: TabDefinition) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 12, 8, 12)
        content_layout.setSpacing(10)
        for package in definition.packages:
            accordion = PackageAccordion(
                package,
                self.profile.weight_for,
                self.profile.set_weight,
                content,
                conversion_source_enabled=(
                    self.profile.conversion_source_enabled
                ),
                set_conversion_source_enabled=(
                    self.profile.set_conversion_source_enabled
                ),
            )
            accordion.weight_changed.connect(self._weights_changed)
            accordion.bulk_applied.connect(self._weights_bulk_changed)
            accordion.conversion_source_changed.connect(
                self._conversion_source_changed
            )
            content_layout.addWidget(accordion)
            self.accordions[package.package_id] = accordion
        content_layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _name_changed(self, name: str) -> None:
        self.profile.name = name
        self._mark_unsaved()

    def _weights_changed(self, _stat_id: str, _weight: int) -> None:
        self._mark_unsaved()
        sender = self.sender()
        if isinstance(sender, PackageAccordion) and sender._in_bulk_update:
            return
        self.profile_changed.emit()

    def _weights_bulk_changed(self) -> None:
        self._mark_unsaved()
        self.profile_changed.emit()

    def _skills_changed(self) -> None:
        self._mark_unsaved()
        self.profile_changed.emit()

    def _conversion_source_changed(
        self, _destination: str, _source: str, _enabled: bool
    ) -> None:
        self._mark_unsaved()
        self.profile_changed.emit()

    def save_to_path(self, path: Path) -> Path:
        """Save the active profile, primarily for UI actions and tests."""

        self._stamp_profile_snapshot_from_settings()
        destination = save_profile(self.profile, path)
        self.current_profile_path = destination
        self.is_dirty = False
        self.file_status.setText(f"Saved {destination.name}")
        self.file_status.setToolTip(str(destination))
        self._refresh_profile_selectors(selected_path=destination)
        self.profile_path_changed.emit(destination)
        return destination

    def _save_current_profile(self) -> bool:
        target = self.current_profile_path
        if target is None or target in self._default_profile_paths:
            slug = self._profile_slug(self.profile.name)
            target = self.custom_profiles_root / f"{slug}.json"
        try:
            self.save_to_path(target)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Could Not Save Profile", str(error))
            return False
        return True

    def _stamp_profile_snapshot_from_settings(self) -> None:
        if self.settings is None:
            return
        raw = self.settings.value(GAME_FOLDER_SETTING, "", type=str).strip()
        if not raw:
            return
        snapshot = detect_game_snapshot(Path(raw))
        self.profile.saved_db_hash = snapshot.db_hash
        self.profile.saved_steam_build_id = snapshot.steam_build_id
        self.profile.saved_patch_versions = snapshot.patch_versions

    def load_from_path(self, path: Path) -> BuildProfile:
        """Load *path* into the existing profile object and refresh controls."""

        loaded = load_profile(path)
        self.profile.name = loaded.name
        self.profile.weights.clear()
        for stat_id, weight in loaded.weights.items():
            self.profile.set_weight(stat_id, weight)
        self.profile.masteries = loaded.masteries
        self.profile.skill_weights.clear()
        for skill_id, weight in loaded.skill_weights.items():
            self.profile.set_skill_weight(skill_id, weight)
        self.profile.excluded_conversion_sources.clear()
        for destination, sources in loaded.excluded_conversion_sources.items():
            for source in sources:
                self.profile.set_conversion_source_enabled(
                    destination, source, False
                )
        self.profile.resistance_cap_enabled = loaded.resistance_cap_enabled
        self.profile.resistance_cap_weights.clear()
        for stat_id, weight in loaded.resistance_cap_weights.items():
            self.profile.set_resistance_cap_weight(stat_id, weight)

        blocker = QSignalBlocker(self.name_edit)
        self.name_edit.setText(self.profile.name)
        del blocker
        for accordion in self.accordions.values():
            accordion.refresh_from_profile()
        self.skills_editor.refresh_from_profile()

        self.current_profile_path = Path(path)
        self.is_dirty = False
        self.file_status.setText(f"Loaded {self.current_profile_path.name}")
        self.file_status.setToolTip(str(self.current_profile_path))
        self._refresh_profile_selectors(selected_path=self.current_profile_path)
        self.profile_path_changed.emit(self.current_profile_path)
        self.profile_changed.emit()
        return self.profile

    def new_profile(self) -> bool:
        """Reset every profile field after resolving unsaved changes."""

        if self.is_dirty:
            action = self._prompt_unsaved_action()
            if action == QMessageBox.StandardButton.Cancel:
                return False
            if action == QMessageBox.StandardButton.Save and not self._save_before_reset():
                return False

        baseline = BuildProfile()
        self.profile.name = baseline.name
        self.profile.weights.clear()
        self.profile.masteries = baseline.masteries
        self.profile.skill_weights.clear()
        self.profile.excluded_conversion_sources.clear()
        self.profile.resistance_cap_enabled = baseline.resistance_cap_enabled
        self.profile.resistance_cap_weights.clear()
        blocker = QSignalBlocker(self.name_edit)
        self.name_edit.setText(self.profile.name)
        del blocker
        for accordion in self.accordions.values():
            accordion.refresh_from_profile()
        self.skills_editor.refresh_from_profile()
        self.current_profile_path = None
        self.is_dirty = False
        self.file_status.setText("New profile not saved")
        self.file_status.setToolTip("")
        self._refresh_profile_selectors()
        self.profile_path_changed.emit(None)
        self.profile_changed.emit()
        return True

    def confirm_close(self) -> bool:
        """Resolve unsaved profile changes before the application closes."""

        if not self.is_dirty:
            return True
        action = self._prompt_exit_unsaved_action()
        if action == QMessageBox.StandardButton.Cancel:
            return False
        if action == QMessageBox.StandardButton.Save:
            return self._save_before_reset()
        return True

    def _prompt_unsaved_action(self) -> QMessageBox.StandardButton:
        return self._prompt_unsaved(
            "Save changes to the current profile before starting a new one?",
        )

    def _prompt_exit_unsaved_action(self) -> QMessageBox.StandardButton:
        return self._prompt_unsaved(
            "Save changes to the current profile before exiting?"
        )

    def _prompt_unsaved(self, message: str) -> QMessageBox.StandardButton:
        return QMessageBox.warning(
            self,
            "Unsaved Profile",
            message,
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

    def _save_before_reset(self) -> bool:
        if self.current_profile_path is None:
            return self._save_current_profile()
        try:
            self.save_to_path(self.current_profile_path)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Could Not Save Profile", str(error))
            return False
        return True

    def _choose_profile_to_save(self) -> bool:
        suggested = str(
            self.current_profile_path
            or self.profiles_root
            / f"{self.profile.name.strip() or 'build-profile'}.json"
        )
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save Build Profile",
            suggested,
            "Grim Gleaner Profiles (*.json);;All Files (*)",
        )
        if not selected:
            return False
        try:
            self.save_to_path(Path(selected))
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Could Not Save Profile", str(error))
            return False
        return True

    def _choose_profile_to_load(self) -> bool:
        starting_path = str(self.current_profile_path or self.profiles_root)
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Load Build Profile",
            starting_path,
            "Grim Gleaner Profiles (*.json);;All Files (*)",
        )
        if not selected:
            return False
        try:
            self.load_from_path(Path(selected))
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Could Not Load Profile", str(error))
            return False
        return True

    def _apply_selected_default_profile(self) -> bool:
        if not self._default_selector_paths:
            return False
        index = self.default_profile_selector.currentIndex()
        if index < 0 or index >= len(self._default_selector_paths):
            return False
        return self._load_profile_with_unsaved_prompt(
            self._default_selector_paths[index]
        )

    def _apply_selected_custom_profile(self) -> bool:
        if not self._custom_selector_paths:
            return False
        index = self.custom_profile_selector.currentIndex()
        if index < 0 or index >= len(self._custom_selector_paths):
            return False
        return self._load_profile_with_unsaved_prompt(
            self._custom_selector_paths[index]
        )

    def _load_profile_with_unsaved_prompt(self, path: Path) -> bool:
        if self.is_dirty:
            action = self._prompt_unsaved_action()
            if action == QMessageBox.StandardButton.Cancel:
                return False
            if action == QMessageBox.StandardButton.Save and not self._save_before_reset():
                return False
        try:
            self.load_from_path(path)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Could Not Load Profile", str(error))
            return False
        return True

    def _discover_default_profile_paths(self) -> tuple[Path, ...]:
        candidates: set[Path] = set()
        examples = self.profiles_root / "examples"
        if examples.is_dir():
            candidates.update(
                path for path in examples.glob("*.json") if path.is_file()
            )
        return tuple(sorted(candidates, key=lambda path: path.name.casefold()))

    def _align_profile_row_labels(self) -> None:
        if not self._profile_row_labels:
            return
        width = max(label.sizeHint().width() for label in self._profile_row_labels)
        for label in self._profile_row_labels:
            label.setFixedWidth(width)
        self.status_indent.setFixedWidth(width + self._profile_row_spacing)

    def _align_action_buttons(self) -> None:
        width = max(
            self.load_default_button.sizeHint().width(),
            self.load_custom_button.sizeHint().width(),
        )
        self.load_default_button.setFixedWidth(width)
        self.load_custom_button.setFixedWidth(width)

    def _list_custom_profile_paths(self) -> tuple[Path, ...]:
        paths = tuple(
            sorted(
                (
                    path
                    for path in self.profiles_root.rglob("*.json")
                    if path.is_file() and path not in self._default_profile_paths
                ),
                key=lambda path: path.name.casefold(),
            )
        )
        return paths

    def _refresh_profile_selectors(self, *, selected_path: Path | None = None) -> None:
        self._default_selector_paths = list(self._default_profile_paths)
        self._custom_selector_paths = list(self._list_custom_profile_paths())

        self.default_profile_selector.blockSignals(True)
        self.default_profile_selector.clear()
        for path in self._default_selector_paths:
            label = self._selector_label(path)
            self.default_profile_selector.addItem(label)
        self.default_profile_selector.blockSignals(False)
        self.load_default_button.setEnabled(bool(self._default_selector_paths))

        self.custom_profile_selector.blockSignals(True)
        self.custom_profile_selector.clear()
        if self._custom_selector_paths:
            for path in self._custom_selector_paths:
                label = self._selector_label(path)
                self.custom_profile_selector.addItem(label)
        else:
            self.custom_profile_selector.addItem("No custom profiles saved yet")
        self.custom_profile_selector.blockSignals(False)
        self.custom_profile_selector.setEnabled(bool(self._custom_selector_paths))
        self.load_custom_button.setEnabled(bool(self._custom_selector_paths))

        if selected_path is None:
            selected_path = self.current_profile_path
        active_default = False
        active_custom = False
        if selected_path is not None:
            selected = Path(selected_path).expanduser().resolve()
            if selected in self._default_selector_paths:
                self.default_profile_selector.setCurrentIndex(
                    self._default_selector_paths.index(selected)
                )
                active_default = True
            if selected in self._custom_selector_paths:
                self.custom_profile_selector.setCurrentIndex(
                    self._custom_selector_paths.index(selected)
                )
                active_custom = True
        self._set_active_selector(
            self.default_profile_selector,
            active_default,
        )
        self._set_active_selector(
            self.custom_profile_selector,
            active_custom,
        )

    def _set_active_selector(self, selector: QComboBox, active: bool) -> None:
        selector.setProperty("activeLoaded", active)
        selector.style().unpolish(selector)
        selector.style().polish(selector)

    def _selector_label(self, path: Path) -> str:
        try:
            relative = path.relative_to(self.profiles_root)
            return relative.as_posix()
        except ValueError:
            return path.name

    def _profile_slug(self, value: str) -> str:
        cleaned = "".join(
            character if character.isalnum() or character in {"-", "_"} else "-"
            for character in value.strip().lower()
        ).strip("-")
        return cleaned or "build-profile"

    def _mark_unsaved(self) -> None:
        self.is_dirty = True
        if self.current_profile_path is None:
            self.file_status.setText("Not saved")
            self.file_status.setToolTip("")
        else:
            self.file_status.setText(f"Unsaved {self.current_profile_path.name}")
            self.file_status.setToolTip(str(self.current_profile_path))

    def mark_external_change(self) -> None:
        """Mark profile state changed by a control outside this editor page."""

        self._mark_unsaved()
