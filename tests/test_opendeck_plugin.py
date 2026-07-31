from __future__ import annotations

import json
import zipfile
from pathlib import Path

from scripts.build_opendeck_plugin import PLUGIN_DIR_NAME, OUTPUT_NAME, build, project_root, validate


def test_manifest_exposes_full_akp153_layout() -> None:
    source = project_root() / "opendeck" / PLUGIN_DIR_NAME
    manifest = validate(source)
    actions = manifest["Actions"]
    assert len(actions) == 15
    assert [action["Name"] for action in actions] == [
        "FT", "RW", "Копировать", "Подтвердить", "Пропустить",
        "5.5", "LIV", "4.3.1", "4.3.2", "1.11",
        "2.12", "4.1", "4.6", "4.7", "4.8",
    ]
    plugin_html = (source / "plugin.html").read_text(encoding="utf-8")
    for action in actions:
        assert action["UUID"] in plugin_html


def test_builder_creates_opendeck_install_archive(tmp_path: Path) -> None:
    output = build(tmp_path)
    assert output.name == OUTPUT_NAME
    assert output.is_file()
    assert (tmp_path / "BanHelper-AKP153-SHA256SUMS.txt").is_file()

    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert names
        assert all(name.startswith(f"{PLUGIN_DIR_NAME}/") for name in names)
        manifest_name = f"{PLUGIN_DIR_NAME}/manifest.json"
        assert manifest_name in names
        assert f"{PLUGIN_DIR_NAME}/plugin.html" in names
        assert f"{PLUGIN_DIR_NAME}/propertyInspector/settings.html" in names
        manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
        assert len(manifest["Actions"]) == 15
