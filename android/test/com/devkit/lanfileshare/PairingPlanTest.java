package com.devkit.lanfileshare;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class PairingPlanTest {
    @Test
    public void aLinkKeyAlwaysRotatesEvenOnThePairedPc() {
        assertEquals(PairingPlan.ROTATE_WITH_LINK_KEY, PairingPlan.choose(true, true));
        assertEquals(PairingPlan.ROTATE_WITH_LINK_KEY, PairingPlan.choose(true, false));
    }

    @Test
    public void thePairedPcOnlyReconnects() {
        assertEquals(PairingPlan.RECONNECT, PairingPlan.choose(false, true));
    }

    @Test
    public void aNewPcPairsWithThePassword() {
        assertEquals(PairingPlan.ROTATE_WITH_PASSWORD, PairingPlan.choose(false, false));
    }
}
