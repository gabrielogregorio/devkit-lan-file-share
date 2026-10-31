package com.devkit.lanfileshare;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

import java.nio.file.Files;
import java.nio.file.Paths;

public class ProtocolTest {
    private static final int EXPECTED_VECTORS = 4;

    /** The same file proofs.py is tested against: a mismatch means phone and PC stopped agreeing. */
    @Test
    public void proofsMatchThePythonSide() throws Exception {
        int checked = 0;
        for (String line : Files.readAllLines(Paths.get("../tests/vectors.txt"))) {
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            String[] field = line.split("\t");
            assertEquals(field[3], Protocol.sign(field[0], field[1], field[2]));
            checked += 1;
        }
        assertEquals(EXPECTED_VECTORS, checked);
    }

    @Test
    public void hexKeepsLeadingZeros() {
        assertEquals("000fff", Protocol.hex(new byte[]{0, 15, -1}));
    }
}
