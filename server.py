"""
server.py
Servidor del juego (Jugador 1) para el modo multijugador por LAN.
El servidor es la autoridad de la partida: recibe los disparos del cliente,
los valida, los procesa, actualiza los tableros y envía los resultados.
Ejecutar solo este modo:   python server.py
"""
import random
import socket
from game_logic import (
    PUERTO, Tablero, Canal,
    parse_coordenada, a_texto_red, describir_jugada,
    pedir_nombre, pedir_coordenada, colocar_flota_interactivo, mostrar_tableros,
)
def ip_local():
    """IP de esta máquina en la red, para decírsela al cliente."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no envía datos; solo averigua qué interfaz se usaría
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"

def enviar_estado(canal, tab_srv, tab_cli):
    """ESTADO;<tablero propio del cliente>;<vista del cliente del tablero del servidor>"""
    canal.enviar("ESTADO", tab_cli.codificar(False), tab_srv.codificar(True))

def jugar_partida(canal):
    nombre_srv = pedir_nombre("Tu nombre (Jugador Servidor): ")
    # Intercambio de nombres
    msg = canal.recibir()
    if msg[0] != "NOMBRE" or len(msg) < 2:
        raise ConnectionError("Mensaje inicial inesperado del cliente.")
    nombre_cli = msg[1]
    canal.enviar("NOMBRE", nombre_srv)
    print(f"\n{nombre_cli} se conectó.\n")
    # Colocación de barcos (cada jugador coloca los suyos)
    tab_srv = Tablero()
    colocar_flota_interactivo(tab_srv)
    print(f"\nEsperando la flota de {nombre_cli}...")
    msg = canal.recibir()
    tab_cli = Tablero.desde_flota(msg[1]) if msg[0] == "FLOTA" and len(msg) > 1 else None
    if tab_cli is None:
        canal.enviar("ERROR", "FLOTA_INVALIDA")
        print("El cliente envió una flota inválida. Partida cancelada.")
        return
    # Asignación aleatoria: 1 = servidor, 2 = cliente (quien empieza)
    turno = random.choice([1, 2])
    print(f"Sorteo: empieza {nombre_srv if turno == 1 else nombre_cli}.")
    enviar_estado(canal, tab_srv, tab_cli)
    while True:
        canal.enviar("TURNO", turno)
        objetivo = tab_cli if turno == 1 else tab_srv  # tablero que recibe el disparo
        if turno == 1:
            mostrar_tableros(tab_srv.codificar(False), tab_cli.codificar(True))
            print("\n>>> ES TU TURNO")
            fila, col = pedir_coordenada("Tu disparo", objetivo.disparos)
        else:
            print(f"\nTurno de {nombre_cli}. Esperando su disparo...")
            while True:
                msg = canal.recibir()
                coord = parse_coordenada(msg[1]) if msg[0] == "DISPARO" and len(msg) > 1 else None
                if coord is None or coord in objetivo.disparos:
                    canal.enviar("ERROR", "COORDENADA_INVALIDA")  # el cliente vuelve a intentar
                    continue
                fila, col = coord
                break
        resultado = objetivo.recibir_disparo(fila, col)
        canal.enviar("RESULTADO", resultado, turno, a_texto_red(fila, col))
        enviar_estado(canal, tab_srv, tab_cli)
        atacante = nombre_srv if turno == 1 else nombre_cli
        mostrar_tableros(tab_srv.codificar(False), tab_cli.codificar(True))
        print(describir_jugada(resultado, atacante, fila, col))
        if objetivo.todos_hundidos():
            canal.enviar("FIN", "GANADOR", atacante)
            print(f"\n** FIN DE LA PARTIDA ** Ganador: {atacante}")
            return
        turno = 2 if turno == 1 else 1

def iniciar_servidor(puerto=PUERTO):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:                                                                                                                                                           srv.bind(("0.0.0.0", puerto))
    except OSError as e:
        print(f"No se pudo abrir el puerto {puerto}: {e}")
        srv.close()
        return
    srv.listen(1)
    print(f"\nServidor activo. Dile al otro jugador que se conecte a: {ip_local()}  (puerto {puerto})")
    print("Esperando conexión...")
    canal = None
    try:
        conn, direccion = srv.accept()
        print(f"Conexión recibida desde {direccion[0]}")
        canal = Canal(conn)
        jugar_partida(canal)
    except (ConnectionError, OSError):
        print("\n[!] Se perdió la conexión con el cliente. La partida terminó.")
    except KeyboardInterrupt:
        print("\nSaliste de la partida.")
        if canal:
            try:
                canal.enviar("ERROR", "DESCONECTADO")
            except OSError:
                pass
    finally:
        if canal:
            canal.cerrar()
        srv.close()

if __name__ == "__main__":
    iniciar_servidor()
    