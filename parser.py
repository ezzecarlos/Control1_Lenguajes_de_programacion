# -*- coding: utf-8 -*-


from dataclasses import dataclass, field
from typing import List

import ply.yacc as yacc

from lexer import tokens  # noqa: F401  (PLY exige que 'tokens' esté disponible)
from lexer import lexer as _lexer_instance
from simbolos import TablaSimbolos, Nodo, ErrorSimbolo
from grafo import Grafo, ErrorGrafo

#Excepción propia para errores de sintaxis (secuencias de tokens que no calzan con ninguna regla gramatical).
class ErrorSintactico(Exception):
    
    pass



# 1. NODOS DEL AST

# Se modela cada instrucción del DSL como una pequeña clase de datos (dataclass). Guardar el número de línea en cada nodo permite que los errores semánticos (fase 2) también indiquen dónde ocurrió el problema.

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



# 2. GRAMÁTICA (reglas p_*)


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
    # Caso sin REPLICAS: se asume una sola instancia (replicas=1)
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


#Manejador de errores sintácticos de PLY. Se invoca cuando el parser encuentra un token que no puede encajar en ninguna regla dada la posición actual
def p_error(p):
    
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


#Ejecuta la fase sintactica: recibe el código fuente completo y retorna la lista de nodos AST (uno por instrucción), en el mismo orden en que aparecen en el archivo. No hace ninguna validación semántica todavía.
def parsear(codigo):
    

    _lexer_instance.lineno = 1
    return parser.parse(codigo, lexer=_lexer_instance)



# 3. Fase semantica: construcción de la Tabla de Símbolos y el Grafo

def construir_topologia(instrucciones):
    
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

    # Pasada 2: conexiones y simulaciones
    simulaciones = []
    for instr in instrucciones:
        if isinstance(instr, Conexion):
            # tabla.obtener() lanza ErrorSimbolo si el id no existe:
            tabla.obtener(instr.origen)
            tabla.obtener(instr.destino)
            grafo.agregar_arista(instr.origen, instr.destino)
        elif isinstance(instr, Simular):
            simulaciones.append(instr.cantidad)

    grafo.validar_estructura(tabla)

    return tabla, grafo, simulaciones


if __name__ == '__main__':
    # Demo manual: "python parser.py" 
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
