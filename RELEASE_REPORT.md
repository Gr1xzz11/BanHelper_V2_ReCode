# BanHelper 2.0 — release verification

- Python tests: 38 passed (Python 3.14.6, PySide6 6.11.1).
- Manual statistics adjustment: total/week counters can be corrected without changing history.
- Fabric tests: 8 passed; Minecraft/Fabric 1.21.4 JAR built.
- End-to-end: 3 HTTP events, current card, queue, confirmation, statistics, restart and layout restore passed.
- 100-event HTTP benchmark: median 16.617 ms, p95 26.512 ms, maximum 29.224 ms, lost 0, duplicates created 0.
- GUI launch: Linux Wayland and X11/XWayland passed. Windows build config is prepared but was not run on Linux.
- Screenshots: `screenshots/01-standard-layout.png` through `screenshots/10-minimum-size.png`.

Known verification limits: Minecraft itself and Windows were not available in this environment; the mod was compiled and unit-tested, and the Windows PyInstaller script was prepared but not executed.
