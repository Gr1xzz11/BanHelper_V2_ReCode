package ru.gr1xzz1.banhelper.gui;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.widget.ButtonWidget;
import net.minecraft.client.gui.widget.TextFieldWidget;
import net.minecraft.text.Text;
import ru.gr1xzz1.banhelper.*;
import java.io.IOException;
import java.util.concurrent.CompletableFuture;

public final class BridgeConfigScreen extends Screen {
    private enum Tab { STATUS, SIMULATION, LOGS, SETTINGS }
    private final Screen parent;
    private Tab tab = Tab.STATUS;
    private TextFieldWidget playerField, reasonField, hoverField, moderatorField, addressField, portField, tokenField, modeField;
    private String status = "Готово";
    private int statusColor = 0xA0A0A0;

    public BridgeConfigScreen(Screen parent) {
        super(Text.literal("BanHelper Bridge"));
        this.parent = parent;
    }

    @Override protected void init() { rebuild(); }

    private void rebuild() {
        clearChildren();
        int c = width / 2;
        int top = height / 2 - 132;
        String[] names = {"Статус", "Симуляция", "Логи", "Настройки"};
        Tab[] tabs = Tab.values();
        for (int i = 0; i < tabs.length; i++) {
            final Tab selected = tabs[i];
            addDrawableChild(ButtonWidget.builder(Text.literal(names[i]), b -> { tab = selected; rebuild(); })
                    .dimensions(c - 196 + i * 98, top + 30, 94, 20).build());
        }
        switch (tab) {
            case STATUS -> statusTab(c, top);
            case SIMULATION -> simulationTab(c, top);
            case LOGS -> logsTab(c, top);
            case SETTINGS -> settingsTab(c, top);
        }
        addDrawableChild(ButtonWidget.builder(Text.literal("Закрыть"), b -> close())
                .dimensions(c - 70, top + 236, 140, 20).build());
    }

    private void statusTab(int c, int top) {
        addDrawableChild(ButtonWidget.builder(Text.literal("Проверить соединение"), b -> ping())
                .dimensions(c - 150, top + 86, 300, 20).build());
        addDrawableChild(ButtonWidget.builder(Text.literal("Отправить очередь сейчас"), b -> {
            BridgeSender.retryNow();
            status = "Повторная отправка запланирована";
            statusColor = 0x55FF55;
        }).dimensions(c - 150, top + 126, 300, 20).build());
    }

    private void simulationTab(int c, int top) {
        playerField = field(c - 150, top + 82, 145, "TestPlayer", "Игрок");
        reasonField = field(c + 5, top + 82, 145, "4.3.2", "Причина");
        hoverField = field(c - 150, top + 122, 300, "Причина: 4.3.2", "HoverText");
        addDrawableChild(ButtonWidget.builder(Text.literal("Проверить парсер"), b -> testParser())
                .dimensions(c - 150, top + 156, 145, 20).build());
        addDrawableChild(ButtonWidget.builder(Text.literal("Отправить тест"), b -> simulate())
                .dimensions(c + 5, top + 156, 145, 20).build());
    }

    private TextFieldWidget field(int x, int y, int w, String value, String label) {
        TextFieldWidget field = new TextFieldWidget(textRenderer, x, y, w, 20, Text.literal(label));
        field.setText(value);
        addDrawableChild(field);
        return field;
    }

    private void logsTab(int c, int top) {
        addDrawableChild(ButtonWidget.builder(Text.literal("Обновить"), b -> rebuild())
                .dimensions(c - 70, top + 198, 140, 20).build());
    }

    private void settingsTab(int c, int top) {
        addressField = field(c - 150, top + 70, 145, BridgeConfig.DATA.address, "Адрес");
        portField = field(c + 5, top + 70, 145, String.valueOf(BridgeConfig.DATA.port), "Порт");
        tokenField = field(c - 150, top + 104, 300, BridgeConfig.DATA.token, "Токен");
        moderatorField = field(c - 150, top + 138, 145, BridgeConfig.DATA.moderator, "Модератор");
        modeField = field(c + 5, top + 138, 145, BridgeConfig.DATA.serverMode, "Режим FT/RW");
        addDrawableChild(ButtonWidget.builder(Text.literal("Мод: " + (BridgeConfig.DATA.enabled ? "ВКЛ" : "ВЫКЛ")), b -> {
            BridgeConfig.DATA.enabled = !BridgeConfig.DATA.enabled; save(); BridgeSender.retryNow(); rebuild();
        }).dimensions(c - 150, top + 172, 145, 20).build());
        addDrawableChild(ButtonWidget.builder(Text.literal("Чат: " + (BridgeConfig.DATA.chatNotifications ? "ВКЛ" : "ВЫКЛ")), b -> {
            BridgeConfig.DATA.chatNotifications = !BridgeConfig.DATA.chatNotifications; save(); rebuild();
        }).dimensions(c + 5, top + 172, 145, 20).build());
        addDrawableChild(ButtonWidget.builder(Text.literal("Фильтр модератора: " + (BridgeConfig.DATA.moderatorFilter ? "ВКЛ" : "ВЫКЛ")), b -> {
            BridgeConfig.DATA.moderatorFilter = !BridgeConfig.DATA.moderatorFilter; save(); rebuild();
        }).dimensions(c - 150, top + 196, 145, 20).build());
        addDrawableChild(ButtonWidget.builder(Text.literal("Сохранить"), b -> {
            BridgeConfig.DATA.address = addressField.getText().trim();
            try { BridgeConfig.DATA.port = Integer.parseInt(portField.getText().trim()); } catch (NumberFormatException ignored) { BridgeConfig.DATA.port = 8765; }
            BridgeConfig.DATA.token = tokenField.getText().trim(); BridgeConfig.DATA.moderator = moderatorField.getText().trim();
            BridgeConfig.DATA.serverMode = modeField.getText().trim(); BridgeConfig.sanitize(); save(); BridgeSender.retryNow();
        }).dimensions(c + 5, top + 196, 145, 20).build());
    }

    private void ping() {
        status = "Проверка...";
        BridgeSender.testConnectionAsync().thenAccept(code -> runClient(() -> {
            status = ConnectionState.detail();
            statusColor = code >= 200 && code < 300 ? 0x55FF55 : 0xFF5555;
        }));
    }

    private void testParser() {
        String visible = BridgeConfig.DATA.moderator + " забанил " + playerField.getText().trim() + " [Подробнее]";
        BanParser.parse(visible, hoverField.getText()).ifPresentOrElse(
                ban -> { status = "Парсер: " + ban.moderator() + " / " + ban.player() + " / " + ban.reason(); statusColor = 0x55FF55; },
                () -> { status = "Парсер не нашёл причину"; statusColor = 0xFFAA00; }
        );
    }

    private void simulate() {
        BridgeSender.simulateBanAsync(playerField.getText(), reasonField.getText()).thenAccept(code -> runClient(() -> {
            status = code >= 200 && code < 300 ? "Событие отправлено" : "Сохранено в очередь / ошибка: " + code;
            statusColor = code >= 200 && code < 300 ? 0x55FF55 : 0xFFAA00;
        }));
    }

    private void save() {
        status = "Сохранение…";
        CompletableFuture.runAsync(() -> {
            try { BridgeConfig.save(); runClient(() -> { status = "Настройки сохранены"; statusColor = 0x55FF55; }); }
            catch (IOException e) { runClient(() -> { status = e.getMessage(); statusColor = 0xFF5555; }); }
        });
    }

    private void runClient(Runnable runnable) { MinecraftClient.getInstance().execute(runnable); }

    @Override public void render(DrawContext ctx, int mouseX, int mouseY, float delta) {
        renderBackground(ctx, mouseX, mouseY, delta);
        int c = width / 2;
        int top = height / 2 - 132;
        ctx.fill(c - 214, top, c + 214, top + 270, 0xD912151B);
        ctx.fill(c - 214, top, c - 210, top + 270, 0xFF7C5CFC);
        ctx.drawTextWithShadow(textRenderer, Text.literal("BAN HELPER"), c - 194, top + 10, 0xFFFFFFFF);
        ctx.drawTextWithShadow(textRenderer, Text.literal("Bridge 2.0 · MC 1.21.4"), c + 54, top + 10, 0xFF9AA4B2);
        super.render(ctx, mouseX, mouseY, delta);
        ctx.drawCenteredTextWithShadow(textRenderer, Text.literal(status), c, top + 218, statusColor);
        if (tab == Tab.STATUS) {
            ctx.drawTextWithShadow(textRenderer, Text.literal("Состояние: " + ConnectionState.detail()), c - 150, top + 62, 0xFFFFFFFF);
            ctx.drawTextWithShadow(textRenderer, Text.literal("Офлайн-очередь: " + BridgeSender.pendingCount()), c + 40, top + 62, 0xFF9AA4B2);
        } else if (tab == Tab.LOGS) {
            String[] logs = ConnectionState.logs();
            for (int i = 0; i < Math.min(logs.length, 7); i++)
                ctx.drawTextWithShadow(textRenderer, Text.literal(logs[i]), c - 190, top + 62 + i * 18, 0xFFC8CDD5);
        } else if (tab == Tab.SIMULATION) {
            ctx.drawTextWithShadow(textRenderer, Text.literal("Игрок"), c - 150, top + 68, 0xFF9AA4B2);
            ctx.drawTextWithShadow(textRenderer, Text.literal("Причина"), c + 5, top + 68, 0xFF9AA4B2);
            ctx.drawTextWithShadow(textRenderer, Text.literal("Raw HoverText / тест парсера"), c - 150, top + 108, 0xFF9AA4B2);
        } else {
            ctx.drawTextWithShadow(textRenderer, Text.literal("Локальный listener, токен, модератор и fallback-режим"), c - 150, top + 58, 0xFF9AA4B2);
        }
    }

    @Override public boolean shouldPause() { return false; }
    @Override public void close() { if (client != null) client.setScreen(parent); }
}
