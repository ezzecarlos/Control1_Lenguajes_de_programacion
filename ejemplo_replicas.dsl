# Ejemplo con un operador replicado (op1 tiene 2 réplicas).
# f1 reparte sus tuplas hacia las réplicas de op1 de forma round-robin:
# tupla 1 -> réplica 1, tupla 2 -> réplica 2, tupla 3 -> réplica 1, etc.
FUENTE f1
OPERADOR op1 TIEMPO_SERVICIO 3 REPLICAS 2
OPERADOR op2 TIEMPO_SERVICIO 4
SUMIDERO s1

CONECTAR f1 A op1
CONECTAR op1 A op2
CONECTAR op2 A s1

SIMULAR 4
