# Optimizador de Código Intermedio (IR/TAC) para B-Minor

Este proyecto implementa un motor de optimización local e iterativo para la Representación Intermedia (IR) en Código de Tres Direcciones (TAC) diseñado para el lenguaje **B-Minor**. El optimizador permite transformar secuencias de instrucciones crudas en código intermedio altamente eficiente mediante reescrituras seguras a nivel local (`-O1`) y análisis de flujo reverso (`-O2`).

---

## Estructura del Proyecto

El entorno de desarrollo está organizado de la siguiente manera para garantizar modularidad y facilitar las pruebas:

```text
PARCIAL 2 - COMPILADORES/
│
├── ircode.py               # Estructuras de datos base (IRProgram, IRFunction)
├── iroptimizer.py          # Script principal del optimizador y CLI
│
├── pruebas/             # Casos de estudio en lenguaje B-Minor
│   ├── prueba_O1.bminor    # Código fuente diseñado para evaluar el nivel O1
│   └── prueba_O2.bminor    # Código fuente diseñado para evaluar el nivel O2
│
└── README.md               # Documentación y manual de usuario (Este archivo)

```

---

## 🛠️ Niveles de Optimización Implementados

El comportamiento del optimizador se segmenta a través de banderas de la línea de comandos de manera progresiva:

### 1. Nivel `-O0` (Preservación del Código)

Mantiene la Representación Intermedia original intacta. No altera ninguna instrucción, sirviendo como base de comparación para validar la fidelidad semántica del compilador.

### 2. Nivel `-O1` (Optimización Local y Estructuras de Control)

Aplica un enfoque de pasada única e iterativa que busca alcanzar un **punto fijo** (repite las pasadas hasta que el código ya no sufra más reducciones). Implementa:

* **Constant Folding (Plegado de Constantes):** Evalúa operaciones aritméticas (`ADDI`, `MULI`, etc.) y relacionales (`CMPI`) en tiempo de compilación si ambos operandos son numéricos conocidos, omitiendo divisiones de riesgo por cero.
* **Simplificación Algebraica:** Aplica identidades matemáticas clásicas para limpiar el flujo de control como:
* $x + 0 \rightarrow x$
* $x \times 1 \rightarrow x$
* $x \times 0 \rightarrow 0$


* **Reducción de Ramas Estáticas:** Transforma saltos condicionales (`CBRANCH`) cuyos predicados lógicos se conocen con certeza en saltos incondicionales directos (`BRANCH`).
* **Eliminación de Código Inalcanzable:** Remueve bloques enteros de instrucciones redundantes que quedan atrapados después de un `BRANCH` o un `RET` antes de la siguiente etiqueta (`LABEL`).
* **Remoción de Saltos Superfluos:** Elimina instrucciones `BRANCH` cuyo destino directo sea la etiqueta inmediatamente consecutiva en la línea de flujo.

### 3. Nivel `-O2` (Eliminación de Temporales Muertos)

Hereda de forma estricta todas las transformaciones logradas en `-O1` y añade:

* **Liveness Analysis Reverso (Análisis de Flujo hacia Atrás):** Recorre el bloque de instrucciones desde el final de la función hacia el principio manteniendo un conjunto dinámico de temporales "vivos". Toda instrucción pura (definición de registros temporales) cuyo destino no vuelva a ser leído aguas abajo es purgada por completo de la emisión final del TAC.

---

## Guía de Ejecución Paso a Paso

Para probar el correcto funcionamiento del optimizador localmente, abre una terminal de **PowerShell** o tu consola del sistema, ubícate en la raíz del proyecto y ejecuta los siguientes comandos:

### Paso 1: Ejecutar sin optimización (`-O0`)

Comprueba cómo se genera la estructura TAC cruda original (la simulación incorporada muestra el código con operaciones fijas redundantes y ramas lógicas completas).

```bash
python iroptimizer.py pruebas/prueba_O1.bminor -O0

```

### Paso 2: Ejecutar optimizaciones de nivel local (`-O1`)

Observa en pantalla cómo el motor pliega las sumas/multiplicaciones numéricas fijos, resuelve las comparaciones lógicas convirtiendo el condicional en un salto directo, y elimina las instrucciones que correspondían a la rama inalcanzable.

```bash
python iroptimizer.py pruebas/prueba_O1.bminor -O1

```

### Paso 3: Ejecutar optimizaciones avanzadas (`-O2`)

Inyecta un entorno simulado donde se computan operaciones asignadas a una variable muerta (`y`). Comprueba cómo el análisis hacia atrás expulsa con éxito los registros intermedios que no influyen en salidas (`PRINT`) ni retornos.

```bash
python iroptimizer.py pruebas/prueba_O2.bminor -O2

```

---

## Guardado de Evidencias (Automatización)

Si deseas exportar los resultados legibles directamente a archivos de texto de forma automatizada para adjuntar a tus informes o entregas, puedes redirigir las salidas usando el operador `>`:

```bash
# Crear un directorio para agrupar los resultados
mkdir salidas

# Generar y almacenar las trazas comparativas de forma automática
python iroptimizer.py pruebas/prueba_O1.bminor -O0 > salidas/salida_O0.tac
python iroptimizer.py pruebas/prueba_O1.bminor -O1 > salidas/salida_O1.tac
python iroptimizer.py pruebas/prueba_O2.bminor -O2 > salidas/salida_O2.tac

```

---

## Consideraciones de Seguridad

El diseño de este optimizador opera bajo criterios estrictamente conservadores según la teoría de diseño de compiladores:

1. No optimiza divisiones aritméticas si el denominador es cero para preservar excepciones de ejecución en tiempo de ejecución.
2. Instrucciones con potenciales efectos secundarios sobre memoria (`STORE`), llamadas a subrutinas (`CALL`) o despliegue en consola (`PRINT`) jamás son candidatas a remoción en el módulo de código muerto.

```

```
