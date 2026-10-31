package com.devkit.lanfileshare;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ClipData;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.database.Cursor;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.OpenableColumns;
import android.webkit.MimeTypeMap;
import android.widget.Toast;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Sends one share at a time. Runs in the foreground so a long upload survives leaving the app. */
public class UploadService extends Service {
    private static final String CHANNEL_PROGRESS = "progress";
    private static final String CHANNEL_RESULT = "result";
    private static final int ID_PROGRESS = 1;
    private static final long WAKE_LIMIT_MS = 6 * 60 * 60 * 1000L;
    private static final long NOTIFY_EVERY_MS = 500;
    private static final String EXTRA_TEXT = "text";
    private static final String EXTRA_TITLE = "title";
    private static final long UNKNOWN_SIZE = -1;
    private static final int PROGRESS_SCALE = 1000;

    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private NotificationManager notifications;
    private int nextResultId = 100;

    /** Files travel as ClipData because that is what carries the read grant from the sender. */
    static void send(Context context, List<Uri> files, String text, String title) {
        Intent intent = new Intent(context, UploadService.class);
        intent.putExtra(EXTRA_TEXT, text);
        intent.putExtra(EXTRA_TITLE, title);
        if (!files.isEmpty()) {
            ClipData clip = ClipData.newRawUri("files", files.get(0));
            for (Uri uri : files.subList(1, files.size())) {
                clip.addItem(new ClipData.Item(uri));
            }
            intent.setClipData(clip);
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        }
        try {
            context.startForegroundService(intent);
        } catch (SecurityException denied) { // the sender shared a file without granting read access
            String message = context.getString(R.string.error_read);
            History.add(context, files.get(0).getLastPathSegment(), UNKNOWN_SIZE, message);
            Toast.makeText(context, context.getString(R.string.failed, message), Toast.LENGTH_LONG).show();
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        notifications = getSystemService(NotificationManager.class);
        notifications.createNotificationChannel(new NotificationChannel(CHANNEL_PROGRESS,
                getString(R.string.channel_progress), NotificationManager.IMPORTANCE_LOW));
        notifications.createNotificationChannel(new NotificationChannel(CHANNEL_RESULT,
                getString(R.string.channel_result), NotificationManager.IMPORTANCE_DEFAULT));
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Notification notification = progress(getString(R.string.state_searching), "", 0, 0);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(ID_PROGRESS, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(ID_PROGRESS, notification);
        }
        worker.execute(() -> {
            try {
                run(intent);
            } finally {
                stopSelf(startId); // the read grant lives until this start ends
            }
        });
        return START_NOT_STICKY;
    }

    @Override
    public void onTimeout(int startId, int fgsType) {
        stopSelf(); // Android 15+ caps dataSync at 6 hours
    }

    @Override
    public void onDestroy() {
        worker.shutdownNow();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private static final class Item {
        Uri uri;
        byte[] text;
        String name;
        long size = UNKNOWN_SIZE;

        InputStream open(Context context) throws IOException {
            if (text != null) {
                return new ByteArrayInputStream(text);
            }

            InputStream input = context.getContentResolver().openInputStream(uri);
            if (input == null) {
                throw new IOException("no stream");
            }

            return input;
        }
    }

    private void run(Intent intent) {
        PowerManager.WakeLock wake = getSystemService(PowerManager.class)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "lanfileshare:upload");
        WifiManager.WifiLock wifi = getApplicationContext().getSystemService(WifiManager.class)
                .createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "lanfileshare:upload");
        wake.acquire(WAKE_LIMIT_MS);
        wifi.acquire();
        try {
            transfer(items(intent));
        } finally {
            wifi.release();
            wake.release();
        }
    }

    private void transfer(List<Item> items) {
        if (items.isEmpty()) {
            finish(getString(R.string.failed, getString(R.string.error_nothing)));

            return;
        }

        PcClient.Pc pc;
        try {
            pc = reach();
        } catch (IOException error) {
            String reason = reasonFor(error);
            for (Item item : items) {
                History.add(this, item.name, item.size, reason);
            }
            finish(getString(R.string.failed, reason));

            return;
        }

        int failed = 0;
        String lastSent = null;
        String lastError = null;
        for (int index = 0; index < items.size(); index += 1) {
            try {
                lastSent = send(pc, pc.secret, items.get(index), index, items.size());
            } catch (IOException | SecurityException error) {
                failed += 1;
                lastError = reasonFor(error);
                History.add(this, items.get(index).name, items.get(index).size, lastError);
            }
        }
        finish(summary(failed, items.size(), lastSent, lastError));
    }

    private String summary(int failed, int total, String lastSent, String lastError) {
        if (failed == 0) {
            return total == 1 ? getString(R.string.done_one, lastSent) : getString(R.string.done_many, total);
        }
        if (total == 1) {
            return getString(R.string.failed, lastError);
        }

        return getString(R.string.failed_count, failed, total);
    }

    /** The saved address first; on failure, finds the same PC again, since DHCP moves it around. */
    private PcClient.Pc reach() throws IOException {
        PcClient.Pc pc = PairingStore.saved(this);
        if (pc == null) {
            throw new IOException("not paired");
        }

        try {
            PairingStore.connect(this, pc);

            return pc;
        } catch (PcClient.Refused | PcClient.NotProven refused) {
            throw refused;
        } catch (IOException unreachable) {
            PcClient.Pc moved = PcClient.discover(pc.fingerprint);
            if (moved == null) {
                throw unreachable;
            }

            PairingStore.connect(this, moved);
            PairingStore.save(this, moved);

            return moved;
        }
    }

    private String send(PcClient.Pc pc, String secret, Item item, int index, int count) throws IOException {
        String title = getString(R.string.sending, item.name);
        String detail = getString(R.string.sending_count, index + 1, count);
        long[] lastNotified = {0};
        long[] total = {0};
        notifications.notify(ID_PROGRESS, progress(title, detail, 0, item.size));
        try (InputStream input = item.open(this)) {
            String stored = PcClient.upload(pc, secret, item.name, input, sent -> {
                total[0] = sent;
                long now = System.currentTimeMillis();
                if (now - lastNotified[0] >= NOTIFY_EVERY_MS) {
                    lastNotified[0] = now;
                    notifications.notify(ID_PROGRESS, progress(title, detail, sent, item.size));
                }
            });
            History.add(this, stored, total[0], null);

            return stored;
        }
    }

    private List<Item> items(Intent intent) {
        List<Item> items = new ArrayList<>();
        ClipData clip = intent.getClipData();
        if (clip != null) {
            for (int index = 0; index < clip.getItemCount(); index += 1) {
                Uri uri = clip.getItemAt(index).getUri();
                // a file:// link from another app could point at this app's own private files
                if (uri != null && ContentResolver.SCHEME_CONTENT.equals(uri.getScheme())) {
                    items.add(describe(uri));
                }
            }
        }
        String text = intent.getStringExtra(EXTRA_TEXT);
        if (items.isEmpty() && text != null && !text.isEmpty()) {
            Item item = new Item();
            item.text = text.getBytes(StandardCharsets.UTF_8);
            item.size = item.text.length;
            item.name = Names.textFile(intent.getStringExtra(EXTRA_TITLE), new Date());
            items.add(item);
        }

        return items;
    }

    private Item describe(Uri uri) {
        Item item = new Item();
        item.uri = uri;
        try (Cursor cursor = getContentResolver().query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int name = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                int size = cursor.getColumnIndex(OpenableColumns.SIZE);
                if (name >= 0 && !cursor.isNull(name)) {
                    item.name = cursor.getString(name);
                }
                if (size >= 0 && !cursor.isNull(size)) {
                    item.size = cursor.getLong(size);
                }
            }
        } catch (RuntimeException queryFailed) {
            item.size = UNKNOWN_SIZE; // some providers throw on query: the name falls back below
        }
        if (item.name == null || item.name.isEmpty()) {
            String last = uri.getLastPathSegment();
            item.name = last == null ? "file" : last.substring(last.lastIndexOf('/') + 1);
        }
        if (!item.name.contains(".")) {
            String extension = MimeTypeMap.getSingleton().getExtensionFromMimeType(getContentResolver().getType(uri));
            if (extension != null) {
                item.name += "." + extension;
            }
        }

        return item;
    }

    private String reasonFor(Exception error) {
        switch (Failure.of(error)) {
            case PASSWORD:
                return getString(R.string.error_password);
            case DISK:
                return getString(R.string.error_disk);
            case DAMAGED:
                return getString(R.string.error_damaged);
            case UNREADABLE:
                return getString(R.string.error_read);
            case OFFLINE:
                return getString(R.string.error_offline);
            default:
                return getString(R.string.error_transfer);
        }
    }

    private PendingIntent openApp() {
        return PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class),
                PendingIntent.FLAG_IMMUTABLE);
    }

    private Notification progress(String title, String detail, long sent, long total) {
        Notification.Builder builder = new Notification.Builder(this, CHANNEL_PROGRESS)
                .setSmallIcon(R.drawable.ic_folder)
                .setContentTitle(title)
                .setContentText(detail)
                .setContentIntent(openApp())
                .setOnlyAlertOnce(true)
                .setOngoing(true);
        if (total > 0) {
            int done = (int) Math.min(PROGRESS_SCALE, sent * PROGRESS_SCALE / total);
            builder.setProgress(PROGRESS_SCALE, done, false);
        } else {
            builder.setProgress(0, 0, true);
        }

        return builder.build();
    }

    /** Also a toast: the notification alone says nothing when that permission was denied. */
    private void finish(String message) {
        nextResultId += 1;
        notifications.notify(nextResultId, new Notification.Builder(this, CHANNEL_RESULT)
                .setSmallIcon(R.drawable.ic_folder)
                .setContentTitle(message)
                .setContentIntent(openApp())
                .setAutoCancel(true)
                .build());
        main.post(() -> Toast.makeText(this, message, Toast.LENGTH_LONG).show());
    }
}
