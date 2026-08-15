"""Install and restore graded Grim Dawn item localization."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.catalog import AffixCatalog, ItemCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.grade_export import (
    GradeExportResult,
    GradeSnapshotApplyResult,
    ProfileGradeSnapshot,
    apply_profile_grade_snapshot,
    backup_available,
    export_grades_to_game,
    grim_dawn_text_root,
    list_profile_grade_snapshots,
    restore_game_backup,
)
from gd_affix_relevance.output import build_affix_markers, build_unique_item_markers
from gd_affix_relevance.profile_store import load_profile
from gd_affix_relevance.ui.settings import (
    GAME_FOLDER_SETTING,
    PALETTE_FILE_SETTING,
)

LAST_EXPORTED_PROFILE_SETTING = "export/last_profile_name"


class GenerateOutputPage(QWidget):
    def __init__(
        self,
        catalog: AffixCatalog | None,
        profile: BuildProfile,
        *,
        items: ItemCatalog | None = None,
        source_root: Path,
        output_root: Path,
        backups_root: Path,
        profiles_root: Path | None = None,
        catalog_status: str = "",
        settings: QSettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.items = items or ItemCatalog((), (), (), (), (), ())
        self.profile = profile
        self.catalog_status = catalog_status
        self.settings = settings
        self.bundled_source_root = Path(source_root)
        self.staging_root = Path(output_root)
        self.backups_root = Path(backups_root)
        self.profiles_root = (
            Path(profiles_root).expanduser().resolve()
            if profiles_root is not None
            else (Path.cwd() / "artifacts" / "profiles").resolve()
        )
        self.custom_profiles_root = self.profiles_root / "custom"
        self._default_profile_paths: list[Path] = []
        self._custom_profile_paths: list[Path] = []
        self.last_result: GradeExportResult | None = None
        self._snapshot_ids: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        heading = QLabel("Export Grades", self)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        explanation = QLabel(
            "Export Grades applies the active profile's affix and unique-item "
            "grades directly to Grim Dawn's item names. Existing installed item-tag "
            "files are retained as the source, while Grim Gleaner's bundled "
            "files supply anything missing. Before the first export, the "
            "current text_en folder is backed up so it can be restored here.",
            self,
        )
        explanation.setObjectName("pageHint")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.target_label = QLabel(self)
        self.target_label.setObjectName("fieldLabel")
        self.target_label.setWordWrap(True)
        layout.addWidget(self.target_label)

        action_row = QHBoxLayout()
        self.generate_button = QPushButton("Export Grades", self)
        self.generate_button.setObjectName("primaryAction")
        self.generate_button.setEnabled(catalog is not None)
        self.generate_button.clicked.connect(self.generate)
        action_row.addWidget(self.generate_button)

        self.restore_button = QPushButton("Restore Backups", self)
        self.restore_button.setObjectName("profileAction")
        self.restore_button.clicked.connect(self.restore_backup)
        action_row.addWidget(self.restore_button)
        action_row.addStretch()
        layout.addLayout(action_row)

        default_row = QHBoxLayout()
        default_row.setSpacing(8)
        default_label = QLabel("Switch default profile", self)
        default_label.setObjectName("fieldLabel")
        default_row.addWidget(default_label)
        self.default_profile_selector = QComboBox(self)
        self.default_profile_selector.setObjectName("profileSwapSelector")
        default_row.addWidget(self.default_profile_selector, 1)
        self.apply_default_profile_button = QPushButton(
            "Export Selected Default",
            self,
        )
        self.apply_default_profile_button.setObjectName("profileAction")
        self.apply_default_profile_button.clicked.connect(
            self.export_selected_default
        )
        default_row.addWidget(self.apply_default_profile_button)
        layout.addLayout(default_row)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        custom_label = QLabel("Switch custom profile", self)
        custom_label.setObjectName("fieldLabel")
        custom_row.addWidget(custom_label)
        self.custom_profile_selector = QComboBox(self)
        self.custom_profile_selector.setObjectName("profileSwapSelector")
        custom_row.addWidget(self.custom_profile_selector, 1)
        self.apply_custom_profile_button = QPushButton(
            "Export Selected Custom",
            self,
        )
        self.apply_custom_profile_button.setObjectName("profileAction")
        self.apply_custom_profile_button.clicked.connect(
            self.export_selected_custom
        )
        custom_row.addWidget(self.apply_custom_profile_button)
        layout.addLayout(custom_row)

        switch_row = QHBoxLayout()
        switch_row.setSpacing(8)
        switch_label = QLabel("Switch saved profile grades", self)
        switch_label.setObjectName("fieldLabel")
        switch_row.addWidget(switch_label)
        self.snapshot_selector = QComboBox(self)
        self.snapshot_selector.setObjectName("profileSwapSelector")
        switch_row.addWidget(self.snapshot_selector, 1)
        self.apply_snapshot_button = QPushButton(
            "Apply Selected Profile Grades",
            self,
        )
        self.apply_snapshot_button.setObjectName("profileAction")
        self.apply_snapshot_button.clicked.connect(self.apply_selected_snapshot)
        switch_row.addWidget(self.apply_snapshot_button)
        layout.addLayout(switch_row)

        self.status = QLabel(self)
        self.status.setObjectName("pageHint")
        self.status.setWordWrap(True)
        if catalog is None:
            self.status.setText(catalog_status or "No compiled catalog is available.")
        else:
            self.status.setText(catalog_status)
        layout.addWidget(self.status)

        last_export_row = QHBoxLayout()
        last_export_label = QLabel("Last Exported Profile:", self)
        last_export_label.setObjectName("fieldLabel")
        last_export_row.addWidget(last_export_label)
        self.last_exported_profile = QLabel(self._last_exported_profile_name(), self)
        self.last_exported_profile.setObjectName("lastExportedProfile")
        last_export_row.addWidget(self.last_exported_profile)
        last_export_row.addStretch()
        layout.addLayout(last_export_row)
        layout.addStretch()
        self._refresh_profile_selectors()
        self.refresh_game_location()

    def set_profiles_root(self, profiles_root: Path) -> None:
        self.profiles_root = Path(profiles_root).expanduser().resolve()
        self.custom_profiles_root = self.profiles_root / "custom"
        self._refresh_profile_selectors()

    def refresh_profile_selectors(self) -> None:
        self._refresh_profile_selectors()

    def generate(self, _checked: bool = False) -> None:
        if self.catalog is None:
            return
        self._export_with_profile(self.profile)

    def export_selected_default(self, _checked: bool = False) -> None:
        if not self._default_profile_paths:
            return
        index = self.default_profile_selector.currentIndex()
        if index < 0 or index >= len(self._default_profile_paths):
            return
        self._export_from_path(self._default_profile_paths[index])

    def export_selected_custom(self, _checked: bool = False) -> None:
        if not self._custom_profile_paths:
            return
        index = self.custom_profile_selector.currentIndex()
        if index < 0 or index >= len(self._custom_profile_paths):
            return
        self._export_from_path(self._custom_profile_paths[index])

    def _export_from_path(self, path: Path) -> None:
        try:
            export_profile = load_profile(path)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Could Not Load Profile", str(error))
            return
        self._export_with_profile(export_profile)

    def _export_with_profile(self, export_profile: BuildProfile) -> None:
        if self.catalog is None:
            return
        try:
            game_folder = self._configured_game_folder()
            grim_dawn_text_root(game_folder)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Could Not Export Grades", str(error))
            return

        affix_count = len(build_affix_markers(self.catalog, export_profile))
        unique_count = len(build_unique_item_markers(self.items, export_profile))
        profile_name = export_profile.name.strip() or "Unnamed Profile"
        choice = QMessageBox.question(
            self,
            "Export Grades",
            f"About to export grades for {profile_name}. "
            "\nAbout to apply grade tags to "
            f"{affix_count} affix and {unique_count} unique item entries. "
            "Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        try:
            result = export_grades_to_game(
                game_folder,
                self.bundled_source_root,
                self.staging_root,
                self.backups_root,
                self.catalog,
                export_profile,
                items=self.items,
                palette_file=self._configured_palette_file(),
            )
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.critical(self, "Could Not Export Grades", str(error))
            return

        self.last_result = result
        backup_status = (
            "Created the original-state backup."
            if result.backup_created
            else "Preserved the existing original-state backup."
        )
        self.status.setText(
            f"{backup_status}"
            f"\nExported grades to {result.target_root}. "
            f"\nUpdated {result.generation.annotated_lines} localization entries. "
        )
        exported_name = export_profile.name.strip() or "Unnamed Profile"
        self.last_exported_profile.setText(exported_name)
        if self.settings is not None:
            self.settings.setValue(LAST_EXPORTED_PROFILE_SETTING, exported_name)
            self.settings.sync()
        self.refresh_game_location(update_status=False)
        self._refresh_snapshot_selector()

    def _discover_default_profile_paths(self) -> tuple[Path, ...]:
        examples = self.profiles_root / "examples"
        if not examples.is_dir():
            return ()
        return tuple(
            sorted(
                (path for path in examples.glob("*.json") if path.is_file()),
                key=lambda path: path.name.casefold(),
            )
        )

    def _list_custom_profile_paths(self) -> tuple[Path, ...]:
        defaults = set(self._default_profile_paths)
        return tuple(
            sorted(
                (
                    path
                    for path in self.profiles_root.rglob("*.json")
                    if path.is_file() and path not in defaults
                ),
                key=lambda path: path.name.casefold(),
            )
        )

    def _refresh_profile_selectors(self) -> None:
        self._default_profile_paths = list(self._discover_default_profile_paths())
        self._custom_profile_paths = list(self._list_custom_profile_paths())

        self.default_profile_selector.blockSignals(True)
        self.default_profile_selector.clear()
        for path in self._default_profile_paths:
            self.default_profile_selector.addItem(self._selector_label(path))
        self.default_profile_selector.blockSignals(False)
        self.apply_default_profile_button.setEnabled(bool(self._default_profile_paths))
        if not self._default_profile_paths:
            self.default_profile_selector.addItem("No default profiles found")
            self.default_profile_selector.setEnabled(False)
            self.apply_default_profile_button.setEnabled(False)
        else:
            self.default_profile_selector.setEnabled(True)

        self.custom_profile_selector.blockSignals(True)
        self.custom_profile_selector.clear()
        for path in self._custom_profile_paths:
            self.custom_profile_selector.addItem(self._selector_label(path))
        self.custom_profile_selector.blockSignals(False)
        has_custom = bool(self._custom_profile_paths)
        self.custom_profile_selector.setEnabled(has_custom)
        self.apply_custom_profile_button.setEnabled(has_custom)
        if not has_custom:
            self.custom_profile_selector.addItem("No custom profiles saved yet")
            self.custom_profile_selector.setEnabled(False)
            self.apply_custom_profile_button.setEnabled(False)

    def _selector_label(self, path: Path) -> str:
        try:
            return path.relative_to(self.profiles_root).as_posix()
        except ValueError:
            return path.name

    def restore_backup(self, _checked: bool = False) -> None:
        try:
            game_folder = self._configured_game_folder()
            if not backup_available(game_folder, self.backups_root):
                raise ValueError(
                    "No original-state backup exists for the configured Grim Dawn folder."
                )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Could Not Restore Backup", str(error))
            return

        choice = QMessageBox.question(
            self,
            "Restore Backup",
            "Restoring Grim Dawn/settings/text_en folder to original state.\n\n"
            "Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        try:
            result = restore_game_backup(game_folder, self.backups_root)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Could Not Restore Backup", str(error))
            return
        if result.original_existed:
            message = f"Restored {result.restored_files} files to {result.target_root}."
        else:
            message = (
                "Restored the clean-install state by removing Grim Gleaner's "
                f"generated folder at {result.target_root}."
            )
        self.status.setText(message)
        self.last_result = None
        self.refresh_game_location(update_status=False)
        self._refresh_snapshot_selector()

    def apply_selected_snapshot(self, _checked: bool = False) -> None:
        try:
            game_folder = self._configured_game_folder()
            grim_dawn_text_root(game_folder)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Could Not Apply Saved Grades", str(error))
            return

        index = self.snapshot_selector.currentIndex()
        if index < 0 or index >= len(self._snapshot_ids):
            QMessageBox.warning(
                self,
                "No Saved Profile Grades",
                "Export at least one profile first, then choose it from the selector.",
            )
            return

        snapshot_id = self._snapshot_ids[index]
        selected_name = self.snapshot_selector.currentText().strip()
        choice = QMessageBox.question(
            self,
            "Apply Saved Profile Grades",
            "About to replace current graded localization with selected saved profile "
            f"grades ({selected_name}). Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        try:
            result = apply_profile_grade_snapshot(
                game_folder,
                self.backups_root,
                snapshot_id,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Could Not Apply Saved Grades", str(error))
            return

        self._apply_snapshot_result(result)
        self.refresh_game_location(update_status=False)

    def _apply_snapshot_result(self, result: GradeSnapshotApplyResult) -> None:
        backup_status = (
            "Created the original-state backup."
            if result.backup_created
            else "Preserved the existing original-state backup."
        )
        self.status.setText(
            f"{backup_status}"
            f"\nApplied saved grades for {result.profile_name} to {result.target_root}."
            f"\nInstalled {result.files_installed} localization files."
        )
        self.last_exported_profile.setText(result.profile_name)
        if self.settings is not None:
            self.settings.setValue(
                LAST_EXPORTED_PROFILE_SETTING,
                result.profile_name,
            )
            self.settings.sync()

    def _refresh_snapshot_selector(self) -> None:
        snapshots = list_profile_grade_snapshots(self.backups_root)
        self.snapshot_selector.blockSignals(True)
        self.snapshot_selector.clear()
        self._snapshot_ids = []
        for snapshot in snapshots:
            timestamp = snapshot.created_at.replace("T", " ")[:16]
            self.snapshot_selector.addItem(
                f"{snapshot.profile_name} ({timestamp})"
            )
            self._snapshot_ids.append(snapshot.snapshot_id)
        self.snapshot_selector.blockSignals(False)
        has_options = bool(self._snapshot_ids)
        self.snapshot_selector.setEnabled(has_options)
        self.apply_snapshot_button.setEnabled(has_options)
        if not has_options:
            self.snapshot_selector.addItem("No saved profile-grade exports yet")
            self.snapshot_selector.setEnabled(False)
            self.apply_snapshot_button.setEnabled(False)

    def refresh_game_location(
        self,
        _game_folder: str = "",
        *,
        update_status: bool = False,
    ) -> None:
        try:
            game_folder = self._configured_game_folder()
            target = grim_dawn_text_root(game_folder)
        except (OSError, ValueError):
            self.target_label.setText(
                "Target: Set a valid Grim Dawn folder on the Settings page."
            )
            self.generate_button.setEnabled(False)
            self.restore_button.setEnabled(False)
            self.default_profile_selector.setEnabled(False)
            self.custom_profile_selector.setEnabled(False)
            self.apply_default_profile_button.setEnabled(False)
            self.apply_custom_profile_button.setEnabled(False)
            self.snapshot_selector.setEnabled(False)
            self.apply_snapshot_button.setEnabled(False)
            if update_status:
                self.status.setText("A valid Grim Dawn folder is required.")
            return
        self.target_label.setText(f"Target: {target}")
        self.generate_button.setEnabled(self.catalog is not None)
        self.restore_button.setEnabled(
            backup_available(game_folder, self.backups_root)
        )
        self._refresh_profile_selectors()
        self._refresh_snapshot_selector()

    def _configured_game_folder(self) -> Path:
        if self.settings is None:
            raise ValueError("Set the Grim Dawn folder on the Settings page first.")
        raw_path = self.settings.value(GAME_FOLDER_SETTING, "", type=str).strip()
        if not raw_path:
            raise ValueError("Set the Grim Dawn folder on the Settings page first.")
        return Path(raw_path)

    def _configured_palette_file(self) -> Path | None:
        if self.settings is None:
            return None
        raw_path = self.settings.value(PALETTE_FILE_SETTING, "", type=str).strip()
        if not raw_path:
            return None
        return Path(raw_path)

    def _last_exported_profile_name(self) -> str:
        if self.settings is None:
            return "None"
        return self.settings.value(
            LAST_EXPORTED_PROFILE_SETTING,
            "None",
            type=str,
        )
