"""Application-level settings page."""

from __future__ import annotations

import os
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

class SettingsPage(QWidget):
    """Store application paths that are not part of a build profile."""

    game_folder_changed = Signal(str)

    def __init__(
        self,
        settings: QSettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings

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
            "Optional: path to palette file (key=value)"
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
        form.addRow("Export palette file", palette_row)
        layout.addLayout(form)

        self.game_folder_status = QLabel(self)
        self.game_folder_status.setWordWrap(True)
        layout.addWidget(self.game_folder_status)

        self.palette_file_status = QLabel(self)
        self.palette_file_status.setWordWrap(True)
        layout.addWidget(self.palette_file_status)

        note = QLabel(
            "Export Grades checks this folder's settings/text_en directory for "
            "existing item-tag files. Installed files take precedence and the "
            "bundled clean-install tags fill any missing files. Export writes "
            "the graded files there after preserving an original-state backup.",
            self,
        )
        note.setObjectName("pageHint")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        self._refresh_game_folder_status()
        self._refresh_palette_file_status()

    @staticmethod
    def _sanitize_path(value: str) -> str:
        return sanitize_path(value)

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
        if self.settings is None:
            return
        if value:
            self.settings.setValue(GAME_FOLDER_SETTING, value)
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
        if self.settings is None:
            return
        if value:
            self.settings.setValue(PALETTE_FILE_SETTING, value)
        else:
            self.settings.remove(PALETTE_FILE_SETTING)
        self.settings.sync()

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
                f"Confirmed Grim Dawn installation: {game}"
            )
        self.game_folder_status.style().unpolish(self.game_folder_status)
        self.game_folder_status.style().polish(self.game_folder_status)

    def _refresh_palette_file_status(self) -> None:
        value = self.palette_file_edit.text().strip()
        if not value:
            self.palette_file_status.setObjectName("pageHint")
            self.palette_file_status.setText(
                "Using built-in Python palette defaults for export markers."
            )
        else:
            palette_path = Path(value)
            if palette_path.is_file():
                self.palette_file_status.setObjectName("gameFolderConfirmed")
                self.palette_file_status.setText(
                    f"Palette override file selected: {palette_path}"
                )
            else:
                self.palette_file_status.setObjectName("gameFolderWarning")
                self.palette_file_status.setText(
                    "Not confirmed: palette file path does not exist."
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
