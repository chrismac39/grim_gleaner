"""Install and restore graded Grim Dawn item localization."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.catalog import AffixCatalog, ItemCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.game_version import detect_game_snapshot
from gd_affix_relevance.grade_export import (
    build_profile_grade_snapshot,
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
from gd_affix_relevance.palette_config import default_palette, load_palette, palette_fingerprint
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
        self.current_profile_path: Path | None = None
        self.last_result: GradeExportResult | None = None
        self._saved_export_entries: list[tuple[str, str]] = []
        self._switch_row_labels: list[QLabel] = []
        self._switch_row_buttons: list[QPushButton] = []

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

        profile_row = QHBoxLayout()
        profile_row.setSpacing(8)
        profile_label = QLabel("Loaded", self)
        profile_label.setObjectName("fieldLabel")
        self._switch_row_labels.append(profile_label)
        profile_row.addWidget(profile_label)
        self.loaded_profile_badge = QLabel(self)
        self.loaded_profile_badge.setObjectName("profileStatusPill")
        profile_row.addWidget(self.loaded_profile_badge)
        profile_row.addStretch()
        layout.addLayout(profile_row)

        saved_heading = self._build_section_heading("Saved Export Switching")
        layout.addWidget(saved_heading)

        switch_row = QHBoxLayout()
        switch_row.setSpacing(8)
        switch_label = QLabel("Switch Saved Exports", self)
        switch_label.setObjectName("fieldLabel")
        self._switch_row_labels.append(switch_label)
        switch_row.addWidget(switch_label)
        self.snapshot_selector = QComboBox(self)
        self.snapshot_selector.setObjectName("profileSwapSelector")
        switch_row.addWidget(self.snapshot_selector, 1)
        self.apply_snapshot_button = QPushButton(
            "Apply Selected Export",
            self,
        )
        self.apply_snapshot_button.setObjectName("profileAction")
        self.apply_snapshot_button.clicked.connect(self.apply_selected_snapshot)
        self._switch_row_buttons.append(self.apply_snapshot_button)
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
        self._align_switch_rows()
        self._refresh_profile_selectors()
        self.refresh_game_location()

    def _align_switch_rows(self) -> None:
        if self._switch_row_labels:
            width = max(label.sizeHint().width() for label in self._switch_row_labels)
            for label in self._switch_row_labels:
                label.setFixedWidth(width)
        if self._switch_row_buttons:
            width = max(button.sizeHint().width() for button in self._switch_row_buttons)
            for button in self._switch_row_buttons:
                button.setFixedWidth(width)

    def _build_section_heading(self, title: str) -> QWidget:
        wrapper = QWidget(self)
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        label = QLabel(title, wrapper)
        label.setObjectName("exportSectionTitle")
        divider = QFrame(wrapper)
        divider.setObjectName("exportSectionDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)
        row.addWidget(label)
        row.addWidget(divider, 1)
        return wrapper

    def set_profiles_root(self, profiles_root: Path) -> None:
        self.profiles_root = Path(profiles_root).expanduser().resolve()
        self.custom_profiles_root = self.profiles_root / "custom"
        self._refresh_profile_selectors()

    def set_profile_path(self, path: Path | None) -> None:
        self.current_profile_path = (
            Path(path).expanduser().resolve() if path is not None else None
        )
        self._update_loaded_profile_pill()

    def refresh_profile_selectors(self) -> None:
        self._refresh_profile_selectors()

    def generate(self, _checked: bool = False) -> None:
        if self.catalog is None:
            return
        self._export_with_profile(self.profile)

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

    def _refresh_profile_selectors(self) -> None:
        self._default_profile_paths = list(self._discover_default_profile_paths())
        self._update_loaded_profile_pill()
        self._refresh_snapshot_selector()

    def refresh_default_exports_for_palette(self) -> None:
        """Refresh cached built-in exports without installing anything."""

        self._refresh_snapshot_selector(force_default_palette_refresh=True)

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
        if index < 0 or index >= len(self._saved_export_entries):
            QMessageBox.warning(
                self,
                "No Saved Exports",
                "Choose a default profile or export at least one custom profile first.",
            )
            return

        entry_kind, entry_value = self._saved_export_entries[index]
        snapshot_id = entry_value
        if not snapshot_id:
            QMessageBox.warning(
                self,
                "Saved Export Unavailable",
                "No default saved export is ready yet. Export once to initialize it.",
            )
            return
        selected_name = self.snapshot_selector.currentText().strip()
        choice = QMessageBox.question(
            self,
            "Apply Saved Export",
            "About to replace current graded localization with selected saved profile "
            f"grades ({selected_name}). Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        try:
            if entry_kind == "custom":
                snapshot = next(
                    (
                        candidate
                        for candidate in list_profile_grade_snapshots(self.backups_root)
                        if candidate.snapshot_id == snapshot_id
                    ),
                    None,
                )
                current_patch = detect_game_snapshot(game_folder).patch_versions
                is_stale = (
                    snapshot is not None
                    and snapshot.patch_versions
                    and snapshot.patch_versions.casefold() != "unknown"
                    and current_patch.casefold() != "unknown"
                    and snapshot.patch_versions != current_patch
                )
                if is_stale and snapshot is not None:
                    if not isinstance(snapshot.profile_payload, dict):
                        raise ValueError(
                            "This saved export predates auto-refresh metadata. "
                            "Re-export this custom profile once, then switch again."
                        )
                    refreshed_profile = BuildProfile.from_dict(snapshot.profile_payload)
                    refreshed = build_profile_grade_snapshot(
                        game_folder,
                        self.bundled_source_root,
                        self.staging_root,
                        self.backups_root,
                        self.catalog,
                        refreshed_profile,
                        items=self.items,
                        palette_file=self._configured_palette_file(),
                        source_kind="custom",
                    )
                    snapshot_id = refreshed.snapshot_id
            result = apply_profile_grade_snapshot(
                game_folder,
                self.backups_root,
                snapshot_id,
            )
        except (OSError, ValueError, TypeError) as error:
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

    def _refresh_snapshot_selector(
        self,
        *,
        force_default_palette_refresh: bool = False,
    ) -> None:
        snapshots = list_profile_grade_snapshots(self.backups_root)
        snapshots = self._ensure_default_saved_exports(
            snapshots,
            force_default_palette_refresh=force_default_palette_refresh,
        )
        self.snapshot_selector.blockSignals(True)
        self.snapshot_selector.clear()
        self._saved_export_entries = []

        snapshots_by_name: dict[tuple[str, str], ProfileGradeSnapshot] = {
            (snapshot.source_kind, snapshot.profile_name): snapshot
            for snapshot in snapshots
        }

        current_patch = "unknown"
        try:
            current_patch = detect_game_snapshot(self._configured_game_folder()).patch_versions
        except (OSError, ValueError):
            current_patch = "unknown"

        for path in self._default_profile_paths:
            label = self._selector_label(path)
            loaded = None
            try:
                loaded = load_profile(path)
            except (OSError, ValueError, TypeError):
                loaded = None
            snapshot = (
                snapshots_by_name.get(("default", loaded.name.strip() or ""))
                if loaded is not None
                else None
            )
            snapshot_id = ""
            patch_text = "patch unknown"
            if snapshot is not None:
                snapshot_id = snapshot.snapshot_id
                patch_text = f"patch {snapshot.patch_versions}"
            self.snapshot_selector.addItem(
                f"default {label} {patch_text}"
            )
            self._saved_export_entries.append(("default", snapshot_id))

        for snapshot in snapshots:
            if snapshot.source_kind != "custom":
                continue
            timestamp = snapshot.created_at.replace("T", " ")[:16]
            stale = (
                snapshot.patch_versions.casefold() != "unknown"
                and current_patch.casefold() != "unknown"
                and snapshot.patch_versions != current_patch
            )
            stale_mark = " ✕" if stale else ""
            self.snapshot_selector.addItem(
                "custom "
                f"{snapshot.profile_name} {timestamp} patch {snapshot.patch_versions}{stale_mark}"
            )
            row_index = self.snapshot_selector.count() - 1
            if stale:
                self.snapshot_selector.setItemData(
                    row_index,
                    QBrush(QColor("#ff8f9a")),
                    Qt.ItemDataRole.ForegroundRole,
                )
            self._saved_export_entries.append(("custom", snapshot.snapshot_id))
        self.snapshot_selector.blockSignals(False)
        has_options = bool(self._saved_export_entries)
        self.snapshot_selector.setEnabled(has_options)
        self.apply_snapshot_button.setEnabled(has_options)
        if not has_options:
            self.snapshot_selector.addItem("No saved exports available")
            self.snapshot_selector.setEnabled(False)
            self.apply_snapshot_button.setEnabled(False)

    def _ensure_default_saved_exports(
        self,
        snapshots: tuple[ProfileGradeSnapshot, ...],
        *,
        force_default_palette_refresh: bool = False,
    ) -> tuple[ProfileGradeSnapshot, ...]:
        if self.catalog is None:
            return snapshots
        try:
            game_folder = self._configured_game_folder()
            current_patch = detect_game_snapshot(game_folder).patch_versions
        except (OSError, ValueError):
            return snapshots

        by_name = {
            (snapshot.source_kind, snapshot.profile_name): snapshot
            for snapshot in snapshots
        }
        current_palette_fingerprint = self._configured_palette_fingerprint()
        changed = False
        for default_path in self._default_profile_paths:
            try:
                profile = load_profile(default_path)
            except (OSError, ValueError, TypeError):
                continue
            profile_name = profile.name.strip() or "Unnamed Profile"
            existing = by_name.get(("default", profile_name))
            stale = (
                existing is None
                or (
                    existing.patch_versions.casefold() != "unknown"
                    and current_patch.casefold() != "unknown"
                    and existing.patch_versions != current_patch
                )
                or (
                    force_default_palette_refresh
                    and existing is not None
                    and existing.palette_fingerprint != current_palette_fingerprint
                )
            )
            if not stale:
                continue
            try:
                refreshed = build_profile_grade_snapshot(
                    game_folder,
                    self.bundled_source_root,
                    self.staging_root,
                    self.backups_root,
                    self.catalog,
                    profile,
                    items=self.items,
                    palette_file=self._configured_palette_file(),
                    source_kind="default",
                )
            except (OSError, ValueError, TypeError):
                continue
            by_name[("default", profile_name)] = refreshed
            changed = True

        if not changed:
            return snapshots
        return list_profile_grade_snapshots(self.backups_root)

    def _configured_palette_fingerprint(self) -> str:
        palette_file = self._configured_palette_file()
        if palette_file is None:
            return palette_fingerprint(default_palette())
        try:
            values = load_palette(palette_file).values
        except (OSError, ValueError):
            values = default_palette()
        return palette_fingerprint(values)

    def _update_loaded_profile_pill(self) -> None:
        if self.current_profile_path is None:
            display = self.profile.name.strip() or "New Build Profile"
            self.loaded_profile_badge.setText(f"Unsaved ({display})")
            self.loaded_profile_badge.setToolTip("")
            return
        self.loaded_profile_badge.setText(self.current_profile_path.name)
        self.loaded_profile_badge.setToolTip(str(self.current_profile_path))

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
