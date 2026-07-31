# BanHelper 2

BanHelper 2 — нативный локальный desktop-инструмент для Minecraft 1.21.4
Fabric. GUI написан на PySide6, данные хранятся в SQLite WAL. В проекте
нет S3, сайта, HTML-GUI, Discord, Academy, pairing и облачной
статистики.

## Что работает

- локальный HTTP protocol v2 с авторизацией и persistent-дедупликацией;
- bounded ingress-очередь, один DB-worker и узкие Qt signals;
- текущая карточка, persistent-очередь, ручной fallback причины;
- строгий трёхстрочный FT/RW-отчёт;
- SQLite-история с поиском, фильтрами, SQL-сортировкой, страницами и CSV-экспортом;
- SQL-статистика, календарная неделя в локальном часовом поясе;
- восемь OBS-подобных dock-панелей, floating, tabify, lock и профили раскладок;
- раздельные FT/RW-причины, избранное и настраиваемые горячие клавиши;
- резервные копии, восстановление и транзакционный идемпотентный импорт v1;
- single instance с активацией первого окна;
- ограниченный GUI-журнал и ротация файловых логов.
- локальные плагины собственного формата `.bhplugin`, верхнее меню установки,
  включения и создания шаблонов для разработчиков.

Документация Plugin API и формата пакета: [`PLUGINS.md`](PLUGINS.md).

## Данные

- Windows: `%APPDATA%\BanHelper`
- Linux: `$XDG_DATA_HOME/BanHelper`
- Linux fallback: `~/.local/share/BanHelper`

Там находятся `banhelper.sqlite3`, `logs/` и `backups/`. Исходники и
исполняемый файл не используются для хранения пользовательских данных.

## Запуск из исходников

Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./start.sh
```

Windows:

```bat
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
start.bat
```

Поддерживаемый Python: 3.11–3.14.

## Тесты, smoke и benchmark

```bash
python -m pip install -r requirements-dev.txt
QT_QPA_PLATFORM=offscreen python -m pytest -q
QT_QPA_PLATFORM=offscreen python -m tools.smoke_app
python -m tools.benchmark_pipeline
python -m tools.benchmark_events --count 100
```

Зафиксированные цифры находятся в `BENCHMARK_RESULTS.json`, результат
проверочного импорта — в `IMPORT_CHECK_RESULTS.json`.

## Fabric-мод

Требуются Minecraft 1.21.4, Fabric Loader, Fabric API и JDK 21.

```bash
cd fabric_mod
./gradlew clean test build
```

JAR: `fabric_mod/build/libs/banhelper-bridge-2.0.0.jar`. Клавиша настроек в игре —
Right Shift. Токен в desktop и моде должен совпадать. Полный формат:
[`FABRIC_PROTOCOL.md`](FABRIC_PROTOCOL.md).

## Сборка desktop

Linux:

```bash
python -m PyInstaller packaging/banhelper.spec --noconfirm --clean
./dist/banhelper --smoke-test
```

Windows — в Windows-окружении:

```bat
python -m PyInstaller packaging\banhelper.spec --noconfirm --clean
dist\banhelper.exe --smoke-test
```

PyInstaller не является кросс-компилятором. Windows-сборку нужно собирать и
проверять на Windows 10/11.
