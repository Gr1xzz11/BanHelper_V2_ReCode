# BanHelper Plugin API v1

BanHelper 2.1.0 loads plugins from the user data directory:

- Linux: `$XDG_DATA_HOME/banhelper/plugins` or `~/.local/share/banhelper/plugins`
- Windows: `%APPDATA%\BanHelper\plugins`

A plugin can be an unpacked directory or a ZIP archive renamed to `.bhplugin`.

## Bundle layout

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
  "author": "Example"
}
```

`plugin.py`:

```python
class Plugin:
    def activate(self, context):
        context.register_action("echo", self.echo)
        context.log("INFO", "ready")

    def echo(self, payload):
        return payload

    def deactivate(self):
        pass
```

The full action id becomes `dev.example.echo.echo`.

## Rules

- `api_version` must currently be `1`.
- Plugin and action IDs may contain lowercase ASCII letters, digits, `.`, `_`, and `-`.
- Archives are checked for path traversal before extraction.
- A plugin executes Python code with the same user permissions as BanHelper. Install only trusted bundles.
- Plugin failures are isolated during discovery: a broken bundle is logged and other plugins continue loading.

## OpenDeck and Ajazz AKP153

Hardware support belongs to OpenDeck, not to BanHelper's Python plugin loader. For Ajazz AKP153 install the dedicated OpenDeck device plugin, then install a BanHelper action plugin/profile in OpenDeck. OpenDeck uses Stream Deck/OpenAction-style plugin manifests and processes; `.bhplugin` and OpenDeck plugin packages are separate formats and must not be renamed into one another.
