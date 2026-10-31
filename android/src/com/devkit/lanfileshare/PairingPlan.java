package com.devkit.lanfileshare;

/** What a pairing attempt does once it found the PC. A real pairing ends with a new key; a known PC only reconnects. */
enum PairingPlan {
    ROTATE_WITH_LINK_KEY,
    RECONNECT,
    ROTATE_WITH_PASSWORD;

    static PairingPlan choose(boolean linkHasKey, boolean samePc) {
        if (linkHasKey) {
            return ROTATE_WITH_LINK_KEY;
        }
        if (samePc) {
            return RECONNECT;
        }

        return ROTATE_WITH_PASSWORD;
    }
}
