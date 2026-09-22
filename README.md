# Intérprete para Topologías de Stream Processing

Implementación en **Python + PLY** (Python Lex-Yacc, el equivalente de
Flex/Bison para Python) del DSL descrito en el enunciado: un lenguaje
para declarar topologías de procesamiento de flujos de datos (fuentes,
operadores, sumideros y sus conexiones) y simular el paso de tuplas a
través de ellas.

## 1. Archivos del proyecto

| Archivo                  | Rol |
|---------------------------|-----|
| `lexer.py`                | Análisis léxico (PLY `lex`). Convierte el código fuente en tokens. |
| `parser.py`                | Análisis sintáctico (PLY `yacc`). Construye el AST y coordina la fase semántica. |
| `simbolos.py`              | Tabla de Símbolos: registro de nodos, detección de duplicados y validación de referencias. |
| `grafo.py`                 | Grafo dirigido de la topología + Lógica de Simulación (recorrido, round-robin, trazas y tiempo acumulado). |
| `main.py`                  | Punto de entrada: lee un archivo `.dsl`, ejecuta las 4 fases y ejecuta las instrucciones `SIMULAR`. |
| `ejemplo.dsl`              | Reproduce exactamente el ejemplo de salida del enunciado. |
| `ejemplo_replicas.dsl`     | Ejemplo con un operador replicado, para ver el reparto round-robin en acción. |

`main.py` no era uno de los 4 archivos pedidos explícitamente, pero se
agrega porque el enunciado pide "un programa que funcione como
intérprete" — sin un punto de entrada que una las piezas y ejecute
`SIMULAR`, las cuatro estructuras por sí solas no constituyen un
intérprete ejecutable.

### Requisitos y ejecución

```bash
pip install ply
python main.py ejemplo.dsl
python main.py ejemplo_replicas.dsl
```

Salida de `ejemplo.dsl` (idéntica al ejemplo del enunciado):

```
Evento 1: FUENTE f1 -> OPERADOR op1 (T: 5) -> SUMIDERO s1
Tiempo total acumulado: 5
```

## 2. El lenguaje (DSL)

### Palabras reservadas y gramática (BNF)

```
programa             : lista_instrucciones

lista_instrucciones   : lista_instrucciones instruccion
                      | instruccion

instruccion           : declaracion_fuente
                      | declaracion_operador
                      | declaracion_sumidero
                      | declaracion_conectar
                      | declaracion_simular

declaracion_fuente     : FUENTE ID

declaracion_operador   : OPERADOR ID TIEMPO_SERVICIO NUMERO
                      | OPERADOR ID TIEMPO_SERVICIO NUMERO REPLICAS NUMERO

declaracion_sumidero   : SUMIDERO ID

declaracion_conectar   : CONECTAR ID A ID

declaracion_simular    : SIMULAR NUMERO
```

Tokens reconocidos por el lexer:

- Palabras reservadas: `FUENTE`, `OPERADOR`, `SUMIDERO`, `CONECTAR`,
  `A`, `TIEMPO_SERVICIO`, `REPLICAS`, `SIMULAR`.
- `ID`: `[a-zA-Z_][a-zA-Z0-9_]*` que no coincide con ninguna palabra
  reservada (identificadores de nodos, ej. `f1`, `op1`, `s1`).
- `NUMERO`: `\d+`, casteado a `int`.
- Comentarios `# ...` hasta fin de línea (ignorados).
- Espacios, tabs y saltos de línea (ignorados salvo para contar líneas).

### Ejemplo completo

```dsl
FUENTE f1
OPERADOR op1 TIEMPO_SERVICIO 5
SUMIDERO s1

CONECTAR f1 A op1
CONECTAR op1 A s1

SIMULAR 1
```

## 3. Diseño: por qué dos fases (AST → construcción de topología)

El enunciado pide explícitamente una Tabla de Símbolos y un
"AST/grafo dirigido" como estructuras. Por eso el `parser.py` **no**
ejecuta las instrucciones a medida que las reconoce en una sola
pasada. En cambio, separa el trabajo en dos fases:

1. **Fase sintáctica** (reglas `p_*` + `yacc.yacc()`): el parser solo
   valida que la secuencia de tokens sea gramaticalmente correcta y
   construye una **lista de nodos AST** (`NodoFuente`, `NodoOperador`,
   `NodoSumidero`, `Conexion`, `Simular`), uno por instrucción, en el
   mismo orden del archivo fuente. En esta fase no se detectan
   duplicados ni referencias inválidas — solo errores de sintaxis.

2. **Fase semántica** (`construir_topologia` en `parser.py`): recorre
   la lista de nodos AST ya construida, en **dos pasadas**:
   - *Pasada 1*: registra todos los nodos (`FUENTE`/`OPERADOR`/
     `SUMIDERO`) en la Tabla de Símbolos y en el Grafo.
   - *Pasada 2*: procesa las instrucciones `CONECTAR` (validando que
     ambos extremos ya existan) y recolecta las instrucciones
     `SIMULAR`.

**Ventaja concreta de este diseño:** al registrar primero todos los
nodos y recién después las conexiones, un `CONECTAR` puede referenciar
válidamente un nodo declarado **más abajo** en el archivo, no solo uno
declarado antes. Si se hiciera todo en una sola pasada (como ejecutar
cada instrucción apenas se reconoce, al estilo de las acciones
semánticas embebidas de Bison), un `CONECTAR f1 A op1` antes de la
declaración de `op1` fallaría incorrectamente.

Esta separación además refleja la división estándar de un compilador
(scanning → parsing → análisis semántico usando el árbol sintáctico y
la tabla de símbolos) vista en la unidad del curso.

## 4. Tabla de Símbolos (`simbolos.py`)

- Estructura: diccionario `id -> Nodo` (Python preserva el orden de
  inserción desde 3.7, lo cual se aprovecha para iterar las `FUENTE`
  en el orden en que fueron declaradas).
- `Nodo` guarda: `id`, `tipo` (`FUENTE`/`OPERADOR`/`SUMIDERO`),
  `tiempo_servicio` (solo relevante para `OPERADOR`) y `replicas`
  (solo relevante para `OPERADOR`; por defecto 1).
- `agregar()` lanza `ErrorSimbolo` si el id ya existe → cumple
  "evitar declaraciones duplicadas".
- `obtener()` lanza `ErrorSimbolo` si el id no existe → cumple
  "las instrucciones CONECTAR deben referenciar únicamente a nodos
  existentes".
- **No** guarda aristas: por diseño, esa información vive solo en el
  Grafo, para que cada estructura tenga una única responsabilidad
  (la tabla sabe "qué existe", el grafo sabe "cómo se conecta").

## 5. Grafo dirigido y Lógica de Simulación (`grafo.py`)

- Estructura: lista de adyacencia (`dict[id] -> [ids_destino]`). Se
  eligió por sobre una matriz de adyacencia porque las topologías son
  dispersas (pocas conexiones por nodo) y una lista de adyacencia es
  más simple de recorrer e imprimir.
- `validar_estructura()` exige al menos una `FUENTE` y un `SUMIDERO`
  (regla obligatoria del enunciado). La **detección de ciclos es
  opcional** según el enunciado y no se implementa como rechazo duro;
  en su lugar, `simular()` tiene un límite de pasos de seguridad
  (`LIMITE_PASOS`) que lanza `ErrorGrafo` si una simulación entra en
  un ciclo infinito sin llegar a un `SUMIDERO`, evitando que el
  programa se cuelgue.
- `simular(tabla, cantidad_eventos)` recorre el grafo desde una
  `FUENTE` hasta un `SUMIDERO` por cada evento, acumulando el tiempo
  de servicio de cada `OPERADOR` atravesado, e imprime la traza con el
  formato exacto del enunciado:

  ```
  Evento 1: FUENTE f1 -> OPERADOR op1 (T: 5) -> SUMIDERO s1
  Tiempo total acumulado: 5
  ```

### 5.1 Round-robin hacia operadores replicados

Como el grafo modela cada `OPERADOR` como **un solo nodo lógico** (no
crea un nodo por cada réplica física), el reparto round-robin se
implementa con **un contador por arista** `(origen, destino)`: cada vez
que una tupla atraviesa esa arista y el destino tiene `N` réplicas, se
calcula `(contador % N) + 1` como la réplica usada, y se incrementa el
contador. Esto se ve en la traza como `[réplica k]` junto al nodo
destino. Se verificó en `ejemplo_replicas.dsl` (operador con 2
réplicas, 4 eventos) que el reparto alterna correctamente
`1, 2, 1, 2`.

### 5.2 Decisión de diseño para el caso no completamente especificado

El enunciado indica explícitamente que el caso de **dos nodos
adyacentes replicados simultáneamente** (un `OPERADOR` con varias
réplicas que alimenta a otro `OPERADOR` también replicado) no está
completamente especificado, y pide justificar la decisión en el
README.

**Decisión tomada:** el contador de round-robin de una arista
`(origen, destino)` es único y global para esa arista, **sin importar
cuántas réplicas tenga el nodo origen**. Es decir, el reparto hacia las
réplicas del destino se calcula "como si" todas las tuplas salieran de
un único punto lógico en el origen, independientemente de qué réplica
del origen procesó cada tupla.

**Justificación:** el enunciado solo especifica con precisión el
reparto round-robin *hacia* un destino replicado ("el nodo que lo
alimenta debe repartir... de forma circular"), pero no dice nada sobre
cómo se reparten las tuplas *entre* las réplicas del nodo origen en
primer lugar (eso tampoco está resuelto por el enunciado para el caso
base de un único origen no replicado alimentando a un destino
replicado — ahí el "nodo que alimenta" es tratado como una sola
entidad lógica). Mantener un único nodo lógico también para el origen
replicado es la extensión más simple y consistente de esa misma regla,
y evita introducir un mecanismo adicional (por ejemplo, "cada réplica
del origen lleva su propio contador hacia el destino") que el
enunciado no pide ni sugiere. Además, evita tener que modelar el
origen replicado como múltiples nodos físicos separados, lo cual
obligaría a rediseñar la Tabla de Símbolos y el Grafo para soportar
identificadores de instancia (ej. `op1_1`, `op1_2`), algo que el
enunciado tampoco pide explícitamente (solo pide poder simular el
recorrido y el tiempo total, no analizar el paralelismo interno de
cada réplica).

### 5.3 Fan-out real (un nodo con conexiones a destinos distintos)

Además del caso de réplicas, el DSL permite declarar más de un
`CONECTAR` con el mismo origen pero **distinto destino** (por ejemplo,
un operador que reparte su salida hacia dos sumideros distintos). Este
caso tampoco está cubierto por el enunciado. Decisión de diseño: la
tupla se **duplica** y continúa su recorrido por cada arista saliente
distinta (comportamiento de *broadcast*, coherente con la definición
general de un grafo dirigido, que no restringe el grado de salida de
un nodo). Cada camino resultante hasta un `SUMIDERO` se imprime como un
sub-evento (`Evento N.1`, `Evento N.2`, ...). En el caso normal —un
nodo con una sola arista saliente, que es el de todos los ejemplos y
la inmensa mayoría de topologías esperadas— el comportamiento es
exactamente el simple: `Evento N`.

### 5.4 Múltiples `FUENTE` y múltiples `SIMULAR`

- Si hay más de una `FUENTE` declarada, los eventos de una simulación
  se reparten round-robin entre ellas también (mismo criterio que para
  réplicas), en el orden de declaración. El enunciado no dice qué
  hacer con múltiples fuentes, por lo que se optó por reutilizar el
  mismo mecanismo de reparto circular ya definido para réplicas, en
  vez de inventar un criterio distinto (por ejemplo, elegir siempre la
  primera fuente, que dejaría sin uso a las demás).
- El contador de "Evento N" es **global y persistente** durante toda
  la ejecución del programa DSL: si hay varias instrucciones `SIMULAR`
  en el mismo archivo, la numeración de eventos continúa de forma
  consecutiva entre ellas en vez de reiniciar en 1 en cada una.

## 6. Manejo de errores

Cada fase lanza su propia excepción, para que `main.py` pueda
distinguir el tipo de error y mostrar un mensaje claro con la línea
donde ocurrió (cuando aplica):

- `ErrorLexico` (`lexer.py`): carácter no reconocido.
- `ErrorSintactico` (`parser.py`): secuencia de tokens inválida según
  la gramática, o fin de archivo inesperado.
- `ErrorSimbolo` (`simbolos.py`): nodo declarado dos veces, o
  `CONECTAR` que referencia un id no declarado.
- `ErrorGrafo` (`grafo.py`): falta `FUENTE` o `SUMIDERO`, o se alcanzó
  el límite de pasos durante la simulación (posible ciclo).

## 7. Limitaciones conocidas

- No se implementa detección/rechazo de ciclos (explícitamente
  opcional en el enunciado); en su lugar hay un límite de pasos de
  seguridad durante la simulación.
- El AST se mantiene íntegramente en memoria como una lista de
  `dataclasses` de Python; no se genera ningún archivo intermedio.
- El contenido de las tuplas es sintético/abstracto: no se modela
  ningún dato real viajando por la topología, tal como indica el
  enunciado ("simular el procesamiento de tuplas con contenido
  sintético"); lo que se reporta es únicamente la traza de nodos y el
  tiempo acumulado.
