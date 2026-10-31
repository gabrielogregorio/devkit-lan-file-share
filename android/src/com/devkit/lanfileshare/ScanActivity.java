package com.devkit.lanfileshare;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Matrix;
import android.graphics.SurfaceTexture;
import android.hardware.Camera;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.view.Gravity;
import android.view.TextureView;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import com.google.zxing.BinaryBitmap;
import com.google.zxing.DecodeHintType;
import com.google.zxing.PlanarYUVLuminanceSource;
import com.google.zxing.ReaderException;
import com.google.zxing.common.HybridBinarizer;
import com.google.zxing.qrcode.QRCodeReader;

import java.io.IOException;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/** Reads the pairing QR code with the camera and hands the link back to MainActivity. */
@SuppressWarnings("deprecation") // android.hardware.Camera: a fraction of the code camera2 needs for one preview
public class ScanActivity extends Activity implements TextureView.SurfaceTextureListener, Camera.PreviewCallback {
    private static final int ASK_CAMERA = 1;
    private static final int PREFERRED_PREVIEW_WIDTH = 1280;
    private static final int SUCCESS_VIBRATION_MS = 60;
    private static final Map<DecodeHintType, ?> HINTS = Collections.singletonMap(DecodeHintType.TRY_HARDER, true);

    private final QRCodeReader reader = new QRCodeReader();
    private TextureView preview;
    private TextView hint;
    private Camera camera;
    private HandlerThread decoderThread;
    private Handler decoder;
    private int width;
    private int height;
    private volatile boolean done;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        FrameLayout root = new FrameLayout(this);
        preview = new TextureView(this);
        preview.setSurfaceTextureListener(this);
        root.addView(preview);
        ScanOverlay overlay = new ScanOverlay(this);
        root.addView(overlay);

        float density = getResources().getDisplayMetrics().density;
        hint = new TextView(this);
        hint.setText(R.string.scan_hint);
        hint.setTextColor(0xFFFFFFFF);
        hint.setTextSize(15);
        hint.setGravity(Gravity.CENTER);
        hint.setPadding((int) (24 * density), 0, (int) (24 * density), 0);
        FrameLayout.LayoutParams hintPosition = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.TOP);
        root.addView(hint, hintPosition);
        overlay.addOnLayoutChangeListener((view, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom) ->
                hint.setY(overlay.windowBottom() + 24 * density));

        ImageView close = new ImageView(this);
        close.setImageResource(R.drawable.ic_close);
        close.setColorFilter(0xFFFFFFFF);
        close.setContentDescription(getString(R.string.confirm_no));
        int closePadding = (int) (14 * density);
        close.setPadding(closePadding, closePadding, closePadding, closePadding);
        close.setOnClickListener(view -> finish());
        int closeSize = (int) (52 * density);
        FrameLayout.LayoutParams corner = new FrameLayout.LayoutParams(closeSize, closeSize, Gravity.END);
        corner.topMargin = (int) (28 * density);
        root.addView(close, corner);
        setContentView(root);

        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, ASK_CAMERA);
        }
    }

    @Override
    public void onRequestPermissionsResult(int request, String[] names, int[] results) {
        if (results.length == 0 || results[0] != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, R.string.scan_denied, Toast.LENGTH_LONG).show();
            finish();

            return;
        }
        if (preview.isAvailable()) {
            startCamera();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        decoderThread = new HandlerThread("qr");
        decoderThread.start();
        decoder = new Handler(decoderThread.getLooper());
        if (preview.isAvailable()) {
            startCamera();
        }
    }

    @Override
    protected void onPause() {
        stopCamera();
        decoderThread.quitSafely();
        super.onPause();
    }

    @Override
    public void onSurfaceTextureAvailable(SurfaceTexture surface, int surfaceWidth, int surfaceHeight) {
        startCamera();
    }

    @Override
    public void onSurfaceTextureSizeChanged(SurfaceTexture surface, int surfaceWidth, int surfaceHeight) {
        fitPreview();
    }

    @Override
    public boolean onSurfaceTextureDestroyed(SurfaceTexture surface) {
        stopCamera();

        return true;
    }

    @Override
    public void onSurfaceTextureUpdated(SurfaceTexture surface) {
    }

    private void startCamera() {
        if (camera != null || decoder == null
                || checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            return;
        }

        try {
            camera = Camera.open();
            if (camera == null) {
                throw new IOException("no back camera");
            }
            Camera.Parameters parameters = camera.getParameters();
            Camera.Size size = bestSize(parameters.getSupportedPreviewSizes());
            width = size.width;
            height = size.height;
            parameters.setPreviewSize(width, height);
            if (parameters.getSupportedFocusModes().contains(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE)) {
                parameters.setFocusMode(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE);
            }
            camera.setParameters(parameters);
            camera.setDisplayOrientation(90);
            camera.setPreviewTexture(preview.getSurfaceTexture());
            camera.addCallbackBuffer(new byte[width * height * 3 / 2]);
            camera.setPreviewCallbackWithBuffer(this);
            camera.startPreview();
            fitPreview();
        } catch (IOException | RuntimeException cameraFailed) {
            stopCamera();
            Toast.makeText(this, R.string.scan_no_camera, Toast.LENGTH_LONG).show();
            finish();
        }
    }

    private void stopCamera() {
        if (camera != null) {
            camera.setPreviewCallbackWithBuffer(null);
            camera.stopPreview();
            camera.release();
            camera = null;
        }
    }

    private static Camera.Size bestSize(List<Camera.Size> sizes) {
        Camera.Size best = sizes.get(0);
        for (Camera.Size size : sizes) {
            if (Math.abs(size.width - PREFERRED_PREVIEW_WIDTH) < Math.abs(best.width - PREFERRED_PREVIEW_WIDTH)) {
                best = size;
            }
        }

        return best;
    }

    /** Center crop: the camera is rotated 90 degrees, so its width runs along the screen height. */
    private void fitPreview() {
        if (width == 0 || preview.getWidth() == 0) {
            return;
        }

        float scale = Math.max(preview.getWidth() / (float) height, preview.getHeight() / (float) width);
        Matrix matrix = new Matrix();
        matrix.setScale(height * scale / preview.getWidth(), width * scale / preview.getHeight(),
                preview.getWidth() / 2f, preview.getHeight() / 2f);
        preview.setTransform(matrix);
    }

    @Override
    public void onPreviewFrame(byte[] frame, Camera source) {
        final int frameWidth = width;
        final int frameHeight = height;
        decoder.post(() -> decode(frame, frameWidth, frameHeight, source));
    }

    private void decode(byte[] frame, int frameWidth, int frameHeight, Camera source) {
        String text = null;
        try {
            text = reader.decode(new BinaryBitmap(new HybridBinarizer(
                    new PlanarYUVLuminanceSource(frame, frameWidth, frameHeight, 0, 0, frameWidth, frameHeight,
                            false))), HINTS).getText();
        } catch (ReaderException noCodeInFrame) {
            reader.reset();
        }
        if (text != null && !done) {
            found(text);
        }
        if (!done && !isFinishing()) {
            runOnUiThread(() -> {
                if (camera == source) {
                    source.addCallbackBuffer(frame);
                }
            });
        }
    }

    private void found(String text) {
        if (PairLink.parse(text) == null) {
            runOnUiThread(() -> hint.setText(R.string.scan_wrong));

            return;
        }

        done = true;
        getSystemService(Vibrator.class).vibrate(
                VibrationEffect.createOneShot(SUCCESS_VIBRATION_MS, VibrationEffect.DEFAULT_AMPLITUDE));
        runOnUiThread(() -> {
            setResult(RESULT_OK, new Intent().setData(Uri.parse(text)));
            finish();
        });
    }
}
