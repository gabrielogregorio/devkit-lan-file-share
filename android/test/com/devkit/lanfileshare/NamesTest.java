package com.devkit.lanfileshare;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.Date;

public class NamesTest {
    @Test
    public void kindIsTheExtension() {
        assertEquals("PDF", Names.kind("relatório.pdf"));
        assertEquals("JPG", Names.kind("a.b.jpg"));
    }

    @Test
    public void kindFallsBackForMissingOrLongExtensions() {
        assertEquals("FILE", Names.kind("README"));
        assertEquals("FILE", Names.kind("trailing."));
        assertEquals("FILE", Names.kind("archive.backup"));
    }

    @Test
    public void textFileUsesTheSubject() {
        assertEquals("Notes.txt", Names.textFile("  Notes ", new Date(0)));
    }

    @Test
    public void textFileWithoutSubjectUsesTheMoment() {
        assertTrue(Names.textFile(null, new Date(0)).matches("text-\\d{8}-\\d{6}\\.txt"));
        assertTrue(Names.textFile("   ", new Date(0)).matches("text-\\d{8}-\\d{6}\\.txt"));
    }

    @Test
    public void headerSurvivesSpacesAndAccents() {
        assertEquals("rel%C3%B3rio%20final.pdf", Names.header("relório final.pdf"));
    }
}
