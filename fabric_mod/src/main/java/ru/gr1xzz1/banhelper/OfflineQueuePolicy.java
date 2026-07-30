package ru.gr1xzz1.banhelper;

import com.google.gson.JsonParser;

import java.util.ArrayList;
import java.util.List;

final class OfflineQueuePolicy {
    static boolean validJsonObject(String value) {
        try { return JsonParser.parseString(value).isJsonObject(); }
        catch (Exception error) { return false; }
    }

    static List<String> appendBounded(List<String> existing, String value, int limit) {
        List<String> result = new ArrayList<>(existing);
        while (result.size() >= limit) result.removeFirst();
        result.add(value);
        return result;
    }

    private OfflineQueuePolicy() {}
}
