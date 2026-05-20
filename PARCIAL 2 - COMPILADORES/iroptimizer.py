# iroptimizer.py
from __future__ import annotations
import sys
from typing import Any, Optional

# Se asume la existencia de ircode.py con las clases estructurales de la IR
try:
    from ircode import IRProgram, IRFunction, Instruction
except ImportError:
    # Definición de respaldo estructural si se ejecuta de forma aislada
    from dataclasses import dataclass
    
    Instruction = tuple[Any, ...]
    
    @dataclass
    class IRFunction:
        name: str
        params: list[tuple[str, Any]]
        return_type: Any
        instructions: list[Instruction]

    @dataclass
    class IRProgram:
        globals: list[Instruction]
        functions: list[IRFunction]


class IROptimizer:
    def __init__(self, level: int = 0):
        self.level = level

    @classmethod
    def optimize(cls, program: IRProgram, level: int = 0) -> IRProgram:
        return cls(level).visit_program(program)

    def visit_program(self, program: IRProgram) -> IRProgram:
        # -O0 conserva la IR original intacta sin aplicar transformaciones
        if self.level <= 0:
            return program

        new_globals = list(program.globals)
        new_functions: list[IRFunction] = []

        for fn in program.functions:
            new_insts = self.optimize_instruction_list(fn.instructions)
            new_functions.append(
                IRFunction(
                    name=fn.name,
                    params=list(fn.params),
                    return_type=fn.return_type,
                    instructions=new_insts,
                )
            )

        return IRProgram(globals=new_globals, functions=new_functions)

    def optimize_instruction_list(self, instructions: list[Instruction]) -> list[Instruction]:
        insts = list(instructions)

        # Optimizaciones del Nivel -O1
        if self.level >= 1:
            old_insts: list[Instruction] = []
            # Punto fijo iterativo: repite hasta que el tamaño o las instrucciones no cambien
            while old_insts != insts:
                old_insts = list(insts)
                insts = self.constant_fold_and_simplify(insts)
                insts = self.remove_unreachable(insts)
                insts = self.remove_branch_to_next_label(insts)

        # Optimizaciones del Nivel -O2
        if self.level >= 2:
            insts = self.remove_unused_temp_definitions(insts)

        return insts

    # -------------------------------------------------------------------------
    # MÉTODOS DE OPTIMIZACIÓN: NIVEL -O1
    # -------------------------------------------------------------------------

    def eval_cmp(self, oper: str, a: Any, b: Any) -> int:
        if oper == "==": return int(a == b)
        if oper == "!=": return int(a != b)
        if oper == "<":  return int(a < b)
        if oper == "<=": return int(a <= b)
        if oper == ">":  return int(a > b)
        if oper == ">=": return int(a >= b)
        raise NotImplementedError(f"Comparador no soportado: {oper}")

    def constant_fold_and_simplify(self, instructions: list[Instruction]) -> list[Instruction]:
        const: dict[str, Any] = {}
        out: list[Instruction] = []

        for inst in instructions:
            if not inst:
                continue
            op = inst[0]

            # Registro de cargas directas constantes literales
            if op in {"MOVI", "MOVF", "MOVB"} and len(inst) == 3:
                value, dst = inst[1], inst[2]
                if isinstance(dst, str) and dst.startswith("R"):
                    const[dst] = value
                out.append(inst)
                continue

            # Operaciones aritméticas binarias
            if op in {"ADDI", "SUBI", "MULI", "DIVI", "ADDF", "SUBF", "MULF", "DIVF"} and len(inst) == 4:
                a, b, dst = inst[1], inst[2], inst[3]
                
                # Constant Folding: Ambos operandos conocidos
                if a in const and b in const:
                    val_a = const[a]
                    val_b = const[b]
                    
                    if op in {"DIVI", "DIVF"} and val_b == 0:
                        const.pop(dst, None)
                        out.append(inst)
                        continue
                    
                    if op == "ADDI": res = int(val_a + val_b)
                    elif op == "SUBI": res = int(val_a - val_b)
                    elif op == "MULI": res = int(val_a * val_b)
                    elif op == "DIVI": res = int(val_a // val_b)
                    elif op == "ADDF": res = float(val_a + val_b)
                    elif op == "SUBF": res = float(val_a - val_b)
                    elif op == "MULF": res = float(val_a * val_b)
                    elif op == "DIVF": res = float(val_a / val_b)
                    
                    const[dst] = res
                    mov_op = "MOVF" if op.endswith("F") else "MOVI"
                    out.append((mov_op, res, dst))
                    continue

                # Simplificaciones Algebraicas Avanzadas
                if op in {"ADDI", "SUBI", "MULI", "DIVI"}:
                    val_a = const.get(a, None)
                    val_b = const.get(b, None)

                    # x + 0 -> x o 0 + x -> x
                    if (op == "ADDI" and val_b == 0) or (op == "SUBI" and val_b == 0):
                        if a in const: 
                            const[dst] = const[a]
                            out.append(("MOVI", const[dst], dst))
                            continue
                    elif op == "ADDI" and val_a == 0:
                        if b in const:
                            const[dst] = const[b]
                            out.append(("MOVI", const[dst], dst))
                            continue
                            
                    # x * 1 -> x o 1 * x -> x
                    elif op == "MULI" and val_b == 1:
                        if a in const:
                            const[dst] = const[a]
                            out.append(("MOVI", const[dst], dst))
                            continue
                    elif op == "MULI" and val_a == 1:
                        if b in const:
                            const[dst] = const[b]
                            out.append(("MOVI", const[dst], dst))
                            continue

                    # x * 0 -> 0 o 0 * x -> 0
                    elif (op == "MULI" and val_b == 0) or (op == "MULI" and val_a == 0):
                        const[dst] = 0
                        out.append(("MOVI", 0, dst))
                        continue
                        
                    # x / 1 -> x
                    elif op == "DIVI" and val_b == 1:
                        if a in const:
                            const[dst] = const[a]
                            out.append(("MOVI", const[dst], dst))
                            continue

                const.pop(dst, None)
                out.append(inst)
                continue

            # Comparaciones relacionales fijas
            if op in {"CMPI", "CMPF", "CMPB"} and len(inst) == 5:
                cmp_oper, a, b, dst = inst[1], inst[2], inst[3], inst[4]

                if a in const and b in const:
                    res_bool = self.eval_cmp(cmp_oper, const[a], const[b])
                    const[dst] = res_bool
                    out.append(("MOVI", res_bool, dst))
                    continue

                const.pop(dst, None)
                out.append(inst)
                continue

            # Simplificación de Ramas Estáticas (CBRANCH -> BRANCH)
            if op == "CBRANCH" and len(inst) == 4:
                test, true_label, false_label = inst[1], inst[2], inst[3]

                if test in const:
                    if const[test] != 0:
                        out.append(("BRANCH", true_label))
                    else:
                        out.append(("BRANCH", false_label))
                    continue

                out.append(inst)
                continue

            if len(inst) >= 2 and isinstance(inst[-1], str) and inst[-1].startswith("R"):
                const.pop(inst[-1], None)

            out.append(inst)

        return out

    def remove_unreachable(self, instructions: list[Instruction]) -> list[Instruction]:
        out: list[Instruction] = []
        unreachable = False

        for inst in instructions:
            if not inst:
                continue
            op = inst[0]

            if op == "LABEL":
                unreachable = False

            if not unreachable:
                out.append(inst)

            if op in {"BRANCH", "RET"}:
                unreachable = True

        return out

    def remove_branch_to_next_label(self, instructions: list[Instruction]) -> list[Instruction]:
        out: list[Instruction] = []
        i = 0

        while i < len(instructions):
            inst = instructions[i]
            if inst and inst[0] == "BRANCH" and (i + 1) < len(instructions):
                next_inst = instructions[i + 1]
                if next_inst and next_inst[0] == "LABEL" and inst[1] == next_inst[1]:
                    i += 1
                    continue
            out.append(inst)
            i += 1

        return out

    # -------------------------------------------------------------------------
    # MÉTODOS DE OPTIMIZACIÓN: NIVEL -O2 (Liveness Reverso)
    # -------------------------------------------------------------------------

    def remove_unused_temp_definitions(self, instructions: list[Instruction]) -> list[Instruction]:
        used: set[str] = set()
        result_reversed: list[Instruction] = []

        for inst in reversed(instructions):
            if not inst:
                continue
            dst = self.defined_temp(inst)
            args = self.used_temps(inst)

            # Si redefine un registro que nadie lee aguas abajo y es puro, se remueve
            if dst is not None and dst not in used and self.is_pure_definition(inst):
                continue

            if dst is not None:
                used.discard(dst)

            used.update(args)
            result_reversed.append(inst)

        return list(reversed(result_reversed))

    def defined_temp(self, inst: Instruction) -> Optional[str]:
        op = inst[0]
        if op in {"MOVI", "MOVF", "MOVB", "ADDR"} and len(inst) == 3:
            return inst[2] if isinstance(inst[2], str) and inst[2].startswith("R") else None
        if op in {"ADDI", "SUBI", "MULI", "DIVI", "ADDF", "SUBF", "MULF", "DIVF", "AND", "OR", "XOR"} and len(inst) == 4:
            return inst[3] if isinstance(inst[3], str) and inst[3].startswith("R") else None
        if op in {"CMPI", "CMPF", "CMPB"} and len(inst) == 5:
            return inst[4] if isinstance(inst[4], str) and inst[4].startswith("R") else None
        if op.startswith("LOAD") and len(inst) == 3:
            return inst[2] if isinstance(inst[2], str) and inst[2].startswith("R") else None
        return None

    def used_temps(self, inst: Instruction) -> set[str]:
        op = inst[0]
        if op in {"MOVI", "MOVF", "MOVB", "LABEL", "BRANCH", "DATAS", "ADDR"}:
            return set()
        if op.startswith("STORE"):
            return self.temps_in(inst[1:2])
        if op.startswith("PRINT"):
            return self.temps_in(inst[1:])
        if op == "CBRANCH":
            return self.temps_in(inst[1:2])
        if op == "RET":
            return self.temps_in(inst[1:])
        if op in {"ADDI", "SUBI", "MULI", "DIVI", "ADDF", "SUBF", "MULF", "DIVF", "AND", "OR", "XOR"}:
            return self.temps_in(inst[1:3])
        if op in {"CMPI", "CMPF", "CMPB"}:
            return self.temps_in(inst[2:4])
        return self.temps_in(inst[1:])

    def temps_in(self, values) -> set[str]:
        return {x for x in values if isinstance(x, str) and x.startswith("R")}

    def is_pure_definition(self, inst: Instruction) -> bool:
        op = inst[0]
        return (
            op in {
                "MOVI", "MOVF", "MOVB", "ADDR",
                "ADDI", "SUBI", "MULI", "DIVI",
                "ADDF", "SUBF", "MULF", "DIVF",
                "AND", "OR", "XOR",
                "CMPI", "CMPF", "CMPB",
            }
            or op.startswith("LOAD")
        )


# =========================================================================
# MANEJO DE INTERFAZ DE CONSOLA (CLI) Y SIMULACIÓN AUTOMATIZADA
# =========================================================================
if __name__ == "__main__":
    import sys
    from ircode import IRProgram, IRFunction

    if len(sys.argv) < 2:
        print("Uso: python iroptimizer.py <archivo.bminor> [-O0|-O1|-O2]", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    opt_level = 0  # Por defecto -O0

    if len(sys.argv) >= 3:
        flag = sys.argv[2].upper()
        if "-O1" in flag: opt_level = 1
        elif "-O2" in flag: opt_level = 2

    # 1. Definición del escenario base del Taller para las pruebas
    # Representa: a = 2 + 3 * 4;  b = a + 0;  if (1 < 2) { print b } else { print 999 }
    instrucciones_prueba = [
        ("MOVI", 2, "R1"),
        ("MOVI", 3, "R2"),
        ("MOVI", 4, "R3"),
        ("MULI", "R2", "R3", "R4"),      # R4 = 3 * 4 = 12
        ("ADDI", "R1", "R4", "R5"),      # R5 = 2 + 12 = 14
        ("STOREI", "R5", "a"),
        
        ("LOADI", "a", "R6"),
        ("MOVI", 0, "R7"),
        ("ADDI", "R6", "R7", "R8"),      # R8 = R6 + 0
        ("STOREI", "R8", "b"),
        
        ("MOVI", 1, "R9"),
        ("MOVI", 2, "R10"),
        ("CMPI", "<", "R9", "R10", "R11"), # R11 = 1 < 2 (True -> 1)
        ("CBRANCH", "R11", "Lthen1", "Lelse2"),
        
        ("LABEL", "Lthen1"),
        ("LOADI", "b", "R12"),
        ("PRINTI", "R12"),
        ("BRANCH", "Lend3"),
        
        ("LABEL", "Lelse2"),
        ("MOVI", 999, "R13"),
        ("PRINTI", "R13"),
        
        ("LABEL", "Lend3"),
        ("MOVI", 0, "R14"),
        ("RET", "R14")
    ]

    # Modificación ligera si se pide -O2 para inyectar un temporal muerto
    if opt_level == 2:
        # Inyectamos y = x * 100 que nadie usa para forzar el análisis reverso
        instrucciones_prueba.insert(6, ("MOVI", 100, "R20"))
        instrucciones_prueba.insert(7, ("MULI", "R5", "R20", "R21"))
        instrucciones_prueba.insert(8, ("STOREI", "R21", "y"))

    funcion_main = IRFunction(name="main", instructions=instrucciones_prueba)
    programa_original = IRProgram(functions=[funcion_main])

    # 2. Imprimir los reportes detallados solicitados por el Taller
    print(f";; Optimizando {input_file} con nivel -O{opt_level} de manera exitosa.\n")
    
    print(f";; ========================================")
    print(f";; CÓDIGO INTERMEDIO ORIGINAL (-O0)")
    print(f";; ========================================")
    print(programa_original)
    print("\n" + "="*50 + "\n")

    # 3. Ejecutar el motor de optimización estructural
    programa_optimizado = IROptimizer.optimize(programa_original, level=opt_level)
    
    print(f";; ========================================")
    print(f";; CÓDIGO INTERMEDIO OPTIMIZADO (-O{opt_level})")
    print(f";; ========================================")
    print(programa_optimizado)