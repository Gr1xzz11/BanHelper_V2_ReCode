from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

PLUGIN_DIR_NAME = "dev.gr1xzz1.banhelper.sdPlugin"
OUTPUT_NAME = "BanHelper-AKP153.OpenDeckPlugin"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def validate(source: Path) -> dict:
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actions = manifest.get("Actions")
    if not isinstance(actions, list) or len(actions) != 15:
        raise ValueError("AKP153 package must expose exactly 15 actions")
    uuids = [str(action.get("UUID", "")) for action in actions]
    if any(not value.startswith("dev.gr1xzz1.banhelper.") for value in uuids):
        raise ValueError("Unexpected action UUID")
    if len(set(uuids)) != len(uuids):
        raise ValueError("Duplicate action UUID")
    required = [manifest.get("CodePath"), manifest.get("Icon")]
    for action in actions:
        required.append(action.get("Icon"))
        required.append(action.get("PropertyInspectorPath"))
        for state in action.get("States", []):
            required.append(state.get("Image"))
    missing = sorted({str(path) for path in required if not path or not (source / str(path)).is_file()})
    if missing:
        raise FileNotFoundError(f"Missing plugin assets: {', '.join(missing)}")
    return manifest


def build(output_dir: Path | None = None) -> Path:
    root = project_root()
    source = root / "opendeck" / PLUGIN_DIR_NAME
    validate(source)
    destination_dir = Path(output_dir) if output_dir is not None else root / "dist" / "opendeck"
    destination_dir.mkdir(parents=True, exist_ok=True)
    output = destination_dir / OUTPUT_NAME
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, Path(PLUGIN_DIR_NAME) / path.relative_to(source))
    temporary.replace(output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (destination_dir / "BanHelper-AKP153-SHA256SUMS.txt").write_text(
        f"{digest}  {output.name}\n",
        encoding="utf-8",
    )
    return output


if __name__ == "__main__":
    print(build())
