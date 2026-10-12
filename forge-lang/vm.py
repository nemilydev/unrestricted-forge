#!/usr/bin/env python3
"""
Ember VM — bytecode compiler + stack machine for the Unrestricted Forge.

Pipeline: source → Lexer/Parser (shared with main.py) → Compiler (AST →
bytecode with constant pool) → VM (frames, value stack, upvalue cells).

Why: the tree-walking interpreter re-visits every node on every execution.
The VM visits the AST once, then executes flat instructions. Closures use
Lua-style upvalue cells: a captured variable is boxed into a Cell at
closure-creation time, so loops capture per-iteration bindings (0,1,2 —
not 2,2,2) and mutations stay shared.

Usage:
    python3 vm.py examples/fibonacci.fl
    python3 vm.py -e 'print("hello, vm")'
"""

import sys
import time

from main import (
    Lexer, Parser, LexerError, ParseError,
    Num, Str, Bool, Nil, Ident, ListLit, BinOp, UnaryOp, Assign,
    Call, Index, Member, Let, Fn, If, While, For, Return, Break,
    Continue, ExprStmt, Block,
    EmberList, EmberBuiltin, EmberDict,
)


# ──────────────────────────────────────────────────────────────
# 1. INSTRUCTION SET
# ──────────────────────────────────────────────────────────────

# Stack-machine ops. Operand in comments.
OPS = [
    "CONST",        # arg: constant-pool index → push constant
    "NIL",          # → push None
    "TRUE",         # → push True
    "FALSE",        # → push False
    "POP",          # pop and discard
    "DUP",          # duplicate top
    "LOAD_NAME",    # arg: name index → resolve scopes→chain→globals
    "DEF_NAME",     # arg: name index → define in current scope (let)
    "STORE_NAME",   # arg: name index → assign through existing binding
    "GET_INDEX",    # obj, idx → obj[idx]
    "GET_PROP",     # arg: name index → property or bound method
    "BINOP",        # arg: op string (+ - * / % == != < > <= >=)
    "UNARY",        # arg: "not" | "-"
    "MAKE_LIST",    # arg: n → pop n, push EmberList
    "JUMP",         # arg: target ip
    "JUMP_FALSE",   # arg: target ip (pops condition)
    "JUMP_BACK",    # arg: target ip
    "JUMP_TRUE",    # arg: target ip (pops condition)
    "FOR_INIT",     # iterable → push iterator
    "FOR_ITER",     # arg: exit ip; iterator → item | jump
    "PUSH_SCOPE",   # push a scope dict on the frame
    "POP_SCOPE",    # pop one
    "CAPTURE",      # arg: name index → box variable into Cell, push Cell
    "CLOSURE",      # arg: function index; pops N cells → push Closure
    "CALL",         # arg: argc → call
    "RETURN",       # pop value, pop frame
]


class Instr:
    __slots__ = ("op", "arg")
    def __init__(self, op, arg=None):
        self.op = op
        self.arg = arg
    def __repr__(self):
        return f"({self.op} {self.arg!r})" if self.arg is not None else f"({self.op})"


class EmberFunc:
    """Compiled function: bytecode + metadata."""
    __slots__ = ("name", "params", "code", "free_vars", "consts")
    def __init__(self, name, params, code, free_vars, consts):
        self.name = name
        self.params = params
        self.code = code
        self.free_vars = free_vars
        self.consts = consts


class Closure:
    __slots__ = ("func", "cells", "env")
    def __init__(self, func, cells, env):
        self.func = func      # EmberFunc
        self.cells = cells    # list of Cell, parallel to func.free_vars
        self.env = env        # Frame the closure was created in (may be None)
    def __repr__(self):
        return f"<fn {self.func.name}({', '.join(self.func.params)})>"


class Cell:
    __slots__ = ("value",)
    def __init__(self, value):
        self.value = value


class BoundMethod:
    __slots__ = ("obj", "name")
    def __init__(self, obj, name):
        self.obj = obj
        self.name = name
    def __repr__(self):
        return f"<method {self.name}>"


class Iterator:
    __slots__ = ("items", "i")
    def __init__(self, items):
        self.items = items
        self.i = 0


# ──────────────────────────────────────────────────────────────
# 2. COMPILER — AST → bytecode
# ──────────────────────────────────────────────────────────────

class CompileError(Exception):
    pass


class Compiler:
    """Compiles one function body at a time."""

    def __init__(self):
        self.pool = []       # shared constant pool (strings for names/ops)
        self._pool_idx = {}

    def const(self, value):
        if value not in self._pool_idx:
            self._pool_idx[value] = len(self.pool)
            self.pool.append(value)
        return self._pool_idx[value]

    # ── entry: compile a whole script ──
    def compile_script(self, stmts):
        return self.compile_function("<script>", [], stmts)

    def compile_function(self, name, params, body):
        c = FuncCompiler(self, name, params)
        code = c.compile_body(body, toplevel=(name == "<script>"))
        free = free_variables(body, set(params))
        return EmberFunc(name, params, code, free, self.pool)


class FuncCompiler:
    def __init__(self, owner, name, params):
        self.owner = owner           # shared Compiler (constant pool)
        self.name = name
        self.params = params
        self.code = []
        self.scope_depth = 0
        self.loops = []              # (continue_ip, break_patches, scope_depth)

    def emit(self, op, arg=None):
        self.code.append(Instr(op, arg))
        return len(self.code) - 1

    def patch(self, ip, target):
        self.code[ip].arg = target

    def cname(self, name):
        return self.owner.const(name)

    # ── statements ──
    def compile_body(self, stmts, toplevel=False):
        if toplevel:
            self.emit("PUSH_SCOPE")
        for s in stmts:
            self.stmt(s)
        self.emit("RETURN")
        return self.code

    def stmt(self, node):
        t = type(node)
        if t is Let:
            self.expr(node.value)
            self.emit("DEF_NAME", self.cname(node.name))
        elif t is ExprStmt:
            self.expr(node.expr)
            # Assign already consumed its value via STORE_NAME — no POP
            if type(node.expr) is not Assign:
                self.emit("POP")
        elif t is Fn:
            self.function(node)
            self.emit("DEF_NAME", self.cname(node.name))
        elif t is If:
            self.if_stmt(node)
        elif t is While:
            self.while_stmt(node)
        elif t is For:
            self.for_stmt(node)
        elif t is Return:
            if node.value is None:
                self.emit("NIL")
            else:
                self.expr(node.value)
            self.emit("RETURN")
        elif t is Break:
            _, patches, loop_depth = self.loops[-1]
            for _ in range(self.scope_depth - loop_depth):
                self.emit("POP_SCOPE")
            patches.append(self.emit("JUMP", None))
        elif t is Continue:
            cont_ip, _, loop_depth = self.loops[-1]
            for _ in range(self.scope_depth - loop_depth):
                self.emit("POP_SCOPE")
            self.emit("JUMP_BACK", cont_ip)
        elif t is Block:
            self.emit("PUSH_SCOPE")
            self.scope_depth += 1
            for s in node.stmts:
                self.stmt(s)
            self.scope_depth -= 1
            self.emit("POP_SCOPE")
        else:
            raise CompileError(f"Cannot compile statement {t.__name__}")

    def if_stmt(self, node):
        # every branch's exit jump lands at the same end — collect ALL of
        # them, not just the last (each `elif` adds another)
        end_jumps = []
        self.expr(node.cond)
        j_else = self.emit("JUMP_FALSE", None)
        for s in node.then:
            self.stmt(s)
        end_jumps.append(self.emit("JUMP", None))
        self.patch(j_else, len(self.code))

        for econd, ebody in node.branches:
            self.expr(econd)
            j_next = self.emit("JUMP_FALSE", None)
            for s in ebody:
                self.stmt(s)
            end_jumps.append(self.emit("JUMP", None))  # each branch → end
            self.patch(j_next, len(self.code))

        if node.els is not None:
            for s in node.els:
                self.stmt(s)
        for j in end_jumps:
            self.patch(j, len(self.code))

    def while_stmt(self, node):
        top = len(self.code)
        self.expr(node.cond)
        j_exit = self.emit("JUMP_FALSE", None)
        self.emit("PUSH_SCOPE")
        self.scope_depth += 1
        self.loops.append((None, [], self.scope_depth))
        for s in node.body:
            self.stmt(s)
        loop = self.loops.pop()
        self.scope_depth -= 1
        self.emit("POP_SCOPE")
        self.emit("JUMP_BACK", top)
        self.patch(j_exit, len(self.code))
        for bp in loop[1]:
            self.patch(bp, len(self.code))

    def for_stmt(self, node):
        self.expr(node.iterable)
        self.emit("FOR_INIT")
        top = len(self.code)
        j_exit = self.emit("FOR_ITER", None)
        self.emit("PUSH_SCOPE")
        self.scope_depth += 1
        # fresh binding per iteration: DEF into the fresh scope
        self.emit("DEF_NAME", self.cname(node.var))
        # continue → FOR_ITER: it advances the iterator and re-tests,
        # so the fresh scope/binding on the next lap is emitted again
        self.loops.append((top, [], self.scope_depth))
        for s in node.body:
            self.stmt(s)
        loop = self.loops.pop()
        self.scope_depth -= 1
        self.emit("POP_SCOPE")
        self.emit("JUMP_BACK", top)
        self.patch(j_exit, len(self.code))
        self.emit("POP")               # discard iterator
        for bp in loop[1]:
            self.patch(bp, len(self.code))

    # ── expressions ──
    def expr(self, node):
        t = type(node)
        if t is Num:
            self.emit("CONST", self.owner.const(node.value))
        elif t is Str:
            self.emit("CONST", self.owner.const(node.value))
        elif t is Bool:
            self.emit("TRUE" if node.value else "FALSE")
        elif t is Nil:
            self.emit("NIL")
        elif t is Ident:
            self.emit("LOAD_NAME", self.cname(node.name))
        elif t is ListLit:
            for e in node.elements:
                self.expr(e)
            self.emit("MAKE_LIST", len(node.elements))
        elif t is BinOp:
            if node.op == "and":
                self.expr(node.left)
                self.emit("DUP")
                j = self.emit("JUMP_FALSE", None)
                self.emit("POP")
                self.expr(node.right)
                self.patch(j, len(self.code))
            elif node.op == "or":
                self.expr(node.left)
                self.emit("DUP")
                j = self.emit("JUMP_TRUE", None)
                self.emit("POP")
                self.expr(node.right)
                self.patch(j, len(self.code))
            else:
                self.expr(node.left)
                self.expr(node.right)
                self.emit("BINOP", self.owner.const(node.op))
        elif t is UnaryOp:
            self.expr(node.operand)
            self.emit("UNARY", self.owner.const(node.op))
        elif t is Assign:
            self.expr(node.value)
            self.emit("STORE_NAME", self.cname(node.name))
        elif t is Call:
            self.expr(node.callee)
            for a in node.args:
                self.expr(a)
            self.emit("CALL", len(node.args))
        elif t is Index:
            self.expr(node.obj)
            self.expr(node.index)
            self.emit("GET_INDEX")
        elif t is Member:
            self.expr(node.obj)
            self.emit("GET_PROP", self.cname(node.name))
        elif t is Fn:
            self.function(node)
        else:
            raise CompileError(f"Cannot compile expression {t.__name__}")

    def function(self, node):
        inner = FuncCompiler(self.owner, node.name or "<anon>", node.params)
        inner.emit("PUSH_SCOPE")
        # NOTE: params are bound by do_call directly into the frame's
        # scope — emitting DEF_NAME here would pop the caller's stack.
        for s in node.body:
            inner.stmt(s)
        inner.emit("RETURN")
        free = free_variables(node, set(node.params))
        func = EmberFunc(node.name or "<anon>", node.params,
                         inner.code, free, self.owner.pool)
        fidx = self.owner.const(func)
        # push cells for each free variable, then CLOSURE pops them
        for fv in free:
            self.emit("CAPTURE", self.cname(fv))
        self.emit("CLOSURE", fidx)


def free_variables(node, bound):
    """Names referenced but not bound inside this function's own scope.

    One sequential walker: statement lists are walked in order with an
    evolving bound-set, so `let a = 0` binds `a` for everything after it.
    Nested function bodies are walked with their own bound-set (params +
    their own name); references that fall through land in `free`, which
    is exactly the capture list — no separate inner-collector needed.
    """
    free = set()

    def walk_stmts(stmts, bound):
        b = set(bound)
        for s in stmts:
            walk(s, b)

    def walk(n, bound):
        t = type(n)
        if t is Ident:
            if n.name not in bound:
                free.add(n.name)
        elif t is BinOp:
            walk(n.left, bound); walk(n.right, bound)
        elif t is UnaryOp:
            walk(n.operand, bound)
        elif t is Assign:
            walk(n.value, bound)
            # assigning to an outer variable captures it too
            if n.name not in bound:
                free.add(n.name)
        elif t is Call:
            walk(n.callee, bound)
            for a in n.args: walk(a, bound)
        elif t is Index:
            walk(n.obj, bound); walk(n.index, bound)
        elif t is Member:
            walk(n.obj, bound)
        elif t is ListLit:
            for e in n.elements: walk(e, bound)
        elif t is Let:
            walk(n.value, bound)
            bound.add(n.name)          # binds from here on
        elif t is ExprStmt:
            walk(n.expr, bound)
        elif t is Fn:
            inner = set(bound) | set(n.params)
            if n.name: inner.add(n.name)
            walk_stmts(n.body, inner)
            if n.name: bound.add(n.name)  # fn decl binds its name from here on
        elif t is If:
            walk(n.cond, bound)
            walk_stmts(n.then, bound)
            for ec, eb in n.branches:
                walk(ec, bound)
                walk_stmts(eb, bound)
            if n.els is not None:
                walk_stmts(n.els, bound)
        elif t is While:
            walk(n.cond, bound)
            walk_stmts(n.body, bound)
        elif t is For:
            walk(n.iterable, bound)
            walk_stmts(n.body, bound | {n.var})
        elif t is Return:
            if n.value is not None: walk(n.value, bound)
        elif t is Block:
            walk_stmts(n.stmts, bound)
        elif t in (Break, Continue, Nil, Bool, Num, Str):
            pass
        else:
            raise CompileError(f"free_variables: unknown node {t.__name__}")

    # node is either a Fn (params already in `bound`) or a stmt list
    if isinstance(node, list):
        walk_stmts(node, bound)
    else:
        walk(node, bound)
    return sorted(free)


# ──────────────────────────────────────────────────────────────
# 3. VIRTUAL MACHINE
# ──────────────────────────────────────────────────────────────

class EmberRuntimeError(Exception):
    pass


class Frame:
    __slots__ = ("func", "ip", "scopes", "chain", "base", "cells")
    def __init__(self, func, chain, base, cells=None):
        self.func = func
        self.ip = 0
        self.scopes = [{}]   # scope stack; vars may be Cell
        self.chain = chain   # enclosing frame chain (closure env)
        self.base = base     # value-stack base for this frame
        self.cells = cells or {}  # name → Cell (closure's captured free vars)


def truthy(v):
    if v is None: return False
    if isinstance(v, bool): return v
    if isinstance(v, (int, float)): return v != 0
    if isinstance(v, str): return len(v) > 0
    if isinstance(v, EmberList): return len(v.elements) > 0
    return True


def to_str(v):
    if v is None: return "nil"
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15: return str(int(v))
        return str(v)
    if isinstance(v, EmberList):
        return "[" + ", ".join(to_str(e) for e in v.elements) + "]"
    if isinstance(v, EmberDict):
        return "{" + ", ".join(f"{k}: {to_str(x)}" for k, x in v.pairs.items()) + "}"
    if isinstance(v, (Closure, EmberBuiltin, BoundMethod)):
        return repr(v)
    return str(v)


class VM:
    def __init__(self):
        self.globals = {}
        self.stack = []
        self.frames = []
        self._install_builtins()

    # ── builtins ──
    def _install_builtins(self):
        g = self.globals
        g["print"] = EmberBuiltin(self._b_print, "print")
        g["str"] = EmberBuiltin(lambda a: to_str(a[0]), "str")
        g["num"] = EmberBuiltin(lambda a: float(a[0]) if a[0] is not None else 0.0, "num")
        g["int"] = EmberBuiltin(lambda a: int(a[0]), "int")
        g["abs"] = EmberBuiltin(lambda a: abs(a[0]), "abs")
        g["min"] = EmberBuiltin(lambda a: min(a), "min")
        g["max"] = EmberBuiltin(lambda a: max(a), "max")
        g["floor"] = EmberBuiltin(lambda a: float(int(a[0])), "floor")
        g["ceil"] = EmberBuiltin(lambda a: float(int(a[0]) + (1 if a[0] != int(a[0]) else 0)), "ceil")
        g["round"] = EmberBuiltin(lambda a: round(a[0]), "round")

        def _len(a):
            v = a[0]
            if isinstance(v, EmberList): return len(v.elements)
            if isinstance(v, str): return len(v)
            return 0
        g["len"] = EmberBuiltin(_len, "len")

        def _type(a):
            v = a[0]
            if v is None: return "nil"
            if isinstance(v, bool): return "bool"
            if isinstance(v, (int, float)): return "number"
            if isinstance(v, str): return "string"
            if isinstance(v, EmberList): return "list"
            if isinstance(v, (Closure, EmberBuiltin, BoundMethod)): return "function"
            return "unknown"
        g["type"] = EmberBuiltin(_type, "type")

        def _range(a):
            if len(a) > 1:
                return EmberList(list(range(int(a[0]), int(a[1]))))
            return EmberList(list(range(0, int(a[0]))))
        g["range"] = EmberBuiltin(_range, "range")

        def _push(a):
            lst, val = a[0], a[1]
            if isinstance(lst, EmberList):
                lst.elements.append(val)
            return None
        g["push"] = EmberBuiltin(_push, "push")

    def _b_print(self, args):
        print(" ".join(to_str(a) for a in args))
        return None

    # ── driver ──
    def run(self, source):
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        compiler = Compiler()
        script = compiler.compile_script(ast)
        frame = Frame(script, None, 0)
        self.frames.append(frame)
        self.exec_loop()

    # ── name resolution ──
    def _lookup_frame(self, frame, name):
        for scope in reversed(frame.scopes):
            if name in scope:
                return scope
        chain = frame.chain
        while chain is not None:
            for scope in reversed(chain.scopes):
                if name in scope:
                    return scope
            chain = chain.chain
        return None

    def load_name(self, frame, name):
        scope = self._lookup_frame(frame, name)
        if scope is not None:
            v = scope[name]
            return v.value if isinstance(v, Cell) else v
        if name in frame.cells:
            return frame.cells[name].value
        if name in self.globals:
            return self.globals[name]
        raise EmberRuntimeError(f"Undefined variable '{name}'")

    def store_name(self, frame, name, value):
        scope = self._lookup_frame(frame, name)
        if scope is not None:
            v = scope[name]
            if isinstance(v, Cell):
                v.value = value
            else:
                scope[name] = value
            return
        if name in frame.cells:
            frame.cells[name].value = value
            return
        if name in self.globals:
            self.globals[name] = value
            return
        raise EmberRuntimeError(
            f"Cannot assign to undefined variable '{name}' — use 'let' first")

    def capture(self, frame, name):
        """Box `name` into a Cell in whichever frame owns it; return the Cell."""
        for scope in reversed(frame.scopes):
            if name in scope:
                v = scope[name]
                if not isinstance(v, Cell):
                    v = Cell(v)
                    scope[name] = v
                return v
        chain = frame.chain
        while chain is not None:
            for scope in reversed(chain.scopes):
                if name in scope:
                    v = scope[name]
                    if not isinstance(v, Cell):
                        v = Cell(v)
                        scope[name] = v
                    return v
            chain = chain.chain
        if name in frame.cells:
            return frame.cells[name]
        if name in self.globals:
            return Cell(self.globals[name])
        raise EmberRuntimeError(f"Undefined variable '{name}'")

    # ── the dispatch loop ──
    def exec_loop(self, stop_depth=None):
        """Run frames until empty — or until the frame stack shrinks back
        to stop_depth (used by synchronous host-driven calls like map)."""
        stack = self.stack
        while self.frames and (stop_depth is None or len(self.frames) > stop_depth):
            frame = self.frames[-1]
            code = frame.func.code
            consts = frame.func.consts
            ip = frame.ip
            op = code[ip].op
            arg = code[ip].arg
            frame.ip = ip + 1

            if op == "CONST":
                stack.append(consts[arg])
            elif op == "NIL":
                stack.append(None)
            elif op == "TRUE":
                stack.append(True)
            elif op == "FALSE":
                stack.append(False)
            elif op == "POP":
                stack.pop()
            elif op == "DUP":
                stack.append(stack[-1])
            elif op == "LOAD_NAME":
                stack.append(self.load_name(frame, consts[arg]))
            elif op == "DEF_NAME":
                frame.scopes[-1][consts[arg]] = stack.pop()
            elif op == "STORE_NAME":
                self.store_name(frame, consts[arg], stack.pop())
            elif op == "GET_INDEX":
                idx, obj = stack.pop(), stack.pop()
                stack.append(self.get_index(obj, idx))
            elif op == "GET_PROP":
                obj = stack.pop()
                stack.append(self.get_prop(obj, consts[arg]))
            elif op == "BINOP":
                right, left = stack.pop(), stack.pop()
                stack.append(self.binop(consts[arg], left, right))
            elif op == "UNARY":
                v = stack.pop()
                opname = consts[arg]
                if opname == "not":
                    stack.append(not truthy(v))
                elif opname == "-":
                    stack.append(-v)
                else:
                    raise EmberRuntimeError(f"Unknown unary operator {opname}")
            elif op == "MAKE_LIST":
                n = arg
                items = stack[len(stack)-n:]
                del stack[len(stack)-n:]
                stack.append(EmberList(items))
            elif op == "JUMP":
                frame.ip = arg
            elif op == "JUMP_FALSE":
                if not truthy(stack.pop()):
                    frame.ip = arg
            elif op == "JUMP_TRUE":
                if truthy(stack.pop()):
                    frame.ip = arg
            elif op == "JUMP_BACK":
                frame.ip = arg
            elif op == "FOR_INIT":
                it = stack.pop()
                if isinstance(it, EmberList):
                    stack.append(Iterator(list(it.elements)))
                elif isinstance(it, str):
                    stack.append(Iterator(list(it)))
                elif isinstance(it, (int, float)):
                    stack.append(Iterator(list(range(int(it)))))
                else:
                    raise EmberRuntimeError(f"Cannot iterate over {type(it).__name__}")
            elif op == "FOR_ITER":
                it = stack[-1]
                if it.i < len(it.items):
                    stack.append(it.items[it.i])
                    it.i += 1
                else:
                    frame.ip = arg
            elif op == "PUSH_SCOPE":
                frame.scopes.append({})
            elif op == "POP_SCOPE":
                frame.scopes.pop()
            elif op == "CAPTURE":
                stack.append(self.capture(frame, consts[arg]))
            elif op == "CLOSURE":
                func = consts[arg]
                n = len(func.free_vars)
                cells = stack[len(stack)-n:] if n else []
                if n:
                    del stack[len(stack)-n:]
                stack.append(Closure(func, cells, frame))
            elif op == "CALL":
                self.do_call(arg)
            elif op == "RETURN":
                ret = stack.pop() if len(stack) > frame.base else None
                del stack[frame.base:]      # discard the frame's scratch stack
                self.frames.pop()
                if self.frames:
                    stack.append(ret)
            else:
                raise EmberRuntimeError(f"Unknown opcode {op}")

    # ── calls ──
    def do_call(self, argc):
        args = self.stack[len(self.stack)-argc:] if argc else []
        if argc:
            del self.stack[len(self.stack)-argc:]
        callee = self.stack.pop()

        if isinstance(callee, Closure):
            func = callee.func
            if len(args) != len(func.params):
                raise EmberRuntimeError(
                    f"Expected {len(func.params)} arguments, got {len(args)}")
            base = len(self.stack)
            cells = dict(zip(func.free_vars, callee.cells)) if func.free_vars else {}
            fr = Frame(func, callee.env, base, cells)
            fr.scopes = [{}]
            for p, a in zip(func.params, args):
                fr.scopes[0][p] = a
            self.frames.append(fr)
        elif isinstance(callee, BoundMethod):
            self.stack.append(self.call_method(callee, args))
        elif isinstance(callee, EmberBuiltin):
            self.stack.append(callee.fn(args))
        else:
            raise EmberRuntimeError(f"Cannot call {type(callee).__name__}")

    def call_value(self, callee, args):
        """Synchronous call from host code (method callbacks like map/filter)."""
        if isinstance(callee, Closure):
            func = callee.func
            if len(args) != len(func.params):
                raise EmberRuntimeError(
                    f"Expected {len(func.params)} arguments, got {len(args)}")
            base = len(self.stack)
            fr = Frame(func, callee.env, base)
            fr.scopes = [{}]
            for p, a in zip(func.params, args):
                fr.scopes[0][p] = a
            self.frames.append(fr)
            # run ONLY the frames this call adds — the caller's loop
            # resumes where it left off instead of re-executing
            self.exec_loop(stop_depth=len(self.frames) - 1)
            return self.stack.pop() if len(self.stack) > base else None
        if isinstance(callee, EmberBuiltin):
            return callee.fn(args)
        if isinstance(callee, BoundMethod):
            return self.call_method(callee, args)
        raise EmberRuntimeError(f"Cannot call {type(callee).__name__}")

    def call_method(self, bm, args):
        obj, name = bm.obj, bm.name
        if isinstance(obj, EmberList):
            el = obj.elements
            if name == "push":
                el.append(args[0]); return None
            if name == "pop":
                return el.pop() if el else None
            if name == "join":
                sep = args[0] if args else ", "
                return sep.join(to_str(e) for e in el)
            if name == "map":
                fn = args[0]
                return EmberList([self.call_value(fn, [item]) for item in list(el)])
            if name == "filter":
                fn = args[0]
                return EmberList([item for item in list(el) if truthy(self.call_value(fn, [item]))])
        if isinstance(obj, str):
            if name == "upper": return obj.upper()
            if name == "lower": return obj.lower()
            if name == "split":
                sep = args[0] if args else " "
                return EmberList(obj.split(sep))
        raise EmberRuntimeError(f"No method '{name}' on {type(obj).__name__}")

    # ── operators ──
    def get_index(self, obj, idx):
        if isinstance(obj, EmberList):
            if not isinstance(idx, (int, float)):
                raise EmberRuntimeError("List index must be a number")
            i = int(idx)
            if i < 0: i += len(obj.elements)
            if i < 0 or i >= len(obj.elements):
                raise EmberRuntimeError(
                    f"Index {i} out of range (0..{len(obj.elements)-1})")
            return obj.elements[i]
        if isinstance(obj, str):
            i = int(idx)
            if i < 0: i += len(obj)
            return obj[i]
        raise EmberRuntimeError(f"Cannot index {type(obj).__name__}")

    def get_prop(self, obj, name):
        if isinstance(obj, EmberList):
            if name == "len": return len(obj.elements)
            if name == "first": return obj.elements[0] if obj.elements else None
            if name == "last": return obj.elements[-1] if obj.elements else None
            if name in ("push", "pop", "join", "map", "filter"):
                return BoundMethod(obj, name)
        if isinstance(obj, str):
            if name == "len": return len(obj)
            if name in ("upper", "lower", "split"):
                return BoundMethod(obj, name)
        raise EmberRuntimeError(f"No member '{name}' on {type(obj).__name__}")

    def binop(self, op, left, right):
        if op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return to_str(left) + to_str(right)
            if isinstance(left, EmberList) and isinstance(right, EmberList):
                return EmberList(left.elements + right.elements)
            return left + right
        if op == "-": return left - right
        if op == "*":
            if isinstance(left, str) and isinstance(right, (int, float)):
                return left * int(right)
            if isinstance(left, (int, float)) and isinstance(right, str):
                return right * int(left)
            return left * right
        if op == "/":
            if right == 0: raise EmberRuntimeError("Division by zero")
            return left / right
        if op == "%":
            if right == 0: raise EmberRuntimeError("Modulo by zero")
            return left % right
        if op == "==": return left == right
        if op == "!=": return left != right
        if op == "<": return left < right
        if op == ">": return left > right
        if op == "<=": return left <= right
        if op == ">=": return left >= right
        raise EmberRuntimeError(f"Unknown operator {op}")


# ──────────────────────────────────────────────────────────────
# 4. ENTRY POINT
# ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Ember VM — bytecode compiler + stack machine")
        print("Usage: vm.py <file.fl>  |  vm.py -e '<code>'")
        sys.exit(0)

    if sys.argv[1] == "-e":
        source = sys.argv[2]
    else:
        with open(sys.argv[1]) as f:
            source = f.read()

    vm = VM()
    try:
        vm.run(source)
    except (LexerError, ParseError, CompileError, EmberRuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
