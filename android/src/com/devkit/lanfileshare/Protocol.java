package com.devkit.lanfileshare;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/** The proofs both sides compute. Must match proofs.py on the PC: tests/vectors.txt pins them together. */
final class Protocol {
    static final String CLIENT_ROLE = "client";
    static final String SERVER_ROLE = "server";
    private static final String HMAC_SHA256 = "HmacSHA256";

    private Protocol() {
    }

    static String hex(byte[] bytes) {
        StringBuilder text = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            text.append(String.format("%02x", value & 0xff));
        }

        return text.toString();
    }

    static String sign(String secret, String role, String fingerprint) {
        try {
            Mac mac = Mac.getInstance(HMAC_SHA256);
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), HMAC_SHA256));

            return hex(mac.doFinal((role + "|" + fingerprint).getBytes(StandardCharsets.UTF_8)));
        } catch (GeneralSecurityException error) {
            throw new IllegalStateException(error);
        }
    }
}
