package com.devkit.lanfileshare;

import java.io.FileNotFoundException;
import java.net.ConnectException;
import java.net.NoRouteToHostException;
import java.net.SocketTimeoutException;

/** Why a transfer failed, in the terms the person sees. */
enum Failure {
    PASSWORD,
    DISK,
    DAMAGED,
    UNREADABLE,
    OFFLINE,
    INTERRUPTED;

    private static final int UNAUTHORIZED = 401;
    private static final int TOO_MANY_REQUESTS = 429;
    private static final int INSUFFICIENT_STORAGE = 507;

    private static Failure ofStatus(int status) {
        if (status == UNAUTHORIZED || status == TOO_MANY_REQUESTS) {
            return PASSWORD;
        }
        if (status == INSUFFICIENT_STORAGE) {
            return DISK;
        }

        return INTERRUPTED;
    }

    static Failure of(Exception error) {
        if (error instanceof PcClient.Refused) {
            return ofStatus(((PcClient.Refused) error).status);
        }
        if (error instanceof PcClient.NotProven) {
            return PASSWORD;
        }
        if (error instanceof PcClient.Damaged) {
            return DAMAGED;
        }
        if (error instanceof SecurityException || error instanceof FileNotFoundException) {
            return UNREADABLE;
        }
        if (error instanceof ConnectException || error instanceof SocketTimeoutException
                || error instanceof NoRouteToHostException) {
            return OFFLINE;
        }

        return INTERRUPTED;
    }
}
