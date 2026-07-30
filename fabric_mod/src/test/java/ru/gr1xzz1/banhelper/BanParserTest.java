package ru.gr1xzz1.banhelper;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class BanParserTest {
    @Test void parsesFtHoverReason() {
        var result = BanParser.parse("Admin забанил Player_1 [Подробнее]", "Причина: 4.3.1").orElseThrow();
        assertEquals("Admin", result.moderator());
        assertEquals("Player_1", result.player());
        assertEquals("4.3.1", result.reason());
        assertEquals("FT", result.serverMode());
    }

    @Test void parsesRwAndRawHover() {
        var result = BanParser.parse("Администратор Admin забанил игрока Player_2 [Подробнее]", "Правило: 5.5").orElseThrow();
        assertEquals("RW", result.serverMode());
        assertEquals("5.5", result.reason());
    }

    @Test void doesNotUseMinecraftVersionAsReasonWithoutLabel() {
        var result = BanParser.parse("Admin забанил Player_3 [Подробнее]", "Minecraft 1.21.4").orElseThrow();
        assertEquals("", result.reason());
    }
}
