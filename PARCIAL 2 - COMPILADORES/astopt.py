# astopt.py
# ---------------------------------------------------
# Optimizador O1 sobre AST para B-Minor
#
# Fase recomendada:
#
#     source
#       ↓
#     parser
#       ↓
#     checker
#       ↓
#     ASTOptimizer O1   ← este archivo
#       ↓
#     ircode
#
# ---------------------------------------------------

from __future__ import annotations

from dataclasses import replace, is_dataclass, fields
from typing import Optional

from model import *


# ---------------------------------------------------
# Utilidades para literales
# ---------------------------------------------------

def is_int(node):
	return isinstance(node, IntegerLiteral)
	
	
def is_float(node):
	return isinstance(node, FloatLiteral)
	
	
def is_bool(node):
	return isinstance(node, BooleanLiteral)
	
	
def is_char(node):
	return isinstance(node, CharLiteral)
	
	
def is_string(node):
	return isinstance(node, StringLiteral)
	
	
def is_number(node):
	return is_int(node) or is_float(node)
	
	
def value_of(node):
	return getattr(node, "value", None)
	
	
def is_zero(node):
	return is_number(node) and value_of(node) == 0
	
	
def is_one(node):
	return is_number(node) and value_of(node) == 1
	
	
def make_number(value, template):
	'''
	Crea un literal numérico conservando el tipo base 
	del template.
	'''
	if isinstance(template, FloatLiteral):
		return FloatLiteral(float(value), lineno=getattr(template, "lineno", 0))
	return IntegerLiteral(int(value), lineno=getattr(template, "lineno", 0))
	
	
def make_bool(value, template=None):
	return BooleanLiteral(bool(value), lineno=getattr(template, "lineno", 0) if template else 0)
	
	
def same_literal_family(a, b):
	"""Familia compatible para folding directo."""
	if is_number(a) and is_number(b):
		return True
	return type(a) is type(b) and (
		is_bool(a) or is_char(a) or is_string(a)
	)
	
	
def has_side_effect(node):
	'''
	Conservador: una llamada puede tener efectos laterales.
	Se usa para evitar transformar x * 0 -> 0 si x es una llamada.
	'''
	if isinstance(node, FuncCall):
		return True
	if isinstance(node, BinOp):
		return has_side_effect(node.left) or has_side_effect(node.right)
	if isinstance(node, UnaryOp):
		return has_side_effect(node.expr)
	if isinstance(node, ConditionalExpr):
		return (
			has_side_effect(node.test)
			or has_side_effect(node.then_expr)
			or has_side_effect(node.else_expr)
		)
	if isinstance(node, ExprList):
		return any(has_side_effect(expr) for expr in node.exprs)
	return False
	
	
# ---------------------------------------------------
# Visitor de optimización O1
# ---------------------------------------------------

class ASTOptimizer(Visitor):
	def __init__(self):
		self.changed = False
		
	def mark_changed(self):
		self.changed = True
		
	# -------------------------------------------------
	# Fallback genérico
	# -------------------------------------------------
	
	def visit(self, node: Node):
		'''
		Fallback para nodos no especializados.
		Recorre dataclasses y optimiza campos que sean Node o list[Node].
		'''
		if not is_dataclass(node):
			return node
			
		updates = {}
		
		for f in fields(node):
			name = f.name
			value = getattr(node, name)
			
			if isinstance(value, list):
				new_list = []
				local_changed = False
				
				for item in value:
					if isinstance(item, Node):
						new_item = item.accept(self)
						if new_item is None:
							local_changed = True
							self.mark_changed()
							continue
						if isinstance(new_item, list):
							new_list.extend(new_item)
							local_changed = True
							self.mark_changed()
						else:
							new_list.append(new_item)
							if new_item is not item:
								local_changed = True
					else:
						new_list.append(item)
						
				if local_changed:
					updates[name] = new_list
					
			elif isinstance(value, Node):
				new_value = value.accept(self)
				if new_value is not value:
					updates[name] = new_value
					
		if updates:
			self.mark_changed()
			return replace(node, **updates)
			
		return node
		
	# -------------------------------------------------
	# Programa y bloques
	# -------------------------------------------------
	
	def visit(self, node: Program):
		decls = []
		local_changed = False
		
		for decl in node.decls:
			new_decl = decl.accept(self)
			
			if new_decl is None:
				local_changed = True
				self.mark_changed()
				continue
				
			if isinstance(new_decl, list):
				decls.extend(new_decl)
				local_changed = True
				self.mark_changed()
			else:
				decls.append(new_decl)
				if new_decl is not decl:
					local_changed = True
					
		if local_changed:
			self.mark_changed()
			return replace(node, decls=decls)
			
		return node
		
	def visit(self, node: Block):
		stmts = []
		local_changed = False
		
		for stmt in node.stmts:
			new_stmt = stmt.accept(self)
			
			if new_stmt is None:
				local_changed = True
				self.mark_changed()
				continue
				
			# if true { ... } puede devolver un Block; se aplana.
			if isinstance(new_stmt, Block):
				stmts.extend(new_stmt.stmts)
				local_changed = True
				self.mark_changed()
				continue
				
			if isinstance(new_stmt, list):
				stmts.extend(new_stmt)
				local_changed = True
				self.mark_changed()
				continue
				
			stmts.append(new_stmt)
			if new_stmt is not stmt:
				local_changed = True
				
		if local_changed:
			self.mark_changed()
			return replace(node, stmts=stmts)
			
		return node
		
	# -------------------------------------------------
	# Declaraciones
	# -------------------------------------------------
	
	def visit(self, node: VarDecl):
		if node.value is None:
			return node
		value = node.value.accept(self)
		if value is not node.value:
			self.mark_changed()
			return replace(node, value=value)
		return node
		
	def visit(self, node: ConstDecl):
		value = node.value.accept(self)
		if value is not node.value:
			self.mark_changed()
			return replace(node, value=value)
		return node
		
	def visit(self, node: FuncDecl):
		body = node.body.accept(self)
		if body is not node.body:
			self.mark_changed()
			return replace(node, body=body)
		return node
		
	# Opcional: solo funcionará si agrega ArrayDecl a model.py.
	def visit(self, node: ArrayDecl):
		updates = {}
		
		if getattr(node, "size", None) is not None and isinstance(node.size, Node):
			size = node.size.accept(self)
			if size is not node.size:
				updates["size"] = size
				
		value = getattr(node, "value", None)
		if value is not None and isinstance(value, Node):
			new_value = value.accept(self)
			if new_value is not value:
				updates["value"] = new_value
				
		if updates:
			self.mark_changed()
			return replace(node, **updates)
			
		return node
		
	# -------------------------------------------------
	# Sentencias
	# -------------------------------------------------
	
	def visit(self, node: Assignment):
		loc = node.loc.accept(self)
		expr = node.expr.accept(self)
		
		if loc is not node.loc or expr is not node.expr:
			self.mark_changed()
			return replace(node, loc=loc, expr=expr)
			
		return node
		
	def visit(self, node: PrintStmt):
		expr = node.expr.accept(self)
		if expr is not node.expr:
			self.mark_changed()
			return replace(node, expr=expr)
		return node
		
	def visit(self, node: ReturnStmt):
		if node.expr is None:
			return node
		expr = node.expr.accept(self)
		if expr is not node.expr:
			self.mark_changed()
			return replace(node, expr=expr)
		return node
		
	def visit(self, node: IfStmt):
		test = node.test.accept(self)
		then_block = node.then_block.accept(self)
		else_block = node.else_block.accept(self) if node.else_block else None
		
		# if true { A } else { B } -> A
		# if false { A } else { B } -> B o eliminado
		if is_bool(test):
			self.mark_changed()
			if test.value:
				return then_block
			return else_block
			
		if (
			test is not node.test
			or then_block is not node.then_block
			or else_block is not node.else_block
		):
			self.mark_changed()
			return replace(
				node,
				test=test,
				then_block=then_block,
				else_block=else_block,
			)
			
		return node
		
	def visit(self, node: WhileStmt):
		test = node.test.accept(self)
		body = node.body.accept(self)
		
		# while false { ... } -> eliminado
		if is_bool(test) and test.value is False:
			self.mark_changed()
			return None
			
		if test is not node.test or body is not node.body:
			self.mark_changed()
			return replace(node, test=test, body=body)
			
		return node
		
	def visit(self, node: ForStmt):
		init = node.init.accept(self) if node.init else None
		test = node.test.accept(self) if node.test else None
		step = node.step.accept(self) if node.step else None
		body = node.body.accept(self)
		
		# for(init; false; step) body -> init
		if test is not None and is_bool(test) and test.value is False:
			self.mark_changed()
			return init
			
		if init is not node.init or test is not node.test or step is not node.step or body is not node.body:
			self.mark_changed()
			return replace(node, init=init, test=test, step=step, body=body)
			
		return node
		
	# -------------------------------------------------
	# Ubicaciones y llamadas
	# -------------------------------------------------
	
	def visit(self, node: VarLoc):
		return node
		
	def visit(self, node: ArrayLoc):
		index = node.index.accept(self)
		if index is not node.index:
			self.mark_changed()
			return replace(node, index=index)
		return node
		
	def visit(self, node: FuncCall):
		args = node.args.accept(self)
		if args is not node.args:
			self.mark_changed()
			return replace(node, args=args)
		return node
		
	def visit(self, node: ExprList):
		exprs = []
		local_changed = False
		
		for expr in node.exprs:
			new_expr = expr.accept(self)
			exprs.append(new_expr)
			if new_expr is not expr:
				local_changed = True
				
		if local_changed:
			self.mark_changed()
			return replace(node, exprs=exprs)
			
		return node
		
	# -------------------------------------------------
	# Literales
	# -------------------------------------------------
	
	def visit(self, node: IntegerLiteral):
		return node
		
	def visit(self, node: FloatLiteral):
		return node
		
	def visit(self, node: BooleanLiteral):
		return node
		
	def visit(self, node: CharLiteral):
		return node
		
	def visit(self, node: StringLiteral):
		return node
		
	# -------------------------------------------------
	# Expresiones
	# -------------------------------------------------
	
	def visit(self, node: BinOp):
		left = node.left.accept(self)
		right = node.right.accept(self)
		oper = node.oper
		
		# -----------------------------------------------
		# 1. Constant folding aritmético
		# -----------------------------------------------
		if same_literal_family(left, right):
			lv = value_of(left)
			rv = value_of(right)
			
			try:
				if is_number(left) and is_number(right):
					template = left if is_float(left) or is_float(right) else left
					
					if oper == "+":
						self.mark_changed()
						return make_number(lv + rv, template)
					if oper == "-":
						self.mark_changed()
						return make_number(lv - rv, template)
					if oper == "*":
						self.mark_changed()
						return make_number(lv * rv, template)
					if oper == "/" and rv != 0:
						self.mark_changed()
						if is_int(left) and is_int(right):
							return IntegerLiteral(lv // rv, lineno=node.lineno)
						return FloatLiteral(lv / rv, lineno=node.lineno)
					if oper == "%" and rv != 0 and is_int(left) and is_int(right):
						self.mark_changed()
						return IntegerLiteral(lv % rv, lineno=node.lineno)
						
				# Relacionales con literales compatibles
				if oper == "==":
					self.mark_changed()
					return BooleanLiteral(lv == rv, lineno=node.lineno)
				if oper == "!=":
					self.mark_changed()
					return BooleanLiteral(lv != rv, lineno=node.lineno)
				if oper == "<":
					self.mark_changed()
					return BooleanLiteral(lv < rv, lineno=node.lineno)
				if oper == "<=":
					self.mark_changed()
					return BooleanLiteral(lv <= rv, lineno=node.lineno)
				if oper == ">":
					self.mark_changed()
					return BooleanLiteral(lv > rv, lineno=node.lineno)
				if oper == ">=":
					self.mark_changed()
					return BooleanLiteral(lv >= rv, lineno=node.lineno)
					
			except Exception:
				# Si por alguna razón no puede plegar, conserva el árbol.
				pass
				
		# -----------------------------------------------
		# 2. Simplificación algebraica conservadora
		# -----------------------------------------------
		if oper == "+":
			if is_zero(right):
				self.mark_changed()
				return left
			if is_zero(left):
				self.mark_changed()
				return right
				
		elif oper == "-":
			if is_zero(right):
				self.mark_changed()
				return left
				
		elif oper == "*":
			if is_one(right):
				self.mark_changed()
				return left
			if is_one(left):
				self.mark_changed()
				return right
				
			# Solo se elimina x si sabemos que no hay efectos laterales.
			if is_zero(right) and not has_side_effect(left):
				self.mark_changed()
				return right
			if is_zero(left) and not has_side_effect(right):
				self.mark_changed()
				return left
				
		elif oper == "/":
			if is_one(right):
				self.mark_changed()
				return left
				
		elif oper == "%":
			if is_one(right) and not has_side_effect(left):
				self.mark_changed()
				return IntegerLiteral(0, lineno=node.lineno)
				
		# -----------------------------------------------
		# 3. Simplificación booleana
		# -----------------------------------------------
		elif oper in ("&&", "and"):
			if is_bool(left) and left.value is False:
				self.mark_changed()
				return left
			if is_bool(left) and left.value is True:
				self.mark_changed()
				return right
			if is_bool(right) and right.value is False and not has_side_effect(left):
				self.mark_changed()
				return right
			if is_bool(right) and right.value is True:
				self.mark_changed()
				return left
				
		elif oper in ("||", "or"):
			if is_bool(left) and left.value is True:
				self.mark_changed()
				return left
			if is_bool(left) and left.value is False:
				self.mark_changed()
				return right
			if is_bool(right) and right.value is True and not has_side_effect(left):
				self.mark_changed()
				return right
			if is_bool(right) and right.value is False:
				self.mark_changed()
				return left
				
		if left is not node.left or right is not node.right:
			self.mark_changed()
			return replace(node, left=left, right=right)
			
		return node
		
	def visit(self, node: UnaryOp):
		expr = node.expr.accept(self)
		oper = node.oper
		
		if is_int(expr):
			if oper == "-":
				self.mark_changed()
				return IntegerLiteral(-expr.value, lineno=node.lineno)
			if oper == "+":
				self.mark_changed()
				return expr
				
		if is_float(expr):
			if oper == "-":
				self.mark_changed()
				return FloatLiteral(-expr.value, lineno=node.lineno)
			if oper == "+":
				self.mark_changed()
				return expr
				
		if is_bool(expr) and oper in ("!", "not"):
			self.mark_changed()
			return BooleanLiteral(not expr.value, lineno=node.lineno)
			
		if expr is not node.expr:
			self.mark_changed()
			return replace(node, expr=expr)
			
		return node
		
	def visit(self, node: ConditionalExpr):
		test = node.test.accept(self)
		then_expr = node.then_expr.accept(self)
		else_expr = node.else_expr.accept(self)
		
		# true ? a : b -> a
		# false ? a : b -> b
		if is_bool(test):
			self.mark_changed()
			return then_expr if test.value else else_expr
			
		if test is not node.test or then_expr is not node.then_expr or else_expr is not node.else_expr:
			self.mark_changed()
			return replace(
			node,
			test=test,
			then_expr=then_expr,
			else_expr=else_expr,
			)
			
		return node
		
		
# ---------------------------------------------------
# API pública
# ---------------------------------------------------

def optimize_ast_o1(ast: Node, max_passes: int = 10, verbose: bool = False) -> Node:
	"""
	Ejecuta O1 sobre el AST.
	
	Se hacen varias pasadas porque una optimización puede habilitar otra:
	
	(3 * 4) + 0
	12 + 0
	12
	"""
	current = ast
	
	for passno in range(1, max_passes + 1):
		opt = ASTOptimizer()
		new_ast = current.accept(opt)
		
		if verbose:
			print(f"[O1] pasada {passno}: changed={opt.changed}")
			
		current = new_ast
		
		if not opt.changed:
			break
			
	return current


ast = Program([
	VarDecl(
        "x",
        IntegerType(),

        BinOp(
            "+",
            IntegerLiteral(value=3),

            BinOp(
                "*",
                IntegerLiteral(value=4),
                IntegerLiteral(value=2)
            )
        )
    ),

    VarDecl(
        "y",
        IntegerType(),

        BinOp(
            "+",
            VarLoc("x"),
            IntegerLiteral(value=0)
        )
    ),

    VarDecl(
        "z",
        IntegerType(),

        BinOp(
            "*",
            VarLoc("y"),
            IntegerLiteral(value=1)
        )
    ),

    VarDecl(
        "w",
        IntegerType(),

        BinOp(
            "*",
            VarLoc("z"),
            IntegerLiteral(value=0)
        )
    ),

    IfStmt(
        BooleanLiteral(value=True),

        Block([
            PrintStmt(
                IntegerLiteral(value=111)
            )
        ]),

        Block([
            PrintStmt(
                IntegerLiteral(value=222)
            )
        ])
    ),

    WhileStmt(
        BooleanLiteral(value=False),

        Block([
            PrintStmt(
                IntegerLiteral(value=999)
            )
        ])
    ),

    VarDecl(
        "t",
        IntegerType(),

        ConditionalExpr(
            BooleanLiteral(value=True),
            IntegerLiteral(value=10),
            IntegerLiteral(value=20)
        )
    )

])

print("===================================")
print("AST ORIGINAL")
print("===================================")
print(ast)

optimized = optimize_ast_o1(ast, verbose=True)

print()
print("===================================")
print("AST OPTIMIZADO")
print("===================================")
print(optimized)
