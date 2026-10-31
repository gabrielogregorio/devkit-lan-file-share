package com.devkit.lanfileshare;

import java.io.UnsupportedEncodingException;
import java.net.URLEncoder;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** File names and labels, free of the Android API. */
final class Names {
    private static final String FALLBACK_KIND = "FILE";
    private static final int MAX_KIND_CHARACTERS = 4;

    private Names() {
    }

    /** The extension, as the label on the file tile. */
    static String kind(String name) {
        int dot = name.lastIndexOf('.');
        if (dot < 0) {
            return FALLBACK_KIND;
        }

        String extension = name.substring(dot + 1).toUpperCase(Locale.ROOT);
        if (extension.isEmpty() || extension.length() > MAX_KIND_CHARACTERS) {
            return FALLBACK_KIND;
        }

        return extension;
    }

    /** Name for shared text: the subject the sender gave, or the moment it was shared. */
    static String textFile(String title, Date now) {
        if (title != null && !title.trim().isEmpty()) {
            return title.trim() + ".txt";
        }

        return "text-" + new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.ROOT).format(now) + ".txt";
    }

    /** Percent-encoded for the X-File-Name header, the form the PC decodes. */
    static String header(String value) {
        try {
            return URLEncoder.encode(value, "UTF-8").replace("+", "%20");
        } catch (UnsupportedEncodingException error) {
            throw new IllegalStateException(error);
        }
    }
}
