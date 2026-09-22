# -*- coding: utf-8 -*-


from dataclasses import dataclass

# Excepción para errores de la tabla de símbolos: declaración duplicada de un id, o referencia (en CONECTAR) a un id que no fue declarado. 
class ErrorSimbolo(Exception):
  
    pass

# Representa un nodo de la topología dentro de la tabla de símbolos.
@dataclass
class Nodo:

    id: str
    tipo: str
    tiempo_servicio: int = 0
    replicas: int = 1


class TablaSimbolos:
   
    def __init__(self):
        self._simbolos = {}

    #Agrega un nuevo nodo a la tabla.
    def agregar(self, nodo: Nodo):
        
        if nodo.id in self._simbolos:
            existente = self._simbolos[nodo.id]
            raise ErrorSimbolo(
                f"Nodo duplicado: '{nodo.id}' ya fue declarado "
                f"como {existente.tipo} anteriormente "
                f"(no se puede redeclarar como {nodo.tipo})."
            )
        self._simbolos[nodo.id] = nodo

    def obtener(self, id_nodo: str) -> Nodo:
        
        # Retorna el Nodo asociado a id_nodo. Lanza ErrorSimbolo si el id no existe en la tabla 

        if id_nodo not in self._simbolos:
            raise ErrorSimbolo(
                f"Referencia a nodo no declarado: '{id_nodo}'. "
                f"Todo id usado en CONECTAR debe haber sido declarado previamente con FUENTE, OPERADOR o SUMIDERO."
            )
        return self._simbolos[id_nodo]

    def existe(self, id_nodo: str) -> bool:
        #Retorna True si id_nodo ya fue declarado, sin lanzar error.
        return id_nodo in self._simbolos

    def ids_por_tipo(self, tipo: str):
        
        #Retorna la lista de ids de nodos de un tipo dado ('FUENTE','OPERADOR' o 'SUMIDERO'), en el orden en que fueron declarados.
    
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
