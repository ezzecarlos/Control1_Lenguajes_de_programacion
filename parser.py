# -*- coding: utf-8 -*-
"""
parser.py — Análisis Sintáctico del DSL de Topologías de Stream Processing
============================================================================

Este módulo define el ANALIZADOR SINTÁCTICO (parser) del DSL usando PLY
(módulo yacc), que cumple el mismo rol que Bison pero para Python.

Diseño en DOS FASES (justificado en el README, sección "Diseño"):
--------------------------------------------------------------------
El enunciado pide explícitamente construir un AST / grafo dirigido como
estructura intermedia. Por eso el parser NO ejecuta directamente las
instrucciones a medida que las reconoce (enfoque de "una sola pasada").
En su lugar:

    FASE SINTÁCTICA (este archivo, función yacc):
        Recorre el código fuente y construye una lista de nodos AST
        (uno por cada instrucción: FUENTE, OPERADOR, SUMIDERO,
        CONECTAR o SIMULAR). En esta fase NO se valida nada semántico
        (no se revisan duplicados ni referencias inexistentes): solo se
        verifica que la SINTAXIS sea correcta.

    FASE SEMÁNTICA (función construir_topologia, al final de este
    archivo):
        Recorre la lista de nodos AST ya construida y, en ese recorrido,
        llena la Tabla de Símbolos (simbolos.py) y el Grafo Dirigido
        (grafo.py), aplicando las reglas semánticas: nodos duplicados,
        referencias a nodos inexistentes en CONECTAR, y validación
        estructural del grafo (al menos una FUENTE y un SUMIDERO).

Esta separación en dos fases es la práctica estándar en construcción de
compiladores (ver diapositivas de la unidad: "un AST se construye a
partir de un árbol de parseo... el análisis semántico usa el árbol
sintáctico y la tabla de símbolos"), y tiene una ventaja práctica
concreta para este enunciado: permite que CONECTAR referencie nodos
declarados MÁS ADELANTE en el archivo fuente (no solo hacia atrás), ya
que todos los nodos se registran antes de resolver las conexiones.
"""

from dataclasses import dataclass, field
from typing import List

import ply.yacc as yacc

from lexer import tokens  # noqa: F401  (PLY exige que 'tokens' esté disponible)
from lexer import lexer as _lexer_instance
from simbolos import TablaSimbolos, Nodo, ErrorSimbolo
from grafo import Grafo, ErrorGrafo


class ErrorSintactico(Exception):
    """
    Excepción propia para errores de sintaxis (secuencias de tokens que
    no calzan con ninguna regla gramatical). Igual que ErrorLexico en
    lexer.py, se define para poder distinguir este tipo de error en
    main.py y mostrar un mensaje amigable.
    """
    pass


# ===========================================================================
# 1. NODOS DEL AST
# ===========================================================================
# Se modela cada instrucción del DSL como una pequeña clase de datos
# (dataclass). Guardar el número de línea en cada nodo permite que los
# errores semánticos (fase 2) también indiquen dónde ocurrió el problema.

@dataclass
class NodoFuente:
    id: str
    linea: int


@dataclass
class NodoOperador:
    id: str
    tiempo_servicio: int
    replicas: int
    linea: int


@dataclass
class NodoSumidero:
    id: str
    linea: int


@dataclass
class Conexion:
    origen: str
    destino: str
    linea: int


@dataclass
class Simular:
    cantidad: int
    linea: int


# ===========================================================================
# 2. GRAMÁTICA (reglas p_*)
# ===========================================================================
# Gramática BNF que reconoce este parser (ver README para la versión
# formal completa):
#
#   programa            : lista_instrucciones
#   lista_instrucciones  : lista_instrucciones instruccion
#                        | instruccion
#   instruccion          : declaracion_fuente
#                        | declaracion_operador
#                        | declaracion_sumidero
#                        | declaracion_conectar
#                        | declaracion_simular
#   declaracion_fuente    : FUENTE ID
#   declaracion_operador  : OPERADOR ID TIEMPO_SERVICIO NUMERO
#                        | OPERADOR ID TIEMPO_SERVICIO NUMERO REPLICAS NUMERO
#   declaracion_sumidero  : SUMIDERO ID
#   declaracion_conectar  : CONECTAR ID A ID
#   declaracion_simular   : SIMULAR NUMERO
#
# Nótese que es una gramática NO recursiva por la derecha para la lista
# de instrucciones (lista_instrucciones : lista_instrucciones instruccion)
# sino recursiva por la izquierda, que es la forma preferida en parsers
# LALR (como los que genera PLY/Bison) porque evita crecer la pila del
# parser innecesariamente (ver diapositivas: "gramática no ambigua, por
# la izquierda").

def p_programa(p):
    'programa : lista_instrucciones'
    p[0] = p[1]


def p_lista_instrucciones_multiple(p):
    'lista_instrucciones : lista_instrucciones instruccion'
    p[0] = p[1] + [p[2]]


def p_lista_instrucciones_simple(p):
    'lista_instrucciones : instruccion'
    p[0] = [p[1]]


def p_instruccion(p):
    '''instruccion : declaracion_fuente
                    | declaracion_operador
                    | declaracion_sumidero
                    | declaracion_conectar
                    | declaracion_simular'''
    p[0] = p[1]


def p_declaracion_fuente(p):
    'declaracion_fuente : FUENTE ID'
    p[0] = NodoFuente(id=p[2], linea=p.lineno(1))


def p_declaracion_operador_simple(p):
    'declaracion_operador : OPERADOR ID TIEMPO_SERVICIO NUMERO'
    # Caso sin REPLICAS: se asume una sola instancia (replicas=1), tal
    # como indica el enunciado ("si se omite, se asume una sola
    # instancia").
    p[0] = NodoOperador(id=p[2], tiempo_servicio=p[4], replicas=1,
                         linea=p.lineno(1))


def p_declaracion_operador_replicado(p):
    'declaracion_operador : OPERADOR ID TIEMPO_SERVICIO NUMERO REPLICAS NUMERO'
    p[0] = NodoOperador(id=p[2], tiempo_servicio=p[4], replicas=p[6],
                         linea=p.lineno(1))


def p_declaracion_sumidero(p):
    'declaracion_sumidero : SUMIDERO ID'
    p[0] = NodoSumidero(id=p[2], linea=p.lineno(1))


def p_declaracion_conectar(p):
    'declaracion_conectar : CONECTAR ID A ID'
    p[0] = Conexion(origen=p[2], destino=p[4], linea=p.lineno(1))


def p_declaracion_simular(p):
    'declaracion_simular : SIMULAR NUMERO'
    p[0] = Simular(cantidad=p[2], linea=p.lineno(1))


def p_error(p):
    """
    Manejador de errores sintácticos de PLY. Se invoca cuando el parser
    encuentra un token que no puede encajar en ninguna regla dada la
    posición actual (por ejemplo, "FUENTE" sin ID a continuación, o un
    NUMERO donde se esperaba un ID).
    """
    if p is None:
        raise ErrorSintactico(
            "Error de sintaxis: fin de archivo inesperado "
            "(¿falta alguna instrucción o quedó incompleta?)"
        )
    raise ErrorSintactico(
        f"Error de sintaxis en línea {p.lineno}: "
        f"token inesperado '{p.value}' (tipo {p.type})"
    )


# Se construye el parser a partir de las reglas p_* definidas arriba.
parser = yacc.yacc()


def parsear(codigo):
    """
    Ejecuta la FASE SINTÁCTICA: recibe el código fuente completo (str)
    y retorna la lista de nodos AST (uno por instrucción), en el mismo
    orden en que aparecen en el archivo. No hace ninguna validación
    semántica todavía.
    """
    _lexer_instance.lineno = 1
    return parser.parse(codigo, lexer=_lexer_instance)


# ===========================================================================
# 3. FASE SEMÁNTICA: construcción de la Tabla de Símbolos y el Grafo
# ===========================================================================

def construir_topologia(instrucciones):
    """
    Recorre la lista de nodos AST (ya generada por parsear()) y construye:

      - tabla: una TablaSimbolos (simbolos.py) con un Nodo por cada
        FUENTE/OPERADOR/SUMIDERO declarado.
      - grafo: un Grafo (grafo.py) con las aristas indicadas por cada
        CONECTAR.
      - simulaciones: la lista de cantidades de eventos pedidas por
        cada instrucción SIMULAR, en el orden en que aparecieron.

    El recorrido se hace en DOS PASADAS sobre la misma lista de AST:

      Pasada 1 (declaración de nodos): registra en la tabla de símbolos
      y en el grafo TODOS los nodos (FUENTE/OPERADOR/SUMIDERO), sin
      importar en qué parte del archivo están. Esto es lo que permite
      que un CONECTAR pueda referenciar válidamente un nodo declarado
      más abajo en el archivo fuente.

      Pasada 2 (conexiones y simulaciones): procesa las instrucciones
      CONECTAR (ya con la tabla de símbolos completa, para validar que
      ambos extremos existan) y recolecta las instrucciones SIMULAR.

    Lanza ErrorSimbolo si hay un nodo duplicado o si CONECTAR referencia
    un id inexistente; lanza ErrorGrafo si la topología no cumple las
    reglas estructurales mínimas (al menos una FUENTE y un SUMIDERO).
    """
    tabla = TablaSimbolos()
    grafo = Grafo()

    # --- Pasada 1: declaración de nodos ---
    for instr in instrucciones:
        if isinstance(instr, NodoFuente):
            tabla.agregar(Nodo(id=instr.id, tipo='FUENTE'))
            grafo.agregar_nodo(instr.id)
        elif isinstance(instr, NodoOperador):
            tabla.agregar(Nodo(id=instr.id, tipo='OPERADOR',
                                tiempo_servicio=instr.tiempo_servicio,
                                replicas=instr.replicas))
            grafo.agregar_nodo(instr.id)
        elif isinstance(instr, NodoSumidero):
            tabla.agregar(Nodo(id=instr.id, tipo='SUMIDERO'))
            grafo.agregar_nodo(instr.id)

    # --- Pasada 2: conexiones y simulaciones ---
    simulaciones = []
    for instr in instrucciones:
        if isinstance(instr, Conexion):
            # tabla.obtener() lanza ErrorSimbolo si el id no existe:
            # así se cumple "las instrucciones CONECTAR deben referenciar
            # únicamente a nodos existentes".
            tabla.obtener(instr.origen)
            tabla.obtener(instr.destino)
            grafo.agregar_arista(instr.origen, instr.destino)
        elif isinstance(instr, Simular):
            simulaciones.append(instr.cantidad)

    # Validación estructural mínima exigida por el enunciado.
    grafo.validar_estructura(tabla)

    return tabla, grafo, simulaciones


if __name__ == '__main__':
    # Demo manual: "python parser.py" parsea y construye la topología
    # de un ejemplo embebido, y muestra el resultado.
    ejemplo = """
    FUENTE f1
    OPERADOR op1 TIEMPO_SERVICIO 5
    SUMIDERO s1
    CONECTAR f1 A op1
    CONECTAR op1 A s1
    SIMULAR 1
    """
    ast = parsear(ejemplo)
    print("AST:", ast)
    tabla, grafo, simulaciones = construir_topologia(ast)
    print("Tabla de símbolos:", tabla)
    print("Grafo:", grafo)
    print("Simulaciones pedidas:", simulaciones)
