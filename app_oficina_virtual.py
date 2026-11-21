"""Ventana "Iniciar Sesión Oficina Virtual" (DGII).

- Botón "Iniciar": abre el navegador, hace el login automático y lo deja abierto
  (el usuario trabaja el tiempo que necesite: declaraciones, trámites, consultas...).
- Botón "Salir": pulsa "Salir" en el menú de la Oficina Virtual y cierra el navegador.

Con argumentos de línea de comandos (--headless, --probar-navegador) se comporta
como la versión de consola.
"""
import asyncio
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import login_dgii

TITULO = "Iniciar Sesión Oficina Virtual"


def recurso(nombre: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    ruta = base / "recursos" / nombre
    if not ruta.exists():  # ejecutando desde el código fuente
        ruta = Path(__file__).resolve().parent / "recursos" / nombre
    return ruta


class Aplicacion:
    ANCHO, ALTO = 520, 300

    def __init__(self) -> None:
        self.sesion: login_dgii.Sesion | None = None
        self.ocupado = False

        # Bucle asyncio en un hilo aparte (Playwright) para no congelar la ventana
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()

        self.root = tk.Tk()
        self.root.title(TITULO)
        self.root.resizable(False, False)
        try:
            self.root.iconbitmap(str(recurso("app.ico")))
        except tk.TclError:
            pass
        x = (self.root.winfo_screenwidth() - self.ANCHO) // 2
        y = (self.root.winfo_screenheight() - self.ALTO) // 2
        self.root.geometry(f"{self.ANCHO}x{self.ALTO}+{x}+{y}")

        lienzo = tk.Canvas(self.root, width=self.ANCHO, height=self.ALTO, highlightthickness=0)
        lienzo.pack()
        self.fondo = tk.PhotoImage(file=str(recurso("fondo.png")))
        lienzo.create_image(0, 0, image=self.fondo, anchor="nw")
        lienzo.create_text(
            self.ANCHO // 2, 55, text=TITULO, fill="white", font=("Segoe UI", 20, "bold")
        )
        lienzo.create_text(
            self.ANCHO // 2, 92, text="Dirección General de Impuestos Internos",
            fill="#cfe3f7", font=("Segoe UI", 10),
        )

        estilo = dict(font=("Segoe UI", 12, "bold"), width=12, bd=0, cursor="hand2", pady=6)
        self.btn_iniciar = tk.Button(
            self.root, text="Iniciar", bg="#2eb85c", fg="white", activebackground="#27a050",
            activeforeground="white", command=self.al_iniciar, **estilo,
        )
        self.btn_salir = tk.Button(
            self.root, text="Salir", bg="#d9534f", fg="white", activebackground="#c9302c",
            activeforeground="white", command=self.al_salir, **estilo,
        )
        lienzo.create_window(170, 160, window=self.btn_iniciar)
        lienzo.create_window(350, 160, window=self.btn_salir)

        self.estado = lienzo.create_text(
            self.ANCHO // 2, 235, text="Pulse «Iniciar» para entrar a la Oficina Virtual.",
            fill="white", font=("Segoe UI", 10), width=470, justify="center",
        )
        self.lienzo = lienzo
        login_dgii._gancho_log = lambda m: self.root.after(0, self.mostrar, m)
        self.root.protocol("WM_DELETE_WINDOW", self.al_salir)

    # ---- utilidades de interfaz -------------------------------------------
    def mostrar(self, texto: str) -> None:
        self.lienzo.itemconfig(self.estado, text=texto)

    def poner_ocupado(self, ocupado: bool) -> None:
        self.ocupado = ocupado
        self.btn_iniciar.config(state="disabled" if (ocupado or self.sesion) else "normal")
        self.btn_salir.config(state="disabled" if ocupado else "normal")

    def ejecutar(self, corutina, al_terminar) -> None:
        futuro = asyncio.run_coroutine_threadsafe(corutina, self.loop)
        futuro.add_done_callback(lambda f: self.root.after(0, al_terminar, f))

    # ---- acciones ----------------------------------------------------------
    def al_iniciar(self) -> None:
        self.poner_ocupado(True)
        self.mostrar("Iniciando sesión, por favor espere...")
        self.ejecutar(login_dgii.iniciar_sesion(headless=False), self.fin_inicio)

    def fin_inicio(self, futuro) -> None:
        try:
            self.sesion = futuro.result()
        except login_dgii.ErrorLoginDGII as e:
            self.sesion = None
            self.mostrar("No se pudo iniciar sesión.")
            messagebox.showerror(TITULO, str(e))
        except Exception as e:  # noqa: BLE001
            self.sesion = None
            self.mostrar("Error inesperado al iniciar sesión.")
            messagebox.showerror(TITULO, f"{type(e).__name__}: {e}")
        else:
            self.mostrar(
                "Sesión iniciada. Trabaje en el navegador; cuando termine pulse «Salir»."
            )
            self.sesion.navegador.on(
                "disconnected", lambda *_: self.root.after(0, self.navegador_cerrado)
            )
        self.poner_ocupado(False)

    def navegador_cerrado(self) -> None:
        """El usuario cerró el navegador manualmente."""
        if self.sesion and not self.ocupado:
            self.sesion = None
            self.mostrar("El navegador se cerró. Pulse «Iniciar» para volver a entrar.")
            self.poner_ocupado(False)

    def al_salir(self) -> None:
        if not self.sesion:
            self.root.destroy()
            return
        self.poner_ocupado(True)
        self.mostrar("Cerrando sesión en la Oficina Virtual...")
        sesion, self.sesion = self.sesion, None
        self.ejecutar(login_dgii.salir_de_oficina_virtual(sesion), self.fin_salida)

    def fin_salida(self, _futuro) -> None:
        self.mostrar("Sesión cerrada. Puede pulsar «Iniciar» o cerrar esta ventana.")
        self.poner_ocupado(False)

    def correr(self) -> None:
        self.root.mainloop()


def main() -> None:
    if len(sys.argv) > 1:  # modo consola (--headless, --probar-navegador, ...)
        login_dgii.main()
        return
    Aplicacion().correr()


if __name__ == "__main__":
    main()
