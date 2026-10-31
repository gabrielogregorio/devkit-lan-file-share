package com.devkit.lanfileshare;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/** The entry in the share sheet: no screen, it hands what it got to the service and leaves. */
public class ShareActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        if (PairingStore.saved(this) == null) {
            Toast.makeText(this, R.string.not_paired_toast, Toast.LENGTH_LONG).show();
            startActivity(new Intent(this, MainActivity.class));
        } else {
            Intent intent = getIntent();
            CharSequence text = intent.getCharSequenceExtra(Intent.EXTRA_TEXT);
            UploadService.send(this, files(intent), text == null ? null : text.toString(),
                    intent.getStringExtra(Intent.EXTRA_SUBJECT));
        }
        finish();
    }

    private static List<Uri> files(Intent intent) {
        Set<Uri> uris = new LinkedHashSet<>();
        if (Intent.ACTION_SEND_MULTIPLE.equals(intent.getAction())) {
            List<Uri> list = streams(intent);
            if (list != null) {
                uris.addAll(list);
            }
        } else {
            Uri uri = stream(intent);
            if (uri != null) {
                uris.add(uri);
            }
        }
        ClipData clip = intent.getClipData();
        if (clip != null) {
            for (int index = 0; index < clip.getItemCount(); index += 1) {
                if (clip.getItemAt(index).getUri() != null) {
                    uris.add(clip.getItemAt(index).getUri());
                }
            }
        }

        return new ArrayList<>(uris);
    }

    @SuppressWarnings("deprecation")
    private static Uri stream(Intent intent) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            return intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri.class);
        }

        return intent.getParcelableExtra(Intent.EXTRA_STREAM);
    }

    @SuppressWarnings("deprecation")
    private static List<Uri> streams(Intent intent) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            return intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri.class);
        }

        return intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
    }
}
