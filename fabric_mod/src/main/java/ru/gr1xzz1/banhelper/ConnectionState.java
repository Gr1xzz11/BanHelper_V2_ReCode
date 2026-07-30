package ru.gr1xzz1.banhelper;

import java.time.Instant;
import java.util.ArrayDeque;
import java.util.Deque;

public final class ConnectionState {
    public enum State { CONNECTED, CONNECTING, AUTH_ERROR, OFFLINE }
    private static volatile State state = State.CONNECTING;
    private static volatile String detail = "Проверка связи";
    private static volatile long lastSuccess = 0L;
    private static final Deque<String> logs = new ArrayDeque<>();
    public static synchronized void set(State value, String text) { state=value; detail=text; if(value==State.CONNECTED) lastSuccess=System.currentTimeMillis(); log(text); }
    public static State state(){return state;} public static String detail(){return detail;} public static long lastSuccess(){return lastSuccess;}
    public static synchronized void log(String text){ logs.addFirst(Instant.now()+" · "+text); while(logs.size()>30) logs.removeLast(); }
    public static synchronized String[] logs(){return logs.toArray(String[]::new);} private ConnectionState(){}
}
