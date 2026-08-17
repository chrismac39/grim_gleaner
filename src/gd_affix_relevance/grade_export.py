"""Install generated grade tags into Grim Dawn with recoverable backups."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from gd_affix_relevance.catalog import AffixCatalog, ItemCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.game_version import detect_game_snapshot
from gd_affix_relevance.output import (
    RainbowGenerationResult,
    generate_rainbow_output,
    marker_palette_from_values,
)
from gd_affix_relevance.palette_config import (
    load_palette,
    palette_fingerprint,
)
from gd_affix_relevance.runtime_paths import resolve_export_sources

BACKUP_SCHEMA_VERSION = 1
BACKUP_MANIFEST = "backup-manifest.json"
BACKUP_CONTENTS = "text_en"
GRIM_DAWN_EXECUTABLE = "Grim Dawn.exe"
PROFILE_SNAPSHOT_SCHEMA_VERSION = 3
SUPPORTED_PROFILE_SNAPSHOT_SCHEMA_VERSIONS = frozenset({1, 2, 3})
PROFILE_SNAPSHOT_ROOT = "profile-grade-snapshots"
PROFILE_SNAPSHOT_METADATA = "snapshot.json"


@dataclass(frozen=True, slots=True)
class GradeExportResult:
    target_root: Path
    backup_root: Path
    backup_created: bool
    generation: RainbowGenerationResult


@dataclass(frozen=True, slots=True)
class GradeRestoreResult:
    target_root: Path
    original_existed: bool
    restored_files: int


@dataclass(frozen=True, slots=True)
class ProfileGradeSnapshot:
    snapshot_id: str
    profile_name: str
    created_at: str
    file_count: int
    patch_versions: str = "unknown"
    source_kind: str = "custom"
    palette_fingerprint: str = ""
    profile_payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class GradeSnapshotApplyResult:
    target_root: Path
    profile_name: str
    snapshot_id: str
    files_installed: int
    backup_created: bool


def validate_grim_dawn_folder(game_folder: Path) -> Path:
    """Return a confirmed Grim Dawn install root.

    A directory alone is not sufficient: users commonly select the Steam
    library or ``steamapps/common`` parent instead of the actual game folder.
    The executable is the stable, inexpensive confirmation available at
    runtime.
    """

    game = Path(game_folder).expanduser().resolve()
    if not game.is_dir():
        raise ValueError(f"Grim Dawn folder does not exist: {game}")
    executable = game / GRIM_DAWN_EXECUTABLE
    if not executable.is_file():
        raise ValueError(
            f"Selected folder does not contain {GRIM_DAWN_EXECUTABLE}: {game}"
        )
    return game


def grim_dawn_text_root(game_folder: Path) -> Path:
    game = validate_grim_dawn_folder(game_folder)
    return game / "settings" / "text_en"


def export_grades_to_game(
    game_folder: Path,
    bundled_tags_root: Path,
    staging_root: Path,
    backups_root: Path,
    catalog: AffixCatalog,
    profile: BuildProfile,
    *,
    items: ItemCatalog | None = None,
    palette_file: Path | None = None,
) -> GradeExportResult:
    """Generate, back up the original once, and install graded localization."""

    target = grim_dawn_text_root(game_folder)
    selection = resolve_export_sources(game_folder, bundled_tags_root)
    stage = Path(staging_root).expanduser().resolve()
    if target.resolve() == stage or target.resolve().is_relative_to(stage):
        raise ValueError("staging and Grim Dawn text_en paths must not overlap")

    stage.parent.mkdir(parents=True, exist_ok=True)
    loaded_palette = load_palette(palette_file)
    palette_values = loaded_palette.overrides if palette_file is not None else None
    current_palette_fingerprint = palette_fingerprint(loaded_palette.values)
    temporary = Path(tempfile.mkdtemp(prefix=".grade-export-", dir=stage.parent))
    try:
        generated = temporary / "text_en"
        generation = generate_rainbow_output(
            selection.primary_root,
            generated,
            catalog,
            profile,
            items=items,
            fallback_source_root=selection.fallback_root,
            marker_palette=marker_palette_from_values(palette_values),
        )
        _replace_directory(stage, generated)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    backup, backup_created = _ensure_original_backup(target, backups_root)
    current_snapshot = detect_game_snapshot(Path(game_folder))
    store_profile_grade_snapshot(
        backups_root,
        profile,
        stage,
        patch_versions=current_snapshot.patch_versions,
        source_kind="custom",
        palette_fingerprint=current_palette_fingerprint,
    )
    _install_directory(stage, target)
    return GradeExportResult(
        target_root=target,
        backup_root=backup,
        backup_created=backup_created,
        generation=replace(generation, output_root=stage),
    )


def build_profile_grade_snapshot(
    game_folder: Path,
    bundled_tags_root: Path,
    staging_root: Path,
    backups_root: Path,
    catalog: AffixCatalog,
    profile: BuildProfile,
    *,
    items: ItemCatalog | None = None,
    palette_file: Path | None = None,
    source_kind: str = "custom",
) -> ProfileGradeSnapshot:
    """Generate a profile-grade snapshot without installing to game files."""

    selection = resolve_export_sources(game_folder, bundled_tags_root)
    stage = Path(staging_root).expanduser().resolve()
    stage.parent.mkdir(parents=True, exist_ok=True)
    loaded_palette = load_palette(palette_file)
    palette_values = loaded_palette.overrides if palette_file is not None else None
    current_palette_fingerprint = palette_fingerprint(loaded_palette.values)
    temporary = Path(tempfile.mkdtemp(prefix=".grade-snapshot-", dir=stage.parent))
    try:
        generated = temporary / "text_en"
        generate_rainbow_output(
            selection.primary_root,
            generated,
            catalog,
            profile,
            items=items,
            fallback_source_root=selection.fallback_root,
            marker_palette=marker_palette_from_values(palette_values),
        )
        current_snapshot = detect_game_snapshot(Path(game_folder))
        return store_profile_grade_snapshot(
            backups_root,
            profile,
            generated,
            patch_versions=current_snapshot.patch_versions,
            source_kind=source_kind,
            palette_fingerprint=current_palette_fingerprint,
        )
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def store_profile_grade_snapshot(
    backups_root: Path,
    profile: BuildProfile,
    source_text_root: Path,
    *,
    patch_versions: str = "unknown",
    source_kind: str = "custom",
    palette_fingerprint: str = "",
) -> ProfileGradeSnapshot:
    """Persist one re-applicable export snapshot keyed by profile content."""

    source = Path(source_text_root).expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"profile snapshot source is not a directory: {source}")

    snapshot_id = _profile_snapshot_id(profile)
    profile_name = profile.name.strip() or "Unnamed Profile"
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    file_count = sum(1 for path in source.rglob("*") if path.is_file())

    root = _profile_snapshot_root(backups_root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / snapshot_id

    temporary = Path(tempfile.mkdtemp(prefix=".profile-snapshot-", dir=root))
    try:
        staged = temporary / "snapshot"
        staged.mkdir(parents=True)
        shutil.copytree(source, staged / BACKUP_CONTENTS)
        (staged / PROFILE_SNAPSHOT_METADATA).write_text(
            json.dumps(
                {
                    "schema_version": PROFILE_SNAPSHOT_SCHEMA_VERSION,
                    "snapshot_id": snapshot_id,
                    "profile_name": profile_name,
                    "created_at": created_at,
                    "file_count": file_count,
                    "patch_versions": patch_versions,
                    "source_kind": source_kind,
                    "palette_fingerprint": palette_fingerprint,
                    "profile_payload": profile.to_dict(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        _replace_directory(target, staged)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    return ProfileGradeSnapshot(
        snapshot_id=snapshot_id,
        profile_name=profile_name,
        created_at=created_at,
        file_count=file_count,
        patch_versions=patch_versions,
        source_kind=source_kind,
        palette_fingerprint=palette_fingerprint,
        profile_payload=profile.to_dict(),
    )


def list_profile_grade_snapshots(
    backups_root: Path,
) -> tuple[ProfileGradeSnapshot, ...]:
    """Return saved profile-grade snapshots sorted newest first."""

    root = _profile_snapshot_root(backups_root)
    if not root.is_dir():
        return ()

    snapshots: list[ProfileGradeSnapshot] = []
    for entry in sorted(path for path in root.iterdir() if path.is_dir()):
        metadata = entry / PROFILE_SNAPSHOT_METADATA
        source = entry / BACKUP_CONTENTS
        if not metadata.is_file() or not source.is_dir():
            continue
        try:
            payload = json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("schema_version") not in SUPPORTED_PROFILE_SNAPSHOT_SCHEMA_VERSIONS:
            continue
        snapshot_id = str(payload.get("snapshot_id", "")).strip()
        profile_name = str(payload.get("profile_name", "")).strip()
        created_at = str(payload.get("created_at", "")).strip()
        file_count = payload.get("file_count", 0)
        patch_versions = str(payload.get("patch_versions", "unknown")).strip() or "unknown"
        source_kind = str(payload.get("source_kind", "custom")).strip() or "custom"
        snapshot_palette_fingerprint = str(
            payload.get("palette_fingerprint", "")
        ).strip()
        profile_payload = payload.get("profile_payload")
        if not isinstance(profile_payload, dict):
            profile_payload = None
        if not snapshot_id or not profile_name:
            continue
        if isinstance(file_count, bool) or not isinstance(file_count, int):
            file_count = 0
        snapshots.append(
            ProfileGradeSnapshot(
                snapshot_id=snapshot_id,
                profile_name=profile_name,
                created_at=created_at,
                file_count=file_count,
                patch_versions=patch_versions,
                source_kind=source_kind,
                palette_fingerprint=snapshot_palette_fingerprint,
                profile_payload=profile_payload,
            )
        )

    snapshots.sort(key=lambda snapshot: snapshot.created_at, reverse=True)
    return tuple(snapshots)


def apply_profile_grade_snapshot(
    game_folder: Path,
    backups_root: Path,
    snapshot_id: str,
) -> GradeSnapshotApplyResult:
    """Install one saved profile-grade snapshot into settings/text_en."""

    target = grim_dawn_text_root(game_folder)
    normalized_id = snapshot_id.strip()
    if not normalized_id:
        raise ValueError("profile grade snapshot ID must not be blank")

    snapshot_dir = _profile_snapshot_root(backups_root) / normalized_id
    metadata, source = _load_profile_snapshot(snapshot_dir)
    _, backup_created = _ensure_original_backup(target, backups_root)
    _install_directory(source, target)

    files_installed = sum(1 for path in source.rglob("*") if path.is_file())
    return GradeSnapshotApplyResult(
        target_root=target,
        profile_name=metadata.profile_name,
        snapshot_id=metadata.snapshot_id,
        files_installed=files_installed,
        backup_created=backup_created,
    )


def restore_game_backup(
    game_folder: Path,
    backups_root: Path,
) -> GradeRestoreResult:
    """Restore and consume the original snapshot for the configured game."""

    target = grim_dawn_text_root(game_folder)
    backup = backup_path_for(target, backups_root)
    manifest = _load_backup_manifest(backup, target)
    original_existed = bool(manifest["original_existed"])
    contents = backup / BACKUP_CONTENTS
    restored_files = 0
    if original_existed:
        if not contents.is_dir():
            raise ValueError(f"backup contents are missing: {contents}")
        restored_files = sum(1 for path in contents.rglob("*") if path.is_file())
        _install_directory(contents, target)
    else:
        _remove_directory_recoverably(target)
    shutil.rmtree(backup)
    return GradeRestoreResult(target, original_existed, restored_files)


def backup_path_for(target_root: Path, backups_root: Path) -> Path:
    target = Path(target_root).expanduser().resolve()
    identity = hashlib.sha256(str(target).casefold().encode("utf-8")).hexdigest()[:12]
    return Path(backups_root).expanduser().resolve() / f"{identity}-text_en"


def backup_available(game_folder: Path, backups_root: Path) -> bool:
    try:
        target = grim_dawn_text_root(game_folder)
    except ValueError:
        return False
    return (backup_path_for(target, backups_root) / BACKUP_MANIFEST).is_file()


def _ensure_original_backup(target: Path, backups_root: Path) -> tuple[Path, bool]:
    backup = backup_path_for(target, backups_root)
    if backup.exists():
        _load_backup_manifest(backup, target)
        return backup, False

    backup.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".backup-", dir=backup.parent))
    try:
        original_existed = target.is_dir()
        if original_existed:
            shutil.copytree(target, temporary / BACKUP_CONTENTS)
        (temporary / BACKUP_MANIFEST).write_text(
            json.dumps(
                {
                    "schema_version": BACKUP_SCHEMA_VERSION,
                    "target_root": str(target.resolve()),
                    "original_existed": original_existed,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(backup)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return backup, True


def _load_backup_manifest(backup: Path, target: Path) -> dict[str, object]:
    manifest_path = backup / BACKUP_MANIFEST
    if not manifest_path.is_file():
        raise ValueError(f"no original-state backup exists for {target}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read backup manifest: {error}") from error
    if payload.get("schema_version") != BACKUP_SCHEMA_VERSION:
        raise ValueError("unsupported backup manifest version")
    if Path(str(payload.get("target_root", ""))).resolve() != target.resolve():
        raise ValueError("backup does not belong to the configured Grim Dawn folder")
    return payload


def _install_directory(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".grim-gleaner-install-", dir=target.parent))
    try:
        incoming = temporary / "text_en"
        shutil.copytree(source, incoming)
        _replace_directory(target, incoming)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def _replace_directory(target: Path, incoming: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = target.parent / f".{target.name}-grim-gleaner-previous"
    if previous.exists():
        raise ValueError(f"unfinished prior replacement exists: {previous}")
    moved_previous = False
    try:
        if target.exists():
            target.replace(previous)
            moved_previous = True
        incoming.replace(target)
    except Exception:
        if moved_previous and not target.exists():
            previous.replace(target)
        raise
    else:
        if moved_previous:
            shutil.rmtree(previous)


def _remove_directory_recoverably(target: Path) -> None:
    if not target.exists():
        return
    temporary = target.parent / f".{target.name}-grim-gleaner-restore"
    if temporary.exists():
        raise ValueError(f"unfinished prior restore exists: {temporary}")
    target.replace(temporary)
    shutil.rmtree(temporary)


def _profile_snapshot_root(backups_root: Path) -> Path:
    return Path(backups_root).expanduser().resolve() / PROFILE_SNAPSHOT_ROOT


def _profile_snapshot_id(profile: BuildProfile) -> str:
    canonical = json.dumps(
        profile.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _load_profile_snapshot(snapshot_dir: Path) -> tuple[ProfileGradeSnapshot, Path]:
    if not snapshot_dir.is_dir():
        raise ValueError(f"profile grade snapshot not found: {snapshot_dir}")

    metadata_path = snapshot_dir / PROFILE_SNAPSHOT_METADATA
    source = snapshot_dir / BACKUP_CONTENTS
    if not metadata_path.is_file() or not source.is_dir():
        raise ValueError(f"profile grade snapshot is incomplete: {snapshot_dir}")

    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read profile snapshot metadata: {error}") from error
    if payload.get("schema_version") not in SUPPORTED_PROFILE_SNAPSHOT_SCHEMA_VERSIONS:
        raise ValueError("unsupported profile snapshot version")

    snapshot_id = str(payload.get("snapshot_id", "")).strip()
    profile_name = str(payload.get("profile_name", "")).strip()
    created_at = str(payload.get("created_at", "")).strip()
    file_count = payload.get("file_count", 0)
    patch_versions = str(payload.get("patch_versions", "unknown")).strip() or "unknown"
    source_kind = str(payload.get("source_kind", "custom")).strip() or "custom"
    profile_payload = payload.get("profile_payload")
    if not isinstance(profile_payload, dict):
        profile_payload = None
    if not snapshot_id or not profile_name:
        raise ValueError("profile snapshot metadata is missing required fields")
    if isinstance(file_count, bool) or not isinstance(file_count, int):
        file_count = 0

    return (
        ProfileGradeSnapshot(
            snapshot_id=snapshot_id,
            profile_name=profile_name,
            created_at=created_at,
            file_count=file_count,
            patch_versions=patch_versions,
            source_kind=source_kind,
            profile_payload=profile_payload,
        ),
        source,
    )
