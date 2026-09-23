
from collections import defaultdict

# Excepción para errores de validación estructural del grafo

class ErrorGrafo(Exception):
    pass

# Grafo dirigido de la topología, más la lógica de simulación de eventos 

class Grafo:
   

    # Límite de seguridad para evitar recursión infinita al simular si la topología tiene un ciclo 
    LIMITE_PASOS = 10_000

    def __init__(self):

        self.adyacencia = {}
        
        self._contadores_replica = defaultdict(int)

        # Contador global de eventos ya simulados
        self._evento_actual = 0

#Registra un nodo en el grafo (con lista de adyacencia vacía). 
#Se llama una vez por cada FUENTE/OPERADOR/SUMIDERO declarado, para que todo nodo aparezca en el grafo aunque no tenga conexiones todavía.
    def agregar_nodo(self, id_nodo: str):

        if id_nodo not in self.adyacencia:
            self.adyacencia[id_nodo] = []

# Registra que las tuplas emitidas por `origen` fluyen hacia `destino`
    def agregar_arista(self, origen: str, destino: str):
        

        self.adyacencia.setdefault(origen, []).append(destino)

    def validar_estructura(self, tabla):

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


    # Lógica de Simulación
    
# Construye el texto que representa a un nodo dentro de la traza impresa de un evento
    def _etiqueta(self, id_nodo, nodo):
        
        if nodo.tipo == 'OPERADOR':
            return f"OPERADOR {id_nodo} (T: {nodo.tiempo_servicio})"
        return f"{nodo.tipo} {id_nodo}"

    def _procesar_nodo(self, id_nodo, tabla, tiempo_acumulado,sufijo_etiqueta, profundidad):
       
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
                # Reparto round-robin: un contador independiente por arista (id_nodo, destino).
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
        #Ejecuta la instrucción SIMULAR <cantidad_eventos>: simula ese número de tuplas viajando por la topología, imprimiendo por
        #cada una la traza de nodos atravesados y el tiempo total acumulado
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
                # Fan-out real: se imprime un sub-evento por cada camino distinto hasta un SUMIDERO.
                for idx, (etiquetas, tiempo_total) in enumerate(caminos, 1):
                    identificador = f"{self._evento_actual}.{idx}"
                    print(f"Evento {identificador}: "
                          + " -> ".join(etiquetas))
                    print(f"Tiempo total acumulado: {tiempo_total}")
                    resultados.append((identificador, etiquetas, tiempo_total))
        return resultados

    def __repr__(self):
        return f"Grafo({self.adyacencia})"
