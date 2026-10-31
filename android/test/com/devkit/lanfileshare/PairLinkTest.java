package com.devkit.lanfileshare;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class PairLinkTest {
    private static final String FINGERPRINT = "e8".repeat(32);
    private static final String KEY = "ab".repeat(32);
    private static final String VALID_LINK = "lanfileshare://pair?host=192.168.0.10&port=8908&fp=" + FINGERPRINT + "&k=" + KEY;

    @Test
    public void readsWhatThePanelWrites() {
        PairLink link = PairLink.parse(VALID_LINK);
        assertEquals("192.168.0.10", link.host);
        assertEquals(8908, link.port);
        assertEquals(FINGERPRINT, link.fingerprint);
        assertEquals(KEY, link.key);
    }

    @Test
    public void keyIsOptional() {
        assertNull(PairLink.parse("lanfileshare://pair?host=pc.local&port=8908&fp=" + FINGERPRINT).key);
    }

    @Test
    public void refusesOtherSchemesAndHosts() {
        assertNull(PairLink.parse(null));
        assertNull(PairLink.parse("https://example.com/?host=a&port=1&fp=" + FINGERPRINT));
        assertNull(PairLink.parse("lanfileshare://other?host=a&port=1&fp=" + FINGERPRINT));
        assertFalse(PairLink.isOurs("WIFI:S:home;;"));
        assertTrue(PairLink.isOurs(VALID_LINK));
    }

    @Test
    public void refusesMalformedFields() {
        assertNull(PairLink.parse("lanfileshare://pair?port=8908&fp=" + FINGERPRINT));
        assertNull(PairLink.parse("lanfileshare://pair?host=a&port=99999&fp=" + FINGERPRINT));
        assertNull(PairLink.parse("lanfileshare://pair?host=a&port=0&fp=" + FINGERPRINT));
        assertNull(PairLink.parse("lanfileshare://pair?host=a&port=8908&fp=short"));
        assertNull(PairLink.parse(VALID_LINK.replace(KEY, "zz")));
        assertNull(PairLink.parse("lanfileshare://pair?host=a%2Fb&port=8908&fp=" + FINGERPRINT));
    }

    @Test
    public void typedAddressMayCarryAPort() {
        assertEquals(18908, PairLink.portOf("10.0.2.2:18908", 8908));
        assertEquals("10.0.2.2", PairLink.hostOf("10.0.2.2:18908"));
        assertEquals(8908, PairLink.portOf("pc.local", 8908));
        assertEquals("pc.local", PairLink.hostOf("pc.local"));
        assertEquals(8908, PairLink.portOf("pc:99999", 8908));
    }

    @Test
    public void aLinkFromOutsideNeedsConfirmationUnlessItIsThePairedPc() {
        assertTrue(PairLink.needsConfirmation(false, false));
        assertFalse(PairLink.needsConfirmation(false, true));
    }

    @Test
    public void theScannerNeedsNoConfirmationBecauseThePersonPointedTheCamera() {
        assertFalse(PairLink.needsConfirmation(true, false));
    }

    @Test
    public void refusesBrokenEscapes() {
        assertNull(PairLink.parse("lanfileshare://pair?host=%zz&port=8908&fp=" + FINGERPRINT));
    }
}
