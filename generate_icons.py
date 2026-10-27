"""予約アプリ用のPWAアイコンを生成する開発用スクリプト。"""

from pathlib import Path

from PIL import Image, ImageDraw

ICON_DIR = Path(__file__).resolve().parent / "static" / "icons"
GREEN = (22, 163, 74, 255)
GREEN_DARK = (21, 128, 61, 255)
WHITE = (255, 255, 255, 255)


def draw_car(draw: ImageDraw.ImageDraw, size: int, scale: float = 1.0) -> None:
    center = size / 2
    unit = size * scale

    body_left = center - unit * 0.36
    body_right = center + unit * 0.36
    body_top = center + unit * 0.02
    body_bottom = center + unit * 0.2
    draw.rounded_rectangle(
        (body_left, body_top, body_right, body_bottom),
        radius=unit * 0.08,
        fill=WHITE,
    )

    roof_top = center - unit * 0.24
    roof = [
        (center - unit * 0.24, body_top),
        (center - unit * 0.15, roof_top),
        (center + unit * 0.16, roof_top),
        (center + unit * 0.26, body_top),
    ]
    draw.polygon(roof, fill=WHITE)

    window = [
        (center - unit * 0.18, body_top - unit * 0.02),
        (center - unit * 0.11, roof_top + unit * 0.04),
        (center + unit * 0.11, roof_top + unit * 0.04),
        (center + unit * 0.19, body_top - unit * 0.02),
    ]
    draw.polygon(window, fill=GREEN)

    wheel_radius = unit * 0.09
    for x in (center - unit * 0.24, center + unit * 0.24):
        draw.ellipse(
            (
                x - wheel_radius,
                body_bottom - wheel_radius,
                x + wheel_radius,
                body_bottom + wheel_radius,
            ),
            fill=GREEN_DARK,
        )
        inner = wheel_radius * 0.45
        draw.ellipse(
            (x - inner, body_bottom - inner, x + inner, body_bottom + inner),
            fill=WHITE,
        )


def create_icon(size: int, path: Path, maskable: bool = False) -> None:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    padding = int(size * 0.14) if maskable else 0
    radius = int(size * (0.5 if maskable else 0.22))
    draw.rounded_rectangle(
        (padding, padding, size - padding, size - padding),
        radius=radius,
        fill=GREEN,
    )
    draw_car(draw, size, scale=0.78 if maskable else 1.0)
    image.save(path, format="PNG")


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    create_icon(192, ICON_DIR / "icon-192.png")
    create_icon(512, ICON_DIR / "icon-512.png")
    create_icon(512, ICON_DIR / "icon-maskable-512.png", maskable=True)
    create_icon(180, ICON_DIR / "apple-touch-icon.png")
    print(f"アイコンを生成しました: {ICON_DIR}")


if __name__ == "__main__":
    main()
