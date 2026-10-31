package com.devkit.lanfileshare;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.InterfaceAddress;
import java.net.NetworkInterface;
import java.net.SocketTimeoutException;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.util.Collections;
import java.util.List;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

/**
 * Everything that talks to the PC: discovery, proofs, pinned HTTPS and the upload itself.
 * Free of the Android API, so the end to end tests run this same code on a plain JVM against the real server.
 */
final class PcClient {
    static final int DEFAULT_PORT = 8908;
    private static final String APP_ID = "lan-file-share";
    private static final byte[] DISCOVER = "LFS-DISCOVER-1".getBytes(StandardCharsets.US_ASCII);
    private static final int BLOCK_BYTES = 256 * 1024;
    private static final int CONNECT_TIMEOUT_MS = 5000;
    private static final int READ_TIMEOUT_MS = 60000;
    private static final int DISCOVERY_ATTEMPTS = 3;
    private static final int DISCOVERY_WAIT_MS = 700;
    private static final int MAX_REPLY_BYTES = 1024;
    private static final int UNAUTHORIZED = 401;
    private static final String AUTH_HEADER = "X-Auth";

    /** The PC refused with this HTTP status. */
    static final class Refused extends IOException {
        final int status;

        Refused(int status) {
            super("HTTP " + status);
            this.status = status;
        }
    }

    /** The PC answered, but did not prove it knows the secret. */
    static final class NotProven extends IOException {
    }

    /** The bytes stored on the PC are not the bytes read here. */
    static final class Damaged extends IOException {
    }

    interface Progress {
        void sent(long bytes);
    }

    static final class Pc {
        String host;
        int port;
        String fingerprint;
        String name;
        String secret; // the one this PC accepted, set by connect()
    }

    /** A key the PC just issued. */
    static final class Issued {
        final String id;
        final String key;

        Issued(String id, String key) {
            this.id = id;
            this.key = key;
        }
    }

    private PcClient() {
    }

    private static String fingerprintOf(X509Certificate certificate) throws CertificateException {
        try {
            return Protocol.hex(MessageDigest.getInstance("SHA-256").digest(certificate.getEncoded()));
        } catch (GeneralSecurityException error) {
            throw new CertificateException(error);
        }
    }

    /** Trusts only the certificate with this fingerprint; null trusts any and records what it saw. */
    private static SSLSocketFactory tls(final String pinned, final String[] seen) throws IOException {
        TrustManager manager = new X509TrustManager() {
            @Override
            public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                throw new CertificateException("no client certificates");
            }

            @Override
            public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                String fingerprint = fingerprintOf(chain[0]);
                if (seen != null) {
                    seen[0] = fingerprint;
                }
                if (pinned != null && !pinned.equals(fingerprint)) {
                    throw new CertificateException("certificate is not the paired one");
                }
            }

            @Override
            public X509Certificate[] getAcceptedIssuers() {
                return new X509Certificate[0];
            }
        };
        try {
            SSLContext context = SSLContext.getInstance("TLS");
            context.init(null, new TrustManager[]{manager}, null);

            return context.getSocketFactory();
        } catch (GeneralSecurityException error) {
            throw new IOException(error);
        }
    }

    private static HttpsURLConnection open(Pc pc, String path) throws IOException {
        URL url = new URL("https", pc.host, pc.port, path);
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        connection.setSSLSocketFactory(tls(pc.fingerprint, null));
        connection.setHostnameVerifier((host, session) -> true); // identity is the pin, not the name
        connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(READ_TIMEOUT_MS);

        return connection;
    }

    /** Reads the certificate of a PC typed by hand; the proof in hello() is what makes it trusted. */
    static String probeFingerprint(String host, int port) throws IOException {
        String[] seen = new String[1];
        try (SSLSocket socket = (SSLSocket) tls(null, seen).createSocket()) {
            socket.connect(new InetSocketAddress(host, port), CONNECT_TIMEOUT_MS);
            socket.setSoTimeout(CONNECT_TIMEOUT_MS);
            socket.startHandshake();
        }

        return seen[0];
    }

    /** Checks both ways that this PC and this phone share the secret; fills in the PC name. */
    static void hello(Pc pc, String secret) throws IOException {
        HttpsURLConnection connection = open(pc, "/api/v1/hello");
        try {
            connection.setRequestProperty(AUTH_HEADER, Protocol.sign(secret, Protocol.CLIENT_ROLE, pc.fingerprint));
            JSONObject answer = readJson(connection);
            if (!Protocol.sign(secret, Protocol.SERVER_ROLE, pc.fingerprint).equals(answer.optString("proof"))) {
                throw new NotProven();
            }
            pc.name = answer.optString("name", pc.name);
        } finally {
            connection.disconnect();
        }
    }

    /** Finds a secret this PC still accepts, in the order given; stops early when the PC locks out. */
    static String connect(Pc pc, List<String> secrets) throws IOException {
        Refused last = null;
        for (String secret : secrets) {
            try {
                hello(pc, secret);
                pc.secret = secret;

                return secret;
            } catch (Refused refused) {
                last = refused;
                if (refused.status != UNAUTHORIZED) {
                    break;
                }
            }
        }

        throw last == null ? new Refused(401) : last;
    }

    /** Asks the PC for a new key: the step that makes the key change when a phone pairs. */
    static Issued rotateKey(Pc pc, String secret, String device) throws IOException {
        HttpsURLConnection connection = open(pc, "/api/v1/pair");
        try {
            connection.setRequestMethod("POST");
            connection.setRequestProperty(AUTH_HEADER, Protocol.sign(secret, Protocol.CLIENT_ROLE, pc.fingerprint));
            connection.setRequestProperty("X-Device", Names.header(device));
            JSONObject answer = readJson(connection);

            return new Issued(answer.getString("id"), answer.getString("key"));
        } catch (JSONException error) {
            throw new IOException(error);
        } finally {
            connection.disconnect();
        }
    }

    /** Sends one stream; the PC hashes what it stored and the answer must match what was read here. */
    static String upload(Pc pc, String secret, String name, InputStream input, Progress progress)
            throws IOException {
        HttpsURLConnection connection = open(pc, "/api/v1/files");
        try {
            connection.setRequestMethod("PUT");
            connection.setDoOutput(true);
            connection.setChunkedStreamingMode(BLOCK_BYTES); // providers often report a wrong size, or none
            connection.setRequestProperty(AUTH_HEADER, Protocol.sign(secret, Protocol.CLIENT_ROLE, pc.fingerprint));
            connection.setRequestProperty("X-File-Name", Names.header(name));
            MessageDigest digest = sha256();
            byte[] buffer = new byte[BLOCK_BYTES];
            long total = 0;
            try (OutputStream output = connection.getOutputStream()) {
                int read = input.read(buffer);
                while (read != -1) {
                    output.write(buffer, 0, read);
                    digest.update(buffer, 0, read);
                    total += read;
                    progress.sent(total);
                    read = input.read(buffer);
                }
            }
            JSONObject answer = readJson(connection);
            if (!Protocol.hex(digest.digest()).equals(answer.optString("sha256"))) {
                throw new Damaged();
            }

            return answer.optString("name", name);
        } finally {
            connection.disconnect();
        }
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (GeneralSecurityException error) {
            throw new IllegalStateException(error);
        }
    }

    private static JSONObject readJson(HttpURLConnection connection) throws IOException {
        int status = connection.getResponseCode();
        if (status < 200 || status >= 300) {
            throw new Refused(status);
        }
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        try (InputStream input = connection.getInputStream()) {
            byte[] buffer = new byte[4096];
            int read = input.read(buffer);
            while (read != -1) {
                body.write(buffer, 0, read);
                read = input.read(buffer);
            }
        }
        try {
            return new JSONObject(body.toString("UTF-8"));
        } catch (JSONException error) {
            throw new IOException(error);
        }
    }

    /** Asks the LAN for the PC. With wanted set, only that certificate counts: the IP may have changed. */
    static Pc discover(String wanted) throws IOException {
        return discover(wanted, DEFAULT_PORT, null);
    }

    /** direct, when given, replaces the broadcast. */
    static Pc discover(String wanted, int port, InetAddress direct) throws IOException {
        try (DatagramSocket socket = new DatagramSocket()) {
            socket.setBroadcast(true);
            socket.setSoTimeout(DISCOVERY_WAIT_MS);
            byte[] buffer = new byte[MAX_REPLY_BYTES];
            for (int attempt = 0; attempt < DISCOVERY_ATTEMPTS; attempt += 1) {
                if (direct != null) {
                    socket.send(new DatagramPacket(DISCOVER, DISCOVER.length, direct, port));
                } else {
                    broadcast(socket, port);
                }
                long deadline = System.currentTimeMillis() + DISCOVERY_WAIT_MS;
                while (System.currentTimeMillis() < deadline) {
                    DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                    try {
                        socket.receive(packet);
                    } catch (SocketTimeoutException waitedEnough) {
                        break;
                    }
                    Pc pc = parseReply(packet);
                    if (pc != null && (wanted == null || wanted.equals(pc.fingerprint))) {
                        return pc;
                    }
                }
            }
        }

        return null;
    }

    private static void broadcast(DatagramSocket socket, int port) throws IOException {
        socket.send(new DatagramPacket(DISCOVER, DISCOVER.length, InetAddress.getByName("255.255.255.255"), port));
        for (NetworkInterface network : Collections.list(NetworkInterface.getNetworkInterfaces())) {
            if (!network.isUp() || network.isLoopback()) {
                continue;
            }
            for (InterfaceAddress address : network.getInterfaceAddresses()) {
                InetAddress target = address.getBroadcast();
                if (target != null) {
                    socket.send(new DatagramPacket(DISCOVER, DISCOVER.length, target, port));
                }
            }
        }
    }

    private static Pc parseReply(DatagramPacket packet) {
        try {
            JSONObject reply = new JSONObject(
                    new String(packet.getData(), 0, packet.getLength(), StandardCharsets.UTF_8));
            if (!APP_ID.equals(reply.optString("app"))) {
                return null;
            }

            Pc pc = new Pc();
            pc.host = packet.getAddress().getHostAddress();
            pc.port = reply.getInt("port");
            pc.fingerprint = reply.getString("fingerprint");
            pc.name = reply.optString("name", "PC");

            return pc;
        } catch (JSONException malformed) {
            return null;
        }
    }
}
