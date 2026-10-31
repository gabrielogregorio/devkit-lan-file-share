package com.devkit.lanfileshare;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** What was sent lately, shown on the main screen. */
final class History {
    private static final int KEPT_ITEMS = 12;
    private static final String ITEMS = "items";

    private History() {
    }

    static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences("history", Context.MODE_PRIVATE);
    }

    static JSONArray items(Context context) {
        try {
            return new JSONArray(preferences(context).getString(ITEMS, "[]"));
        } catch (JSONException error) {
            return new JSONArray();
        }
    }

    /** error null means it arrived. */
    static synchronized void add(Context context, String name, long size, String error) {
        JSONObject item;
        try {
            item = new JSONObject().put("name", name).put("size", size)
                    .put("time", System.currentTimeMillis()).put("error", error);
        } catch (JSONException invalidValue) {
            return;
        }

        JSONArray kept = KeyRing.newestFirst(item, items(context), KEPT_ITEMS);
        preferences(context).edit().putString(ITEMS, kept.toString()).apply();
    }
}
