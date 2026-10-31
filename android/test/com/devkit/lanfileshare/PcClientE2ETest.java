package com.devkit.lanfileshare;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;

import org.json.JSONArray;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Proxy;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.cert.Certificate;
import java.security.cert.CertificateFactory;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Random;
import java.util.stream.Stream;

import javax.net.ssl.SSLException;
import javax.net.ssl.SSLPeerUnverifiedException;
import javax.net.ssl.SSLSession;

/** The app's real network code against the real server in its own process, on a throwaway config. */
public class PcClientE2ETest {
    private static final String PASSWORD = "1234";

    private Path root;
    private Path inbox;
    private Path config;
    private Process server;
    private int port;
    private PcClient.Pc pc;

    @Before
    public void startServer() throws Exception {
        root = Files.createTempDirectory("lfs-e2e");
        inbox = root.resolve("inbox");
        config = root.resolve("config");
        Files.createDirectories(config);
        Files.write(config.resolve("config.json"),
                ("{\"folder\": \"" + inbox + "\"}").getBytes(StandardCharsets.UTF_8));
        try (ServerSocket free = new ServerSocket(0)) {
            port = free.getLocalPort();
        }
        ProcessBuilder builder = new ProcessBuilder("python3", "-m", "server.main").directory(new File(".."));
        builder.environment().put("LFS_PORT", String.valueOf(port));
        builder.environment().put("LFS_CONFIG_DIR", config.toString());
        builder.environment().put("LFS_NAME", "e2e-pc");
        builder.redirectErrorStream(true).redirectOutput(ProcessBuilder.Redirect.DISCARD);
        server = builder.start();
        for (int attempt = 0; attempt < 100; attempt++) {
            try (Socket socket = new Socket()) {
                socket.connect(new InetSocketAddress("127.0.0.1", port), 200);
                pc = PcClient.discover(null, port, InetAddress.getLoopbackAddress());
                assertNotNull("discovery", pc);
                return;
            } catch (IOException notYet) {
                Thread.sleep(50);
            }
        }
        throw new AssertionError("server did not start");
    }

    @After
    public void stopServer() throws Exception {
        server.destroyForcibly().waitFor();
        try (Stream<Path> paths = Files.walk(root)) {
            paths.sorted(Comparator.reverseOrder()).map(Path::toFile).forEach(File::delete);
        }
    }

    private String qrKey() throws Exception {
        JSONArray keys = new JSONArray(new String(Files.readAllBytes(config.resolve("keys.json")), StandardCharsets.UTF_8));
        return keys.getJSONObject(keys.length() - 1).getString("secret");
    }

    private void revoke(String secret) throws Exception {
        String code = "from pathlib import Path\nfrom server.keys import KeyStore\n"
                + "store = KeyStore(Path('" + config + "'))\n"
                + "[store.revoke(record['id']) for record in store.all() if record['secret'] == '" + secret + "']";
        assertEquals(0, new ProcessBuilder("python3", "-c", code).directory(new File("..")).start().waitFor());
    }

    @Test
    public void discoveryFindsThePcAndItsCertificate() throws Exception {
        assertEquals("127.0.0.1", pc.host);
        assertEquals(port, pc.port);
        assertEquals("e2e-pc", pc.name);
        assertEquals(pc.fingerprint, PcClient.probeFingerprint(pc.host, pc.port));
    }

    @Test
    public void discoveryIgnoresAnotherCertificate() throws Exception {
        assertNull(PcClient.discover("00".repeat(32), port, InetAddress.getLoopbackAddress()));
    }

    @Test
    public void pairingWithTheQrKeyRotatesItAndBothKeysKeepWorking() throws Exception {
        String qr = qrKey();
        PcClient.hello(pc, qr);
        PcClient.Issued issued = PcClient.rotateKey(pc, qr, "Pixel é 8");
        assertNotEquals(qr, issued.key);
        assertEquals(issued.key, qrKey());
        PcClient.hello(pc, issued.key);
        PcClient.hello(pc, qr);
        String keys = new String(Files.readAllBytes(config.resolve("keys.json")), StandardCharsets.UTF_8);
        assertTrue(keys.contains("Pixel é 8") || keys.contains("Pixel \\u00e9 8"));
    }

    @Test
    public void defaultPasswordPairs() throws Exception {
        assertEquals(PASSWORD, PcClient.connect(pc, List.of(PASSWORD)));
        assertEquals("e2e-pc", pc.name);
    }

    @Test
    public void wrongSecretIsRefused() {
        PcClient.Refused refused = assertThrows(PcClient.Refused.class, () -> PcClient.hello(pc, "wrong"));
        assertEquals(401, refused.status);
    }

    @Test
    public void uploadArrivesByteForByte() throws Exception {
        byte[] body = new byte[3_000_000];
        new Random(7).nextBytes(body);
        long[] sent = {0};
        String stored = PcClient.upload(pc, PASSWORD, "relatório final.pdf", new ByteArrayInputStream(body), sentBytes -> sent[0] = sentBytes);
        assertEquals("relatório final.pdf", stored);
        assertEquals(body.length, sent[0]);
        assertArrayEquals(body, Files.readAllBytes(inbox.resolve(stored)));
    }

    @Test
    public void emptyFileAndSameNameBothArrive() throws Exception {
        PcClient.upload(pc, PASSWORD, "same.txt", new ByteArrayInputStream(new byte[0]), sentBytes -> { });
        String second = PcClient.upload(pc, PASSWORD, "same.txt", new ByteArrayInputStream(new byte[]{1}), sentBytes -> { });
        assertEquals("same (1).txt", second);
        assertEquals(0, Files.size(inbox.resolve("same.txt")));
    }

    @Test
    public void uploadWithWrongSecretLeavesNothing() {
        assertThrows(IOException.class, () -> PcClient.upload(pc, "wrong", "x.bin",
                new ByteArrayInputStream(new byte[1000]), sentBytes -> { }));
        assertFalse(Files.exists(inbox.resolve("x.bin")));
    }

    @Test
    public void anotherCertificateIsRefusedBeforeAnySecretIsProven() {
        PcClient.Pc impostor = new PcClient.Pc();
        impostor.host = pc.host;
        impostor.port = pc.port;
        impostor.fingerprint = "00".repeat(32);
        assertThrows(SSLException.class, () -> PcClient.hello(impostor, PASSWORD));
    }

    private static SSLSession sessionWith(Certificate[] certificates) {
        return (SSLSession) Proxy.newProxyInstance(SSLSession.class.getClassLoader(), new Class<?>[]{SSLSession.class},
                (proxy, method, arguments) -> {
                    if (certificates == null) {
                        throw new SSLPeerUnverifiedException("no certificate");
                    }

                    return certificates;
                });
    }

    @Test
    public void hostnameCheckAcceptsOnlyThePinnedCertificate() throws Exception {
        try (InputStream file = Files.newInputStream(config.resolve("cert.pem"))) {
            Certificate[] certificates = {CertificateFactory.getInstance("X.509").generateCertificate(file)};

            assertTrue(PcClient.presentsPin(sessionWith(certificates), pc.fingerprint));
            assertFalse(PcClient.presentsPin(sessionWith(certificates), "00".repeat(32)));
        }
        assertFalse(PcClient.presentsPin(sessionWith(null), pc.fingerprint));
    }

    @Test
    public void revokedKeyFallsBackToTheNextSecret() throws Exception {
        String qr = qrKey();
        String newer = PcClient.rotateKey(pc, qr, "phone").key;
        revoke(newer);
        assertEquals(qr, PcClient.connect(pc, Arrays.asList(newer, qr, PASSWORD)));
        assertEquals(qr, pc.secret);
    }

    @Test
    public void lockoutStopsTheFallback() throws Exception {
        String[] wrong = new String[5];
        Arrays.fill(wrong, "wrong");
        assertThrows(PcClient.Refused.class, () -> PcClient.connect(pc, Arrays.asList(wrong)));
        PcClient.Refused locked = assertThrows(PcClient.Refused.class, () -> PcClient.hello(pc, PASSWORD));
        assertEquals(429, locked.status);
    }
}
