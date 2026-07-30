package ru.gr1xzz1.banhelper;

import net.minecraft.client.MinecraftClient;

import java.util.ArrayDeque;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Optional;
import java.util.Queue;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Tracks check-related chat messages that do not contain a normal ban line. */
public final class VerificationTracker {
    private static final Pattern FORMATTING = Pattern.compile("§[0-9A-FK-ORa-fk-or]");
    private static final Pattern PLAYER_DATA = Pattern.compile(
            "(?iu)(?:Данные\\s+игрока|Авто:\\s*/dupeip|Аккаунты\\s+игрока)\\s+([A-Za-z0-9_]{2,16})"
    );
    private static final Pattern ACCOUNT_LIST = Pattern.compile(
            "(?iu)^([A-Za-z0-9_]{2,16}(?:\\s*,\\s*[A-Za-z0-9_]{2,16})*)$"
    );
    private static final Pattern CHECK_STARTED = Pattern.compile("(?iu)Проверка\\s+начата");
    private static final Pattern CHECK_LEFT = Pattern.compile(
            "(?iu)Игрок\\s+вышел\\s*\\(бан\\s+уже\\s+был\\s+выдан\\)"
    );
    private static final Queue<String> COMMANDS = new ArrayDeque<>();
    private static final Set<String> QUEUED = new LinkedHashSet<>();
    private static String candidatePlayer;
    private static String activePlayer;
    private static boolean awaitingAccounts;
    private static long nextCommandAt;

    public static synchronized Optional<BanParser.BanData> inspect(String message) {
        String clean = FORMATTING.matcher(message == null ? "" : message).replaceAll("").trim();
        Matcher player = PLAYER_DATA.matcher(clean);
        if (player.find()) {
            candidatePlayer = player.group(1);
            if (activePlayer != null || clean.toLowerCase(Locale.ROOT).contains("/dupeip")) {
                activePlayer = candidatePlayer;
            }
        }

        if (CHECK_STARTED.matcher(clean).find()) {
            activePlayer = candidatePlayer;
            if (activePlayer != null) {
                queue("dupeip " + activePlayer);
                queue("history " + activePlayer);
            }
            return Optional.empty();
        }

        if (clean.toLowerCase(Locale.ROOT).contains("аккаунты игрока")) {
            awaitingAccounts = true;
            return Optional.empty();
        }
        if (awaitingAccounts) {
            Matcher accounts = ACCOUNT_LIST.matcher(clean);
            if (accounts.matches()) {
                for (String account : accounts.group(1).split("\\s*,\\s*")) {
                    queue("history " + account);
                }
                awaitingAccounts = false;
            }
        }

        if (CHECK_LEFT.matcher(clean).find()) {
            String playerName = activePlayer != null ? activePlayer : candidatePlayer;
            activePlayer = null;
            candidatePlayer = null;
            awaitingAccounts = false;
            if (playerName != null) {
                return Optional.of(new BanParser.BanData(
                        BridgeConfig.DATA.moderator, playerName, "LIV", BridgeConfig.DATA.serverMode
                ));
            }
        }
        return Optional.empty();
    }

    private static void queue(String command) {
        if (QUEUED.add(command.toLowerCase(Locale.ROOT))) COMMANDS.add(command);
    }

    public static synchronized void tick(MinecraftClient client) {
        if (client.player == null || client.getNetworkHandler() == null || COMMANDS.isEmpty()) return;
        long now = System.currentTimeMillis();
        if (now < nextCommandAt) return;
        String command = COMMANDS.poll();
        QUEUED.remove(command.toLowerCase(Locale.ROOT));
        client.getNetworkHandler().sendChatCommand(command);
        nextCommandAt = now + 700L;
    }

    private VerificationTracker() {}
}
