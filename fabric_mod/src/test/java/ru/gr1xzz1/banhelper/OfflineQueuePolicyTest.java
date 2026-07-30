package ru.gr1xzz1.banhelper;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class OfflineQueuePolicyTest {
    @Test void keepsNewestItemsWithinLimit() {
        assertEquals(List.of("{\"id\":2}", "{\"id\":3}"),
                OfflineQueuePolicy.appendBounded(List.of("{\"id\":1}", "{\"id\":2}"), "{\"id\":3}", 2));
    }

    @Test void separatesDamagedJson() {
        assertTrue(OfflineQueuePolicy.validJsonObject("{\"event_id\":\"ok\"}"));
        assertFalse(OfflineQueuePolicy.validJsonObject("{broken"));
        assertFalse(OfflineQueuePolicy.validJsonObject("[]"));
    }

    @Test void deliveryCodesDoNotTreatProtocolMismatchAsSuccess() {
        assertTrue(BridgeSender.successful(202));
        assertFalse(BridgeSender.successful(401));
        assertFalse(BridgeSender.successful(409));
    }
}
