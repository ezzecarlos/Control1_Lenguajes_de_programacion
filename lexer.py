
import ply.lex as lex

#Excepción propia para errores léxicos (caracteres no reconocidos).
class ErrorLexico(Exception):
   
    pass



# 1. Palabras reservadas

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


# 2. Lista de tokens

tokens = list(set(reserved.values())) + ['ID', 'NUMERO']


# 3. Caracteres/patrones ignorados

t_ignore = ' \t'



# 4. Reglas de tokens (funciones, se evalúan en orden de definición


def t_ID(t):

    r'[a-zA-Z_][a-zA-Z0-9_]*'
    t.type = reserved.get(t.value, 'ID')
    return t


def t_NUMERO(t):

    r'\d+'
    t.value = int(t.value)
    return t


def t_COMMENT(t):
    
    r'\#[^\n]*'
    pass


def t_newline(t):
    r'\n+'
    # Actualiza el contador de línea del lexer por cada salto de línea
  
    t.lexer.lineno += len(t.value)
    # No se retorna token: los saltos de línea no son significativos para la gramática 

#Se invoca cuando el lexer encuentra un carácter que no calza con ninguna de las reglas anteriores 
def t_error(t):

    mensaje = (
        f"Error léxico en línea {t.lexer.lineno}: "
        f"carácter no reconocido '{t.value[0]}'"
    )
    raise ErrorLexico(mensaje)



# 5. Construcción del lexer

lexer = lex.lex()

#Función auxiliar de depuración
def tokenizar(codigo):
    
    lexer.input(codigo)
    lexer.lineno = 1
    resultado = []
    while True:
        tok = lexer.token()
        if not tok:
            break
        resultado.append(tok)
    return resultado


# Pequeña demo manual: al ejecutar "python lexer.py" se tokeniza un fragmento de ejemplo y se imprime el resultado.

if __name__ == '__main__':
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
