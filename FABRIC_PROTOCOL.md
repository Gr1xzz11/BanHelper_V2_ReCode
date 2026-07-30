# BanHelper Fabric Protocol v2

Протокол предназначен только для локального соединения Minecraft-клиента с
desktop-приложением. Listener принимает соединения на `127.0.0.1`.

## Авторизация

Токен передаётся в заголовке `X-BanHelper-Token`. Для совместимости desktop
также принимает поле `token` в JSON, но заголовок имеет приоритет. Токен нельзя
записывать в логи.

## `GET /status`

Ответ `200`:

```json
{"ok":true,"service":"BanHelper","protocol_version":2,"queue_capacity":true}
```

Endpoint не создаёт сессию, pairing или heartbeat.

## `POST /ban`

Максимальный размер тела: 64 KiB. `Content-Type` —
`application/json; charset=utf-8`.

Обязательные поля:

- `protocol_version`: строго `2`;
- `event_id`: стабильный уникальный идентификатор длиной 8–128 символов;
- `event_type`: `ban` или `verification_left`;
- `player`: Minecraft-ник из 2–16 латинских букв, цифр или `_`;
- `reason`: `LIV`, цифровой код (`5.5`, `4.3.1`) либо пустая строка, если hover-причину извлечь не удалось;

Необязательные поля:

- `moderator`;
- `timestamp` в ISO 8601;
- `reason_raw`;
- `raw_message`;
- `raw_hover`;
- `extraction_mode`.
- `server_mode`: `FT` либо `RW`. Корректное значение из мода имеет приоритет; при отсутствии или ошибке desktop использует ручной fallback-режим и пишет предупреждение в журнал.

Для `verification_left` desktop всегда заменяет причину на `LIV`, даже если
поле `reason` повреждено окружающим текстом.
Пустая `reason` создаёт карточку с заблокированным подтверждением: модератор выбирает
причину вручную из быстрой панели.

Успешный ответ `202` означает, что событие принято bounded ingress-очередью.
SQLite и GUI обрабатывают его после ответа.

```json
{"ok":true,"accepted":true,"event_id":"550e8400-e29b-41d4-a716-446655440000"}
```

## Ошибки

| Код | Значение |
|---:|---|
| 400 | некорректный запрос или JSON |
| 401 | неправильный токен |
| 404 | неизвестный endpoint |
| 409 | несовместимая версия протокола |
| 411 | отсутствует `Content-Length` |
| 413 | тело больше 64 KiB |
| 422 | не прошло поле валидации |
| 503 | bounded queue заполнена; отправку нужно повторить |

## Дедупликация

`event_id` является первичным ключом таблицы `events`. Повторная доставка
может получить `202`, потому что listener отвечает до SQLite, однако worker
распознаёт повтор в памяти/SQLite и не создаёт карточку, очередь или статистику.
Это работает после перезапуска desktop и повторной отправки offline-очереди.

## Примеры

FT:

```json
{"protocol_version":2,"event_id":"ft-20260729-0001","event_type":"ban","player":"PlayerOne","moderator":"Admin","reason":"5.5","server_mode":"FT","timestamp":"2026-07-29T13:00:00Z"}
```

RW:

```json
{"protocol_version":2,"event_id":"rw-20260729-0001","event_type":"ban","player":"PlayerTwo","moderator":"Admin","reason":"4.3.1","server_mode":"RW","timestamp":"2026-07-29T13:00:01Z"}
```

Выход с проверки:

```json
{"protocol_version":2,"event_id":"liv-20260729-0001","event_type":"verification_left","player":"PlayerThree","moderator":"Admin","reason":"LIV","server_mode":"FT","timestamp":"2026-07-29T13:00:02Z"}
```

Версия протокола меняется только при несовместимом изменении обязательных
полей или семантики ответа.
