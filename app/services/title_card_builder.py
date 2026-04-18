import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.config import get_settings


class TitleCardBuilder:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.backend_root = Path(__file__).resolve().parents[2]

    def build(self, title_text: str = "", tiktok_handle: str = "") -> Path:
        card_width = 900
        card_height = 400
        corner_radius = 30
        shadow_offset = 15

        image_width = card_width + shadow_offset * 2
        image_height = card_height + shadow_offset * 2

        image = Image.new("RGBA", (image_width, image_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        draw.rounded_rectangle(
            [
                shadow_offset + 8,
                shadow_offset + 8,
                card_width + shadow_offset + 8,
                card_height + shadow_offset + 8,
            ],
            radius=corner_radius,
            fill=(0, 0, 0, 120),
        )
        draw.rounded_rectangle(
            [
                shadow_offset,
                shadow_offset,
                card_width + shadow_offset,
                card_height + shadow_offset,
            ],
            radius=corner_radius,
            fill=(255, 255, 255, 240),
        )

        pfp_radius = 25
        pfp_center_x = shadow_offset + 30 + pfp_radius
        pfp_center_y = shadow_offset + 30 + pfp_radius
        draw.ellipse(
            [
                pfp_center_x - pfp_radius,
                pfp_center_y - pfp_radius,
                pfp_center_x + pfp_radius,
                pfp_center_y + pfp_radius,
            ],
            fill="black",
        )

        title_font = self._load_font(
            self.settings.title_font_path,
            self.settings.title_font_size,
        )
        handle_font = self._load_font(
            self.settings.handle_font_path,
            self.settings.handle_font_size,
        )

        handle_x = shadow_offset + 100
        handle_y = shadow_offset + 36
        draw.text(
            (handle_x, handle_y),
            tiktok_handle or self.settings.tiktok_handle,
            fill=(0, 0, 0, 255),
            font=handle_font,
        )

        wrapped_title = self._wrap_text(
            draw,
            title_text,
            title_font,
            max_width=card_width - 90,
        )
        title_box_left = shadow_offset + 45
        title_box_top = shadow_offset + 110
        title_box_right = shadow_offset + card_width - 45
        title_box_bottom = shadow_offset + card_height - 30
        title_bbox = draw.multiline_textbbox(
            (0, 0),
            wrapped_title,
            font=title_font,
            align="center",
            spacing=8,
        )
        text_w = title_bbox[2] - title_bbox[0]
        text_h = title_bbox[3] - title_bbox[1]
        text_x = title_box_left + max(0, (title_box_right - title_box_left - text_w) / 2)
        text_y = title_box_top + max(0, (title_box_bottom - title_box_top - text_h) / 2)
        draw.multiline_text(
            (text_x, text_y),
            wrapped_title,
            fill=(0, 0, 0, 255),
            font=title_font,
            align="center",
            spacing=8,
        )

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        temp_file.close()
        path = Path(temp_file.name)
        image.save(path)
        return path

    def _load_font(self, path: str | None, size: int) -> ImageFont.ImageFont:
        for font_path in self._font_candidates(path):
            if font_path.exists():
                try:
                    return ImageFont.truetype(str(font_path), size)
                except OSError:
                    continue
        try:
            return ImageFont.truetype("arial.ttf", size)
        except OSError:
            pass
        return ImageFont.load_default()

    def _font_candidates(self, explicit_path: str | None) -> list[Path]:
        candidates: list[Path] = []
        if explicit_path:
            candidates.append(Path(explicit_path))

        candidates.extend(
            [
                self.backend_root / "fonts" / "LuckiestGuy-Regular.ttf",
                self.backend_root / "assets" / "fonts" / "LuckiestGuy-Regular.ttf",
                Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts" / "LuckiestGuy-Regular.ttf",
                Path("C:/Windows/Fonts/LuckiestGuy-Regular.ttf"),
                Path("C:/Windows/Fonts/LuckiestGuy.ttf"),
            ]
        )
        return candidates

    @staticmethod
    def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
        words = (text or "").strip().split()
        if not words:
            return ""
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            bbox = draw.textbbox((0, 0), candidate, font=font)
            width = bbox[2] - bbox[0]
            if width <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return "\n".join(lines[:4])
