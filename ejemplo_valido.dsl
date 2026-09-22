# Ejemplo válido: un operador replicado distribuye eventos y luego
# duplica la salida hacia dos sumideros distintos.
FUENTE entrada
OPERADOR procesador TIEMPO_SERVICIO 7 REPLICAS 2
SUMIDERO salida_a
SUMIDERO salida_b

CONECTAR entrada A procesador
CONECTAR procesador A salida_a
CONECTAR procesador A salida_b

SIMULAR 2
