package com.devkit.lanfileshare;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Shader;
import android.view.View;

/** The dimmed camera with a clear window, brand corners and a line sweeping across. */
final class ScanOverlay extends View {
    private static final int BRAND = 0xFF2F80ED;
    private static final int BRAND_END = 0xFF14B8A6;
    private static final int CORNERS = 4;
    private final Paint dim = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint corner = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint sweep = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path shade = new Path();
    private final Path bracket = new Path();
    private final RectF window = new RectF();
    private final float density;
    private ValueAnimator animator;
    private float phase;

    ScanOverlay(Context context) {
        super(context);
        density = getResources().getDisplayMetrics().density;
        dim.setColor(Color.argb(170, 0, 0, 0));
        corner.setStyle(Paint.Style.STROKE);
        corner.setStrokeWidth(5 * density);
        corner.setStrokeCap(Paint.Cap.ROUND);
    }

    @Override
    protected void onSizeChanged(int width, int height, int oldWidth, int oldHeight) {
        float side = Math.min(width, height) * 0.72f;
        float top = (height - side) * 0.42f;
        window.set((width - side) / 2, top, (width + side) / 2, top + side);
        shade.reset();
        shade.setFillType(Path.FillType.EVEN_ODD);
        shade.addRect(0, 0, width, height, Path.Direction.CW);
        shade.addRoundRect(window, 20 * density, 20 * density, Path.Direction.CW);
        corner.setShader(new LinearGradient(window.left, window.top, window.right, window.bottom,
                BRAND, BRAND_END, Shader.TileMode.CLAMP));
        sweep.setShader(new LinearGradient(window.left, 0, window.right, 0,
                new int[]{0, BRAND_END, 0}, null, Shader.TileMode.CLAMP));
    }

    @Override
    protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        animator = ValueAnimator.ofFloat(0f, 1f);
        animator.setDuration(1800);
        animator.setRepeatCount(ValueAnimator.INFINITE);
        animator.setRepeatMode(ValueAnimator.REVERSE);
        animator.addUpdateListener(update -> {
            phase = (float) update.getAnimatedValue();
            invalidate();
        });
        animator.start();
    }

    @Override
    protected void onDetachedFromWindow() {
        animator.cancel();
        super.onDetachedFromWindow();
    }

    float windowBottom() {
        return window.bottom;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        canvas.drawPath(shade, dim);
        float sweepY = window.top + 12 * density + phase * (window.height() - 24 * density);
        canvas.drawRect(window.left + 8 * density, sweepY - density, window.right - 8 * density, sweepY + density,
                sweep);
        float arm = 34 * density;
        float radius = 20 * density;
        for (int cornerIndex = 0; cornerIndex < CORNERS; cornerIndex += 1) {
            canvas.save();
            canvas.rotate(cornerIndex * 90, window.centerX(), window.centerY());
            bracket.reset();
            bracket.moveTo(window.left, window.top + arm);
            bracket.lineTo(window.left, window.top + radius);
            bracket.quadTo(window.left, window.top, window.left + radius, window.top);
            bracket.lineTo(window.left + arm, window.top);
            canvas.drawPath(bracket, corner);
            canvas.restore();
        }
    }
}
