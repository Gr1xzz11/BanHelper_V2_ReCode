# OpenDeck + Ajazz AKP153

BanHelper 2.2.0 exposes a token-protected loopback API for the bundled OpenDeck action plugin.

## Files

The release archive contains:

- `BanHelper.grxt` — BanHelper for Linux with the OpenDeck API;
- `BanHelper-AKP153.OpenDeckPlugin` — installable OpenDeck plugin;
- `banhelper-bridge-2.0.0.jar` — Fabric bridge.

## Installation

1. Install OpenDeck and the Ajazz AKP153 device plugin.
2. Start the new `BanHelper.grxt`.
3. In OpenDeck open **Plugins → Install from file**.
4. Select `BanHelper-AKP153.OpenDeckPlugin`.
5. Drag the 15 BanHelper actions to a dedicated 5 × 3 layout.
6. Open the property inspector for any action and press **Проверить**.

Default connection settings:

```text
API:   http://127.0.0.1:8765
Token: banhelper-local
```

The values must match BanHelper's listener port and token. Settings are global for all 15 actions.

## Recommended layout

```text
FT       RW       COPY     OK       SKIP
5.5      LIV      4.3.1    4.3.2    1.11
2.12     4.1      4.6      4.7      4.8
```

## Local API

- `GET /opendeck/status` — authenticated health check;
- `POST /opendeck/action` — authenticated action request;
- header: `X-BanHelper-Token`;
- JSON: `{ "action": "reason", "value": "5.5" }`.

Supported action values are `mode`, `reason`, `confirm`, `copy`, and `skip`. The server binds only to loopback and does not expose remote control to the network.
