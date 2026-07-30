# BanHelper Bridge 2.0 — Fabric 1.21.4

Клиентский мод читает компоненты чата, извлекает hover-текст `[Подробнее]`
и асинхронно отправляет protocol v2 на desktop listener. Сеть ограничена
`127.0.0.1`/`localhost`.

Если desktop недоступен, события попадают в bounded JSONL-очередь. Один
контролируемый worker выполняет HTTP и дисковые операции. Render/client thread
не блокируется. Повторная отправка сохраняет исходный `event_id`.

## Настройка

Откройте экран мода клавишей Right Shift. В нём есть:

- включение мода;
- адрес, порт и токен;
- ник модератора и фильтр только своих банов;
- fallback-режим FT/RW;
- уведомления в чате;
- статус, размер offline-очереди, test event и принудительная повторная отправка.

Конфиг мода: `.minecraft/config/banhelper-bridge.json`. Desktop и мод не передают
токен друг другу автоматически: его нужно один раз указать одинаковым.

## Извлечение hover

- `HOVER_EVENT`: рекурсивный обход `Text` и `Style.getHoverEvent()`;
- `TEXT_VISITOR`: обход styled-сегментов через `Text.visit(...)`;
- `AUTO`: сначала `HOVER_EVENT`, затем `TEXT_VISITOR`.

Если ник извлечён, а причина нет, desktop всё равно получает карточку и
требует ручной выбор. `verification_left` всегда отправляется с `LIV`.

## Сборка

Требуются JDK 21, Minecraft 1.21.4, Fabric Loader 0.16.10 и Fabric API.

```bash
./gradlew clean test build
```

Результат: `build/libs/banhelper-bridge-2.0.0.jar`.
