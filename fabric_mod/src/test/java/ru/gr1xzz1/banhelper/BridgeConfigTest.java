package ru.gr1xzz1.banhelper;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BridgeConfigTest {
    @AfterEach
    void reset() {
        BridgeConfig.DATA = new BridgeConfig.Data();
    }

    @Test
    void configurationCannotEscapeLoopbackAndNormalizesMode() {
        BridgeConfig.DATA.address = "remote.example";
        BridgeConfig.DATA.port = 1;
        BridgeConfig.DATA.serverMode = "unknown";
        BridgeConfig.DATA.maxOfflineEvents = 99999;
        BridgeConfig.sanitize();
        assertEquals("127.0.0.1", BridgeConfig.DATA.address);
        assertEquals(1024, BridgeConfig.DATA.port);
        assertEquals("FT", BridgeConfig.DATA.serverMode);
        assertEquals(10000, BridgeConfig.DATA.maxOfflineEvents);
    }
}
