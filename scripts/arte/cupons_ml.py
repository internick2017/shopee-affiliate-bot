"""Gera o infografico "Como pegar os cupons do Mercado Livre" para o grupo da Lanny.

Amarelo do Mercado Livre + verde do avatar do grupo. Uso:
    python scripts/arte/cupons_ml.py [saida.png]

Os assets (logo ML recortado da referencia e o avatar da Lanny) vem de assets/.
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
REF = ASSETS / "WhatsApp Image 2026-10-10 at 09.23.19.jpeg"
AVATAR = ASSETS / "lanny-avatar-mercadolivre.png"
FONTS = Path("C:/Windows/Fonts")

S = 2  # supersampling
W, H = 1080, 1440

YELLOW = (255, 230, 0)
YELLOW_LIGHT = (255, 244, 130)
NAVY = (45, 50, 119)
PINK = (255, 61, 127)
GREEN = (200, 233, 168)
GREEN_MID = (150, 208, 100)
GREEN_DARK = (74, 122, 42)
WHITE = (255, 255, 255)

STEPS = [
    "Entrem no **aplicativo do Mercado Livre**.",
    "Procurem a **área de cupons** ou cliquem no **link** que eu mandar aqui no grupo.",
    "Quando o cupom aparecer, cliquem em **“Ativar cupom”** ou **“Pegar cupom”**.",
    "Prontinho! Agora é só **escolher o produto** e conferir se o **desconto apareceu** antes de pagar.",
]
WARNING = ("**Atenção:** Alguns cupons acabam rápido! Fiquem de olho nos horários "
           "e ativem o cupom assim que ele for liberado.")


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size * S)


def px(v):
    return int(v * S)


def key_out_yellow(img):
    """Torna transparente o fundo amarelo do logo; deixa azul e branco opacos."""
    img = img.convert("RGBA")
    data = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, _ = data[x, y]
            t = ((r + g) / 2 - b - 90) / 60
            t = max(0.0, min(1.0, t))
            a = int(255 * (1 - t))
            if r > 190 and g < 130 and b > 70 and r - g > 90:  # tracos rosa da referencia
                a = 0
            data[x, y] = (r, g, b, a)
    return img


def clear_box(img, x0, y0):
    """Apaga (alpha 0) tudo a partir de (x0, y0): sobras do texto vizinho da referencia."""
    data = img.load()
    for y in range(y0, img.height):
        for x in range(x0, img.width):
            r, g, b, _ = data[x, y]
            data[x, y] = (r, g, b, 0)
    return img


def wrap(draw, text, fnt, fnt_bold, max_w):
    words = []  # (palavra, negrito, colada_na_anterior)
    parts = text.split("**")
    for i, part in enumerate(parts):
        bold = i % 2 == 1
        prev_open = i > 0 and not parts[i - 1][-1:].isspace()
        for j, w in enumerate(part.split()):
            glued = j == 0 and prev_open and not part[:1].isspace()
            words.append((w, bold, glued))
    lines, cur, cur_w = [], [], 0
    space = fnt.getlength(" ")
    for w, bold, glued in words:
        f = fnt_bold if bold else fnt
        ww = f.getlength(w)
        sp = 0 if (glued or not cur) else space
        if cur and not glued and cur_w + sp + ww > max_w:
            lines.append(cur)
            cur, cur_w, sp = [], 0, 0
        cur_w += sp + ww
        cur.append((w, bold, glued))
    if cur:
        lines.append(cur)
    return lines


def draw_rich(draw, x, y, lines, fnt, fnt_bold, color, bold_color, line_h):
    space = fnt.getlength(" ")
    for line in lines:
        cx = x
        for k, (w, bold, glued) in enumerate(line):
            f = fnt_bold if bold else fnt
            if k and not glued:
                cx += space
            draw.text((cx, y), w, font=f, fill=bold_color if bold else color)
            cx += f.getlength(w)
        y += line_h
    return y


def heart(draw, cx, cy, size, fill):
    r = size * 0.27
    draw.ellipse((cx - size * 0.5, cy - size * 0.45, cx - size * 0.5 + 2 * r + size * 0.04, cy - size * 0.45 + 2 * r), fill=fill)
    draw.ellipse((cx + size * 0.5 - 2 * r - size * 0.04, cy - size * 0.45, cx + size * 0.5, cy - size * 0.45 + 2 * r), fill=fill)
    draw.polygon([(cx - size * 0.48, cy - size * 0.1), (cx + size * 0.48, cy - size * 0.1), (cx, cy + size * 0.5)], fill=fill)


def sparkle(draw, cx, cy, size, fill):
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rad = size if i % 2 == 0 else size * 0.28
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    draw.polygon(pts, fill=fill)


def shadowed_card(base, box, radius, fill, border=None, border_w=0):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    d.rounded_rectangle((x0, y0 + px(8), x1, y1 + px(8)), radius, fill=(60, 50, 0, 70))
    layer = layer.filter(ImageFilter.GaussianBlur(px(9)))
    base.alpha_composite(layer)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle(box, radius, fill=fill, outline=border, width=border_w)


def build(out_path):
    img = Image.new("RGBA", (px(W), px(H)), YELLOW)
    d = ImageDraw.Draw(img)

    d.rectangle((0, 0, px(W), px(14)), fill=GREEN_MID)
    d.rectangle((0, px(14), px(W), px(20)), fill=GREEN_DARK)

    # faixa verde do grupo no pe da arte
    d.rectangle((0, px(H - 26), px(W), px(H)), fill=GREEN_MID)
    d.rectangle((0, px(H - 26), px(W), px(H - 20)), fill=GREEN_DARK)

    # logo do Mercado Livre (recortado da referencia)
    ref = Image.open(REF).convert("RGB")
    # o oval e o texto sao recortados por separado para nao arrastrar o "ja liberados" de baixo
    oval = key_out_yellow(ref.crop((45, 143, 246, 282)))
    word = clear_box(key_out_yellow(ref.crop((262, 143, 580, 262))), 158, 100)
    oval = clear_box(oval, 185, 125)
    logo = Image.new("RGBA", (535, 139), (0, 0, 0, 0))
    logo.alpha_composite(oval, (0, 0))
    logo.alpha_composite(word, (217, 0))
    lw = 520
    logo = logo.resize((px(lw), int(px(lw) * logo.height / logo.width)), Image.LANCZOS)
    img.alpha_composite(logo, (px(48), px(75)))

    # avatar da Lanny dentro de um circulo
    av = Image.open(AVATAR).convert("RGB").crop((20, 20, 780, 780)).resize((px(230), px(230)), Image.LANCZOS)
    mask = Image.new("L", av.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, av.width - 1, av.height - 1), fill=255)
    ring = px(8)
    ax, ay = px(W - 48 - 230), px(40)
    d.ellipse((ax - ring, ay - ring, ax + av.width + ring, ay + av.height + ring), fill=WHITE)
    img.paste(av, (ax, ay), mask)
    d = ImageDraw.Draw(img)

    # decoracao
    sparkle(d, px(640), px(75), px(26), PINK)
    sparkle(d, px(585), px(215), px(15), PINK)
    sparkle(d, px(60), px(270), px(18), PINK)

    # banner rosa com o titulo
    shadowed_card(img, (px(40), px(300), px(W - 40), px(500)), px(44), PINK)
    d = ImageDraw.Draw(img)
    f_t1 = font("seguibl.ttf", 66)
    for txt, y in (("COMO PEGAR OS CUPONS", 312), ("DO MERCADO LIVRE?", 400)):
        tw = f_t1.getlength(txt)
        d.text(((px(W) - tw) / 2, px(y)), txt, font=f_t1, fill=WHITE)

    # subtitulo
    f_sub = font("segoescb.ttf", 54)
    sub = "É muito fácil, olha só!"
    sw = f_sub.getlength(sub)
    sx = (px(W) - sw) / 2
    d.text((sx, px(512)), sub, font=f_sub, fill=NAVY)
    heart(d, sx - px(46), px(548), px(34), PINK)
    heart(d, sx + sw + px(46), px(548), px(34), PINK)

    # passos
    f_txt, f_bold = font("segoeui.ttf", 34), font("segoeuib.ttf", 34)
    f_num = font("seguibl.ttf", 52)
    card_h, gap, y0 = 140, 16, 610
    for i, step in enumerate(STEPS):
        y = y0 + i * (card_h + gap)
        shadowed_card(img, (px(50), px(y), px(W - 50), px(y + card_h)), px(34), WHITE)
        d = ImageDraw.Draw(img)
        cx, cy, r = 50 + 28 + 48, y + card_h / 2, 48
        d.ellipse((px(cx - r), px(cy - r), px(cx + r), px(cy + r)), fill=GREEN, outline=GREEN_DARK, width=px(5))
        n = str(i + 1)
        nw = f_num.getlength(n)
        d.text((px(cx) - nw / 2, px(cy) - px(36)), n, font=f_num, fill=NAVY)
        lines = wrap(d, step, f_txt, f_bold, px(W - 50 - 50 - 170 - 20))
        th = len(lines) * px(44)
        draw_rich(d, px(190), px(y + card_h / 2) - th / 2, lines, f_txt, f_bold, NAVY, NAVY, px(44))

    # aviso
    wy0, wy1 = 1240, 1392
    shadowed_card(img, (px(50), px(wy0), px(W - 50), px(wy1)), px(34), GREEN, GREEN_DARK, px(4))
    d = ImageDraw.Draw(img)
    tx, ty, ts = 50 + 26 + 44, (wy0 + wy1) / 2, 44
    d.polygon([(px(tx), px(ty - ts)), (px(tx + ts * 1.1), px(ty + ts * 0.8)), (px(tx - ts * 1.1), px(ty + ts * 0.8))],
              fill=YELLOW, outline=NAVY)
    d.line([(px(tx), px(ty - ts)), (px(tx + ts * 1.1), px(ty + ts * 0.8)), (px(tx - ts * 1.1), px(ty + ts * 0.8)), (px(tx), px(ty - ts))],
           fill=NAVY, width=px(5), joint="curve")
    f_ex = font("seguibl.ttf", 44)
    ew = f_ex.getlength("!")
    d.text((px(tx) - ew / 2, px(ty) - px(30)), "!", font=f_ex, fill=NAVY)
    f_w, f_wb = font("segoeui.ttf", 30), font("segoeuib.ttf", 30)
    lines = wrap(d, WARNING, f_w, f_wb, px(W - 50 - 50 - 170 - 10))
    th = len(lines) * px(40)
    draw_rich(d, px(180), px(ty) - th / 2, lines, f_w, f_wb, NAVY, NAVY, px(40))

    out = img.convert("RGB").resize((W, H), Image.LANCZOS)
    out.save(out_path, quality=95)
    return out_path


if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "assets" / "cupons-ml-lanny.png")
    print(build(dest))
