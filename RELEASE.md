# BanHelper 2 — platform release

## Artifacts

### Linux

- `dist/linux/BanHelper.grxt`
- Format: native x86-64 ELF onefile executable (PyInstaller), not a renamed archive.
- Size: 87,764,904 bytes.
- SHA-256: `66244700f2d85efe33be58bbba2e52f80a4556d16f070b6fee6f6b73c55149a9`

Run:

```bash
chmod +x dist/linux/BanHelper.grxt
./dist/linux/BanHelper.grxt
```

The bundle contains Python, PySide6, the ICO/PNG/SVG application icons and
`banhelper-bridge-2.0.0.jar`. It does not contain or copy a virtual environment.

### Windows

- `dist/windows/BanHelper.exe`
- Format: Windows x86-64 GUI onefile executable (PyInstaller, no console).
- Size: 51,045,169 bytes.
- SHA-256: `6a50b3e2928f604af7c3d0728f27608424af2cac2f06d427c71cfafc00e6394f`

The EXE was built and smoke-tested on GitHub `windows-latest` with Python
3.13.14. The test moved the executable, launched it without system Python,
waited for clean exit and verified that SQLite was created in isolated AppData:
https://github.com/Gr1xzz11/BanHelper_V2_ReCode/actions/runs/30505683477

### Fabric mod

- `release/banhelper-bridge-2.0.0.jar`
- Size: 41,468 bytes.
- SHA-256: `45f086824a305a9bc57c34e38ace103c55e95e404798b514221e3127f52ddd1c`

The existing JAR was used without rebuilding. It is embedded as a distribution
resource in both platform specs. BanHelper does not execute the JAR: Minecraft
Fabric loads it inside Minecraft. Therefore the desktop executable does not
need Java. Minecraft 1.21.4 itself requires Java 21, normally supplied by the
Minecraft launcher; Java is not bundled with BanHelper.

## Reproducible builds

Linux:

```bash
./scripts/build_linux.sh
```

Windows PowerShell:

```powershell
.\scripts\build_windows.ps1 -PythonCommand python
```

Build dependencies are pinned in `requirements-build.txt`:

- Python used for the verified Linux build: 3.14.6
- PyInstaller: 6.21.0
- PySide6: 6.11.1
- pyinstaller-hooks-contrib: 2026.6

Each script creates and removes only its own `.build/<platform>` workspace and
`dist/<platform>` output. Paths containing spaces and Cyrillic characters are
quoted throughout.

## Runtime storage

Fresh Linux installations:

- config: `$XDG_CONFIG_HOME/banhelper` or `~/.config/banhelper`
- data: `$XDG_DATA_HOME/banhelper` or `~/.local/share/banhelper`
- cache: `$XDG_CACHE_HOME/banhelper` or `~/.cache/banhelper`

An existing legacy `~/.local/share/BanHelper/banhelper.sqlite3` remains in use
when present, preserving the user's history and counters without deleting or
moving data.

Windows stores settings and data in `%APPDATA%\BanHelper` and cache files in
`%LOCALAPPDATA%\BanHelper\cache`.

## Verification performed

- Python test suite: 40 passed.
- End-to-end listener/GUI test: three `/ban` requests accepted; current card,
  queue, confirmation, statistics, clean shutdown, restart and layout restore
  passed.
- Import and GUI startup: passed.
- Linux onefile startup: passed with no system Python in its environment.
- Frozen resource lookup: ICO, PNG, SVG and Fabric JAR found inside the archive.
- Moved-artifact test: passed from `.build/linux/moved artifact/`.
- Path test: passed with spaces and Cyrillic characters.
- XDG write test: SQLite created under the isolated XDG data directory; no
  database was written beside the executable or into PyInstaller extraction.
- Real GUI startup: passed on Wayland and X11/XWayland.
- Windows onefile build, moved-artifact startup, embedded icon/resources and
  AppData write test: passed on GitHub `windows-latest`.
- JAR SHA-256 matches the pre-existing release JAR.
- Existing Fabric test reports contain 8 passing tests. They were not rerun
  after the final packaging-only changes because the post-restart host only has
  Java 8, while Minecraft 1.21.4/Fabric requires Java 21. Java sources and the
  prebuilt JAR were not changed by the packaging work.

## Known limitations

- Windows was smoke-tested on a clean hosted Windows runner, but not manually
  exercised on physical Windows 10 and Windows 11 machines.
- The Linux onefile was built on CachyOS with glibc 2.44. For maximum
  compatibility with older distributions, run the same script on an older
  manylinux-compatible build host.
- PyInstaller reports the optional Qt TIFF image plugin dependency
  `libtiff.so.5` as unavailable. BanHelper uses SVG/PNG/ICO resources and does
  not load TIFF files; tested application resources work.
