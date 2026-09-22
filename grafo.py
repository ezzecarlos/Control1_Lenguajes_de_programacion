# -*- coding: utf-8 -*-
"""
grafo.py — Grafo Dirigido de la Topología y Lógica de Simulación
====================================================================

Este módulo implementa el GRAFO DIRIGIDO que representa la topología de
stream processing: los nodos son FUENTE/OPERADOR/SUMIDERO (declarados en
la tabla de símbolos, simbolos.py) y las aristas son las conexiones
indicadas por las instrucciones CONECTAR.

Estructura elegida: LISTA DE ADYACENCIA
------------------------------------------
Se usa un diccionario `id_nodo -> [ids_destino]` (lista de adyacencia)
en vez de, por ejemplo, una matriz de adyacencia, porque las topologías
de este enunciado son dispersas (cada nodo típicamente tiene 1 o 2
salidas) y una lista de adyacencia es más simple de recorrer y de
imprimir. Solo se guarda la DIRECCIÓN del flujo (quién apunta a quién);
los atributos de cada nodo (tipo, tiempo de servicio, réplicas) viven en
la Tabla de Símbolos, no aquí — así cada estructura tiene una única
responsabilidad.

Réplicas y reparto round-robin
---------------------------------
El enunciado indica: cuando el nodo destino de una arista CONECTAR está
replicado, el nodo que lo alimenta debe repartir sus tuplas de forma
circular (round-robin) entre las réplicas del destino.

Como el grafo modela cada OPERADOR como UN SOLO nodo lógico (no crea un
nodo por cada réplica física), el round-robin se implementa así: por
cada ARISTA (origen -> destino) se mantiene un contador independiente.
Cada vez que una tupla atraviesa esa arista y el destino tiene N
réplicas, se calcula "en qué réplica cae" como
`(contador_de_la_arista % N) + 1`, y luego se incrementa el contador.
Esto asegura round-robin correcto por cada arista de entrada,
independiente de cuántas otras aristas lleguen al mismo destino.

Decisión de diseño para el caso NO completamente especificado
------------------------------------------------------------------
El enunciado señala explícitamente que el caso de dos nodos adyacentes
replicados simultáneamente (ej. un OPERADOR con varias réplicas que
alimenta a otro OPERADOR también replicado) no está completamente
especificado, y pide justificar la decisión de diseño en el README.
La decisión tomada aquí (ver README para el detalle completo) es:

    El grafo NO modela réplicas individuales como nodos separados —
    solo existe UN contador de round-robin por arista lógica
    (origen -> destino), sin importar cuántas réplicas tenga el
    ORIGEN. Es decir, el reparto round-robin hacia las réplicas del
    destino se hace "como si" todas las tuplas salieran de un único
    punto lógico en el origen (independiente de cuál réplica del
    origen la generó). Esto simplifica el modelo mucho manteniendo el
    comportamiento pedido explícitamente por el enunciado (round-robin
    hacia el destino replicado), y evita tener que modelar el
    comportamiento —no especificado— de cómo se reparten las tuplas
    ENTRE las réplicas del origen en primer lugar.

Fan-out (un nodo con más de una arista saliente hacia destinos
DISTINTOS, no réplicas del mismo id)
------------------------------------------------------------------
El DSL permite declarar varias instrucciones CONECTAR con el mismo
origen pero distinto destino (ej. un operador que reparte su salida
hacia dos sumideros distintos). Esto tampoco está cubierto de forma
explícita por el enunciado (que solo detalla el caso réplicas). La
decisión de diseño tomada es: la tupla se DUPLICA y continúa su
recorrido por cada arista saliente distinta (broadcast), ya que un
grafo dirigido general permite ramificaciones y no hay ninguna regla
que indique lo contrario. Cada rama resultante se imprime como un
sub-evento de la forma "Evento N.1", "Evento N.2", etc. Si el nodo
tiene una sola arista saliente (caso normal en la mayoría de las
topologías de prueba), el comportamiento es el simple: "Evento N".
"""

from collections import defaultdict


class ErrorGrafo(Exception):
    """
    Excepción para errores de validación estructural del grafo (por
    ejemplo: no hay ninguna FUENTE, no hay ningún SUMIDERO, o se
    detecta un recorrido que no llega nunca a un SUMIDERO durante la
    simulación —lo que indicaría un ciclo sin salida).
    """
    pass


class Grafo:
    """
    Grafo dirigido de la topología, más la lógica de simulación de
    eventos (recorrido de tuplas) que exige el enunciado.
    """

    # Límite de seguridad para evitar recursión infinita al simular si
    # la topología tiene un ciclo (la detección de ciclos es opcional
    # según el enunciado, pero igual queremos evitar que el programa
    # se cuelgue si el usuario define uno por error).
    LIMITE_PASOS = 10_000

    def __init__(self):
        # adyacencia[id_origen] = [id_destino_1, id_destino_2, ...]
        # en el orden en que fueron declaradas las instrucciones
        # CONECTAR para ese origen.
        self.adyacencia = {}
        # Contador de round-robin por arista (origen, destino) -> int.
        # defaultdict(int) evita tener que inicializar cada clave a 0
        # manualmente antes de usarla.
        self._contadores_replica = defaultdict(int)
        # Contador global de eventos ya simulados, para que los
        # números de "Evento N" sean consecutivos incluso si el
        # programa DSL tiene varias instrucciones SIMULAR seguidas.
        self._evento_actual = 0

    def agregar_nodo(self, id_nodo: str):
        """
        Registra un nodo en el grafo (con lista de adyacencia vacía).
        Se llama una vez por cada FUENTE/OPERADOR/SUMIDERO declarado,
        para que todo nodo aparezca en el grafo aunque no tenga
        conexiones todavía.
        """
        if id_nodo not in self.adyacencia:
            self.adyacencia[id_nodo] = []

    def agregar_arista(self, origen: str, destino: str):
        """
        Registra que las tuplas emitidas por `origen` fluyen hacia
        `destino` (instrucción CONECTAR <origen> A <destino>).
        """
        self.adyacencia.setdefault(origen, []).append(destino)

    def validar_estructura(self, tabla):
        """
        Valida las reglas estructurales mínimas exigidas por el
        enunciado: toda red debe tener al menos una FUENTE y al menos
        un SUMIDERO. La detección de ciclos es explícitamente OPCIONAL
        según el enunciado, por lo que aquí no se rechaza (si el
        usuario define un ciclo, el límite de pasos en _procesar_nodo
        evita que la simulación quede colgada).
        """
        if not tabla.ids_por_tipo('FUENTE'):
            raise ErrorGrafo(
                "La topología no tiene ninguna FUENTE declarada; se "
                "requiere al menos una para poder simular."
            )
        if not tabla.ids_por_tipo('SUMIDERO'):
            raise ErrorGrafo(
                "La topología no tiene ningún SUMIDERO declarado; se "
                "requiere al menos uno para poder simular."
            )

    # -------------------------------------------------------------
    # Lógica de Simulación
    # -------------------------------------------------------------

    def _etiqueta(self, id_nodo, nodo):
        """
        Construye el texto que representa a un nodo dentro de la
        traza impresa de un evento, siguiendo el formato del ejemplo
        del enunciado:
            FUENTE f1
            OPERADOR op1 (T: 5)
            SUMIDERO s1
        """
        if nodo.tipo == 'OPERADOR':
            return f"OPERADOR {id_nodo} (T: {nodo.tiempo_servicio})"
        return f"{nodo.tipo} {id_nodo}"

    def _procesar_nodo(self, id_nodo, tabla, tiempo_acumulado,
                        sufijo_etiqueta, profundidad):
        """
        Recorre recursivamente el grafo a partir de id_nodo, acumulando
        el tiempo de servicio de cada OPERADOR atravesado, y retorna
        una lista de tuplas (lista_de_etiquetas, tiempo_total) — una
        por cada camino completo hasta un SUMIDERO (normalmente uno
        solo; más de uno solo ocurre si hay fan-out real, ver
        docstring del módulo).

        sufijo_etiqueta permite anotar en la etiqueta del nodo actual
        la réplica que fue seleccionada para llegar a él (asignada por
        el nodo padre, ya que es la arista padre->actual la que decide
        el reparto round-robin).
        """
        if profundidad > self.LIMITE_PASOS:
            raise ErrorGrafo(
                "Se alcanzó el límite de pasos durante la simulación "
                "(posible ciclo sin SUMIDERO en la topología)."
            )

        nodo = tabla.obtener(id_nodo)
        if nodo.tipo == 'OPERADOR':
            tiempo_acumulado += nodo.tiempo_servicio
        etiqueta = self._etiqueta(id_nodo, nodo) + sufijo_etiqueta

        destinos = self.adyacencia.get(id_nodo, [])
        if not destinos:
            # Nodo sin salidas: debe ser un SUMIDERO (fin del camino).
            return [([etiqueta], tiempo_acumulado)]

        resultados = []
        for destino in destinos:
            nodo_destino = tabla.obtener(destino)
            sufijo_destino = ""
            if nodo_destino.replicas > 1:
                # Reparto round-robin: un contador independiente por
                # arista (id_nodo, destino), ver docstring del módulo.
                clave = (id_nodo, destino)
                indice_replica = (self._contadores_replica[clave]
                                   % nodo_destino.replicas) + 1
                self._contadores_replica[clave] += 1
                sufijo_destino = f" [réplica {indice_replica}]"

            sub_resultados = self._procesar_nodo(
                destino, tabla, tiempo_acumulado, sufijo_destino,
                profundidad + 1
            )
            for camino, tiempo_final in sub_resultados:
                resultados.append(([etiqueta] + camino, tiempo_final))
        return resultados

    def simular(self, tabla, cantidad_eventos):
        """
        Ejecuta la instrucción SIMULAR <cantidad_eventos>: simula ese
        número de tuplas viajando por la topología, imprimiendo por
        cada una la traza de nodos atravesados y el tiempo total
        acumulado, con el formato exacto pedido por el enunciado:

            Evento 1: FUENTE f1 -> OPERADOR op1 (T: 5) -> SUMIDERO s1
            Tiempo total acumulado: 5

        Si hay más de una FUENTE declarada, los eventos se reparten
        entre ellas también de forma round-robin (decisión de diseño,
        ver README), en el orden en que las FUENTEs fueron declaradas.

        Retorna la lista de resultados generados (útil para pruebas
        automáticas), cada uno como una tupla
        (numero_evento, lista_etiquetas, tiempo_total).
        """
        fuentes = tabla.ids_por_tipo('FUENTE')
        if not fuentes:
            raise ErrorGrafo("No hay FUENTEs declaradas: no se puede simular.")

        resultados = []
        for _ in range(cantidad_eventos):
            self._evento_actual += 1
            fuente = fuentes[(self._evento_actual - 1) % len(fuentes)]
            caminos = self._procesar_nodo(fuente, tabla, 0, "", 0)

            if len(caminos) == 1:
                etiquetas, tiempo_total = caminos[0]
                print(f"Evento {self._evento_actual}: "
                      + " -> ".join(etiquetas))
                print(f"Tiempo total acumulado: {tiempo_total}")
                resultados.append((self._evento_actual, etiquetas, tiempo_total))
            else:
                # Fan-out real: se imprime un sub-evento por cada
                # camino distinto hasta un SUMIDERO.
                for idx, (etiquetas, tiempo_total) in enumerate(caminos, 1):
                    identificador = f"{self._evento_actual}.{idx}"
                    print(f"Evento {identificador}: "
                          + " -> ".join(etiquetas))
                    print(f"Tiempo total acumulado: {tiempo_total}")
                    resultados.append((identificador, etiquetas, tiempo_total))
        return resultados

    def __repr__(self):
        return f"Grafo({self.adyacencia})"
