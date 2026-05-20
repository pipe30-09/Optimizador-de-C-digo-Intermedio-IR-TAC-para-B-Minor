# ircode.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Union

# Definimos un alias de tipo para las Instrucciones.
# Según la especificación, cada instrucción es una tupla de Python.
# Ejemplos: ("MOVI", 2, "R1"), ("ADDI", "R1", "R2", "R3")
Instruction = tuple[Any, ...]

@dataclass
class IRFunction:
    """
    Representa una función dentro del código intermedio de B-Minor.
    """
    name: str
    params: list[tuple[str, Any]] = field(default_factory=list)
    return_type: Any = None
    instructions: list[Instruction] = field(default_factory=list)

    def __repr__(self) -> str:
        lines = [f"function {self.name}:"]
        if self.params:
            lines.append(f"  params: {self.params}")
        for inst in self.instructions:
            lines.append(f"  {inst}")
        return "\n".join(lines)


@dataclass
class IRProgram:
    """
    Representa el programa completo en Código de Tres Direcciones (TAC).
    Aloja variables globales e instrucciones de inicialización y la lista de funciones.
    """
    globals: list[Instruction] = field(default_factory=list)
    functions: list[IRFunction] = field(default_factory=list)

    def __repr__(self) -> str:
        sections = []
        if self.globals:
            sections.append(";; --- GLOBALS ---")
            for glob in self.globals:
                sections.append(str(glob))
            sections.append("")
        
        for fn in self.functions:
            sections.append(f";; --- FUNCTION {fn.name} ---")
            sections.append(str(fn))
            sections.append("")
            
        return "\n".join(sections)