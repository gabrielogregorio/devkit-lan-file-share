package com.devkit.lanfileshare;

import android.Manifest;
import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.Intent;
import android.content.DialogInterface;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.format.DateUtils;
import android.text.format.Formatter;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/** Pairing, status and history. Sharing itself goes through ShareActivity. */
public class MainActivity extends Activity {
    private static final int PICK_FILES = 1;
    private static final int SCAN = 2;

    private enum State { GOOD, BUSY, BAD }

    private TextView status;
    private TextView detail;
    private View hero;
    private View badge;
    private View connection;
    private View connectionArrow;
    private LinearLayout history;
    private EditText password;
    private EditText host;
    private ObjectAnimator pulse;
    private final SharedPreferences.OnSharedPreferenceChangeListener onHistory =
            (preferences, changedKey) -> runOnUiThread(this::showHistory);

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.main);
        status = findViewById(R.id.status);
        detail = findViewById(R.id.detail);
        hero = findViewById(R.id.hero);
        badge = findViewById(R.id.badge);
        history = findViewById(R.id.history);
        connection = findViewById(R.id.connection);
        connectionArrow = findViewById(R.id.connection_arrow);
        password = findViewById(R.id.password);
        host = findViewById(R.id.host);
        password.setText(PairingStore.password(this));

        findViewById(R.id.send).setOnClickListener(view -> pickFiles());
        findViewById(R.id.scan).setOnClickListener(view ->
                startActivityForResult(new Intent(this, ScanActivity.class), SCAN));
        findViewById(R.id.find).setOnClickListener(view -> pair(null, null, null, null));
        findViewById(R.id.connect).setOnClickListener(view -> connectToTypedAddress());
        findViewById(R.id.connection_header).setOnClickListener(view ->
                showConnection(connection.getVisibility() != View.VISIBLE));

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 0);
        }
        showConnection(PairingStore.saved(this) == null);
        showKeys();
        if (!handlePairLink(getIntent(), false)) {
            refresh();
        }
    }

    private void connectToTypedAddress() {
        String typed = host.getText().toString().trim();
        if (typed.isEmpty()) {
            pair(null, null, null, null);

            return;
        }

        pair(PairLink.hostOf(typed), PairLink.portOf(typed, PcClient.DEFAULT_PORT), null, null);
    }

    @Override
    protected void onStart() {
        super.onStart();
        showHistory();
        History.preferences(this).registerOnSharedPreferenceChangeListener(onHistory);
    }

    @Override
    protected void onStop() {
        History.preferences(this).unregisterOnSharedPreferenceChangeListener(onHistory);
        super.onStop();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handlePairLink(intent, false);
    }

    private void showConnection(boolean open) {
        connection.setVisibility(open ? View.VISIBLE : View.GONE);
        connectionArrow.animate().rotation(open ? 180 : 0).setDuration(150).start();
    }

    private void show(State state, String title, String sub) {
        runOnUiThread(() -> {
            status.setText(title);
            detail.setText(sub);
            hero.setBackgroundResource(heroBackground(state));
            if (pulse != null) {
                pulse.cancel();
                pulse = null;
                badge.setAlpha(1f);
            }
            if (state == State.BUSY) {
                pulse = ObjectAnimator.ofFloat(badge, View.ALPHA, 1f, 0.35f);
                pulse.setDuration(650);
                pulse.setRepeatCount(ValueAnimator.INFINITE);
                pulse.setRepeatMode(ValueAnimator.REVERSE);
                pulse.start();
            }
        });
    }

    private static int heroBackground(State state) {
        if (state == State.GOOD) {
            return R.drawable.hero_ok;
        }
        if (state == State.BUSY) {
            return R.drawable.hero_idle;
        }

        return R.drawable.hero_bad;
    }

    private void searching() {
        show(State.BUSY, getString(R.string.state_searching), getString(R.string.state_searching_sub));
    }

    private void connected(PcClient.Pc pc) {
        show(State.GOOD, getString(R.string.state_connected, pc.name), getString(R.string.state_address, pc.host));
    }

    private void showProblem(IOException error) {
        if (error instanceof PcClient.Refused) {
            show(State.BAD, getString(R.string.state_wrong_password), getString(R.string.state_wrong_password_sub));
            runOnUiThread(() -> showConnection(true));

            return;
        }
        if (error instanceof PcClient.NotProven) {
            show(State.BAD, getString(R.string.state_rejected), getString(R.string.state_rejected_sub));
            runOnUiThread(() -> showConnection(true));

            return;
        }

        show(State.BAD, getString(R.string.state_error), error.getClass().getSimpleName());
    }

    private void showHistory() {
        history.removeAllViews();
        LayoutInflater inflater = getLayoutInflater();
        JSONArray items = History.items(this);
        if (items.length() == 0) {
            TextView empty = new TextView(this);
            empty.setText(R.string.recent_empty);
            empty.setTextColor(getColor(R.color.muted));
            int padding = (int) (12 * getResources().getDisplayMetrics().density);
            empty.setPadding(padding, padding, padding, padding);
            history.addView(empty);

            return;
        }

        for (int index = 0; index < items.length(); index += 1) {
            JSONObject item = items.optJSONObject(index);
            if (item != null) {
                history.addView(historyRow(inflater, item));
            }
        }
    }

    private View historyRow(LayoutInflater inflater, JSONObject item) {
        View row = inflater.inflate(R.layout.history_row, history, false);
        String name = item.optString("name");
        ((TextView) row.findViewById(R.id.history_name)).setText(name);
        ((TextView) row.findViewById(R.id.history_kind)).setText(Names.kind(name));
        TextView meta = row.findViewById(R.id.history_meta);
        ImageView mark = row.findViewById(R.id.history_mark);
        if (item.isNull("error")) {
            CharSequence moment = DateUtils.getRelativeTimeSpanString(item.optLong("time"));
            long size = Math.max(item.optLong("size", 0), 0);
            meta.setText(Formatter.formatShortFileSize(this, size) + " · " + moment);
            mark.setImageResource(R.drawable.ic_check);
            mark.setImageTintList(ColorStateList.valueOf(getColor(R.color.good)));

            return row;
        }

        meta.setText(item.optString("error"));
        meta.setTextColor(getColor(R.color.bad));
        mark.setImageResource(R.drawable.ic_close);
        mark.setImageTintList(ColorStateList.valueOf(getColor(R.color.bad)));

        return row;
    }

    /** Checks the saved PC, or looks for one when there is none: opening the app is enough to pair. */
    private void refresh() {
        final PcClient.Pc saved = PairingStore.saved(this);
        if (saved == null) {
            pair(null, null, null, null);

            return;
        }

        searching();
        new Thread(() -> {
            try {
                PairingStore.connect(this, saved);
                connected(saved);
            } catch (IOException unreachable) {
                try {
                    PcClient.Pc moved = PcClient.discover(saved.fingerprint);
                    if (moved == null) {
                        throw unreachable;
                    }

                    PairingStore.connect(this, moved);
                    PairingStore.save(this, moved);
                    connected(moved);
                } catch (PcClient.Refused | PcClient.NotProven problem) {
                    showProblem(problem);
                } catch (IOException offline) {
                    show(State.BAD, getString(R.string.state_offline, saved.name),
                            getString(R.string.state_offline_sub));
                }
            }
        }).start();
    }

    private boolean handlePairLink(Intent intent, boolean fromScanner) {
        Uri data = intent.getData();
        PairLink link = data == null ? null : PairLink.parse(data.toString());
        if (link == null) {
            return false;
        }

        PcClient.Pc saved = PairingStore.saved(this);
        boolean samePc = saved != null && saved.fingerprint.equals(link.fingerprint);
        if (!PairLink.needsConfirmation(fromScanner, samePc)) {
            pair(link.host, link.port, link.fingerprint, link.key);

            return true;
        }

        int message = saved == null ? R.string.confirm_body_first : R.string.confirm_body;
        DialogInterface.OnClickListener accept =
                (dialog, button) -> pair(link.host, link.port, link.fingerprint, link.key);
        new AlertDialog.Builder(this)
                .setTitle(R.string.confirm_title)
                .setMessage(getString(message, link.host))
                .setPositiveButton(R.string.confirm_ok, accept)
                .setNegativeButton(R.string.confirm_no, (dialog, button) -> refresh())
                .setCancelable(false)
                .show();

        return true;
    }

    /**
     * host null = discovery; fingerprint null = read it from the PC, the proof vouches for it.
     * key is what the QR code carried; without it the secret is the password, or a key of the same PC.
     */
    private void pair(String givenHost, Integer givenPort, String givenFingerprint, String givenKey) {
        final String typed = password.getText().toString();
        PairingStore.savePassword(this, typed);
        searching();
        new Thread(() -> {
            try {
                PcClient.Pc pc = locate(givenHost, givenPort, givenFingerprint);
                if (pc == null) {
                    show(State.BAD, getString(R.string.state_not_found), getString(R.string.state_not_found_sub));

                    return;
                }

                authenticate(pc, givenKey, typed);
                PairingStore.save(this, pc);
                connected(pc);
                runOnUiThread(() -> {
                    showConnection(false);
                    showKeys();
                });
            } catch (IOException error) {
                showProblem(error);
            }
        }).start();
    }

    private static PcClient.Pc locate(String givenHost, Integer givenPort, String givenFingerprint)
            throws IOException {
        if (givenHost == null) {
            return PcClient.discover(null);
        }

        PcClient.Pc pc = new PcClient.Pc();
        pc.host = givenHost;
        pc.port = givenPort == null ? PcClient.DEFAULT_PORT : givenPort;
        pc.name = givenHost;
        pc.fingerprint = givenFingerprint == null ? PcClient.probeFingerprint(pc.host, pc.port) : givenFingerprint;

        return pc;
    }

    private void authenticate(PcClient.Pc pc, String givenKey, String typedPassword) throws IOException {
        PcClient.Pc saved = PairingStore.saved(this);
        boolean samePc = saved != null && saved.fingerprint.equals(pc.fingerprint);
        PairingPlan plan = PairingPlan.choose(givenKey != null, samePc);
        if (plan == PairingPlan.RECONNECT) {
            PairingStore.connect(this, pc);

            return;
        }

        String secret = plan == PairingPlan.ROTATE_WITH_LINK_KEY ? givenKey : typedPassword;
        PcClient.hello(pc, secret);
        PairingStore.rotateKey(this, pc, secret);
    }

    private void showKeys() {
        LinearLayout list = findViewById(R.id.keys);
        list.removeAllViews();
        JSONArray keys = PairingStore.keys(this);
        LayoutInflater inflater = getLayoutInflater();
        for (int index = 0; index < keys.length(); index += 1) {
            JSONObject key = keys.optJSONObject(index);
            boolean isCurrent = index == 0;
            TextView row = (TextView) inflater.inflate(R.layout.key_row, list, false);
            row.setText(getString(isCurrent ? R.string.key_current : R.string.key_old, key.optString("id"),
                    DateUtils.getRelativeTimeSpanString(key.optLong("time"))));
            row.setTextColor(getColor(isCurrent ? R.color.good : R.color.muted));
            list.addView(row);
        }
    }

    private void pickFiles() {
        if (PairingStore.saved(this) == null) {
            Toast.makeText(this, R.string.not_paired_toast, Toast.LENGTH_LONG).show();

            return;
        }

        PairingStore.savePassword(this, password.getText().toString());
        startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType("*/*")
                .putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true), PICK_FILES);
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (result != RESULT_OK || data == null) {
            return;
        }
        if (request == SCAN) {
            handlePairLink(data, true);

            return;
        }
        if (request == PICK_FILES) {
            UploadService.send(this, pickedFiles(data), null, null);
        }
    }

    private static List<Uri> pickedFiles(Intent data) {
        List<Uri> files = new ArrayList<>();
        if (data.getData() != null) {
            files.add(data.getData());
        }
        ClipData clip = data.getClipData();
        if (clip != null) {
            for (int index = 0; index < clip.getItemCount(); index += 1) {
                files.add(clip.getItemAt(index).getUri());
            }
        }

        return files;
    }
}
