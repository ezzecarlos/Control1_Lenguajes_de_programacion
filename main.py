# -*- coding: utf-8 -*-


import sys

from lexer import ErrorLexico
from parser import parsear, construir_topologia, ErrorSintactico
from simbolos import ErrorSimbolo
from grafo import ErrorGrafo

#Lee el archivo DSL indicado, lo interpreta por completo y ejecuta todas las instrucciones SIMULAR que contenga, en el orden en que aparecen en el archivo.
def ejecutar_archivo(ruta):
    
    
    with open(ruta, 'r', encoding='utf-8') as f:
        codigo = f.read()

    # Fase léxica + sintáctica: produce la lista de nodos AST.
    ast = parsear(codigo)

    # Fase semántica: construye tabla de símbolos y grafo, valida duplicados, referencias y estructura mínima de la topología.
    tabla, grafo, simulaciones = construir_topologia(ast)

    if not simulaciones:
        print("Advertencia: el programa no contiene ninguna "
              "instrucción SIMULAR; no se generó ninguna traza.")
        return

    # Lógica de Simulación: se ejecuta cada SIMULAR en el orden en que aparece en el archivo fuente.
    for cantidad in simulaciones:
        grafo.simular(tabla, cantidad)


def main():
    ruta = sys.argv[1] if len(sys.argv) > 1 else 'ejemplo.dsl'
    try:
        ejecutar_archivo(ruta)
    except FileNotFoundError:
        print(f"Error: no se encontró el archivo '{ruta}'.", file=sys.stderr)
        sys.exit(1)
    except ErrorLexico as e:
        print(f"[Error Léxico] {e}", file=sys.stderr)
        sys.exit(1)
    except ErrorSintactico as e:
        print(f"[Error Sintáctico] {e}", file=sys.stderr)
        sys.exit(1)
    except ErrorSimbolo as e:
        print(f"[Error Semántico - Tabla de Símbolos] {e}", file=sys.stderr)
        sys.exit(1)
    except ErrorGrafo as e:
        print(f"[Error Semántico - Grafo] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
