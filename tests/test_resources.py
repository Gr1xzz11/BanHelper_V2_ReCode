from banhelper.app.paths import AppPaths
from banhelper.app.resources import application_icon, fabric_jar, resource_path


def test_source_resources_are_available():
    assert application_icon().is_file()
    assert fabric_jar().is_file()
    assert resource_path("assets/banhelper.png").is_file()


def test_linux_xdg_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    paths = AppPaths.discover()
    assert paths.data_dir == tmp_path / "data" / "banhelper"
    assert paths.config_dir == tmp_path / "config" / "banhelper"
    assert paths.cache_dir == tmp_path / "cache" / "banhelper"
