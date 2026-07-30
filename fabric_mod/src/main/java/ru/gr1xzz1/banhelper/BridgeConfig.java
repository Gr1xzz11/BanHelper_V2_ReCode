package ru.gr1xzz1.banhelper;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.fabricmc.loader.api.FabricLoader;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;

public final class BridgeConfig {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    public static volatile Data DATA = new Data();

    private static Path path() { return FabricLoader.getInstance().getConfigDir().resolve("banhelper-bridge.json"); }

    public static final class Data {
        public boolean enabled = true;
        public String address = "127.0.0.1";
        public int port = 8765;
        public String token = "banhelper-local";
        public String moderator = "";
        public String serverMode = "FT";
        public String extractionMode = "AUTO";
        public boolean moderatorFilter = false;
        public boolean hudEnabled = true;
        public boolean chatNotifications = false;
        public int maxOfflineEvents = 2000;
    }

    public static synchronized void load() {
        try {
            Path path = path();
            if (Files.exists(path)) {
                Data loaded = GSON.fromJson(Files.readString(path, StandardCharsets.UTF_8), Data.class);
                DATA = loaded == null ? new Data() : loaded;
            } else {
                save();
            }
            sanitize();
        } catch (Exception error) {
            DATA = new Data();
            ConnectionState.log("Конфиг повреждён, восстановлены значения по умолчанию");
        }
    }

    public static synchronized void save() throws IOException {
        sanitize();
        Path path = path();
        Files.createDirectories(path.getParent());
        Path temporary = path.resolveSibling(path.getFileName() + ".tmp");
        Files.writeString(temporary, GSON.toJson(DATA), StandardCharsets.UTF_8);
        try {
            Files.move(temporary, path, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException unsupported) {
            Files.move(temporary, path, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    public static synchronized void sanitize() {
        if (!"127.0.0.1".equals(DATA.address) && !"localhost".equalsIgnoreCase(DATA.address)) DATA.address = "127.0.0.1";
        DATA.port = Math.max(1024, Math.min(65535, DATA.port));
        DATA.maxOfflineEvents = Math.max(100, Math.min(10000, DATA.maxOfflineEvents));
        DATA.serverMode = "RW".equalsIgnoreCase(DATA.serverMode) ? "RW" : "FT";
        if (DATA.token == null) DATA.token = "";
        if (DATA.moderator == null) DATA.moderator = "";
    }

    public static String endpoint(String path) {
        return "http://" + DATA.address + ":" + DATA.port + path;
    }

    private BridgeConfig() {}
}
