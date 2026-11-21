"""Genera los iconos e imágenes del programa en la carpeta recursos/.

Uso:  python crear_recursos.py
Crea: app.ico (acceso directo), instalador.ico, fondo.png (ventana), bienvenida.bmp (asistente).
"""
from pathlib import Path

from PIL import Image, ImageDraw

SALIDA = Path(__file__).resolve().parent / "recursos"
SALIDA.mkdir(exist_ok=True)

AZUL_OSCURO = (10, 42, 94)
AZUL_CLARO = (41, 128, 205)
BLANCO = (255, 255, 255)
VERDE = (46, 184, 92)


def degradado(ancho: int, alto: int, arriba=AZUL_OSCURO, abajo=AZUL_CLARO) -> Image.Image:
    img = Image.new("RGB", (ancho, alto))
    d = ImageDraw.Draw(img)
    for y in range(alto):
        t = y / max(alto - 1, 1)
        d.line([(0, y), (ancho, y)], fill=tuple(int(arriba[i] + (abajo[i] - arriba[i]) * t) for i in range(3)))
    return img


def edificio(d: ImageDraw.ImageDraw, x: int, y: int, s: int, color=BLANCO) -> None:
    """Edificio con frontón y columnas (estilo oficina pública) dentro de un cuadro s x s."""
    u = s / 100
    d.polygon([(x + 50 * u, y + 8 * u), (x + 92 * u, y + 34 * u), (x + 8 * u, y + 34 * u)], fill=color)
    for i in range(4):
        cx = x + (18 + i * 21) * u
        d.rectangle([cx, y + 40 * u, cx + 11 * u, y + 76 * u], fill=color)
    d.rectangle([x + 8 * u, y + 80 * u, x + 92 * u, y + 90 * u], fill=color)


def icono(base: Image.Image, insignia: str) -> Image.Image:
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    fondo = degradado(s, s).convert("RGBA")
    mascara = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, s - 1, s - 1], radius=48, fill=255)
    img.paste(fondo, (0, 0), mascara)
    d = ImageDraw.Draw(img)
    edificio(d, 28, 20, 200)
    # Insignia inferior derecha
    d.ellipse([140, 140, 244, 244], fill=VERDE, outline=BLANCO, width=6)
    if insignia == "flecha":  # instalador: flecha hacia abajo
        d.rectangle([180, 160, 204, 196], fill=BLANCO)
        d.polygon([(158, 192), (226, 192), (192, 226)], fill=BLANCO)
    else:  # acceso: marca de verificación
        d.line([(160, 194), (186, 218), (228, 164)], fill=BLANCO, width=16, joint="curve")
    return img


icono(None, "flecha").save(SALIDA / "instalador.ico", sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
icono(None, "check").save(SALIDA / "app.ico", sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])

# Fondo de la ventana principal (520 x 300)
fondo = degradado(520, 300)
d = ImageDraw.Draw(fondo, "RGBA")
edificio(d, 285, 50, 200, color=(255, 255, 255, 38))
d.ellipse([-80, 190, 200, 470], fill=(255, 255, 255, 22))
fondo.save(SALIDA / "fondo.png")

# Imagen lateral del asistente de instalación (164 x 314, BMP de 24 bits)
lateral = degradado(164, 314)
d = ImageDraw.Draw(lateral, "RGBA")
edificio(d, 22, 90, 120)
d.ellipse([-60, 220, 120, 400], fill=(255, 255, 255, 25))
lateral.save(SALIDA / "bienvenida.bmp")
print("Recursos creados en", SALIDA)
