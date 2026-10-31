package com.devkit.lanfileshare;

import static org.junit.Assert.assertEquals;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;

import java.util.Arrays;
import java.util.List;

public class KeyRingTest {
    private static final String PASSWORD = "password";

    private static JSONObject key(String secret) throws Exception {
        return new JSONObject().put("key", secret);
    }

    private static JSONArray keys(String... secrets) throws Exception {
        JSONArray array = new JSONArray();
        for (String secret : secrets) {
            array.put(key(secret));
        }

        return array;
    }

    @Test
    public void newestComesFirstAndTheOldestFallsOffAtTheLimit() throws Exception {
        JSONArray kept = KeyRing.newestFirst(key("new"), keys("older", "oldest"), 2);

        assertEquals(2, kept.length());
        assertEquals("new", kept.getJSONObject(0).getString("key"));
        assertEquals("older", kept.getJSONObject(1).getString("key"));
    }

    @Test
    public void withoutKeysOnlyThePasswordIsTried() {
        assertEquals(List.of(PASSWORD), KeyRing.secretsToTry(new JSONArray(), PASSWORD));
    }

    @Test
    public void keysComeBeforeThePassword() throws Exception {
        assertEquals(Arrays.asList("new", "old", PASSWORD), KeyRing.secretsToTry(keys("new", "old"), PASSWORD));
    }

    @Test
    public void triesStayUnderTheLockoutOfThePc() throws Exception {
        List<String> secrets = KeyRing.secretsToTry(keys("one", "two", "three", "four", "five"), PASSWORD);

        assertEquals(KeyRing.MAX_TRIES, secrets.size());
        assertEquals(PASSWORD, secrets.get(secrets.size() - 1));
    }
}
