package com.devkit.lanfileshare;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;

/** What this phone remembers about the PC: the pairing, the password and the keys it received. */
final class PairingStore {
    static final String DEFAULT_PASSWORD = "1234";

    private PairingStore() {
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences("pairing", Context.MODE_PRIVATE);
    }

    static String password(Context context) {
        return preferences(context).getString("password", DEFAULT_PASSWORD);
    }

    static void savePassword(Context context, String password) {
        preferences(context).edit().putString("password", password).apply();
    }

    /** Keys this phone received, newest first. */
    static JSONArray keys(Context context) {
        try {
            return new JSONArray(preferences(context).getString("keys", "[]"));
        } catch (JSONException error) {
            return new JSONArray();
        }
    }

    private static void addKey(Context context, JSONObject key) {
        JSONArray kept = KeyRing.newestFirst(key, keys(context), KeyRing.KEPT_KEYS);
        preferences(context).edit().putString("keys", kept.toString()).apply();
    }

    static String connect(Context context, PcClient.Pc pc) throws IOException {
        return PcClient.connect(pc, KeyRing.secretsToTry(keys(context), password(context)));
    }

    static void rotateKey(Context context, PcClient.Pc pc, String secret) throws IOException {
        PcClient.Issued issued = PcClient.rotateKey(pc, secret, Build.MODEL);
        try {
            addKey(context, new JSONObject().put("id", issued.id).put("key", issued.key)
                    .put("time", System.currentTimeMillis()));
        } catch (JSONException error) {
            throw new IOException(error);
        }
    }

    static PcClient.Pc saved(Context context) {
        SharedPreferences saved = preferences(context);
        if (!saved.contains("fingerprint")) {
            return null;
        }

        PcClient.Pc pc = new PcClient.Pc();
        pc.host = saved.getString("host", "");
        pc.port = saved.getInt("port", PcClient.DEFAULT_PORT);
        pc.fingerprint = saved.getString("fingerprint", "");
        pc.name = saved.getString("name", "PC");

        return pc;
    }

    static void save(Context context, PcClient.Pc pc) {
        preferences(context).edit().putString("host", pc.host).putInt("port", pc.port)
                .putString("fingerprint", pc.fingerprint).putString("name", pc.name).apply();
    }
}
