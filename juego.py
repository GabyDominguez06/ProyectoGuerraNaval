import tkinter as tk
from tkinter import messagebox, simpledialog
import socket
import threading
import json
import queue

# ==========================================================
# GUERRA NAVAL
# Tablero 10x10 | Tkinter | Modo local y modo LAN (TCP)
# ==========================================================

TAM = 10
FLOTA = [
    ("Barco grande (2 x 6)", 2, 6),
    ("Barco pequeño 1 (2 casillas)", 1, 2),
    ("Barco pequeño 2 (2 casillas)", 1, 2),
    ("Barco mediano (4 casillas)", 1, 4),
    ("Barco largo (5 casillas)", 1, 5),
]


def posiciones_barco(fila, columna, alto, ancho):
    return {(fila + df, columna + dc)
            for df in range(alto) for dc in range(ancho)}


def tablero_vacio():
    return [[False for _ in range(TAM)] for _ in range(TAM)]


def posiciones_a_matriz(posiciones):
    matriz = tablero_vacio()
    for fila, columna in posiciones:
        matriz[fila][columna] = True
    return matriz


class Juego:
    """Reglas de la partida. El servidor controla la partida LAN."""

    def __init__(self, flotas):
        # flotas: lista con las posiciones de cada jugador
        self.barcos = [
            [set(tuple(p) for p in barco) for barco in flota]
            for flota in flotas
        ]
        self.disparos = [set(), set()]
        self.turno = 0
        self.ganador = None

    def atacar(self, jugador, fila, columna):
        if self.ganador is not None:
            return "La partida ya terminó."
        if jugador != self.turno:
            return "No es tu turno."
        if not (0 <= fila < TAM and 0 <= columna < TAM):
            return "Coordenada inválida."
        if (fila, columna) in self.disparos[jugador]:
            return "Esa casilla ya fue atacada."

        self.disparos[jugador].add((fila, columna))
        rival = 1 - jugador
        barco_impactado = next(
            (barco for barco in self.barcos[rival]
             if (fila, columna) in barco), None
        )

        if barco_impactado is None:
            resultado = "AGUA"
        elif barco_impactado.issubset(self.disparos[jugador]):
            resultado = "HUNDIDO"
        else:
            resultado = "TOCADO"

        posiciones_rival = set().union(*self.barcos[rival])
        if posiciones_rival.issubset(self.disparos[jugador]):
            self.ganador = jugador
        else:
            self.turno = rival

        return resultado

    def estado(self, jugador):
        propio = []
        rival = []
        rival_id = 1 - jugador
        barcos_propios = set().union(*self.barcos[jugador])
        barcos_rivales = set().union(*self.barcos[rival_id])

        for fila in range(TAM):
            fila_propia = []
            fila_rival = []
            for columna in range(TAM):
                p = (fila, columna)

                if p in self.disparos[rival_id]:
                    fila_propia.append("X" if p in barcos_propios else "o")
                elif p in barcos_propios:
                    fila_propia.append("B")
                else:
                    fila_propia.append("~")

                if p in self.disparos[jugador]:
                    fila_rival.append("X" if p in barcos_rivales else "o")
                else:
                    fila_rival.append("~")

            propio.append(fila_propia)
            rival.append(fila_rival)

        return {
            "propio": propio,
            "rival": rival,
            "turno": self.turno,
            "ganador": self.ganador,
        }


class ConexionServidor:
    """Servidor TCP: recibe flotas y ataques, y distribuye estados."""

    def __init__(self, eventos):
        self.eventos = eventos
        self.sock = None
        self.cliente = None
        self.lock = threading.Lock()
        self.flotas = [None, None]
        self.juego = None

    def iniciar(self):
        threading.Thread(target=self._escuchar, daemon=True).start()

    def _enviar_socket(self, sock, mensaje):
        datos = (json.dumps(mensaje) + "\n").encode("utf-8")
        with self.lock:
            sock.sendall(datos)

    def enviar_cliente(self, mensaje):
        if self.cliente:
            try:
                self._enviar_socket(self.cliente, mensaje)
            except OSError:
                self.eventos.put(("desconexion", None))

    def enviar_estados(self, resultado=None):
        for jugador in (0, 1):
            estado = self.juego.estado(jugador)
            if resultado is not None:
                estado["resultado"] = resultado
            if jugador == 0:
                self.eventos.put(("estado_local", estado))
            else:
                self.enviar_cliente({"tipo": "estado", "estado": estado})

    def _escuchar(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("0.0.0.0", 5000))
            self.sock.listen(1)
            self.eventos.put(("mensaje", "Esperando al jugador cliente en el puerto 5000..."))
            self.cliente, direccion = self.sock.accept()
            self.eventos.put(("conectado", direccion[0]))
            buffer = ""

            while True:
                datos = self.cliente.recv(4096)
                if not datos:
                    break
                buffer += datos.decode("utf-8")
                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    if not linea.strip():
                        continue
                    mensaje = json.loads(linea)
                    tipo = mensaje.get("tipo")

                    if tipo == "flota":
                        self.flotas[1] = mensaje["barcos"]
                        self.eventos.put(("flota_cliente", None))
                        self._comprobar_inicio()

                    elif tipo == "ataque":
                        if self.juego is None:
                            continue
                        resultado = self.juego.atacar(
                            1, int(mensaje["fila"]), int(mensaje["columna"])
                        )
                        self.enviar_estados(resultado)
        except OSError:
            self.eventos.put(("desconexion", None))
        except Exception as error:
            self.eventos.put(("error", str(error)))

    def enviar(self, mensaje):
        self.enviar_cliente(mensaje)

    def guardar_flota_servidor(self, barcos):
        self.flotas[0] = barcos
        self._comprobar_inicio()

    def _comprobar_inicio(self):
        if self.flotas[0] is not None and self.flotas[1] is not None:
            if self.juego is None:
                self.juego = Juego(self.flotas)
                self.eventos.put(("partida_iniciada", None))
                self.enviar_estados()


class ConexionCliente:
    """Cliente TCP: envía su flota y ataques y recibe estados."""

    def __init__(self, eventos):
        self.eventos = eventos
        self.sock = None
        self.lock = threading.Lock()

    def conectar(self, ip):
        threading.Thread(target=self._conectar, args=(ip,), daemon=True).start()

    def _conectar(self, ip):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((ip, 5000))
            self.eventos.put(("conectado", ip))
            buffer = ""

            while True:
                datos = self.sock.recv(4096)
                if not datos:
                    break
                buffer += datos.decode("utf-8")
                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    if linea.strip():
                        self.eventos.put(("mensaje_servidor", json.loads(linea)))
        except OSError as error:
            self.eventos.put(("error", f"No se pudo conectar: {error}"))

    def enviar(self, mensaje):
        if self.sock:
            try:
                datos = (json.dumps(mensaje) + "\n").encode("utf-8")
                with self.lock:
                    self.sock.sendall(datos)
            except OSError:
                self.eventos.put(("desconexion", None))


class GuerraNavalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Guerra Naval")
        self.root.geometry("940x760")
        self.root.minsize(800, 680)

        self.eventos = queue.Queue()
        self.modo = None
        self.jugador = 0
        self.juego = None
        self.servidor = None
        self.cliente = None

        self.barcos_colocados = []
        self.ocupadas = set()
        self.indice_barco = 0
        self.horizontal = True
        self.en_colocacion = False
        self.partida_lista = False
        self.estado_actual = None

        self.botones_propio = []
        self.botones_rival = []
        self.etiqueta_estado = None
        self.etiqueta_barco = None
        self.boton_giro = None

        self.mostrar_menu()
        self.root.after(100, self.procesar_eventos)

    def limpiar(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def mostrar_menu(self):
        self.limpiar()
        marco = tk.Frame(self.root, padx=30, pady=35)
        marco.pack(expand=True)

        tk.Label(marco, text="⚓ GUERRA NAVAL ⚓",
                 font=("Arial", 28, "bold"), fg="#173f5f").pack(pady=18)
        tk.Label(marco, text="Tablero 10 x 10",
                 font=("Arial", 15, "bold")).pack(pady=5)
        tk.Label(marco, text="Coloca tu flota y enfrenta a tu rival",
                 font=("Arial", 12)).pack(pady=10)

        tk.Button(marco, text="Jugar en la misma computadora",
                  width=34, height=2, command=self.iniciar_local).pack(pady=9)
        tk.Button(marco, text="Crear partida LAN (Servidor)",
                  width=34, height=2, command=self.crear_servidor).pack(pady=9)
        tk.Button(marco, text="Unirse a partida LAN (Cliente)",
                  width=34, height=2, command=self.unirse_servidor).pack(pady=9)

    def iniciar_local(self):
        self.modo = "local"
        self.jugador = 0
        self.reiniciar_colocacion()
        self.mostrar_colocacion()

    def crear_servidor(self):
        self.modo = "servidor"
        self.jugador = 0
        self.servidor = ConexionServidor(self.eventos)
        self.reiniciar_colocacion()
        self.mostrar_espera("Servidor iniciado. Esperando que se conecte el otro jugador...")
        self.servidor.iniciar()

    def unirse_servidor(self):
        ip = simpledialog.askstring("Unirse a partida", "Escribe la IP del servidor:")
        if not ip:
            return
        self.modo = "cliente"
        self.jugador = 1
        self.cliente = ConexionCliente(self.eventos)
        self.mostrar_espera("Conectando con el servidor...")
        self.cliente.conectar(ip.strip())

    def reiniciar_colocacion(self):
        self.barcos_colocados = []
        self.ocupadas = set()
        self.indice_barco = 0
        self.horizontal = True
        self.en_colocacion = True
        self.partida_lista = False
        self.estado_actual = None

    def mostrar_espera(self, texto):
        self.limpiar()
        marco = tk.Frame(self.root, padx=25, pady=40)
        marco.pack(expand=True)
        tk.Label(marco, text="⚓ GUERRA NAVAL",
                 font=("Arial", 24, "bold"), fg="#173f5f").pack(pady=15)
        self.etiqueta_estado = tk.Label(
            marco, text=texto, font=("Arial", 12), wraplength=650
        )
        self.etiqueta_estado.pack(pady=18)
        tk.Button(marco, text="Volver al menú",
                  command=self.mostrar_menu).pack(pady=12)

    def mostrar_colocacion(self):
        self.limpiar()
        cont = tk.Frame(self.root, padx=12, pady=10)
        cont.pack(expand=True)

        titulo = "COLOCACIÓN DE BARCOS"
        tk.Label(cont, text=titulo, font=("Arial", 22, "bold"),
                 fg="#173f5f").pack(pady=5)

        if self.modo == "local":
            jugador_txt = f"Jugador {self.jugador + 1}: coloca tu flota"
        elif self.modo == "servidor":
            jugador_txt = "Servidor (Jugador 1): coloca tu flota"
        else:
            jugador_txt = "Cliente (Jugador 2): coloca tu flota"
        tk.Label(cont, text=jugador_txt, font=("Arial", 12)).pack(pady=3)

        self.etiqueta_barco = tk.Label(cont, text="", font=("Arial", 12, "bold"))
        self.etiqueta_barco.pack(pady=7)

        controles = tk.Frame(cont)
        controles.pack(pady=4)
        self.boton_giro = tk.Button(
            controles, text="Girar barco: horizontal",
            command=self.girar_barco
        )
        self.boton_giro.pack(side="left", padx=5)
        tk.Label(controles, text="Haz clic en la casilla donde comienza el barco",
                 font=("Arial", 10)).pack(side="left", padx=5)

        self.tablero_colocacion = tk.Frame(cont, padx=8, pady=8)
        self.tablero_colocacion.pack()
        self.botones_colocacion = []

        tk.Label(self.tablero_colocacion, text="",
                 width=3).grid(row=0, column=0)
        for c in range(TAM):
            tk.Label(self.tablero_colocacion, text=str(c + 1),
                     width=4, font=("Arial", 9, "bold")).grid(row=0, column=c + 1)

        for f in range(TAM):
            tk.Label(self.tablero_colocacion, text=chr(65 + f),
                     width=3, font=("Arial", 9, "bold")).grid(row=f + 1, column=0)
            fila = []
            for c in range(TAM):
                boton = tk.Button(
                    self.tablero_colocacion, text="~", width=3, height=1,
                    bg="#d6eaf8", font=("Arial", 10, "bold"),
                    command=lambda x=f, y=c: self.colocar_barco(x, y)
                )
                boton.grid(row=f + 1, column=c + 1, padx=1, pady=1)
                fila.append(boton)
            self.botones_colocacion.append(fila)

        tk.Label(cont, text="Tu flota: 1 barco de 2x6, 2 barcos de 2, "
                 "1 barco de 4 y 1 barco de 5 casillas.",
                 font=("Arial", 9), fg="gray").pack(pady=7)
        tk.Button(cont, text="Volver al menú",
                  command=self.mostrar_menu).pack(pady=5)

        self.actualizar_instruccion()

    def actualizar_instruccion(self):
        if self.indice_barco < len(FLOTA):
            nombre, alto, ancho = FLOTA[self.indice_barco]
            if alto == 1:
                forma = f"{ancho} casillas en línea"
            else:
                forma = f"{alto} filas x {ancho} columnas"
                if not self.horizontal:
                    forma = f"{ancho} filas x {alto} columnas"
            self.etiqueta_barco.config(
                text=f"Barco {self.indice_barco + 1} de 5: {nombre} ({forma})"
            )
        else:
            self.etiqueta_barco.config(text="¡Flota completa!")

    def girar_barco(self):
        self.horizontal = not self.horizontal
        self.boton_giro.config(
            text="Girar barco: " + ("horizontal" if self.horizontal else "vertical")
        )
        self.actualizar_instruccion()

    def colocar_barco(self, fila, columna):
        if self.indice_barco >= len(FLOTA):
            return

        nombre, alto, ancho = FLOTA[self.indice_barco]
        if alto == 1:
            alto_real, ancho_real = (1, ancho) if self.horizontal else (ancho, 1)
        else:
            alto_real, ancho_real = (alto, ancho) if self.horizontal else (ancho, alto)

        if fila + alto_real > TAM or columna + ancho_real > TAM:
            messagebox.showwarning(
                "Ubicación no válida",
                "Ese barco se sale del tablero. Elige otra casilla de inicio."
            )
            return

        nuevas = posiciones_barco(fila, columna, alto_real, ancho_real)
        if nuevas & self.ocupadas:
            messagebox.showwarning(
                "Ubicación no válida",
                "Los barcos no pueden ocupar las mismas casillas."
            )
            return

        self.barcos_colocados.append(nuevas)
        self.ocupadas.update(nuevas)
        for f, c in nuevas:
            self.botones_colocacion[f][c].config(
                text="B", bg="#2878a5", fg="white", state="disabled"
            )

        self.indice_barco += 1
        self.actualizar_instruccion()

        if self.indice_barco == len(FLOTA):
            self.terminar_colocacion()

    def terminar_colocacion(self):
        self.en_colocacion = False
        barcos = [
            [[f, c] for f, c in sorted(barco)]
            for barco in self.barcos_colocados
        ]

        if self.modo == "local":
            if self.jugador == 0:
                self._barcos_jugador1 = barcos
                messagebox.showinfo(
                    "Flota lista",
                    "Jugador 1 terminó. Ahora le toca colocar sus barcos al Jugador 2."
                )
                self.jugador = 1
                self.reiniciar_colocacion()
                self.mostrar_colocacion()
            else:
                self.juego = Juego([self._barcos_jugador1, barcos])
                self.jugador = 0
                self.iniciar_partida_visual()
        elif self.modo == "servidor":
            self._barcos_jugador1 = barcos
            self.servidor.guardar_flota_servidor(barcos)
            self.mostrar_espera("Tu flota está lista. Esperando que el cliente coloque sus barcos...")
        elif self.modo == "cliente":
            self.cliente.enviar({"tipo": "flota", "barcos": barcos})
            self.mostrar_espera("Tu flota está lista. Esperando que el servidor inicie la partida...")

    def iniciar_partida_visual(self):
        self.partida_lista = True
        self.mostrar_juego()

    def mostrar_juego(self):
        self.limpiar()
        cont = tk.Frame(self.root, padx=10, pady=8)
        cont.pack(expand=True)

        tk.Label(cont, text="⚓ GUERRA NAVAL",
                 font=("Arial", 22, "bold"), fg="#173f5f").pack(pady=4)
        self.etiqueta_estado = tk.Label(cont, text="", font=("Arial", 12, "bold"))
        self.etiqueta_estado.pack(pady=6)

        tableros = tk.Frame(cont)
        tableros.pack(pady=4)
        izquierda = tk.Frame(tableros, padx=10)
        izquierda.grid(row=0, column=0)
        derecha = tk.Frame(tableros, padx=10)
        derecha.grid(row=0, column=1)

        tk.Label(izquierda, text="Mi tablero",
                 font=("Arial", 11, "bold")).grid(row=0, column=0, columnspan=TAM + 1)
        tk.Label(derecha, text="Tablero rival",
                 font=("Arial", 11, "bold")).grid(row=0, column=0, columnspan=TAM + 1)

        self.botones_propio = []
        self.botones_rival = []

        for c in range(TAM):
            tk.Label(izquierda, text=str(c + 1), width=3).grid(row=1, column=c + 1)
            tk.Label(derecha, text=str(c + 1), width=3).grid(row=1, column=c + 1)

        for f in range(TAM):
            tk.Label(izquierda, text=chr(65 + f), width=2).grid(row=f + 2, column=0)
            tk.Label(derecha, text=chr(65 + f), width=2).grid(row=f + 2, column=0)
            fila_p, fila_r = [], []
            for c in range(TAM):
                b1 = tk.Button(izquierda, text="~", width=3, height=1,
                               state="disabled", bg="#d6eaf8",
                               font=("Arial", 9, "bold"))
                b1.grid(row=f + 2, column=c + 1, padx=1, pady=1)
                fila_p.append(b1)

                b2 = tk.Button(derecha, text="~", width=3, height=1,
                               bg="#d6eaf8", font=("Arial", 9, "bold"),
                               command=lambda x=f, y=c: self.atacar(x, y))
                b2.grid(row=f + 2, column=c + 1, padx=1, pady=1)
                fila_r.append(b2)
            self.botones_propio.append(fila_p)
            self.botones_rival.append(fila_r)

        tk.Label(cont, text="B = barco | X = tocado | o = agua | ~ = sin revelar",
                 font=("Arial", 9), fg="gray").pack(pady=6)
        tk.Button(cont, text="Volver al menú",
                  command=self.mostrar_menu).pack(pady=5)

        if self.modo == "local":
            self.actualizar_vista(self.juego.estado(self.juego.turno))
        elif self.modo == "servidor" and self.servidor.juego:
            self.actualizar_vista(self.servidor.juego.estado(0))

    def atacar(self, fila, columna):
        if self.modo == "local":
            jugador_actual = self.juego.turno
            resultado = self.juego.atacar(jugador_actual, fila, columna)
            if resultado.startswith("No es") or resultado.startswith("Esa casilla") or resultado.startswith("Coordenada"):
                messagebox.showinfo("Guerra Naval", resultado)
                return
            estado = self.juego.estado(self.juego.turno if self.juego.ganador is None
                                       else jugador_actual)
            self.actualizar_vista(estado)
            if self.juego.ganador is not None:
                messagebox.showinfo("Fin de la partida",
                                    f"¡Ganó el Jugador {self.juego.ganador + 1}!")
                self.mostrar_menu()
            else:
                messagebox.showinfo("Resultado", resultado)
                # En el modo local ambos comparten pantalla; el tablero propio cambia
                # según el jugador al que le toca jugar.
                self.actualizar_vista(self.juego.estado(self.juego.turno))

        elif self.modo == "servidor":
            if self.servidor.juego is None:
                return
            if self.servidor.juego.turno != 0:
                messagebox.showinfo("Guerra Naval", "Es el turno del Jugador 2.")
                return
            resultado = self.servidor.juego.atacar(0, fila, columna)
            if resultado.startswith("No es") or resultado.startswith("Esa casilla") or resultado.startswith("Coordenada"):
                messagebox.showinfo("Guerra Naval", resultado)
                return
            self.servidor.enviar_estados(resultado)
            if self.servidor.juego.ganador is not None:
                messagebox.showinfo("Fin de la partida", "¡Ganaste!")
            else:
                messagebox.showinfo("Resultado", resultado)

        elif self.modo == "cliente":
            if self.estado_actual and self.estado_actual.get("turno") == 1:
                self.cliente.enviar({
                    "tipo": "ataque", "fila": fila, "columna": columna
                })
            else:
                messagebox.showinfo("Guerra Naval", "Espera tu turno.")

    def actualizar_vista(self, estado):
        self.estado_actual = estado
        colores = {
            "B": "#2878a5", "X": "#e74c3c",
            "o": "#d6eaf8", "~": "#f2f4f4"
        }

        for f in range(TAM):
            for c in range(TAM):
                valor = estado["propio"][f][c]
                self.botones_propio[f][c].config(
                    text=valor, bg=colores.get(valor, "white"),
                    fg="white" if valor == "B" else "black"
                )
                valor_rival = estado["rival"][f][c]
                self.botones_rival[f][c].config(
                    text=valor_rival, bg=colores.get(valor_rival, "white"),
                    fg="black"
                )

        ganador = estado.get("ganador")
        turno = estado.get("turno")
        if ganador is not None:
            texto = f"¡Fin de la partida! Ganador: Jugador {ganador + 1}"
        elif self.modo == "local":
            texto = f"Turno del Jugador {turno + 1}"
        elif self.modo == "servidor":
            texto = "Tu turno" if turno == 0 else "Turno del Jugador 2"
        else:
            texto = "Tu turno" if turno == 1 else "Turno del Jugador 1"
        self.etiqueta_estado.config(text=texto)

        puede_atacar = ganador is None and (
            (self.modo == "local") or
            (self.modo == "servidor" and turno == 0) or
            (self.modo == "cliente" and turno == 1)
        )
        for fila in self.botones_rival:
            for boton in fila:
                boton.config(state="normal" if puede_atacar else "disabled")

    def procesar_eventos(self):
        try:
            while True:
                tipo, dato = self.eventos.get_nowait()

                if tipo == "mensaje" and self.etiqueta_estado:
                    self.etiqueta_estado.config(text=dato)

                elif tipo == "conectado":
                    if self.modo == "servidor":
                        self.mostrar_colocacion()
                    elif self.modo == "cliente":
                        self.mostrar_colocacion()

                elif tipo == "flota_cliente":
                    if self.etiqueta_estado:
                        self.etiqueta_estado.config(
                            text="El cliente terminó de colocar su flota."
                        )

                elif tipo == "partida_iniciada" and self.modo == "servidor":
                    self.iniciar_partida_visual()

                elif tipo == "estado_local" and self.modo == "servidor":
                    if self.botones_propio:
                        self.actualizar_vista(dato)
                    if dato.get("ganador") is not None:
                        messagebox.showinfo(
                            "Fin de la partida",
                            f"Ganador: Jugador {dato['ganador'] + 1}"
                        )

                elif tipo == "mensaje_servidor" and self.modo == "cliente":
                    if dato.get("tipo") == "estado":
                        estado = dato["estado"]
                        if not self.botones_propio:
                            self.iniciar_partida_visual()
                        self.actualizar_vista(estado)
                        if estado.get("ganador") is not None:
                            messagebox.showinfo(
                                "Fin de la partida",
                                f"Ganador: Jugador {estado['ganador'] + 1}"
                            )

                elif tipo == "desconexion":
                    messagebox.showwarning(
                        "Conexión", "El otro jugador se desconectó."
                    )
                elif tipo == "error":
                    messagebox.showerror("Error", dato)

        except queue.Empty:
            pass

        self.root.after(100, self.procesar_eventos)


if __name__ == "__main__":
    ventana = tk.Tk()
    app = GuerraNavalApp(ventana)
    ventana.mainloop()
