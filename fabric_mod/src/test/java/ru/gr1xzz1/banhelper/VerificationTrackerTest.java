package ru.gr1xzz1.banhelper;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class VerificationTrackerTest {
    @Test void verificationLeftIsAlwaysLiv() {
        VerificationTracker.inspect("Данные игрока Player_4");
        VerificationTracker.inspect("Проверка начата");
        var result = VerificationTracker.inspect("Игрок вышел (бан уже был выдан)").orElseThrow();
        assertEquals("Player_4", result.player());
        assertEquals("LIV", result.reason());
    }
}
