Proyecto integrador Guerra Naval
**Integrantes:** Danae Sánchez, Johanna Parra, Gabriela Domínguez
## Descripción
Juego de Guerra Naval para dos jugadores, hecho en Python. Cada jugador coloca sus barcos en un tablero de 10x10 y, por turnos, dispara al tablero del rival. Gana quien hunda primero todos los barcos del otro.
## Modos de juego
- **Modo local:** dos jugadores en la misma computadora, por turnos. La pantalla se limpia entre turnos para que no se vea la flota del otro
- **Modo multijugador por LAN:** un jugador es el **servidor** (controla la partida) y el otro es el **cliente**. Se comunican por sockets TCP
## Requisitos
- Python 3.8 o superior.
- No necesita instalar librerías externas (solo usa `socket`, `random` y `os` de la biblioteca estándar)
## Cómo ejecutar
```bash
python juego.py
```
Aparece un menú con las opciones: jugar en local, jugar como servidor, jugar como cliente, ver reglas y salir.
### Modo LAN
1. En la primera máquina, elige **servidor**. El programa muestra su IP y el puerto (5000).
2. En la segunda máquina, elige **cliente** e ingresa esa IP.
3. Ambas máquinas deben estar en la misma red y el firewall debe permitir el puerto 5000.
También se puede ejecutar cada modo por separado con `python server.py` y `python client.py`.
## Estructura del proyecto
```
ProyectoJuego/
├── juego.py        # Menú principal y modo local (interfaz de usuario)
├── server.py       # Servidor del juego (Jugador 1 en LAN)
├── client.py       # Cliente del juego (Jugador 2 en LAN)
├── game_logic.py   # Lógica del juego, utilidades de consola y canal de mensajes
├── LICENSE
└── README.md
```
## Cómo se juega
- Flota: Portaaviones (5), Acorazado (4), Crucero (3), Submarino (3) y Destructor (2).
- Los barcos se colocan en horizontal o vertical, sin cruzarse; de forma manual o aleatoria.
- Coordenadas: letra de fila + número de columna (`B7`) o `fila,columna` (`2,7`).
- Símbolos: `B` barco, `X` tocado, `#` hundido, `o` fallo, `~` casilla sin explorar.
- El turno inicial se sortea al azar.
## Estado actual (Fase 3)
Hecho: modo local completo, servidor y cliente por sockets TCP, validación de disparos, detección de tocado/hundido, ganador y aviso de desconexión
Pendiente: volver a jugar en modo LAN, interfaz gráfica (planeada para la entrega final; el juego ya está separado en lógica, servidor y cliente para poder agregarla) y pruebas en las máquinas virtuales del proyecto
## Licencia
Este proyecto se distribuye bajo la licencia **MIT**. Ver el archivo [LICENSE](LICENSE).
## Créditos y declaración de autoría
- **Autoras:** Danae Sánchez, Johanna Parra y Gabriela Domínguez (diseño, diagramas de las fases 1 y 2 y desarrollo)
- **Librerías:** únicamente la biblioteca estándar de Python (`socket`, `random`, `os`). No se usan librerías de terceros
- **Código de terceros:** no se copió código de otros proyectos
- **Uso de IA:** el código inicial de esta fase se generó con ayuda de Claude, a partir de los diagramas y requisitos de las fases 1 y 2 del equipo. Después fue revisado y probado por el equipo
- Trabajo del equipo sobre ese código: revisión y pruebas en modo local y en modo LAN, y explicación de su funcionamiento en el video explicativo
- **Recursos visuales:** los diagramas de las fases 1 y 2 fueron elaborados por el equipo. El juego se muestra en la consola, sin imágenes externas
