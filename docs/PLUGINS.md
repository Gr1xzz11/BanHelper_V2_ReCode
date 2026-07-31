# BanHelper Plugin API v1

BanHelper 2.2.1 показывает управление расширениями в верхнем меню **Плагины** и отдельную вкладку **Настройки → Плагины**.

Доступно:

- установка и обновление `.bhplugin`;
- включение и выключение без ручного редактирования файлов;
- удаление сторонних плагинов;
- перезагрузка;
- открытие папки плагинов;
- создание готового шаблона с `manifest.json`, `plugin.py` и `build.py`;
- команды активных плагинов прямо в интерфейсе;
- выбор установленного плагина и редактирование объявленных им настроек.

При первом запуске устанавливается и включается встроенный **BanHelper Core Tools**. Он проверяет Plugin API и переключает режимы FT/RW.

## Каталоги

- Linux: `$XDG_DATA_HOME/banhelper/plugins` или `~/.local/share/banhelper/plugins`
- Windows: `%APPDATA%\BanHelper\plugins`

Состояние включения хранится отдельно в конфигурационном каталоге `plugins.json`. Данные каждого плагина находятся в `plugins/data/<plugin-id>`.

## Bundle layout

`.bhplugin` является ZIP-архивом:

```text
my-plugin.bhplugin
├── manifest.json
└── plugin.py
```

`manifest.json`:

```json
{
  "id": "dev.example.echo",
  "name": "Echo example",
  "version": "1.0.0",
  "api_version": 1,
  "entrypoint": "plugin.py:Plugin",
  "description": "Example BanHelper plugin",
  "author": "Example",
  "settings": {
    "fields": [
      {
        "key": "endpoint",
        "label": "Адрес сервера",
        "type": "text",
        "default": "127.0.0.1"
      },
      {
        "key": "token",
        "label": "Токен",
        "type": "password",
        "default": ""
      },
      {
        "key": "timeout",
        "label": "Таймаут",
        "type": "number",
        "default": 2.0,
        "minimum": 0.2,
        "maximum": 10.0,
        "decimals": 1
      }
    ]
  }
}
```

Поддерживаемые типы полей:

- `text` — обычная строка;
- `password` — строка со скрытым вводом;
- `integer` — целое число с `minimum` и `maximum`;
- `number` — дробное число с `minimum`, `maximum` и `decimals`;
- `boolean` — флажок;
- `choice` — список значений из `options`.

Настройки сохраняются в `context.data_dir/settings.json`. После нажатия **Сохранить** активный плагин автоматически перезапускается и читает новые значения.

`plugin.py`:

```python
import json


class Plugin:
    def activate(self, context):
        self.context = context
        path = context.data_dir / "settings.json"
        self.settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        context.register_action(
            "echo",
            self.echo,
            "Повторить payload",
        )
        context.log("INFO", "ready")

    def echo(self, payload):
        self.context.show_status("Плагин работает")
        return payload

    def deactivate(self):
        self.context.log("INFO", "stopped")
```

Полный ID команды станет `dev.example.echo.echo`.

## PluginContext

- `context.metadata`, `context.plugin_id`, `context.plugin_name`;
- `context.data_dir` — постоянная папка данных плагина;
- `context.register_action(id, handler, title=None)` — команда в меню;
- `context.show_status(message, timeout_ms=3000)` — сообщение в status bar;
- `context.command(name, payload=None)` — команда BanService;
- `context.log(level, message)` — запись в журнал.

## Ограничения и безопасность

- `api_version` сейчас равен `1`;
- ID содержит строчные ASCII-буквы, цифры, `.`, `_` и `-`;
- архив ограничен 25 МБ, 256 файлами и 50 МБ после распаковки;
- запрещены абсолютные пути, `..` и символические ссылки;
- плагины выполняют Python-код с правами пользователя BanHelper — устанавливайте только доверенные файлы;
- ошибка одного плагина не должна ломать загрузку остальных.

## OpenDeck и Ajazz AKP153

`.bhplugin` и плагины OpenDeck — разные форматы. OpenDeck управляет физическими кнопками AKP153, а `.bhplugin` расширяет BanHelper. Настройки `BanHelper AKP153 Bridge` доступны в **Настройки → Плагины**: адрес, порт, токен и таймаут.
