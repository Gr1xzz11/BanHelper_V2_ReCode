package ru.gr1xzz1.banhelper;

import com.google.gson.Gson;
import net.minecraft.client.MinecraftClient;
import net.minecraft.text.Text;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** One bounded sender worker; Minecraft's render/client thread never performs network or disk I/O. */
public final class BridgeSender {
    public static final int PROTOCOL_VERSION = 2;
    private static final Gson GSON = new Gson();
    private static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(1)).build();
    private static final LinkedBlockingQueue<Outbound> LIVE = new LinkedBlockingQueue<>(1024);
    private static final LinkedBlockingQueue<String> SPILL = new LinkedBlockingQueue<>(8192);
    private static final AtomicBoolean RUNNING = new AtomicBoolean(false);
    private static Thread worker;
    private static volatile long nextRetryAt;
    private static long backoffMs = 2000L;
    private static long lastChatWarning;

    private record Outbound(String json, CompletableFuture<Integer> result) {}

    public static synchronized void initialize() {
        if (!RUNNING.compareAndSet(false, true)) return;
        worker = new Thread(BridgeSender::runWorker, "BanHelper-Sender");
        worker.setDaemon(true);
        worker.start();
    }

    public static void sendAsync(BanParser.BanData ban, String visible, String hover, String extractionMode) {
        enqueue(ban, visible, hover, extractionMode, null);
    }

    public static CompletableFuture<Integer> simulateBanAsync(String player, String reason) {
        String cleanPlayer = player == null || player.isBlank() ? "TestPlayer" : player.trim();
        String cleanReason = reason == null || reason.isBlank() ? "4.3.2" : reason.trim();
        CompletableFuture<Integer> result = new CompletableFuture<>();
        enqueue(new BanParser.BanData(BridgeConfig.DATA.moderator, cleanPlayer, cleanReason, BridgeConfig.DATA.serverMode),
                BridgeConfig.DATA.moderator + " забанил " + cleanPlayer + " [Подробнее]",
                "Причина: " + cleanReason, "GUI_SIMULATION", result);
        return result;
    }

    private static void enqueue(BanParser.BanData ban, String visible, String hover, String extractionMode, CompletableFuture<Integer> result) {
        if (!BridgeConfig.DATA.enabled) { if (result != null) result.complete(0); return; }
        if (BridgeConfig.DATA.moderatorFilter && !BridgeConfig.DATA.moderator.equalsIgnoreCase(ban.moderator())) {
            if (result != null) result.complete(204);
            return;
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("protocol_version", PROTOCOL_VERSION);
        body.put("event_id", UUID.randomUUID().toString());
        body.put("event_type", "CHECK_TRACKER".equals(extractionMode) ? "verification_left" : "ban");
        body.put("player", ban.player()); body.put("moderator", ban.moderator());
        body.put("reason", "CHECK_TRACKER".equals(extractionMode) ? "LIV" : ban.reason());
        body.put("reason_raw", ban.reasonRaw()); body.put("server_mode", ban.serverMode());
        body.put("timestamp", Instant.now().toString()); body.put("raw_message", visible);
        body.put("raw_hover", hover); body.put("extraction_mode", extractionMode);
        Outbound outbound = new Outbound(GSON.toJson(body), result);
        if (!LIVE.offer(outbound)) {
            if (!SPILL.offer(outbound.json())) {
                SPILL.poll();
                SPILL.offer(outbound.json());
                ConnectionState.log("Переполнена spill-очередь; вытеснено самое старое событие");
            }
            if (result != null) result.complete(503);
            warnChatOnce("[BanHelper] Локальная очередь заполнена; событие сохранено");
        }
    }

    public static CompletableFuture<Integer> testConnectionAsync() {
        return CompletableFuture.supplyAsync(() -> {
            int code = getStatus(); updateState(code); return code;
        });
    }

    public static void retryNow() { nextRetryAt = 0L; }

    public static int pendingCount() { return OfflineQueue.size() + LIVE.size() + SPILL.size(); }

    private static void runWorker() {
        OfflineQueue.readValid();
        updateState(getStatus());
        while (RUNNING.get()) {
            try {
                if (!BridgeConfig.DATA.enabled) {
                    ConnectionState.set(ConnectionState.State.OFFLINE, "Мод выключен");
                    Thread.sleep(500L);
                    continue;
                }
                persistSpill();
                Outbound outbound = LIVE.poll(500, TimeUnit.MILLISECONDS);
                if (outbound != null) {
                    if (System.currentTimeMillis() < nextRetryAt) {
                        persistLive(outbound, 100);
                    } else {
                        int code = post(outbound.json());
                        if (outbound.result() != null) outbound.result().complete(code);
                        if (successful(code)) {
                            connected();
                        } else {
                            persistLive(outbound, 100);
                            failed(code);
                        }
                    }
                }
                if (OfflineQueue.size() > 0 && System.currentTimeMillis() >= nextRetryAt) flushOneBatch();
            } catch (InterruptedException stopped) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception error) {
                ConnectionState.log("Ошибка sender worker");
            }
        }
    }

    private static void persistSpill() {
        List<String> batch = new ArrayList<>();
        SPILL.drainTo(batch, 100);
        if (!batch.isEmpty()) OfflineQueue.addAll(batch);
    }

    private static void persistLive(Outbound first, int limit) {
        List<String> batch = new ArrayList<>();
        batch.add(first.json());
        if (first.result() != null && !first.result().isDone()) first.result().complete(503);
        while (batch.size() < limit) {
            Outbound next = LIVE.poll();
            if (next == null) break;
            batch.add(next.json());
            if (next.result() != null && !next.result().isDone()) next.result().complete(503);
        }
        OfflineQueue.addAll(batch);
    }

    private static void flushOneBatch() {
        List<String> pending = OfflineQueue.readValid();
        if (pending.isEmpty()) return;
        List<String> remaining = new ArrayList<>();
        int limit = Math.min(50, pending.size());
        int index = 0;
        for (; index < limit; index++) {
            int code = post(pending.get(index));
            if (!successful(code)) {
                remaining.addAll(pending.subList(index, pending.size()));
                failed(code);
                break;
            }
        }
        if (index == limit) remaining.addAll(pending.subList(limit, pending.size()));
        OfflineQueue.replace(remaining);
        if (remaining.isEmpty() || index > 0) connected();
    }

    private static void connected() {
        backoffMs = 2000L; nextRetryAt = 0L;
        ConnectionState.set(ConnectionState.State.CONNECTED, "Desktop подключён");
    }

    private static void failed(int code) {
        nextRetryAt = System.currentTimeMillis() + backoffMs;
        backoffMs = Math.min(60000L, backoffMs * 2L);
        if (code == 401) ConnectionState.set(ConnectionState.State.AUTH_ERROR, "Неверный токен");
        else ConnectionState.set(ConnectionState.State.OFFLINE, "Desktop недоступен; очередь сохранена");
        warnChatOnce("[BanHelper] Desktop недоступен; бан сохранён в очередь");
    }

    private static int getStatus() {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(BridgeConfig.endpoint("/status"))).timeout(Duration.ofSeconds(2)).GET().build();
            return HTTP.send(request, HttpResponse.BodyHandlers.discarding()).statusCode();
        } catch (Exception error) { return -1; }
    }

    private static int post(String json) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(BridgeConfig.endpoint("/ban"))).timeout(Duration.ofSeconds(3))
                    .header("Content-Type", "application/json; charset=utf-8")
                    .header("X-BanHelper-Token", BridgeConfig.DATA.token)
                    .POST(HttpRequest.BodyPublishers.ofString(json)).build();
            return HTTP.send(request, HttpResponse.BodyHandlers.discarding()).statusCode();
        } catch (Exception error) { return -1; }
    }

    static boolean successful(int code) { return code == 200 || code == 202; }

    private static void updateState(int code) { if (successful(code)) connected(); else failed(code); }

    private static void warnChatOnce(String message) {
        if (!BridgeConfig.DATA.chatNotifications) return;
        long now = System.currentTimeMillis(); if (now - lastChatWarning < 30000L) return; lastChatWarning = now;
        MinecraftClient client = MinecraftClient.getInstance();
        client.execute(() -> { if (client.player != null) client.player.sendMessage(Text.literal(message), false); });
    }

    private BridgeSender() {}
}
