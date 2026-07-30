package ru.gr1xzz1.banhelper;

import net.minecraft.text.HoverEvent;
import net.minecraft.text.Style;
import net.minecraft.text.Text;

import java.lang.reflect.Method;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;

public final class HoverExtractor {
    public record Result(String hoverText, String mode) {}

    public static Optional<Result> extract(Text message, String configuredMode) {
        String mode = configuredMode == null ? "AUTO" : configuredMode.toUpperCase();
        if (mode.equals("HOVER_EVENT")) return hoverEventTree(message).map(v -> new Result(v, "HOVER_EVENT"));
        if (mode.equals("TEXT_VISITOR")) return textVisitor(message).map(v -> new Result(v, "TEXT_VISITOR"));
        Optional<String> first = hoverEventTree(message);
        return first.<Result>map(v -> new Result(v, "HOVER_EVENT"))
                .or(() -> textVisitor(message).map(v -> new Result(v, "TEXT_VISITOR")));
    }

    // Вариант 1: прямой рекурсивный обход Text/siblings и Style.getHoverEvent().
    private static Optional<String> hoverEventTree(Text text) {
        Optional<String> own = hoverValue(text.getStyle());
        if (own.isPresent()) return own;
        for (Text sibling : text.getSiblings()) {
            Optional<String> found = hoverEventTree(sibling);
            if (found.isPresent()) return found;
        }
        return Optional.empty();
    }

    // Вариант 2: Text.visit — Minecraft сам обходит все styled-сегменты.
    private static Optional<String> textVisitor(Text text) {
        AtomicReference<String> found = new AtomicReference<>();
        text.visit((style, segment) -> {
            if (found.get() == null && (segment.contains("Подробнее") || style.getHoverEvent() != null)) {
                hoverValue(style).ifPresent(found::set);
            }
            return Optional.empty();
        }, Style.EMPTY);
        return Optional.ofNullable(found.get());
    }

    private static Optional<String> hoverValue(Style style) {
        HoverEvent event = style.getHoverEvent();
        if (event == null) return Optional.empty();
        // Yarn 1.21.4 exposes typed values through getValue(Action).
        Text shown = event.getValue(HoverEvent.Action.SHOW_TEXT);
        if (shown != null) return Optional.of(shown.getString());
        // Fallback for nearby mappings that expose a no-argument accessor.
        for (String methodName : new String[]{"value", "getValue"}) {
            try {
                Method method = event.getClass().getMethod(methodName);
                Object value = method.invoke(event);
                if (value instanceof Text text) return Optional.of(text.getString());
                if (value != null) return Optional.of(value.toString());
            } catch (ReflectiveOperationException ignored) {}
        }
        return Optional.empty();
    }

    private HoverExtractor() {}
}
