# -*- coding: utf-8 -*-
"""
simbolos.py — Tabla de Símbolos
==================================

La Tabla de Símbolos almacena información sobre cada nodo (FUENTE,
OPERADOR o SUMIDERO) declarado en el programa DSL. Es la estructura
central del ANÁLISIS SEMÁNTICO:

  * Evita declaraciones duplicadas: no se puede declarar dos veces un
    nodo con el mismo id (sin importar si son del mismo tipo o no).
  * Garantiza que las instrucciones CONECTAR referencien únicamente a
    nodos que existen (fueron declarados antes de llamar a obtener()).

Se guarda un objeto Nodo por cada id, con sus atributos relevantes
(tipo, tiempo de servicio y cantidad de réplicas). Estos atributos son
usados después por grafo.py durante la simulación, para saber cuánto
tiempo consume cada OPERADOR y cuántas réplicas tiene disponibles para
repartir tuplas mediante round-robin.

Nota de diseño: la tabla de símbolos NO guarda información de aristas
(quién se conecta con quién) — eso es responsabilidad exclusiva del
Grafo (grafo.py), siguiendo el principio de una única responsabilidad
por estructura: la tabla sabe "qué nodos existen y sus atributos", el
grafo sabe "cómo están conectados".
"""

from dataclasses import dataclass


class ErrorSimbolo(Exception):
    """
    Excepción para errores de la tabla de símbolos: declaración
    duplicada de un id, o referencia (en CONECTAR) a un id que no fue
    declarado. Se usa una excepción propia para que main.py pueda
    capturarla y mostrar un mensaje de error semántico claro,
    distinguible de errores léxicos o sintácticos.
    """
    pass


@dataclass
class Nodo:
    """
    Representa un nodo de la topología dentro de la tabla de símbolos.

    Atributos:
        id: identificador del nodo (ej: 'f1', 'op1', 's1').
        tipo: uno de 'FUENTE', 'OPERADOR' o 'SUMIDERO'.
        tiempo_servicio: unidades de tiempo que consume procesar una
            tupla en este nodo. Solo tiene sentido para OPERADOR; para
            FUENTE y SUMIDERO queda en 0 (no consumen tiempo de
            procesamiento según el enunciado).
        replicas: cantidad de instancias replicadas de este nodo. Solo
            tiene sentido para OPERADOR; para FUENTE y SUMIDERO queda
            en 1 (el enunciado no contempla réplicas de fuentes ni de
            sumideros).
    """
    id: str
    tipo: str
    tiempo_servicio: int = 0
    replicas: int = 1


class TablaSimbolos:
    """
    Envoltorio simple sobre un diccionario id -> Nodo.

    Se usa un dict de Python (que desde 3.7 preserva el orden de
    inserción) en lugar de una estructura más compleja porque el
    enunciado no exige una tabla hash "artesanal": lo importante es
    que cumpla su rol semántico (duplicados + validación de
    referencias), y el orden de inserción es útil para, por ejemplo,
    recorrer las FUENTEs en el orden en que fueron declaradas al
    repartir eventos de simulación entre varias fuentes.
    """

    def __init__(self):
        self._simbolos = {}

    def agregar(self, nodo: Nodo):
        """
        Agrega un nuevo nodo a la tabla.

        Lanza ErrorSimbolo si ya existe un nodo con el mismo id
        (cumple el requisito de "evitar declaraciones duplicadas").
        """
        if nodo.id in self._simbolos:
            existente = self._simbolos[nodo.id]
            raise ErrorSimbolo(
                f"Nodo duplicado: '{nodo.id}' ya fue declarado "
                f"como {existente.tipo} anteriormente "
                f"(no se puede redeclarar como {nodo.tipo})."
            )
        self._simbolos[nodo.id] = nodo

    def obtener(self, id_nodo: str) -> Nodo:
        """
        Retorna el Nodo asociado a id_nodo.

        Lanza ErrorSimbolo si el id no existe en la tabla (cumple el
        requisito de que "las instrucciones CONECTAR referencien
        únicamente a nodos existentes").
        """
        if id_nodo not in self._simbolos:
            raise ErrorSimbolo(
                f"Referencia a nodo no declarado: '{id_nodo}'. "
                f"Todo id usado en CONECTAR debe haber sido declarado "
                f"previamente con FUENTE, OPERADOR o SUMIDERO."
            )
        return self._simbolos[id_nodo]

    def existe(self, id_nodo: str) -> bool:
        """Retorna True si id_nodo ya fue declarado, sin lanzar error."""
        return id_nodo in self._simbolos

    def ids_por_tipo(self, tipo: str):
        """
        Retorna la lista de ids de nodos de un tipo dado ('FUENTE',
        'OPERADOR' o 'SUMIDERO'), en el orden en que fueron declarados.
        Usada por grafo.py para, por ejemplo, encontrar todas las
        FUENTEs disponibles al iniciar una simulación.
        """
        return [id_ for id_, nodo in self._simbolos.items()
                if nodo.tipo == tipo]

    def __contains__(self, id_nodo):
        return id_nodo in self._simbolos

    def __iter__(self):
        return iter(self._simbolos.values())

    def __len__(self):
        return len(self._simbolos)

    def __repr__(self):
        return f"TablaSimbolos({list(self._simbolos.values())})"
