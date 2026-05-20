# Optimización O1 sobre IR/TAC en B-Minor

La optimización **O1** de este `iroptimizer` es una optimización **local y simple sobre IR/TAC**, no sobre AST.

La idea central es recorrer las instrucciones una por una y aplicar **reescrituras seguras**.

```text
IR original
   ↓
O1 optimizer
   ↓
IR simplificado
```

---

# 1. Algoritmo general

El optimizador hace una pasada por las instrucciones:

```python
for inst in instructions:
    nueva_inst = optimizar(inst)
    guardar(nueva_inst)
```

Durante el recorrido mantiene dos tablas:

```python
const = {}
alias = {}
```

`const` guarda registros que tienen un valor constante:

```text
R1 = 5
```

`alias` guarda registros equivalentes:

```text
R3 = R1
```

Esto último es clave, porque la IR no tiene una instrucción clara tipo `MOV R1, R3`.

---

# 2. Constant Folding

Patrón:

```text
MOVI 3, R1
MOVI 4, R2
ADDI R1, R2, R3
```

El optimizador sabe:

```text
R1 = 3
R2 = 4
```

Entonces cambia:

```text
ADDI R1, R2, R3
```

por:

```text
MOVI 7, R3
```

Algoritmo:

```python
if a in const and b in const:
    result = const[a] + const[b]
    emit("MOVI", result, dst)
```

Aplica para:

```text
+
-
*
/
%
comparaciones
booleanos
```

---

# 3. Algebraic Simplification

Aquí están las reglas tipo compilador clásico:

```text
x + 0 → x
0 + x → x
x - 0 → x
x * 1 → x
1 * x → x
x * 0 → 0
0 * x → 0
x / 1 → x
x % 1 → 0
```

Ejemplo:

```text
ADDI R1, R0, R2
```

si `R0 = 0`, entonces:

```text
R2 = R1
```

Pero como no existe `MOV R1, R2`, se guarda:

```python
alias["R2"] = "R1"
```

Luego, si aparece:

```text
PRINTI R2
```

se reescribe como:

```text
PRINTI R1
```

Ese fue el ajuste importante.

---

# 4. Alias Propagation

Este es el patrón que arregla el problema de `x + 0`.

Antes:

```text
R2 = R1 + 0
```

No se podía convertir a:

```text
MOV R1, R2
```

porque la IR no tenía `MOV`.

Entonces hacemos:

```text
R2 es alias de R1
```

Internamente:

```python
alias["R2"] = "R1"
```

Y cada vez que una instrucción usa registros, se aplica:

```python
R2 → R1
```

Ejemplo:

```text
ADDI R1, R0, R2
PRINTI R2
```

se vuelve:

```text
PRINTI R1
```

La instrucción `ADDI` se puede eliminar porque solo produjo un alias.

---

# 5. Copy Propagation

Alias propagation es una forma de **copy propagation**.

Patrón conceptual:

```text
a = b
c = a + 1
```

se transforma en:

```text
c = b + 1
```

En la IR:

```text
R2 alias R1
ADDI R2, R3, R4
```

↓

```text
ADDI R1, R3, R4
```

---

# 6. Dead Temporary Elimination básica

Cuando una operación solo crea un alias:

```text
R2 = R1 + 0
```

no se emite ninguna instrucción para `R2`.

Se guarda:

```python
alias["R2"] = "R1"
```

Por eso esa instrucción desaparece.

Esto es una eliminación sencilla de temporales muertos.

---

# 7. Constant Propagation

Cuando se conoce que un registro vale una constante:

```text
MOVI 10, R1
```

se registra:

```python
const["R1"] = 10
```

Luego:

```text
ADDI R1, R2, R3
```

puede saber que `R1` es `10`.

Y si `R2` también es constante:

```text
R2 = 5
```

entonces hace constant folding:

```text
MOVI 15, R3
```

---

# 8. Invalidación

Cuando un registro se redefine, hay que borrar información vieja.

Ejemplo:

```text
MOVI 5, R1
ADDI R2, R3, R1
```

Después de la segunda instrucción ya no se puede seguir diciendo que:

```text
R1 = 5
```

Entonces el optimizador hace:

```python
kill(dst)
```

que elimina:

```python
const[dst]
alias[dst]
```

También elimina alias que dependan de ese registro.

---

# 9. Reescritura de operandos

Antes de optimizar una instrucción, se normalizan sus operandos.

Ejemplo:

```text
alias["R2"] = "R1"
```

Entonces:

```text
PRINTI R2
```

pasa a verse como:

```text
PRINTI R1
```

Ese patrón se llama:

```text
operand rewriting
```

o:

```text
canonicalization
```

---

# 10. Resumen de patrones usados

```text
Constant Folding
3 + 4 → 7

Constant Propagation
usar valores conocidos

Algebraic Simplification
x + 0 → x

Copy Propagation
a = b; usar a → usar b

Alias Propagation
registrar equivalencias entre temporales

Dead Temporary Elimination
eliminar instrucciones que solo producen alias

Canonicalization
reemplazar operandos por su forma más simple

Iterative Pass
repetir hasta que no haya cambios
```

---

# 11. Por qué esto es O1

Porque no construye CFG (Control Flow Graph), no analiza bloques básicos complejos y no hace SSA.

Es una optimización local:

```text
mira la instrucción actual
usa información simple acumulada
reescribe si puede
```

Por eso es ideal para estudiantes: se ve claramente cómo una IR mejora sin meterse todavía en teoría pesada.
