"""
juego.py
Programa principal de Guerra Naval: menú de inicio y modo local.

Modos:
  1. Local: dos jugadores en la misma computadora (por turnos).
  2. Servidor LAN: este equipo hospeda la partida (server.py).
  3. Cliente LAN: este equipo se conecta a un servidor (client.py).

Ejecutar:   python juego.py
"""
import random

import client
import server
from game_logic import (
    Tablero, limpiar_pantalla, mostrar_tableros, describir_jugada,
    pedir_nombre, pedir_coordenada, colocar_flota_interactivo, FLOTA,
)


def mostrar_reglas():
    print("\n=== REGLAS ===")
    print("* Cada jugador tiene un tablero de 10x10 y una flota de 5 barcos:")
    for nombre, tam in FLOTA:
        print(f"    - {nombre}: {tam} casillas")
    print("* Los barcos se colocan en horizontal o vertical, sin cruzarse.")
    print("* Por turnos, cada jugador dispara a una casilla del tablero enemigo.")
    print("* Coordenadas: letra de fila + número de columna (B7) o fila,columna (2,7).")
    print("* Resultados: agua, tocado o hundido. El turno pasa al otro jugador.")
    print("* Gana quien hunda primero todos los barcos del rival.")


def jugar_local(nombre1, nombre2):
    nombres = {1: nombre1, 2: nombre2}
    tableros = {1: Tablero(), 2: Tablero()}

    # Colocación de barcos: cada jugador en privado
    for j in (1, 2):
        limpiar_pantalla()
        print(f"{nombres[j]}: coloca tus barcos. {nombres[3 - j]} no debe mirar la pantalla.\n")
        colocar_flota_interactivo(tableros[j])
        input("\nPresiona ENTER para ocultar tu flota...")

    # Asignación aleatoria de quién empieza
    turno = random.choice([1, 2])
    limpiar_pantalla()
    input(f"Sorteo: empieza {nombres[turno]}. Presiona ENTER...")

    while True:
        rival = 3 - turno
        limpiar_pantalla()
        input(f"Turno de {nombres[turno]}. Pasa la computadora y presiona ENTER...")
        limpiar_pantalla()
        mostrar_tableros(tableros[turno].codificar(False), tableros[rival].codificar(True))

        fila, col = pedir_coordenada(f"{nombres[turno]}, tu disparo", tableros[rival].disparos)
        resultado = tableros[rival].recibir_disparo(fila, col)

        mostrar_tableros(tableros[turno].codificar(False), tableros[rival].codificar(True))
        print(describir_jugada(resultado, nombres[turno], fila, col))

        if tableros[rival].todos_hundidos():
            print(f"\n*** FIN DE LA PARTIDA *** Ganador: {nombres[turno]}")
            return

        input("\nPresiona ENTER para terminar tu turno...")
        turno = rival


def modo_local():
    print("\n=== MODO LOCAL ===")
    nombre1 = pedir_nombre("Nombre del Jugador 1: ")
    nombre2 = pedir_nombre("Nombre del Jugador 2: ")
    while True:
        jugar_local(nombre1, nombre2)
        if input("\n¿Jugar otra vez? (S/N): ").strip().upper() != "S":
            break


def menu():
    while True:
        print("\n===== GUERRA NAVAL =====")
        print("1. Jugar en modo local (misma computadora)")
        print("2. Jugar en red LAN como SERVIDOR")
        print("3. Jugar en red LAN como CLIENTE")
        print("4. Ver reglas")
        print("5. Salir")
        opcion = input("Elige una opción: ").strip()

        if opcion == "1":
            modo_local()
        elif opcion == "2":
            server.iniciar_servidor()
        elif opcion == "3":
            client.iniciar_cliente()
        elif opcion == "4":
            mostrar_reglas()
        elif opcion == "5":
            print("¡Hasta la próxima!")
            break
        else:
            print("Opción inválida.")


if __name__ == "__main__":
    menu()