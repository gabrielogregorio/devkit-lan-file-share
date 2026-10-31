package com.devkit.lanfileshare;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** The list of keys this phone received, newest first. Free of the Android API. */
final class KeyRing {
    static final int KEPT_KEYS = 8;
    /** One under the wrong tries that lock an address out of the PC, so a stale list cannot lock this phone out. */
    static final int MAX_TRIES = 4;

    private KeyRing() {
    }

    static JSONArray newestFirst(JSONObject newest, JSONArray older, int limit) {
        JSONArray kept = new JSONArray();
        kept.put(newest);
        for (int index = 0; index < older.length() && kept.length() < limit; index += 1) {
            kept.put(older.opt(index));
        }

        return kept;
    }

    /** Newest key first, an older one if the PC revoked it, the password last. */
    static List<String> secretsToTry(JSONArray keys, String password) {
        List<String> secrets = new ArrayList<>();
        for (int index = 0; index < keys.length() && secrets.size() < MAX_TRIES - 1; index += 1) {
            JSONObject key = keys.optJSONObject(index);
            if (key != null) {
                secrets.add(key.optString("key"));
            }
        }
        secrets.add(password);

        return secrets;
    }
}
