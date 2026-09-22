# -*- coding: utf-8 -*-
"""
lexer.py — Análisis Léxico del DSL de Topologías de Stream Processing
=======================================================================

Este módulo define el ANALIZADOR LÉXICO (scanner) del lenguaje de dominio
específico (DSL) usando la librería PLY (Python Lex-Yacc), que cumple el
mismo rol que Flex pero para Python.

¿Qué hace un analizador léxico?
--------------------------------
Divide el texto fuente (la cadena de caracteres que escribe el usuario en
su archivo .dsl) en una secuencia de TOKENS: unidades mínimas con
significado (palabras reservadas, identificadores, números, etc.). El
parser (parser.py) luego combina esos tokens según la gramática para
construir el AST.

Instrucciones que debe reconocer (ver enunciado):
    FUENTE <id>
    OPERADOR <id> TIEMPO_SERVICIO <valor> [REPLICAS <n>]
    SUMIDERO <id>
    CONECTAR <id_origen> A <id_destino>
    SIMULAR <cantidad_eventos>

Además se soportan comentarios de línea con '#'.
"""

import ply.lex as lex


class ErrorLexico(Exception):
    """
    Excepción propia para errores léxicos (caracteres no reconocidos).
    Se define una excepción propia (en vez de usar Exception genérica)
    para que main.py pueda distinguir errores léxicos de otros errores
    y mostrar un mensaje claro al usuario, indicando línea y carácter.
    """
    pass


# ---------------------------------------------------------------------
# 1. Palabras reservadas
# ---------------------------------------------------------------------
# Diccionario que mapea el lexema (la palabra tal cual aparece en el
# código fuente) al nombre del token que PLY debe generar para ella.
# Se usa dentro de t_ID (ver más abajo) para decidir si un identificador
# genérico es en realidad una palabra clave del lenguaje.
reserved = {
    'FUENTE': 'FUENTE',
    'OPERADOR': 'OPERADOR',
    'SUMIDERO': 'SUMIDERO',
    'CONECTAR': 'CONECTAR',
    'A': 'A',
    'TIEMPO_SERVICIO': 'TIEMPO_SERVICIO',
    'REPLICAS': 'REPLICAS',
    'SIMULAR': 'SIMULAR',
}

# ---------------------------------------------------------------------
# 2. Lista de tokens
# ---------------------------------------------------------------------
# PLY exige una lista/tupla llamada "tokens" con TODOS los nombres de
# token que el lexer puede producir. Incluye las palabras reservadas
# (sus valores en el diccionario de arriba) más los tokens "genéricos"
# ID (identificadores de nodos, ej: f1, op1, s1) y NUMERO (enteros).
tokens = list(set(reserved.values())) + ['ID', 'NUMERO']

# ---------------------------------------------------------------------
# 3. Caracteres/patrones ignorados
# ---------------------------------------------------------------------
# t_ignore es una variable especial de PLY: los caracteres que contiene
# se saltan sin generar token ni contar como error. Aquí ignoramos
# espacios y tabulaciones (los saltos de línea se manejan aparte en
# t_newline porque necesitamos contarlos para reportar el nro de línea).
t_ignore = ' \t'


# ---------------------------------------------------------------------
# 4. Reglas de tokens (funciones, se evalúan en orden de definición
#    y PLY las ordena además por longitud de expresión regular cuando
#    hay funciones; por eso ID se define ANTES de que se resuelva como
#    palabra reservada dentro de la misma función)
# ---------------------------------------------------------------------

def t_ID(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    # Patrón clásico en PLY: primero se reconoce como identificador
    # genérico y luego se revisa si el texto coincide con alguna
    # palabra reservada. Si coincide, se cambia el tipo de token
    # (t.type) al de la palabra reservada; si no, se deja como ID.
    t.type = reserved.get(t.value, 'ID')
    return t


def t_NUMERO(t):
    r'\d+'
    # Los números en el DSL son siempre enteros (tiempos de servicio,
    # cantidad de réplicas, cantidad de eventos a simular).
    t.value = int(t.value)
    return t


def t_COMMENT(t):
    r'\#[^\n]*'
    # Comentarios de línea: desde '#' hasta el final de la línea.
    # No se retorna token (pass): el comentario se descarta por
    # completo y no llega al parser.
    pass


def t_newline(t):
    r'\n+'
    # Actualiza el contador de línea del lexer por cada salto de línea
    # encontrado (puede haber varios seguidos, por eso el '+').
    # Esto permite que los mensajes de error indiquen la línea correcta.
    t.lexer.lineno += len(t.value)
    # No se retorna token: los saltos de línea no son significativos
    # para la gramática (las instrucciones no dependen de terminar con
    # ';' ni de estar en una única línea).


def t_error(t):
    """
    Se invoca cuando el lexer encuentra un carácter que no calza con
    ninguna de las reglas anteriores (por ejemplo: @, $, %, etc.).
    En vez de solo imprimir un mensaje, lanzamos una excepción propia
    (ErrorLexico) con el carácter y la línea del problema, para que
    main.py pueda capturarla y mostrar un mensaje claro y detener la
    ejecución de forma controlada.
    """
    mensaje = (
        f"Error léxico en línea {t.lexer.lineno}: "
        f"carácter no reconocido '{t.value[0]}'"
    )
    raise ErrorLexico(mensaje)


# ---------------------------------------------------------------------
# 5. Construcción del lexer
# ---------------------------------------------------------------------
# lex.lex() inspecciona este módulo (globals()), recolecta las variables
# t_* y la lista tokens, y arma el analizador léxico. Se expone como
# variable de módulo "lexer" para que parser.py y main.py puedan
# reutilizar la misma instancia.
lexer = lex.lex()


def tokenizar(codigo):
    """
    Función auxiliar de depuración: recibe un string con código fuente
    del DSL y retorna la lista de tokens reconocidos, sin pasar por el
    parser. Útil para probar el lexer de forma aislada, por ejemplo:

        >>> from lexer import tokenizar
        >>> tokenizar("FUENTE f1")
        [LexToken(FUENTE,'FUENTE',1,0), LexToken(ID,'f1',1,7)]
    """
    lexer.input(codigo)
    lexer.lineno = 1
    resultado = []
    while True:
        tok = lexer.token()
        if not tok:
            break
        resultado.append(tok)
    return resultado


if __name__ == '__main__':
    # Pequeña demo manual: al ejecutar "python lexer.py" se tokeniza
    # un fragmento de ejemplo y se imprime el resultado.
    ejemplo = """
    FUENTE f1
    OPERADOR op1 TIEMPO_SERVICIO 5 REPLICAS 2
    SUMIDERO s1
    CONECTAR f1 A op1
    CONECTAR op1 A s1
    SIMULAR 3 # simula 3 tuplas
    """
    for tok in tokenizar(ejemplo):
        print(tok)
