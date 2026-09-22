
# Variables de entorno
PYTHON = python
VENV = venv
VENV_PYTHON = $(VENV)/Scripts/python
VENV_PIP = $(VENV)/Scripts/pip

# Variable para el archivo a ejecutar (por defecto usa ejemplo.dsl)
ARCHIVO ?= ejemplo_invalido.dsl

# Evita conflictos si existen archivos con estos nombres
.PHONY: default run clean venv install run-venv

default: run

# 1. Ejecutar el simulador con el archivo indicado
run:
	$(PYTHON) main.py $(ARCHIVO)

# 2. Limpiar caché de Python y archivos autogenerados por PLY
clean:
	rm -rf __pycache__
	rm -f parsetab.py parser.out

# 3. Crear un entorno virtual de Python
venv:
	$(PYTHON) -m venv $(VENV)

# 4. Instalar dependencias en el entorno virtual
install: venv
	$(VENV_PIP) install ply

# 5. Ejecutar el simulador utilizando el entorno virtual aislado y el archivo indicado
run-venv:
	$(VENV_PYTHON) main.py $(ARCHIVO)