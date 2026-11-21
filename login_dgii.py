#!/usr/bin/env python3
"""
Automatización del login en la Oficina Virtual (OFV) de la DGII - República Dominicana.

Flujo:
  1. Llena Usuario + Clave y hace clic en "Entrar" (BtnAceptar).
  2. Espera el campo "Tarjeta" (#ctl00_ContentPlaceHolder1_txtpasscodeTarjetaToken).
  3. Lee su atributo data-original-title ("Favor introducir el código número: 19 de su tarjeta"),
     extrae la posición, busca el código en tarjeta_dgii.json, lo escribe y hace clic en
     "Continuar" (BtnAceptarTarjetaToken).

Credenciales: variables de entorno o archivo .env (NUNCA en el código).
Uso:
    python login_dgii.py            # navegador visible
    python login_dgii.py --headless # sin ventana
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Al estar compilado con PyInstaller, el Chromium se empaqueta dentro de la
# propia carpeta del programa; esta variable le indica a Playwright que lo
# busque ahí (y no en AppData del equipo, donde no existirá).
if getattr(sys, "frozen", False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
else:
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

from dotenv import load_dotenv
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright

# --- Configuración -----------------------------------------------------------
# Compilado con PyInstaller, __file__ apunta a una carpeta temporal de extracción;
# por eso, si está "congelado", se usa la carpeta donde vive el .exe (ahí se
# colocan .env y tarjeta_dgii.json).
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
URL_LOGIN = "https://www.dgii.gov.do/OFV/login.aspx"

# Selectores (con alternativas por si la DGII cambia ligeramente los IDs)
SELECTORES_USUARIO = [
    "#ctl00_ContentPlaceHolder1_txtUsuario",
    "#ctl00_ContentPlaceHolder1_txtUserName",
    "input[id*='ContentPlaceHolder1'][id*='Usuario' i]",
    "input[id*='ContentPlaceHolder1'][id*='User' i]",
    "input[type='text'][name*='ContentPlaceHolder1']",
]
SELECTORES_CLAVE = [
    "#ctl00_ContentPlaceHolder1_txtPassword",
    "#ctl00_ContentPlaceHolder1_txtClave",
    "input[type='password'][id*='ContentPlaceHolder1']",
    "input[type='password']",
]
XPATH_BOTON_ENTRAR = '//*[@id="ctl00_ContentPlaceHolder1_BtnAceptar"]'
XPATH_BOTON_SALIR = '//*[@id="menus"]/li[5]/a'
XPATH_BOTON_CONTINUAR = '//*[@id="ctl00_ContentPlaceHolder1_BtnAceptarTarjetaToken"]'
SELECTOR_TARJETA = "#ctl00_ContentPlaceHolder1_txtpasscodeTarjetaToken"

# Regex: "Favor introducir el código número: 19 de su tarjeta"
REGEX_POSICION = re.compile(r"n[uú]mero\s*:?\s*(\d{1,3})", re.IGNORECASE)
REGEX_POSICION_RESPALDO = re.compile(r"(\d{1,3})")

TIMEOUT_MS = 30_000


class ErrorLoginDGII(Exception):
    """Error controlado del proceso de login (mensaje legible en español)."""


# --- Utilidades --------------------------------------------------------------
# La consola de Windows (cp1252) no puede imprimir emojis; se sustituyen por
# '?' en vez de provocar un fallo.
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")


_gancho_log = None  # la interfaz gráfica lo usa para mostrar el estado


def log(mensaje: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {mensaje}", flush=True)
    if _gancho_log:
        _gancho_log(mensaje)


def cargar_configuracion() -> tuple[str, str, Path]:
    load_dotenv(BASE_DIR / ".env")
    usuario = os.getenv("DGII_USUARIO", "").strip()
    clave = os.getenv("DGII_CLAVE", "")
    ruta_tarjeta = Path(os.getenv("DGII_TARJETA_JSON", "tarjeta_dgii.json")).expanduser()
    if not ruta_tarjeta.is_absolute():
        ruta_tarjeta = BASE_DIR / ruta_tarjeta

    if not usuario or not clave:
        raise ErrorLoginDGII(
            "Faltan credenciales. Defina DGII_USUARIO y DGII_CLAVE en el archivo .env "
            "(copie .env.example a .env) o como variables de entorno."
        )
    return usuario, clave, ruta_tarjeta


def cargar_tarjeta(ruta: Path) -> dict[str, str]:
    if not ruta.exists():
        raise ErrorLoginDGII(f"No se encontró el archivo de tarjeta: {ruta}")
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErrorLoginDGII(f"El archivo {ruta.name} no es un JSON válido: {e}") from e
    if not isinstance(datos, dict) or not datos:
        raise ErrorLoginDGII(f"{ruta.name} debe ser un objeto JSON {{\"1\": \"codigo\", ...}}.")

    # Normalizar claves ("01" -> "1") y valores a texto
    tarjeta = {str(int(k)): str(v).strip() for k, v in datos.items() if str(k).strip().isdigit()}

    # Aviso de permisos inseguros (solo en sistemas POSIX)
    es_posix = os.name == "posix"
    if es_posix and (ruta.stat().st_mode & 0o077):
        log(f"[AVISO] Permisos inseguros en {ruta.name}. Recomendado: chmod 600 {ruta.name}")
    return tarjeta


def extraer_posicion(texto: str) -> int:
    """Extrae el número de posición del texto del tooltip."""
    coincidencia = REGEX_POSICION.search(texto) or REGEX_POSICION_RESPALDO.search(texto)
    if not coincidencia:
        raise ErrorLoginDGII(f"No se pudo extraer el número de posición del texto: '{texto}'")
    return int(coincidencia.group(1))


def obtener_codigo(tarjeta: dict[str, str], posicion: int) -> str:
    codigo = tarjeta.get(str(posicion))
    if codigo is None:
        raise ErrorLoginDGII(f"La posición {posicion} no existe en el archivo de tarjeta.")
    if not codigo or set(codigo.upper()) == {"X"}:
        raise ErrorLoginDGII(
            f"La posición {posicion} todavía tiene el valor de ejemplo ('{codigo}'). "
            "Complete tarjeta_dgii.json con los códigos de su tarjeta física."
        )
    return codigo


async def primer_selector_visible(page: Page, selectores: list[str], descripcion: str):
    for selector in selectores:
        loc = page.locator(selector).first
        try:
            if await loc.count() and await loc.is_visible():
                return loc
        except PlaywrightError:
            continue
    raise ErrorLoginDGII(f"No se encontró el campo '{descripcion}' en la página de login.")


async def leer_texto_tooltip(page: Page) -> str:
    """Lee data-original-title del campo Tarjeta (con hover y alternativas por si viene vacío)."""
    campo = page.locator(SELECTOR_TARJETA)
    for _ in range(10):
        texto = await campo.get_attribute("data-original-title")
        if not texto:
            texto = await campo.get_attribute("title")
        if not texto:
            # El tooltip de Bootstrap a veces se inicializa al pasar el mouse
            try:
                await campo.hover(timeout=2_000)
            except PlaywrightError:
                pass
            # Respaldo: tooltip visible (sin depender de su ID dinámico)
            visible = page.locator(".tooltip .tooltip-inner").first
            if await visible.count():
                texto = (await visible.inner_text()).strip()
        if texto:
            return texto.strip()
        await page.wait_for_timeout(500)
    raise ErrorLoginDGII("El campo Tarjeta no tiene el texto 'data-original-title' con la posición solicitada.")


async def detectar_error_en_pagina(page: Page) -> str | None:
    """Busca mensajes de error visibles típicos de la OFV."""
    candidatos = page.locator(
        "[id*='lblMensaje'], [id*='lblError'], .alert-danger, .error, .validation-summary-errors"
    )
    for i in range(await candidatos.count()):
        el = candidatos.nth(i)
        try:
            if await el.is_visible():
                texto = (await el.inner_text()).strip()
                if texto:
                    return texto
        except PlaywrightError:
            continue
    return None


# --- Flujo principal ---------------------------------------------------------
async def probar_navegador() -> int:
    """Autoprueba: verifica que Chromium empaquetado inicie correctamente."""
    async with async_playwright() as p:
        navegador = await p.chromium.launch(headless=True)
        pagina = await navegador.new_page()
        await pagina.goto("about:blank")
        await navegador.close()
    log("[OK] Autoprueba superada: Chromium funciona en este equipo.")
    return 0


class Sesion:
    """Sesión de navegador abierta en la Oficina Virtual."""

    def __init__(self, playwright, navegador, contexto, page: Page) -> None:
        self.playwright = playwright
        self.navegador = navegador
        self.contexto = contexto
        self.page = page

    async def cerrar_navegador(self) -> None:
        try:
            await self.navegador.close()
        except PlaywrightError:
            pass
        try:
            await self.playwright.stop()
        except PlaywrightError:
            pass


async def iniciar_sesion(headless: bool) -> Sesion:
    """Hace el login completo y deja el navegador ABIERTO para que el usuario trabaje."""
    usuario, clave, ruta_tarjeta = cargar_configuracion()
    tarjeta = cargar_tarjeta(ruta_tarjeta)
    log(f"Tarjeta cargada: {len(tarjeta)} posiciones desde {ruta_tarjeta.name}")

    p = await async_playwright().start()
    navegador = None
    try:
        navegador = await p.chromium.launch(headless=headless)
        contexto = await navegador.new_context(locale="es-DO", viewport={"width": 1280, "height": 900})
        page = await contexto.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        # ---------------- Paso 0: abrir la página ----------------
        log(f"Abriendo {URL_LOGIN} ...")
        await page.goto(URL_LOGIN, wait_until="domcontentloaded")

        # ---------------- Paso 1: Usuario + Clave ----------------
        campo_usuario = await primer_selector_visible(page, SELECTORES_USUARIO, "Usuario")
        campo_clave = await primer_selector_visible(page, SELECTORES_CLAVE, "Clave")
        await campo_usuario.fill(usuario)
        await campo_clave.fill(clave)
        log("Usuario y clave ingresados.")

        campo_tarjeta = page.locator(SELECTOR_TARJETA)
        boton = page.locator(f"xpath={XPATH_BOTON_ENTRAR}")

        # Algunas versiones de la OFV muestran el campo Tarjeta desde el inicio.
        tarjeta_ya_visible = await campo_tarjeta.count() and await campo_tarjeta.is_visible()
        if not tarjeta_ya_visible:
            log("Haciendo clic en 'Entrar' (paso 1)...")
            await boton.click()
            try:
                await campo_tarjeta.wait_for(state="visible", timeout=TIMEOUT_MS)
            except PlaywrightTimeoutError:
                msg = await detectar_error_en_pagina(page)
                raise ErrorLoginDGII(
                    "No apareció el campo Tarjeta tras el paso 1. "
                    + (f"Mensaje de la DGII: '{msg}'" if msg else "Verifique usuario y clave.")
                )

        # ---------------- Paso 2: Tarjeta de coordenadas ----------------
        texto = await leer_texto_tooltip(page)
        log(f"Texto del tooltip: '{texto}'")
        posicion = extraer_posicion(texto)
        codigo = obtener_codigo(tarjeta, posicion)
        log(f"Posición solicitada: {posicion} → código encontrado (oculto: {'*' * len(codigo)}).")

        await campo_tarjeta.fill(codigo)

        log("Enviando formulario...")
        url_antes = page.url
        boton_continuar = page.locator(f"xpath={XPATH_BOTON_CONTINUAR}")
        if not await boton_continuar.count():
            boton_continuar = boton
        await boton_continuar.click()
        try:
            await page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
        except PlaywrightTimeoutError:
            log("[AVISO] La página tardó en estabilizarse; se continúa con la verificación.")

        # ---------------- Verificación ----------------
        error = await detectar_error_en_pagina(page)
        sigue_en_login = "login.aspx" in page.url.lower() and await campo_tarjeta.count() > 0
        if error or sigue_en_login:
            raise ErrorLoginDGII(
                "El login no se completó. "
                + (f"Mensaje de la DGII: '{error}'" if error else f"Se permanece en {url_antes}.")
            )

        log(f"[OK] Login exitoso. URL actual: {page.url}")
        return Sesion(p, navegador, contexto, page)

    except PlaywrightTimeoutError as e:
        await _limpiar(p, navegador)
        raise ErrorLoginDGII(f"Tiempo de espera agotado: {e}") from e
    except BaseException:
        await _limpiar(p, navegador)
        raise


async def _limpiar(p, navegador) -> None:
    if navegador is not None:
        try:
            await navegador.close()
        except PlaywrightError:
            pass
    try:
        await p.stop()
    except PlaywrightError:
        pass


async def salir_de_oficina_virtual(sesion: Sesion) -> None:
    """Pulsa 'Salir' en el menú de la OFV (XPATH_BOTON_SALIR) y cierra el navegador."""
    try:
        # El usuario puede haber abierto otras pestañas: se busca el menú en cualquiera.
        paginas = [pg for pg in reversed(sesion.contexto.pages) if not pg.is_closed()]
        salio = False
        for pg in paginas:
            enlace = pg.locator(f"xpath={XPATH_BOTON_SALIR}")
            if await enlace.count():
                log("Haciendo clic en 'Salir' de la Oficina Virtual...")
                await enlace.first.click(timeout=10_000)
                try:
                    await pg.wait_for_load_state("networkidle", timeout=10_000)
                except PlaywrightTimeoutError:
                    pass
                salio = True
                break
        if not salio:
            log("[AVISO] No se encontró el botón 'Salir' en la página actual; se cierra el navegador.")
    except PlaywrightError as e:
        log(f"[AVISO] No se pudo pulsar 'Salir': {e}")
    finally:
        await sesion.cerrar_navegador()
        log("Navegador cerrado.")


async def login(headless: bool) -> int:
    """Modo consola: login y espera a que el usuario cierre el navegador."""
    sesion = await iniciar_sesion(headless)
    if not headless:
        log("El navegador permanecerá abierto. Presione Ctrl+C para cerrar.")
        try:
            await sesion.page.wait_for_event("close", timeout=0)
        except (PlaywrightError, asyncio.CancelledError):
            pass
    await sesion.cerrar_navegador()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Login automático en la OFV de la DGII.")
    parser.add_argument("--headless", action="store_true", help="Ejecutar sin mostrar el navegador")
    parser.add_argument(
        "--probar-navegador",
        action="store_true",
        help="Solo verifica que Chromium inicie correctamente y sale",
    )
    args = parser.parse_args()
    if args.probar_navegador:
        sys.exit(asyncio.run(probar_navegador()))
    try:
        sys.exit(asyncio.run(login(args.headless)))
    except ErrorLoginDGII as e:
        log(f"[ERROR] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        log("Proceso interrumpido por el usuario.")
        sys.exit(130)
    except PlaywrightError as e:
        log(f"[ERROR] Error de Playwright: {e}")
        log("Sugerencia: ejecute 'playwright install chromium' si el navegador no está instalado.")
        sys.exit(1)


if __name__ == "__main__":
    main()
