"""
client.py
Cliente del juego (Jugador 2) para el modo multijugador por LAN.
El cliente se conecta al servidor, coloca sus barcos, y en su turno envía
disparos. Todo lo que ve (tableros, resultados, turnos) viene del servidor.
Ejecutar solo este modo:   python client.py
"""
import socket
from game_logic import (
    PUERTO, AGUA, TAMANO, Canal, Tablero,
    parse_coordenada, a_texto_red, describir_jugada,
    pedir_nombre, pedir_coordenada, colocar_flota_interactivo, mostrar_tableros,
)
def jugar_partida(canal, nombre):
    canal.enviar("NOMBRE", nombre)
    msg = canal.recibir()
    if msg[0] != "NOMBRE" or len(msg) < 2:
        raise ConnectionError("Mensaje inicial inesperado del servidor.")
    rival = msg[1]
    print(f"\nConectado con {rival}.\n")
    propio = Tablero()
    colocar_flota_interactivo(propio)
    canal.enviar("FLOTA", propio.serializar_flota())
    print("\nEsperando a que empiece la partida...")
    vista_rival = AGUA * (TAMANO * TAMANO)  # lo que sé del tablero enemigo
    texto_pendiente = ""                    # resultado de la última jugada
    def disparar():
        bloqueadas = {(i // TAMANO, i % TAMANO) for i, ch in enumerate(vista_rival) if ch != AGUA}
        fila, col = pedir_coordenada("Tu disparo", bloqueadas)
        canal.enviar("DISPARO", a_texto_red(fila, col))
    while True:
        msg = canal.recibir()
        tipo = msg[0]
        if tipo == "RESULTADO" and len(msg) >= 4:
            coord = parse_coordenada(msg[3])
            atacante = "Tú" if msg[2] == "2" else rival
            if coord:
                texto_pendiente = describir_jugada(msg[1], atacante, coord[0], coord[1])
        elif tipo == "ESTADO" and len(msg) >= 3:
            vista_rival = msg[2]
            mostrar_tableros(msg[1], msg[2])
            if texto_pendiente:
                print(texto_pendiente)
                texto_pendiente = ""
        elif tipo == "TURNO" and len(msg) >= 2:
            if msg[1] == "2":
                print("\n>>> ES TU TURNO")
                disparar()
            else:
                print(f"\nTurno de {rival}. Esperando su disparo...")
        elif tipo == "FIN" and len(msg) >= 3:
            print(f"\n** FIN DE LA PARTIDA ** Ganador: {msg[2]}")
            return
        elif tipo == "ERROR":
            if len(msg) >= 2 and msg[1] == "COORDENADA_INVALIDA":
                print("El servidor rechazó esa coordenada. Intenta con otra.")
                disparar()
            else:
                print("[!] El servidor cerró la partida (el otro jugador se desconectó o hubo un error).")
                return


def iniciar_cliente(host=None, puerto=PUERTO):
    if not host:
        host = input("IP del servidor (ej. 192.168.1.10): ").strip() or "127.0.0.1"
    nombre = pedir_nombre("Tu nombre (Jugador Cliente): ")
    try:
        sock = socket.create_connection((host, puerto), timeout=10)
    except OSError as e:
        print(f"No se pudo conectar a {host}:{puerto} ({e}).")
        print("Revisa la IP, que el servidor esté activo y que ambas máquinas estén en la misma red.")
        return
    sock.settimeout(None)
    canal = Canal(sock)
    try:
        jugar_partida(canal, nombre)
    except (ConnectionError, OSError):
        print("\n[!] Se perdió la conexión con el servidor. La partida terminó.")
    except KeyboardInterrupt:
        print("\nSaliste de la partida.")
    finally:
        canal.cerrar()

if __name__ == "__main__":
    iniciar_cliente()
    