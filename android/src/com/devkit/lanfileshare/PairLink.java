package com.devkit.lanfileshare;

import java.io.UnsupportedEncodingException;
import java.net.URLDecoder;
import java.util.HashMap;
import java.util.Map;

/** The lanfileshare://pair link in the QR code. Anything malformed is refused, whatever opened it. */
final class PairLink {
    private static final String PREFIX = "lanfileshare://pair?";
    private static final String HEX_64 = "[0-9a-f]{64}";
    private static final String HOST_PATTERN = "[0-9A-Za-z.:-]{1,253}";
    private static final String PORT_PATTERN = "\\d{1,5}";
    private static final int MAX_PORT = 65535;

    final String host;
    final int port;
    final String fingerprint;
    final String key; // null when the link carries none

    private PairLink(String host, int port, String fingerprint, String key) {
        this.host = host;
        this.port = port;
        this.fingerprint = fingerprint;
        this.key = key;
    }

    private static boolean isValidPort(int number) {
        return number >= 1 && number <= MAX_PORT;
    }

    /** The port in an address typed by hand, "192.168.0.10:8908"; the fallback when there is none. */
    static int portOf(String address, int fallback) {
        int colon = address.lastIndexOf(':');
        if (colon < 0 || !address.substring(colon + 1).matches(PORT_PATTERN)) {
            return fallback;
        }

        int number = Integer.parseInt(address.substring(colon + 1));

        return isValidPort(number) ? number : fallback;
    }

    /** The host in an address typed by hand. */
    static String hostOf(String address) {
        int colon = address.lastIndexOf(':');

        return colon < 0 ? address : address.substring(0, colon);
    }

    static boolean isOurs(String text) {
        return text != null && text.startsWith(PREFIX);
    }

    /**
     * Any app can fire this link, so only the person's own scan or the PC already paired go straight
     * through: otherwise a planted link would send the next shares to another computer.
     */
    static boolean needsConfirmation(boolean fromScanner, boolean samePc) {
        return !fromScanner && !samePc;
    }

    private static Map<String, String> readQuery(String text) throws UnsupportedEncodingException {
        Map<String, String> query = new HashMap<>();
        for (String field : text.substring(PREFIX.length()).split("&")) {
            int equals = field.indexOf('=');
            if (equals > 0) {
                query.put(field.substring(0, equals), URLDecoder.decode(field.substring(equals + 1), "UTF-8"));
            }
        }

        return query;
    }

    /** Returns null when the link is not a valid pairing link. */
    static PairLink parse(String text) {
        if (!isOurs(text)) {
            return null;
        }

        Map<String, String> query;
        try {
            query = readQuery(text);
        } catch (UnsupportedEncodingException | IllegalArgumentException error) {
            return null;
        }

        String host = query.get("host");
        String port = query.get("port");
        String fingerprint = query.get("fp");
        String key = query.get("k");
        boolean hostIsValid = host != null && host.matches(HOST_PATTERN);
        boolean portIsValid = port != null && port.matches(PORT_PATTERN);
        boolean fingerprintIsValid = fingerprint != null && fingerprint.matches(HEX_64);
        boolean keyIsValid = key == null || key.matches(HEX_64);
        if (!hostIsValid || !portIsValid || !fingerprintIsValid || !keyIsValid) {
            return null;
        }

        int number = Integer.parseInt(port);

        return isValidPort(number) ? new PairLink(host, number, fingerprint, key) : null;
    }
}
