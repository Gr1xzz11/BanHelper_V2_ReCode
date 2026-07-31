# Плагины BanHelper

BanHelper использует собственный формат `.bhplugin`. Технически это ZIP-архив
размером до 10 МБ. В его корне обязательно находятся `plugin.json` и Python
entrypoint.

## Быстрый старт

Откройте в BanHelper **Плагины → Создать шаблон плагина**. Приложение создаст:

- `plugin.json` — манифест;
- `main.py` — код плагина;
- `build.py` — сборщик `.bhplugin`;
- `README.md` — краткую памятку.

После изменения кода выполните в папке плагина:

```bash
python build.py
```

Готовый файл устанавливается через **Плагины → Установить .bhplugin…**.
Установленный плагин по умолчанию выключен.

## Манифест

```json
{
  "id": "hello-plugin",
  "name": "Hello Plugin",
  "version": "0.1.0",
  "author": "Developer",
  "description": "Пример плагина",
  "api_version": 1,
  "entrypoint": "main.py"
}
```

`id` содержит 3–64 символа: строчные латинские буквы, цифры, `_` и `-`.
Текущая версия Plugin API — `1`.

## Entrypoint и API v1

```python
def activate(api):
    api.log("Плагин включён")
    api.add_menu_action(
        "Показать сообщение",
        lambda: api.show_status("Hello from plugin"),
    )


def deactivate(api):
    api.log("Плагин выключен")
```

Доступные поля и методы:

- `api.plugin_id`, `api.plugin_name`;
- `api.data_dir` — отдельная постоянная папка данных плагина;
- `api.add_menu_action(title, callback)` — команда в
  **Плагины → Команды плагинов → Название плагина**;
- `api.show_status(message, timeout_ms=3000)` — сообщение в status bar;
- `api.command(name, payload=None)` — отправка команды BanService;
- `api.log(message, level=logging.INFO)` — запись в журнал.

Плагин выполняется в процессе BanHelper. Это не sandbox: вредоносный Python-код
получит права текущего пользователя. Устанавливайте только доверенные файлы.

## Ограничения пакета

- не более 128 файлов;
- не более 25 МБ после распаковки;
- запрещены абсолютные пути, `..` и символические ссылки;
- entrypoint обязан быть `.py`-файлом внутри пакета;
- несовместимая версия API блокирует загрузку.
