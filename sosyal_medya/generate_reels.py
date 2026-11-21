"""Generate 1080x1920 vertical frames for the 3-second redos-lint Reels clip."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from tempfile import gettempdir

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import BashLexer
from pygments.token import Token

WIDTH, HEIGHT = 1080, 1920
OUTPUT = Path(gettempdir()) / "opencode" / "redos-lint-reels"
MARGIN = 84

BG_TOP = (7, 10, 16)
BG_BOTTOM = (18, 26, 38)
WHITE = "#EAF6FF"
MUTED = "#7E93A8"
RED = "#FB7185"
CYAN = "#22D3EE"
GREEN = "#4ADE80"
YELLOW = "#FBBF24"

FONT_MONO = Path("/usr/share/fonts/noto/NotoSansMono-Regular.ttf")
FONT_MONO_BOLD = Path("/usr/share/fonts/noto/NotoSansMono-Bold.ttf")
FONT_SANS_BOLD = Path("/usr/share/fonts/liberation/LiberationSans-Bold.ttf")
FONT_SANS = Path("/usr/share/fonts/liberation/LiberationSans-Regular.ttf")

CODE_COLORS = [
    (Token.Comment, "#64748B"),
    (Token.Keyword, "#C792EA"),
    (Token.Name.Builtin, "#F78C6C"),
    (Token.Name.Function, "#82AAFF"),
    (Token.String, "#C3E88D"),
    (Token.Number, "#F78C6C"),
    (Token.Operator, CYAN),
    (Token.Punctuation, "#94A3B8"),
    (Token.Text, WHITE),
]


@lru_cache(maxsize=64)
def font(size: int, *, mono: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    if mono:
        path = FONT_MONO_BOLD if bold else FONT_MONO
    else:
        path = FONT_SANS_BOLD if bold else FONT_SANS
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def rgb(value: str) -> tuple[int, int, int]:
    raw = value.lstrip("#")
    return tuple(int(raw[index : index + 2], 16) for index in (0, 2, 4))


def base(accent: str, index: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG_TOP)
    draw = ImageDraw.Draw(image, "RGBA")
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        color = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * ratio) for i in range(3))
        draw.line([(0, y), (WIDTH, y)], fill=(*color, 255))
    for x in range(0, WIDTH, 72):
        draw.line([(x, 0), (x, HEIGHT)], fill=(255, 255, 255, 6))
    for y in range(0, HEIGHT, 72):
        draw.line([(0, y), (WIDTH, y)], fill=(255, 255, 255, 6))
    glow = rgb(accent)
    for radius in range(460, 0, -12):
        alpha = int((1 - radius / 460) ** 2 * 26)
        draw.ellipse(
            [WIDTH - 80 - radius, -120 - radius, WIDTH - 80 + radius, -120 + radius],
            fill=(*glow, alpha),
        )
    draw.text(
        (MARGIN, 90), "BAYSOZ LABS // OPEN SOURCE", font=font(28, mono=True, bold=True), fill=MUTED
    )
    draw.line([(MARGIN, 150), (WIDTH - MARGIN, 150)], fill=(*glow, 110), width=3)
    draw.line([(MARGIN, 1790), (WIDTH - MARGIN, 1790)], fill=(255, 255, 255, 40), width=2)
    draw.text((MARGIN, 1822), "@yazilimbaysoz", font=font(27), fill=MUTED)
    draw.text(
        (WIDTH - MARGIN, 1822),
        f"{index}/3",
        font=font(28, mono=True, bold=True),
        fill=accent,
        anchor="ra",
    )
    return image, draw


def code(
    draw: ImageDraw.ImageDraw, source: str, x: int, y: int, lexer: object, size: int = 26
) -> int:
    text_font = font(size, mono=True)
    for line in source.splitlines():
        cursor = x
        for ttype, value in lex(line, lexer):
            value = value.replace("\n", "").replace("\r", "").expandtabs(4)
            if not value:
                continue
            color = WHITE
            name = str(ttype)
            for base, candidate in CODE_COLORS:
                if name.startswith(str(base)):
                    color = candidate
                    break
            draw.text((cursor, y), value, font=text_font, fill=color)
            cursor += draw.textlength(value, font=text_font)
        y += 42
    return y


def hook() -> Image.Image:
    image, draw = base(RED, 1)
    draw.text((MARGIN, 300), "DUR!", font=font(150, bold=True), fill=RED)
    draw.text((MARGIN, 520), "BU REGEX", font=font(104, bold=True), fill=WHITE)
    draw.text((MARGIN, 680), "SERVİSİNİ", font=font(104, bold=True), fill=WHITE)
    draw.text((MARGIN, 840), "ÇÖKERTİR.", font=font(104, bold=True), fill=RED)
    draw.rounded_rectangle(
        [MARGIN, 1070, WIDTH - MARGIN, 1250],
        radius=24,
        fill=(18, 26, 37, 245),
        outline=(*rgb(RED), 180),
        width=3,
    )
    draw.text((MARGIN + 34, 1110), "^(a+)+$", font=font(52, mono=True, bold=True), fill=YELLOW)
    draw.text((MARGIN + 34, 1180), "30 karakter  ->  03:12 incident", font=font(30), fill=MUTED)
    draw.text((MARGIN, 1390), "3 saniyede çözüm:", font=font(40, bold=True), fill=CYAN)
    draw.text(
        (MARGIN, 1470), "redos-lint  //  ReDoS dedektörü", font=font(38, mono=True), fill=GREEN
    )
    return image


def detection() -> Image.Image:
    image, draw = base(CYAN, 2)
    draw.text((MARGIN, 300), "PATTERN'İ", font=font(100, bold=True), fill=WHITE)
    draw.text((MARGIN, 450), "ÇALIŞTIRMADAN", font=font(100, bold=True), fill=WHITE)
    draw.text((MARGIN, 600), "BULUR.", font=font(100, bold=True), fill=CYAN)
    draw.rounded_rectangle(
        [MARGIN, 830, WIDTH - MARGIN, 1360],
        radius=26,
        fill=(7, 11, 17, 250),
        outline=(*rgb(CYAN), 150),
        width=3,
    )
    draw.text((MARGIN + 32, 870), "terminal", font=font(24, mono=True), fill=MUTED)
    code(
        draw,
        "$ redos-lint check '^(a+)+$'\n[CRITICAL] nested-quantifier\nfix: ^a{1,64}$\nexit 1",
        MARGIN + 32,
        960,
        BashLexer(),
    )
    draw.text(
        (MARGIN, 1440), "AST -> heuristic rules -> file:line", font=font(32, mono=True), fill=YELLOW
    )
    draw.text((MARGIN, 1510), "Sıfır bağımlılık. Tamamen çevrimdışı.", font=font(32), fill=GREEN)
    return image


def call_to_action() -> Image.Image:
    image, draw = base(GREEN, 3)
    draw.text((MARGIN, 320), "CI'DA KIRMIZI,", font=font(96, bold=True), fill=WHITE)
    draw.text((MARGIN, 470), "PROD'DA SESSİZ.", font=font(96, bold=True), fill=GREEN)
    draw.rounded_rectangle(
        [MARGIN, 760, WIDTH - MARGIN, 1180],
        radius=26,
        fill=(7, 11, 17, 250),
        outline=(*rgb(GREEN), 160),
        width=3,
    )
    code(
        draw,
        "$ uv tool install redos-lint\n"
        "$ redos-lint scan . --fail-on high\n"
        "0 risky regex  --  exit 0",
        MARGIN + 32,
        860,
        BashLexer(),
    )
    draw.text((MARGIN, 1300), "github.com/yazilimbaysoz-svg/", font=font(36, mono=True), fill=CYAN)
    draw.text((MARGIN, 1350), "redos-lint", font=font(48, mono=True, bold=True), fill=GREEN)
    draw.text((MARGIN, 1520), "Bir yıldız, bir incident az.", font=font(46, bold=True), fill=WHITE)
    return image


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for index, builder in enumerate((hook, detection, call_to_action), start=1):
        frame = builder()
        target = OUTPUT / f"frame_{index:02d}.png"
        frame.save(target, format="PNG", optimize=True)
        print(target)


if __name__ == "__main__":
    main()
