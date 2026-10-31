package com.devkit.lanfileshare;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

import java.io.FileNotFoundException;
import java.io.IOException;
import java.net.ConnectException;
import java.net.NoRouteToHostException;
import java.net.SocketTimeoutException;

public class FailureTest {
    @Test
    public void wrongSecretAndLockoutBothMeanThePassword() {
        assertEquals(Failure.PASSWORD, Failure.of(new PcClient.Refused(401)));
        assertEquals(Failure.PASSWORD, Failure.of(new PcClient.Refused(429)));
        assertEquals(Failure.PASSWORD, Failure.of(new PcClient.NotProven()));
    }

    @Test
    public void fullDiskHasItsOwnReason() {
        assertEquals(Failure.DISK, Failure.of(new PcClient.Refused(507)));
    }

    @Test
    public void anyOtherRefusalIsAnInterruption() {
        assertEquals(Failure.INTERRUPTED, Failure.of(new PcClient.Refused(400)));
    }

    @Test
    public void aHashMismatchIsDamage() {
        assertEquals(Failure.DAMAGED, Failure.of(new PcClient.Damaged()));
    }

    @Test
    public void aFileTheSenderDidNotReleaseIsUnreadable() {
        assertEquals(Failure.UNREADABLE, Failure.of(new SecurityException()));
        assertEquals(Failure.UNREADABLE, Failure.of(new FileNotFoundException()));
    }

    @Test
    public void networkErrorsMeanThePcIsOffline() {
        assertEquals(Failure.OFFLINE, Failure.of(new ConnectException()));
        assertEquals(Failure.OFFLINE, Failure.of(new SocketTimeoutException()));
        assertEquals(Failure.OFFLINE, Failure.of(new NoRouteToHostException()));
    }

    @Test
    public void anythingElseIsAnInterruption() {
        assertEquals(Failure.INTERRUPTED, Failure.of(new IOException("reset")));
    }
}
