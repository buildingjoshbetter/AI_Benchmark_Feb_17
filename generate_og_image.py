#!/usr/bin/env python3
"""Generate an OG image for Twitter/social sharing."""

from PIL import Image, ImageDraw, ImageFont
import os

WIDTH, HEIGHT = 1200, 630
BG = (9, 9, 11)
SURFACE = (17, 17, 20)
BORDER = (39, 39, 42)
TEXT = (228, 228, 231)
DIM = (113, 113, 122)
ACCENT_PURPLE = (124, 106, 255)
ACCENT_GREEN = (74, 240, 192)
ACCENT_PINK = (255, 106, 138)

OUTPUT = os.path.join(os.path.dirname(__file__), "report", "og-image.png")


def get_font(size, bold=False):
    """Try to load Inter or fall back to system fonts."""
    candidates = [
        "/System/Library/Fonts/SFPro-Bold.otf" if bold else "/System/Library/Fonts/SFPro-Regular.otf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def main():
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # Fonts
    font_title = get_font(52, bold=True)
    font_subtitle = get_font(22)
    font_label = get_font(16)
    font_stat_big = get_font(44, bold=True)
    font_stat_unit = get_font(18)
    font_footer = get_font(16)
    font_models = get_font(15)

    # Title
    title = "AI Model Benchmark"
    draw.text((60, 45), title, font=font_title, fill=ACCENT_GREEN)

    # Subtitle
    subtitle = "7 models  ·  30 tasks  ·  every raw output published"
    draw.text((60, 110), subtitle, font=font_subtitle, fill=DIM)

    # Divider line
    draw.line([(60, 155), (WIDTH - 60, 155)], fill=BORDER, width=1)

    # Three stat cards
    card_y = 180
    card_h = 160
    card_w = 330
    gap = 35
    cards = [
        ("$0.72/M", "tokens", "Qwen 3.5 (Open Source)", ACCENT_GREEN),
        ("vs", "", "", DIM),
        ("$75/M", "tokens", "Claude Opus 4.6", ACCENT_PINK),
    ]

    x = 60
    for stat, unit, label, color in cards:
        if stat == "vs":
            # Draw "vs" centered in a smaller space
            vs_x = x + 10
            draw.text((vs_x, card_y + 50), "vs", font=font_stat_big, fill=DIM)
            x += 80
            continue

        draw_rounded_rect(draw, (x, card_y, x + card_w, card_y + card_h),
                          radius=12, fill=SURFACE, outline=BORDER, width=1)

        draw.text((x + 24, card_y + 20), stat, font=font_stat_big, fill=color)
        if unit:
            # Get stat text width to position unit after it
            bbox = draw.textbbox((0, 0), stat, font=font_stat_big)
            stat_w = bbox[2] - bbox[0]
            draw.text((x + 24 + stat_w + 8, card_y + 42), unit, font=font_stat_unit, fill=DIM)
        if label:
            draw.text((x + 24, card_y + 85), label, font=font_label, fill=DIM)
            # Model type badge
            if "Open" in label:
                badge_text = "OPEN SOURCE"
                badge_color = ACCENT_GREEN
            else:
                badge_text = "CLOSED"
                badge_color = ACCENT_PINK
            draw.text((x + 24, card_y + 115), badge_text, font=font_label, fill=badge_color)

        x += card_w + gap

    # Bottom section - task categories
    cat_y = 370
    draw.text((60, cat_y), "BENCHMARK TASKS", font=font_label, fill=DIM)

    cats = [
        ("10 Code Tasks", "REST APIs, React components, parsers, WebSocket servers"),
        ("7 Design Tasks", "Landing pages, dashboards, chat UIs, data tables"),
        ("10 Research Tasks", "Deep analysis, comparisons, frameworks, second-order effects"),
    ]

    cy = cat_y + 30
    for cat_title, cat_desc in cats:
        draw.text((60, cy), "●", font=font_label, fill=ACCENT_PURPLE)
        draw.text((82, cy), cat_title, font=get_font(17, bold=True), fill=TEXT)
        draw.text((82, cy + 24), cat_desc, font=font_models, fill=DIM)
        cy += 58

    # All 7 model names on the right side
    model_y = cat_y
    draw.text((700, model_y), "MODELS TESTED", font=font_label, fill=DIM)
    models = [
        ("Qwen 3.5 397B (Open)", ACCENT_GREEN),
        ("Qwen 3.5 Plus (Hosted)", ACCENT_GREEN),
        ("Claude Sonnet 4.5", ACCENT_PURPLE),
        ("Claude Sonnet 4.6", ACCENT_PURPLE),
        ("Claude Opus 4.5", ACCENT_PURPLE),
        ("Claude Opus 4.6", ACCENT_PURPLE),
        ("Gemini 2.5 Pro", (66, 133, 244)),
    ]
    my = model_y + 30
    for name, color in models:
        draw.text((700, my), "●", font=font_label, fill=color)
        draw.text((722, my), name, font=font_models, fill=TEXT)
        my += 26

    # Footer
    draw.line([(60, HEIGHT - 60), (WIDTH - 60, HEIGHT - 60)], fill=BORDER, width=1)
    draw.text((60, HEIGHT - 45), "ai-benchmark-2026.vercel.app", font=font_footer, fill=ACCENT_GREEN)
    draw.text((WIDTH - 250, HEIGHT - 45), "by @Building_Josh", font=font_footer, fill=DIM)

    img.save(OUTPUT, "PNG", quality=95)
    print(f"OG image saved: {OUTPUT} ({os.path.getsize(OUTPUT):,} bytes)")


if __name__ == "__main__":
    main()
