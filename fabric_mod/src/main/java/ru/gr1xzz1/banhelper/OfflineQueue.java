package ru.gr1xzz1.banhelper;

import com.google.gson.JsonParser;
import net.fabricmc.loader.api.FabricLoader;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/** Bounded crash-safe JSONL queue. All methods are called from BridgeSender's worker. */
public final class OfflineQueue {
    private static final Path PATH = FabricLoader.getInstance().getConfigDir().resolve("banhelper-offline-queue.jsonl");
    private static volatile int cachedSize;

    public static synchronized void addAll(List<String> jsonEvents) {
        if (jsonEvents.isEmpty()) return;
        List<String> pending = readValid();
        for (String json : jsonEvents) {
            pending = OfflineQueuePolicy.appendBounded(pending, json, BridgeConfig.DATA.maxOfflineEvents);
        }
        replace(pending);
    }

    public static synchronized List<String> readValid() {
        List<String> valid = new ArrayList<>();
        List<String> damaged = new ArrayList<>();
        try {
            if (!Files.exists(PATH)) { cachedSize = 0; return valid; }
            for (String line : Files.readAllLines(PATH, StandardCharsets.UTF_8)) {
                if (line.isBlank()) continue;
                try {
                    if (OfflineQueuePolicy.validJsonObject(line)) valid.add(line); else damaged.add(line);
                } catch (Exception error) {
                    damaged.add(line);
                }
            }
            if (!damaged.isEmpty()) {
                Path quarantine = PATH.resolveSibling("banhelper-offline-corrupt-" + Instant.now().toEpochMilli() + ".jsonl");
                Files.write(quarantine, damaged, StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
                replace(valid);
                ConnectionState.log("Повреждённые строки очереди изолированы: " + damaged.size());
            }
        } catch (IOException error) {
            ConnectionState.log("Ошибка чтения offline-очереди");
        }
        cachedSize = valid.size();
        return valid;
    }

    public static synchronized void replace(List<String> remaining) {
        try {
            Files.createDirectories(PATH.getParent());
            Path temporary = PATH.resolveSibling(PATH.getFileName() + ".tmp");
            Files.write(temporary, remaining, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
            try {
                Files.move(temporary, PATH, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            } catch (IOException unsupported) {
                Files.move(temporary, PATH, StandardCopyOption.REPLACE_EXISTING);
            }
            cachedSize = remaining.size();
        } catch (IOException error) {
            ConnectionState.log("Ошибка записи offline-очереди");
        }
    }

    public static int size() { return cachedSize; }
    private OfflineQueue() {}
}
