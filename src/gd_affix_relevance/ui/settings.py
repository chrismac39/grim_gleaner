"""Application-level settings page."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.grade_export import validate_grim_dawn_folder

GAME_FOLDER_SETTING = "paths/grim_dawn_folder"
PALETTE_FILE_SETTING = "paths/palette_file"
PROFILES_ROOT_SETTING = "paths/profiles_root"
GAME_FOLDER_ENV = "GRIM_DAWN_INSTALL_PATH"
WINDOWS_DEFAULT_GAME_FOLDER = (
    r"C:\Program Files (x86)\Steam\steamapps\common\Grim Dawn"
)


def sanitize_path(value: str) -> str:
    trimmed = value.strip()
    if (
        len(trimmed) >= 2
        and trimmed[0] == trimmed[-1]
        and trimmed[0] in {'"', "'"}
    ):
        return trimmed[1:-1].strip()
    return trimmed


def normalize_path_text(value: str) -> str:
    sanitized = sanitize_path(value)
    if not sanitized:
        return ""
    return os.path.normpath(sanitized)

class SettingsPage(QWidget):
    """Store application paths that are not part of a build profile."""

    game_folder_changed = Signal(str)
    profiles_root_changed = Signal(str)

    def __init__(
        self,
        settings: QSettings | None = None,
        parent: QWidget | None = None,
        *,
        profiles_root: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.default_profiles_root = (
            Path(profiles_root).expanduser().resolve()
            if profiles_root is not None
            else (Path.cwd() / "artifacts" / "profiles").resolve()
        )
        self.profiles_root = self._saved_profiles_root()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        heading = QLabel("Settings", self)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        hint = QLabel(
            "Application-level paths and preferences. These settings are "
            "stored separately from build profiles.",
            self,
        )
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        self.game_folder_edit = QLineEdit(self._saved_game_folder(), self)

        self.game_folder_edit.setObjectName("outputPath")
        self.game_folder_edit.setPlaceholderText(
            r"Example: C:\Program Files (x86)\Steam\steamapps\common\Grim Dawn"
        )
        self.game_folder_edit.editingFinished.connect(self._save_game_folder)

        path_row = QWidget(self)
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)
        path_layout.addWidget(self.game_folder_edit, 1)
        self.browse_button = QPushButton("Browse...", path_row)
        self.browse_button.setObjectName("profileAction")
        self.browse_button.clicked.connect(self._browse_game_folder)
        path_layout.addWidget(self.browse_button)
        form.addRow("Grim Dawn folder location", path_row)

        self.palette_file_edit = QLineEdit(self._saved_palette_file(), self)
        self.palette_file_edit.setObjectName("outputPath")
        self.palette_file_edit.setPlaceholderText(
            "Optional: active palette file path used by Color Palette page"
        )
        self.palette_file_edit.editingFinished.connect(self._save_palette_file)
        palette_row = QWidget(self)
        palette_layout = QHBoxLayout(palette_row)
        palette_layout.setContentsMargins(0, 0, 0, 0)
        palette_layout.setSpacing(8)
        palette_layout.addWidget(self.palette_file_edit, 1)
        self.browse_palette_button = QPushButton("Browse...", palette_row)
        self.browse_palette_button.setObjectName("profileAction")
        self.browse_palette_button.clicked.connect(self._browse_palette_file)
        palette_layout.addWidget(self.browse_palette_button)
        form.addRow("Palette file override (optional)", palette_row)

        self.default_profiles_path = QLineEdit(self)
        self.default_profiles_path.setObjectName("outputPath")
        self.default_profiles_path.setReadOnly(True)
        defaults_row = QWidget(self)
        defaults_layout = QHBoxLayout(defaults_row)
        defaults_layout.setContentsMargins(0, 0, 0, 0)
        defaults_layout.setSpacing(8)
        defaults_layout.addWidget(self.default_profiles_path, 1)
        self.browse_default_profiles_button = QPushButton("Browse...", defaults_row)
        self.browse_default_profiles_button.setObjectName("profileAction")
        self.browse_default_profiles_button.clicked.connect(
            self._browse_default_profiles_folder
        )
        defaults_layout.addWidget(self.browse_default_profiles_button)
        form.addRow("Default profiles folder", defaults_row)

        self.custom_profiles_path = QLineEdit(self)
        self.custom_profiles_path.setObjectName("outputPath")
        self.custom_profiles_path.setReadOnly(True)
        custom_row = QWidget(self)
        custom_layout = QHBoxLayout(custom_row)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(8)
        custom_layout.addWidget(self.custom_profiles_path, 1)
        self.browse_custom_profiles_button = QPushButton("Browse...", custom_row)
        self.browse_custom_profiles_button.setObjectName("profileAction")
        self.browse_custom_profiles_button.clicked.connect(
            self._browse_custom_profiles_folder
        )
        custom_layout.addWidget(self.browse_custom_profiles_button)
        form.addRow("Custom profiles folder", custom_row)
        layout.addLayout(form)

        self.game_folder_status = QLabel(self)
        self.game_folder_status.setWordWrap(True)
        layout.addWidget(self.game_folder_status)

        self.palette_file_status = QLabel(self)
        self.palette_file_status.setWordWrap(True)
        layout.addWidget(self.palette_file_status)

        note = QLabel(
            "Export Grades uses this folder's settings/text_en as the working "
            "source, applies the active profile's current grades to item tags, "
            "and writes the result back to settings/text_en (replacing prior "
            "graded output). On first export, Grim Gleaner creates an "
            "original-state backup so Restore Backups can revert cleanly.",
            self,
        )
        note.setObjectName("pageHint")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        self._refresh_profile_folder_paths()
        self._refresh_game_folder_status()
        self._refresh_palette_file_status()

    @staticmethod
    def _sanitize_path(value: str) -> str:
        return normalize_path_text(value)

    @staticmethod
    def _format_path(path: Path) -> str:
        return os.path.normpath(str(path))

    def _saved_game_folder(self) -> str:
        stored = ""
        if self.settings is not None:
            stored = self._sanitize_path(
                self.settings.value(GAME_FOLDER_SETTING, "", type=str)
            )
        if stored:
            self._persist_game_folder(stored)
            return stored

        env_path = self._sanitize_path(os.environ.get(GAME_FOLDER_ENV, ""))
        if env_path and Path(env_path).exists():
            self._persist_game_folder(env_path)
            return env_path

        if Path(WINDOWS_DEFAULT_GAME_FOLDER).exists():
            self._persist_game_folder(WINDOWS_DEFAULT_GAME_FOLDER)
            return WINDOWS_DEFAULT_GAME_FOLDER

        return ""

    def _persist_game_folder(self, value: str) -> None:
        normalized = self._sanitize_path(value)
        if self.settings is None:
            return
        if normalized:
            self.settings.setValue(GAME_FOLDER_SETTING, normalized)
        else:
            self.settings.remove(GAME_FOLDER_SETTING)
        self.settings.sync()

    def _saved_palette_file(self) -> str:
        if self.settings is None:
            return ""
        stored = self._sanitize_path(
            self.settings.value(PALETTE_FILE_SETTING, "", type=str)
        )
        self._persist_palette_file(stored)
        return stored

    def _persist_palette_file(self, value: str) -> None:
        normalized = self._sanitize_path(value)
        if self.settings is None:
            return
        if normalized:
            self.settings.setValue(PALETTE_FILE_SETTING, normalized)
        else:
            self.settings.remove(PALETTE_FILE_SETTING)
        self.settings.sync()

    def _saved_profiles_root(self) -> Path:
        raw = ""
        if self.settings is not None:
            raw = self._sanitize_path(
                self.settings.value(PROFILES_ROOT_SETTING, "", type=str)
            )
        if raw:
            root = Path(raw).expanduser().resolve()
            self._persist_profiles_root(root)
            return root
        self._persist_profiles_root(self.default_profiles_root)
        return self.default_profiles_root

    def _persist_profiles_root(self, root: Path) -> None:
        normalized = Path(root).expanduser().resolve()
        normalized.mkdir(parents=True, exist_ok=True)
        if self.settings is not None:
            self.settings.setValue(
                PROFILES_ROOT_SETTING,
                self._format_path(normalized),
            )
            self.settings.sync()
        self.profiles_root = normalized

    def _refresh_profile_folder_paths(self) -> None:
        defaults = (self.profiles_root / "examples").resolve()
        custom = (self.profiles_root / "custom").resolve()
        defaults_text = self._format_path(defaults)
        custom_text = self._format_path(custom)
        self.default_profiles_path.setText(defaults_text)
        self.default_profiles_path.setToolTip(defaults_text)
        self.custom_profiles_path.setText(custom_text)
        self.custom_profiles_path.setToolTip(custom_text)

    def _browse_default_profiles_folder(self) -> None:
        self._choose_profiles_root(self.profiles_root / "examples")

    def _browse_custom_profiles_folder(self) -> None:
        self._choose_profiles_root(self.profiles_root / "custom")

    def _choose_profiles_root(self, starting: Path) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Profile Folder Location",
            str(starting),
        )
        if not selected:
            return
        selected_path = Path(selected).expanduser().resolve()
        if selected_path.name.casefold() in {"examples", "custom"}:
            new_root = selected_path.parent
        else:
            new_root = selected_path
        if new_root == self.profiles_root:
            return
        choice = QMessageBox.question(
            self,
            "Move Profile Folders",
            "Changing profile folders will move (cut/paste) both default and "
            "custom profile files to the selected location.\n\n"
            f"New root: {self._format_path(new_root)}\n\n"
            "Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            self._migrate_profiles_root(new_root)
        except OSError as error:
            QMessageBox.critical(
                self,
                "Could Not Move Profile Folders",
                str(error),
            )

    def _migrate_profiles_root(self, new_root: Path) -> None:
        source_root = self.profiles_root
        target_root = Path(new_root).expanduser().resolve()
        target_root.mkdir(parents=True, exist_ok=True)

        source_defaults = source_root / "examples"
        source_custom = source_root / "custom"
        target_defaults = target_root / "examples"
        target_custom = target_root / "custom"
        target_defaults.mkdir(parents=True, exist_ok=True)
        target_custom.mkdir(parents=True, exist_ok=True)

        if source_defaults.is_dir():
            shutil.copytree(source_defaults, target_defaults, dirs_exist_ok=True)
        if source_custom.is_dir():
            shutil.copytree(source_custom, target_custom, dirs_exist_ok=True)

        for path in sorted(source_root.glob("*.json")):
            destination = target_custom / path.name
            if destination.exists():
                stem = destination.stem
                suffix = destination.suffix
                candidate = destination
                counter = 2
                while candidate.exists():
                    candidate = destination.with_name(f"{stem}-{counter}{suffix}")
                    counter += 1
                destination = candidate
            shutil.move(str(path), str(destination))

        if source_root != target_root:
            shutil.rmtree(source_defaults, ignore_errors=True)
            shutil.rmtree(source_custom, ignore_errors=True)

        self._persist_profiles_root(target_root)
        self._refresh_profile_folder_paths()
        self.profiles_root_changed.emit(str(target_root))

    def _save_game_folder(self) -> None:
        value = self._sanitize_path(self.game_folder_edit.text())
        self.game_folder_edit.setText(value)
        self._persist_game_folder(value)
        self._refresh_game_folder_status()
        self.game_folder_changed.emit(value)

    def prompt_for_game_folder(self) -> bool:
        """Ask for an install root and return whether it was confirmed."""

        starting_path = self.game_folder_edit.text().strip() or str(Path.cwd())
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Grim Dawn Folder (contains Grim Dawn.exe)",
            starting_path,
        )
        if not selected:
            return False
        self.game_folder_edit.setText(selected)
        self._save_game_folder()
        if not self.has_valid_game_folder():
            QMessageBox.warning(
                self,
                "Grim Dawn Not Found",
                "That folder does not contain Grim Dawn.exe. Select the Grim "
                "Dawn installation folder itself.",
            )
            return False
        return True

    def _browse_game_folder(self) -> None:
        self.prompt_for_game_folder()

    def _save_palette_file(self) -> None:
        value = self._sanitize_path(self.palette_file_edit.text())
        self.palette_file_edit.setText(value)
        self._persist_palette_file(value)
        self._refresh_palette_file_status()

    def _browse_palette_file(self) -> None:
        starting = self.palette_file_edit.text().strip()
        directory = str(Path(starting).parent) if starting else str(Path.cwd())
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select Palette File",
            directory,
            "Text files (*.txt);;All files (*.*)",
        )
        if not selected:
            return
        self.palette_file_edit.setText(selected)
        self._save_palette_file()

    def has_valid_game_folder(self) -> bool:
        game, _ = self._game_folder_validation()
        return game is not None

    def _refresh_game_folder_status(self) -> None:
        game, error = self._game_folder_validation()
        if game is None:
            self.game_folder_status.setObjectName("gameFolderWarning")
            self.game_folder_status.setText(error)
        else:
            self.game_folder_status.setObjectName("gameFolderConfirmed")
            self.game_folder_status.setText(
                "Confirmed Grim Dawn installation: "
                f"{self._format_path(game)}"
            )
        self.game_folder_status.style().unpolish(self.game_folder_status)
        self.game_folder_status.style().polish(self.game_folder_status)

    def _refresh_palette_file_status(self) -> None:
        value = self.palette_file_edit.text().strip()
        if not value:
            self.palette_file_status.setObjectName("pageHint")
            self.palette_file_status.setText(
                "No palette file override path is set. Color Palette will use its default active path."
            )
        else:
            palette_path = Path(value)
            if palette_path.is_file():
                self.palette_file_status.setObjectName("gameFolderConfirmed")
                self.palette_file_status.setText(
                    "Active palette file (same path shown on Color Palette page): "
                    f"{self._format_path(palette_path)}"
                )
            else:
                self.palette_file_status.setObjectName("gameFolderWarning")
                self.palette_file_status.setText(
                    "Not confirmed: configured active palette path does not exist."
                )
        self.palette_file_status.style().unpolish(self.palette_file_status)
        self.palette_file_status.style().polish(self.palette_file_status)

    def _game_folder_validation(self) -> tuple[Path | None, str]:
        value = self.game_folder_edit.text().strip()
        if not value:
            return (
                None,
                "Not configured. Select the folder containing Grim Dawn.exe.",
            )
        try:
            return validate_grim_dawn_folder(Path(value)), ""
        except (OSError, ValueError) as error:
            return None, f"Not confirmed: {error}"
