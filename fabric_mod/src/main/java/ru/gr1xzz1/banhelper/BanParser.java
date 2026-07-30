package ru.gr1xzz1.banhelper;

import java.util.Locale;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Parses the transport-neutral fields and never applies a reason allow-list. */
public final class BanParser {
    private static final Pattern FORMATTING = Pattern.compile("§[0-9A-FK-ORa-fk-or]");
    private static final Pattern PLAYER = Pattern.compile(
            "(?iu)(?:Администратор\\s+)?([\\wА-Яа-яЁё-]{2,32})\\s+забанил(?:а)?\\s+(?:игрока\\s+)?([A-Za-z0-9_]{2,16})"
    );
    private static final Pattern REASON_WITH_LABEL = Pattern.compile(
            "(?iu)(?:причина|правило|пункт)\\s*[:№#=-]?\\s*([^\\r\\n]+)"
    );
    private static final Pattern DETAILS_SUFFIX = Pattern.compile("(?iu)\\s*\\[Подробнее]\\s*$");
    private static final Pattern RW_MARKER = Pattern.compile("(?iu)(?:\\bRW\\b|Really\\s*World|Рили\\s*Ворлд)");
    private static final Pattern RULE_CODE = Pattern.compile("(?iu)^(?:LIV|\\d+(?:\\.\\d+)+)$");

    public record BanData(String moderator, String player, String reason, String reasonRaw, String serverMode) {
        public BanData(String moderator, String player, String reason, String serverMode) {
            this(moderator, player, reason, reason, serverMode);
        }
    }

    public static Optional<BanData> parse(String visible, String hover) {
        if (visible == null) return Optional.empty();
        String cleanVisible = stripFormatting(visible).trim();
        String cleanHover = stripFormatting(hover == null ? "" : hover).trim();
        Matcher player = PLAYER.matcher(cleanVisible);
        if (!player.find()) return Optional.empty();
        String reasonRaw = findReason(cleanHover);
        if (reasonRaw == null) reasonRaw = findReason(cleanVisible);
        if (reasonRaw == null && RULE_CODE.matcher(cleanHover).matches()) reasonRaw = cleanHover;
        if (reasonRaw == null) reasonRaw = "";
        String mode = RW_MARKER.matcher(cleanVisible + "\n" + cleanHover).find()
                || cleanVisible.toLowerCase(Locale.ROOT).startsWith("администратор ") ? "RW" : "FT";
        String normalized = normalizeReason(reasonRaw);
        return Optional.of(new BanData(
                player.group(1), player.group(2), normalized, reasonRaw, mode
        ));
    }

    public static Optional<BanData> parseVisible(String visible) {
        return parse(visible, visible);
    }

    private static String findReason(String text) {
        if (text == null || text.isBlank()) return null;
        Matcher labeled = REASON_WITH_LABEL.matcher(text);
        if (!labeled.find()) return null;
        String reason = DETAILS_SUFFIX.matcher(labeled.group(1)).replaceFirst("").trim();
        return reason.isBlank() ? null : reason;
    }

    private static String normalizeReason(String reason) {
        String clean = reason.trim();
        if (clean.toLowerCase(Locale.ROOT).equals("liv")) return "LIV";
        return RULE_CODE.matcher(clean).matches() ? clean : "";
    }

    private static String stripFormatting(String text) {
        return FORMATTING.matcher(text).replaceAll("");
    }

    private BanParser() {}
}
