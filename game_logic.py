"""
game_logic.py
Logica del juego Guerra Naval
Lo usan juego.py (modo local), server.py y client.py (modo LAN).
las secciones son:
  1. Constantes
  2. Coordenadas
  3. Tablero 
  4. Dibujo en consola
  5. Entrada del usuario 
  6. Comunicacion por socket 
"""
import os
import random

#Constantes
TAMANO = 10
# Simbolos de cada casilla
AGUA = "~"      # casilla sin explorar
BARCO = "B"     # parte de un barco (solo visible en tu propio tablero)
TOCADO = "X"    # barco impactado
FALLO = "o"     # disparo al agua
HUNDIDO = "#"   # barco completamente hundido
# Resultados de un disparo
RES_AGUA = "AGUA"
RES_TOCADO = "TOCADO"
RES_HUNDIDO = "HUNDIDO"
# Flota de cada jugador: (nombre, tamaño)
FLOTA = [
    ("Portaaviones", 5),
    ("Acorazado", 4),
    ("Crucero", 3),
    ("Submarino", 3),
    ("Destructor", 2),
]
PUERTO = 5000
SEP = ";"  # separador de campos en los mensajes de red
#Coordenadas
def parse_coordenada(texto):
    """Convierte 'B7' o '2,7' en (fila, col) con indices desde 0.
    Devuelve None si el texto no es una coordenada valida."""
    t = texto.strip().upper().replace(" ", "")
    try:
        if "," in t:
            f, c = t.split(",")
            fila, col = int(f) - 1, int(c) - 1
        else:
            fila, col = ord(t[0]) - ord("A"), int(t[1:]) - 1
    except (ValueError, IndexError):
        return None
    if 0 <= fila < TAMANO and 0 <= col < TAMANO:
        return fila, col
    return None

def etiqueta(fila, col):
    """(1, 6) -> 'B7' (para mostrar al jugador)."""
    return f"{chr(ord('A') + fila)}{col + 1}"

def a_texto_red(fila, col):
    """(2, 4) -> '3,5' (formato fila,columna del protocolo, desde 1)."""
    return f"{fila + 1},{col + 1}"
#Tablero
class Tablero:
    """Tablero de un jugador: guarda sus barcos y los disparos recibidos."""

    def __init__(self):
        self.limpiar()

    def limpiar(self):
        self.celdas = [[AGUA for _ in range(TAMANO)] for _ in range(TAMANO)]
        self.barcos = []       # lista de dicts con los datos de cada barco
        self.disparos = set()  # casillas (fila, col) ya atacadas

    def colocar_barco(self, nombre, tam, fila, col, horizontal):
        """Coloca un barco si cabe y no se cruza con otro. True si se pudo."""
        celdas = [(fila, col + i) if horizontal else (fila + i, col) for i in range(tam)]
        for f, c in celdas:
            if not (0 <= f < TAMANO and 0 <= c < TAMANO) or self.celdas[f][c] != AGUA:
                return False
        for f, c in celdas:
            self.celdas[f][c] = BARCO
        self.barcos.append({
            "nombre": nombre, "tam": tam, "fila": fila, "col": col,
            "horizontal": horizontal, "celdas": celdas, "tocadas": set(),
        })
        return True

    def colocar_aleatorio(self):
        """Coloca toda la flota en posiciones aleatorias validas."""
        self.limpiar()
        for nombre, tam in FLOTA:
            while True:
                if self.colocar_barco(nombre, tam, random.randrange(TAMANO),
                                      random.randrange(TAMANO), random.choice([True, False])):
                    break

    def recibir_disparo(self, fila, col):
        """Procesa un disparo y devuelve RES_AGUA, RES_TOCADO o RES_HUNDIDO.
        Lanza ValueError si la coordenada es invalida o ya fue atacada."""
        if not (0 <= fila < TAMANO and 0 <= col < TAMANO):
            raise ValueError("Coordenada fuera del tablero.")
        if (fila, col) in self.disparos:
            raise ValueError("Esa casilla ya fue atacada.")
        self.disparos.add((fila, col))

        if self.celdas[fila][col] != BARCO:
            self.celdas[fila][col] = FALLO
            return RES_AGUA
        self.celdas[fila][col] = TOCADO
        for barco in self.barcos:
            if (fila, col) in barco["celdas"]:
                barco["tocadas"].add((fila, col))
                if len(barco["tocadas"]) == barco["tam"]:
                    for f, c in barco["celdas"]:
                        self.celdas[f][c] = HUNDIDO
                    return RES_HUNDIDO
                break
        return RES_TOCADO

    def todos_hundidos(self):
        return bool(self.barcos) and all(len(b["tocadas"]) == b["tam"] for b in self.barcos)

    def codificar(self, ocultar_barcos):
        """Tablero como texto de 100 caracteres (fila por fila).
        Con ocultar_barcos=True no revela donde hay barcos sin tocar."""
        texto = "".join("".join(fila) for fila in self.celdas)
        return texto.replace(BARCO, AGUA) if ocultar_barcos else texto

    def serializar_flota(self):
        """Posicion de los barcos como texto, para enviarla por la red."""
        return ",".join(
            f"{b['nombre']}:{b['fila']}:{b['col']}:{'H' if b['horizontal'] else 'V'}"
            for b in self.barcos
        )
    @classmethod
    def desde_flota(cls, texto):
        """Reconstruye un tablero desde serializar_flota().
        Devuelve None si la flota es invalida (el servidor no confia en el cliente)."""
        esperado = dict(FLOTA)
        tablero = cls()
        vistos = set()
        try:
            for item in texto.split(","):
                nombre, fila, col, ori = item.split(":")
                if nombre not in esperado or nombre in vistos or ori not in ("H", "V"):
                    return None
                vistos.add(nombre)
                if not tablero.colocar_barco(nombre, esperado[nombre], int(fila), int(col), ori == "H"):
                    return None
        except ValueError:
            return None
        return tablero if len(vistos) == len(esperado) else None

#Dibujo en consola
def limpiar_pantalla():
    os.system("cls" if os.name == "nt" else "clear")

def dibujar_codigo(codigo):
    """Convierte un tablero codificado (100 caracteres) en lineas de texto."""
    lineas = ["    " + "".join(f"{c + 1:<3}" for c in range(TAMANO))]
    for f in range(TAMANO):
        fila = codigo[f * TAMANO:(f + 1) * TAMANO]
        lineas.append(f"{chr(ord('A') + f)}   " + "".join(f"{ch:<3}" for ch in fila))
    return lineas

def mostrar_tablero(codigo):
    for linea in dibujar_codigo(codigo):
        print(linea)

def mostrar_tableros(codigo_propio, codigo_rival):
    """Muestra tu flota y la del enemigo lado a lado."""
    izq, der = dibujar_codigo(codigo_propio), dibujar_codigo(codigo_rival)
    print()
    print("TU FLOTA".ljust(38) + "FLOTA ENEMIGA")
    for a, b in zip(izq, der):
        print(a.ljust(38) + b)
    print(f"{BARCO}=barco  {TOCADO}=tocado  {HUNDIDO}=hundido  {FALLO}=fallo  {AGUA}=sin explorar")

def describir_jugada(resultado, atacante, fila, col):
    frases = {RES_AGUA: "agua", RES_TOCADO: "¡TOCADO!", RES_HUNDIDO: "¡HUNDIDO!"}
    verbo = "disparaste" if atacante == "Tu" else "disparo"
    return f"{atacante} {verbo} a {etiqueta(fila, col)}: {frases[resultado]}"

#Entrada del usuario
def pedir_nombre(mensaje):
    nombre = input(mensaje).strip().replace(SEP, "")
    return nombre or "Jugador"

def pedir_coordenada(mensaje, bloqueadas=None):
    """Pide una coordenada hasta que sea valida y no este en 'bloqueadas'."""
    bloqueadas = bloqueadas or set()
    while True:
        coord = parse_coordenada(input(f"{mensaje} (ej. B7 o 2,7): "))
        if coord is None:
            print("Coordenada invalida. Usa una letra A-J y un numero 1-10, o fila,columna.")
        elif coord in bloqueadas:
            print("Ya atacaste esa casilla. Elige otra.")
        else:
            return coord

def colocar_flota_interactivo(tablero):
    """Deja que el jugador coloque su flota de forma manual o aleatoria."""
    while True:
        modo = input("Colocar barcos: [M]anual o [A]leatoria? ").strip().upper()
        if modo in ("M", "A"):
            break
        print("Escribe M o A.")
    if modo == "A":
        while True:
            tablero.colocar_aleatorio()
            print()
            mostrar_tablero(tablero.codificar(False))
            if input("¿Te gusta esta distribucion? (S/N): ").strip().upper() == "S":
                return
    tablero.limpiar()
    for nombre, tam in FLOTA:
        while True:
            print()
            mostrar_tablero(tablero.codificar(False))
            inicio = parse_coordenada(input(f"{nombre} ({tam} casillas) - casilla inicial (ej. A1): "))
            orientacion = input("Orientacion [H]orizontal o [V]ertical: ").strip().upper()
            if inicio is None or orientacion not in ("H", "V"):
                print("Datos invalidos, intenta de nuevo.")
            elif tablero.colocar_barco(nombre, tam, inicio[0], inicio[1], orientacion == "H"):
                break
            else:
                print("No cabe o se cruza con otro barco. Intenta de nuevo.")
    print()
    mostrar_tablero(tablero.codificar(False))
#Comunicacion por socket
class Canal:
    """Envia y recibe mensajes de texto de una linea, con campos separados por ';'.
    Ejemplo: DISPARO;3,5  |  RESULTADO;TOCADO;2;3,5"""

    def __init__(self, sock):
        self.sock = sock
        self.lector = sock.makefile("r", encoding="utf-8", newline="\n")

    def enviar(self, *campos):
        linea = SEP.join(str(c) for c in campos) + "\n"
        self.sock.sendall(linea.encode("utf-8"))

    def recibir(self):
        """Devuelve la lista de campos del siguiente mensaje.
        Lanza ConnectionError si el otro lado se desconecto."""
        linea = self.lector.readline()
        if not linea:
            raise ConnectionError("El otro jugador se desconecto.")
        return linea.strip().split(SEP)

    def cerrar(self):
        try:
            self.lector.close()
            self.sock.close()
        except OSError:
            pass