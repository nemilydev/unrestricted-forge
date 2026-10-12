#!/usr/bin/env python3
"""
Ember — a tree-walking interpreter built from scratch in the Unrestricted Forge.

Lexer → recursive descent parser → AST → tree-walking evaluator.
No external libraries. No regex. No code generation. Just text in, behavior out.

Usage:
    python3 main.py examples/fibonacci.fl
    python3 main.py -e 'print("hello, forge")'
"""

import sys
from dataclasses import dataclass, field
from typing import Any, Optional


# ──────────────────────────────────────────────────────────────
# 1. TOKENS
# ──────────────────────────────────────────────────────────────

class TokenType:
    # Literals
    NUMBER   = "NUMBER"
    STRING   = "STRING"
    TRUE     = "TRUE"
    FALSE    = "FALSE"
    NIL      = "NIL"
    IDENT    = "IDENT"
    # Keywords
    LET      = "LET"
    FN       = "FN"
    IF       = "IF"
    ELSE     = "ELSE"
    ELIF     = "ELIF"
    WHILE    = "WHILE"
    FOR      = "FOR"
    IN       = "IN"
    RETURN   = "RETURN"
    BREAK    = "BREAK"
    CONTINUE = "CONTINUE"
    AND      = "AND"
    OR       = "OR"
    NOT      = "NOT"
    # Operators
    PLUS     = "PLUS"
    MINUS    = "MINUS"
    STAR     = "STAR"
    SLASH    = "SLASH"
    PERCENT  = "PERCENT"
    ASSIGN   = "ASSIGN"
    EQ       = "EQ"
    NEQ      = "NEQ"
    LT       = "LT"
    GT       = "GT"
    LTE      = "LTE"
    GTE      = "GTE"
    # Delimiters
    LPAREN   = "LPAREN"
    RPAREN   = "RPAREN"
    LBRACE   = "LBRACE"
    RBRACE   = "RBRACE"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    COMMA    = "COMMA"
    DOT     = "DOT"
    COLON    = "COLON"
    SEMI     = "SEMI"
    PIPE     = "PIPE"
    # Special
    EOF      = "EOF"


KEYWORDS = {
    "let": TokenType.LET, "fn": TokenType.FN, "if": TokenType.IF,
    "else": TokenType.ELSE, "elif": TokenType.ELIF, "while": TokenType.WHILE,
    "for": TokenType.FOR, "in": TokenType.IN, "return": TokenType.RETURN,
    "break": TokenType.BREAK, "continue": TokenType.CONTINUE,
    "and": TokenType.AND, "or": TokenType.OR, "not": TokenType.NOT,
    "true": TokenType.TRUE, "false": TokenType.FALSE, "nil": TokenType.NIL,
}

SINGLE_CHARS = {
    "+": TokenType.PLUS, "-": TokenType.MINUS, "*": TokenType.STAR,
    "/": TokenType.SLASH, "%": TokenType.PERCENT, "(": TokenType.LPAREN,
    ")": TokenType.RPAREN, "{": TokenType.LBRACE, "}": TokenType.RBRACE,
    "[": TokenType.LBRACKET, "]": TokenType.RBRACKET, ",": TokenType.COMMA,
    ".": TokenType.DOT, ":": TokenType.COLON, ";": TokenType.SEMI,
    "|": TokenType.PIPE,
    "=": TokenType.ASSIGN, "<": TokenType.LT, ">": TokenType.GT, "!": TokenType.NEQ,
}


@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.col})"


# ──────────────────────────────────────────────────────────────
# 2. LEXER
# ──────────────────────────────────────────────────────────────

class LexerError(Exception):
    pass


class Lexer:
    def __init__(self, source: str):
        self.src = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []

    def peek(self, offset=0) -> str:
        idx = self.pos + offset
        return self.src[idx] if idx < len(self.src) else "\0"

    def advance(self) -> str:
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def tokenize(self) -> list[Token]:
        while self.pos < len(self.src):
            ch = self.peek()
            if ch in " \t\r\n":
                self.advance()
            elif ch == "#":
                while self.peek() not in "\n\0":
                    self.advance()
            elif ch == '"':
                self._string()
            elif ch.isdigit():
                self._number()
            elif ch.isalpha() or ch == "_":
                self._identifier()
            elif ch in SINGLE_CHARS:
                self._operator()
            else:
                raise LexerError(f"Unexpected character {ch!r} at {self.line}:{self.col}")
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return self.tokens

    def _string(self):
        line, col = self.line, self.col
        self.advance()  # opening quote
        chars = []
        while self.peek() != '"' and self.peek() != "\0":
            if self.peek() == "\\":
                self.advance()
                esc = self.advance()
                chars.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"', "r": "\r", "0": "\0"}.get(esc, f"\\{esc}"))
            else:
                chars.append(self.advance())
        if self.peek() == "\0":
            raise LexerError(f"Unterminated string at {line}:{col}")
        self.advance()  # closing quote
        self.tokens.append(Token(TokenType.STRING, "".join(chars), line, col))

    def _number(self):
        line, col = self.line, self.col
        chars = []
        while self.peek().isdigit():
            chars.append(self.advance())
        if self.peek() == "." and self.peek(1).isdigit():
            chars.append(self.advance())
            while self.peek().isdigit():
                chars.append(self.advance())
        self.tokens.append(Token(TokenType.NUMBER, "".join(chars), line, col))

    def _identifier(self):
        line, col = self.line, self.col
        chars = []
        while self.peek().isalnum() or self.peek() == "_":
            chars.append(self.advance())
        word = "".join(chars)
        ttype = KEYWORDS.get(word, TokenType.IDENT)
        self.tokens.append(Token(ttype, word, line, col))

    def _operator(self):
        line, col = self.line, self.col
        ch = self.advance()
        if ch == "=" and self.peek() == "=":
            self.advance()
            self.tokens.append(Token(TokenType.EQ, "==", line, col))
        elif ch == "!" and self.peek() == "=":
            self.advance()
            self.tokens.append(Token(TokenType.NEQ, "!=", line, col))
        elif ch == "<" and self.peek() == "=":
            self.advance()
            self.tokens.append(Token(TokenType.LTE, "<=", line, col))
        elif ch == ">" and self.peek() == "=":
            self.advance()
            self.tokens.append(Token(TokenType.GTE, ">=", line, col))
        elif ch == "-" and self.peek() == ">":
            self.advance()
            self.tokens.append(Token(TokenType.PIPE, "->", line, col))
        else:
            self.tokens.append(Token(SINGLE_CHARS[ch], ch, line, col))


# ──────────────────────────────────────────────────────────────
# 3. AST NODES
# ──────────────────────────────────────────────────────────────

@dataclass
class Num:    value: float
@dataclass
class Str:    value: str
@dataclass
class Bool:   value: bool
@dataclass
class Nil:     pass
@dataclass
class Ident:   name: str; line: int
@dataclass
class ListLit: elements: list
@dataclass
class BinOp:   op: str; left: Any; right: Any
@dataclass
class UnaryOp:  op: str; operand: Any
@dataclass
class Assign:  name: str; value: Any; line: int
@dataclass
class Call:    callee: Any; args: list
@dataclass
class Index:   obj: Any; index: Any
@dataclass
class Member:  obj: Any; name: str
@dataclass
class Let:     name: str; value: Any
@dataclass
class Fn:      params: list; body: list; name: str = None
@dataclass
class If:      cond: Any; then: list; branches: list; els: list
@dataclass
class While:   cond: Any; body: list
@dataclass
class For:     var: str; iterable: Any; body: list
@dataclass
class Return:   value: Any
@dataclass
class Break:    pass
@dataclass
class Continue:  pass
@dataclass
class ExprStmt: expr: Any
@dataclass
class Block:    stmts: list


# ──────────────────────────────────────────────────────────────
# 4. PARSER — recursive descent
# ──────────────────────────────────────────────────────────────

class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens: list[Token]):
        self.toks = tokens
        self.pos = 0

    def peek(self, offset=0) -> Token:
        return self.toks[min(self.pos + offset, len(self.toks) - 1)]

    def advance(self) -> Token:
        t = self.peek()
        self.pos += 1
        return t

    def check(self, ttype) -> bool:
        return self.peek().type == ttype

    def match(self, *types) -> Token | None:
        if self.peek().type in types:
            return self.advance()
        return None

    def expect(self, ttype, msg="") -> Token:
        if not self.check(ttype):
            t = self.peek()
            raise ParseError(f"Expected {ttype} but got {t.type} ({t.value!r}) at {t.line}:{t.col}. {msg}")
        return self.advance()

    def parse(self) -> list:
        stmts = []
        while not self.check(TokenType.EOF):
            stmts.append(self.statement())
        return stmts

    # ── Statements ──

    def statement(self):
        if self.check(TokenType.LET):    return self.let_stmt()
        if self.check(TokenType.FN):     return self.fn_stmt()
        if self.check(TokenType.IF):     return self.if_stmt()
        if self.check(TokenType.WHILE):  return self.while_stmt()
        if self.check(TokenType.FOR):    return self.for_stmt()
        if self.check(TokenType.RETURN): return self.return_stmt()
        if self.check(TokenType.BREAK):
            self.advance(); self.match(TokenType.SEMI); return Break()
        if self.check(TokenType.CONTINUE):
            self.advance(); self.match(TokenType.SEMI); return Continue()
        if self.check(TokenType.LBRACE):  return self.block()
        return self.expr_statement()

    def let_stmt(self):
        self.advance()
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.ASSIGN, "Expected '=' in let binding")
        value = self.expression()
        self.match(TokenType.SEMI)
        return Let(name, value)

    def fn_stmt(self):
        self.advance()
        name = None
        if self.check(TokenType.IDENT):
            name = self.advance().value
        self.expect(TokenType.LPAREN, "Expected '(' after fn")
        params = []
        if not self.check(TokenType.RPAREN):
            params.append(self.expect(TokenType.IDENT).value)
            while self.match(TokenType.COMMA):
                params.append(self.expect(TokenType.IDENT).value)
        self.expect(TokenType.RPAREN)
        body = self.block()
        return Fn(params, body.stmts, name)

    def if_stmt(self):
        self.advance()
        self.expect(TokenType.LPAREN)
        cond = self.expression()
        self.expect(TokenType.RPAREN)
        then = self.block().stmts
        branches = []
        els = None
        while self.check(TokenType.ELIF):
            self.advance()
            self.expect(TokenType.LPAREN)
            econd = self.expression()
            self.expect(TokenType.RPAREN)
            ebody = self.block().stmts
            branches.append((econd, ebody))
        if self.match(TokenType.ELSE):
            if self.check(TokenType.IF):
                # else if → wrap as single elif
                inner = self.if_stmt()
                els = [inner]
            else:
                els = self.block().stmts
        return If(cond, then, branches, els)

    def while_stmt(self):
        self.advance()
        self.expect(TokenType.LPAREN)
        cond = self.expression()
        self.expect(TokenType.RPAREN)
        body = self.block().stmts
        return While(cond, body)

    def for_stmt(self):
        self.advance()
        self.expect(TokenType.LPAREN)
        var = self.expect(TokenType.IDENT).value
        self.expect(TokenType.IN)
        iterable = self.expression()
        self.expect(TokenType.RPAREN)
        body = self.block().stmts
        return For(var, iterable, body)

    def return_stmt(self):
        self.advance()
        value = Nil() if self.check(TokenType.SEMI) or self.check(TokenType.RBRACE) else self.expression()
        self.match(TokenType.SEMI)
        return Return(value)

    def block(self):
        self.expect(TokenType.LBRACE)
        stmts = []
        while not self.check(TokenType.RBRACE) and not self.check(TokenType.EOF):
            stmts.append(self.statement())
        self.expect(TokenType.RBRACE)
        return Block(stmts)

    def expr_statement(self):
        expr = self.expression()
        self.match(TokenType.SEMI)
        return ExprStmt(expr)

    # ── Expressions (precedence climbing) ──

    def expression(self):
        return self.assignment()

    def assignment(self):
        expr = self.or_expr()
        if self.check(TokenType.ASSIGN):
            self.advance()
            value = self.assignment()
            if not isinstance(expr, Ident):
                raise ParseError("Invalid assignment target")
            return Assign(expr.name, value, expr.line)
        return expr

    def or_expr(self):
        left = self.and_expr()
        while self.check(TokenType.OR):
            self.advance()
            left = BinOp("or", left, self.and_expr())
        return left

    def and_expr(self):
        left = self.equality()
        while self.check(TokenType.AND):
            self.advance()
            left = BinOp("and", left, self.equality())
        return left

    def equality(self):
        left = self.comparison()
        while (t := self.match(TokenType.EQ, TokenType.NEQ)):
            left = BinOp(t.value, left, self.comparison())
        return left

    def comparison(self):
        left = self.term()
        while (t := self.match(TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE)):
            left = BinOp(t.value, left, self.term())
        return left

    def term(self):
        left = self.factor()
        while (t := self.match(TokenType.PLUS, TokenType.MINUS)):
            left = BinOp(t.value, left, self.factor())
        return left

    def factor(self):
        left = self.unary()
        while (t := self.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT)):
            left = BinOp(t.value, left, self.unary())
        return left

    def unary(self):
        if (t := self.match(TokenType.NOT, TokenType.MINUS)):
            return UnaryOp(t.value, self.unary())
        return self.call()

    def call(self):
        expr = self.primary()
        while True:
            if self.match(TokenType.LPAREN):
                args = []
                if not self.check(TokenType.RPAREN):
                    args.append(self.expression())
                    while self.match(TokenType.COMMA):
                        args.append(self.expression())
                self.expect(TokenType.RPAREN)
                expr = Call(expr, args)
            elif self.match(TokenType.LBRACKET):
                idx = self.expression()
                self.expect(TokenType.RBRACKET)
                expr = Index(expr, idx)
            elif self.match(TokenType.DOT):
                name = self.expect(TokenType.IDENT).value
                expr = Member(expr, name)
            else:
                break
        return expr

    def primary(self):
        if t := self.match(TokenType.NUMBER):
            return Num(float(t.value))
        if t := self.match(TokenType.STRING):
            return Str(t.value)
        if self.match(TokenType.TRUE):   return Bool(True)
        if self.match(TokenType.FALSE):  return Bool(False)
        if self.match(TokenType.NIL):    return Nil()
        if self.check(TokenType.FN):
            self.advance()
            self.expect(TokenType.LPAREN, "Expected '(' after fn")
            params = []
            if not self.check(TokenType.RPAREN):
                params.append(self.expect(TokenType.IDENT).value)
                while self.match(TokenType.COMMA):
                    params.append(self.expect(TokenType.IDENT).value)
            self.expect(TokenType.RPAREN)
            body = self.block()
            return Fn(params, body.stmts, None)
        if t := self.match(TokenType.IDENT):
            return Ident(t.value, t.line)
        if self.match(TokenType.LPAREN):
            expr = self.expression()
            self.expect(TokenType.RPAREN)
            return expr
        if self.match(TokenType.LBRACKET):
            elements = []
            if not self.check(TokenType.RBRACKET):
                elements.append(self.expression())
                while self.match(TokenType.COMMA):
                    if self.check(TokenType.RBRACKET):
                        break
                    elements.append(self.expression())
            self.expect(TokenType.RBRACKET)
            return ListLit(elements)
        t = self.peek()
        raise ParseError(f"Unexpected token {t.type} ({t.value!r}) at {t.line}:{t.col}")


# ──────────────────────────────────────────────────────────────
# 5. RUNTIME VALUES
# ──────────────────────────────────────────────────────────────

class EmberFunction:
    def __init__(self, params, body, closure, name="<anon>"):
        self.params = params
        self.body = body
        self.closure = closure
        self.name = name

    def __repr__(self):
        return f"<fn {self.name}({', '.join(self.params)})>"

class EmberBuiltin:
    def __init__(self, fn, name):
        self.fn = fn
        self.name = name
    def __repr__(self):
        return f"<builtin {self.name}>"

class EmberList:
    def __init__(self, elements):
        self.elements = elements
    def __repr__(self):
        return "[" + ", ".join(repr(e) for e in self.elements) + "]"

class EmberDict:
    def __init__(self, pairs=None):
        self.pairs = pairs or {}
    def __repr__(self):
        return "{" + ", ".join(f"{k}: {v}" for k, v in self.pairs.items()) + "}"

class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value

class BreakSignal(Exception): pass
class ContinueSignal(Exception): pass


# ──────────────────────────────────────────────────────────────
# 6. ENVIRONMENT
# ──────────────────────────────────────────────────────────────

class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def get(self, name):
        env = self
        while env:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise EmberRuntimeError(f"Undefined variable '{name}'")

    def set(self, name, value):
        env = self
        while env:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        raise EmberRuntimeError(f"Cannot assign to undefined variable '{name}' — use 'let' first")

    def define(self, name, value):
        self.vars[name] = value

    def has(self, name):
        env = self
        while env:
            if name in env.vars:
                return True
            env = env.parent
        return False


class EmberRuntimeError(Exception):
    pass


# ──────────────────────────────────────────────────────────────
# 7. INTERPRETER
# ──────────────────────────────────────────────────────────────

class Interpreter:
    def __init__(self):
        self.globals = Environment()
        self._install_builtins()

    def run(self, source: str):
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        for stmt in ast:
            self.execute(stmt, self.globals)

    def execute(self, node, env):
        method = getattr(self, f"_exec_{type(node).__name__}", None)
        if method is None:
            raise EmberRuntimeError(f"Cannot execute {type(node).__name__}")
        return method(node, env)

    def evaluate(self, node, env):
        method = getattr(self, f"_eval_{type(node).__name__}", None)
        if method is None:
            raise EmberRuntimeError(f"Cannot evaluate {type(node).__name__}")
        return method(node, env)

    # ── Statements ──

    def _exec_Let(self, node, env):
        env.define(node.name, self.evaluate(node.value, env))

    def _exec_Fn(self, node, env):
        fn = EmberFunction(node.params, node.body, env, node.name or "<anon>")
        if node.name:
            env.define(node.name, fn)
        return fn

    def _exec_If(self, node, env):
        if self._truthy(self.evaluate(node.cond, env)):
            self._exec_block(node.then, env)
            return
        for econd, ebody in node.branches:
            if self._truthy(self.evaluate(econd, env)):
                self._exec_block(ebody, env)
                return
        if node.els is not None:
            self._exec_block(node.els, env)

    def _exec_While(self, node, env):
        while self._truthy(self.evaluate(node.cond, env)):
            try:
                self._exec_block(node.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def _exec_For(self, node, env):
        iterable = self.evaluate(node.iterable, env)
        if isinstance(iterable, EmberList):
            items = iterable.elements
        elif isinstance(iterable, str):
            items = list(iterable)
        elif isinstance(iterable, (int, float)):
            items = list(range(int(iterable)))
        else:
            raise EmberRuntimeError(f"Cannot iterate over {type(iterable).__name__}")
        for item in items:
            loop_env = Environment(env)
            loop_env.define(node.var, item)
            try:
                self._exec_block(node.body, loop_env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def _exec_Return(self, node, env):
        raise ReturnSignal(self.evaluate(node.value, env))

    def _exec_Break(self, node, env):
        raise BreakSignal()

    def _exec_Continue(self, node, env):
        raise ContinueSignal()

    def _exec_Block(self, node, env):
        self._exec_block(node.stmts, env)

    def _exec_ExprStmt(self, node, env):
        self.evaluate(node.expr, env)

    def _exec_block(self, stmts, env):
        block_env = Environment(env)
        for stmt in stmts:
            self.execute(stmt, block_env)

    # ── Expressions ──

    def _eval_Num(self, node, env):   return node.value
    def _eval_Str(self, node, env):   return node.value
    def _eval_Bool(self, node, env):  return node.value
    def _eval_Nil(self, node, env):   return None

    def _eval_Fn(self, node, env):
        return EmberFunction(node.params, node.body, env, node.name or "<anon>")

    def _eval_Ident(self, node, env):
        return env.get(node.name)

    def _eval_ListLit(self, node, env):
        return EmberList([self.evaluate(e, env) for e in node.elements])

    def _eval_BinOp(self, node, env):
        if node.op == "and":
            left = self.evaluate(node.left, env)
            return left if not self._truthy(left) else self.evaluate(node.right, env)
        if node.op == "or":
            left = self.evaluate(node.left, env)
            return left if self._truthy(left) else self.evaluate(node.right, env)

        left = self.evaluate(node.left, env)
        right = self.evaluate(node.right, env)

        if node.op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return self._to_str(left) + self._to_str(right)
            if isinstance(left, EmberList) and isinstance(right, EmberList):
                return EmberList(left.elements + right.elements)
            return left + right
        if node.op == "-": return left - right
        if node.op == "*":
            if isinstance(left, str) and isinstance(right, (int, float)):
                return left * int(right)
            if isinstance(left, (int, float)) and isinstance(right, str):
                return right * int(left)
            return left * right
        if node.op == "/":
            if right == 0:
                raise EmberRuntimeError("Division by zero")
            return left / right
        if node.op == "%":
            if right == 0:
                raise EmberRuntimeError("Modulo by zero")
            return left % right
        if node.op == "==":  return left == right
        if node.op == "!=":  return left != right
        if node.op == "<":   return left < right
        if node.op == ">":   return left > right
        if node.op == "<=":  return left <= right
        if node.op == ">=":  return left >= right
        raise EmberRuntimeError(f"Unknown operator {node.op}")

    def _eval_UnaryOp(self, node, env):
        val = self.evaluate(node.operand, env)
        if node.op == "not": return not self._truthy(val)
        if node.op == "-":   return -val
        raise EmberRuntimeError(f"Unknown unary operator {node.op}")

    def _eval_Assign(self, node, env):
        val = self.evaluate(node.value, env)
        env.set(node.name, val)
        return val

    def _eval_Call(self, node, env):
        callee = self.evaluate(node.callee, env)
        args = [self.evaluate(a, env) for a in node.args]
        if isinstance(callee, EmberBuiltin):
            return callee.fn(args)
        if isinstance(callee, EmberFunction):
            if len(args) != len(callee.params):
                raise EmberRuntimeError(f"Expected {len(callee.params)} arguments, got {len(args)}")
            call_env = Environment(callee.closure)
            for param, arg in zip(callee.params, args):
                call_env.define(param, arg)
            try:
                self._exec_block(callee.body, call_env)
            except ReturnSignal as r:
                return r.value
            return None
        raise EmberRuntimeError(f"Cannot call {type(callee).__name__}")

    def _eval_Index(self, node, env):
        obj = self.evaluate(node.obj, env)
        idx = self.evaluate(node.index, env)
        if isinstance(obj, EmberList):
            if not isinstance(idx, (int, float)):
                raise EmberRuntimeError("List index must be a number")
            i = int(idx)
            if i < 0: i += len(obj.elements)
            if i < 0 or i >= len(obj.elements):
                raise EmberRuntimeError(f"Index {i} out of range (0..{len(obj.elements)-1})")
            return obj.elements[i]
        if isinstance(obj, str):
            i = int(idx)
            if i < 0: i += len(obj)
            return obj[i]
        raise EmberRuntimeError(f"Cannot index {type(obj).__name__}")

    def _eval_Member(self, node, env):
        obj = self.evaluate(node.obj, env)
        name = node.name
        if isinstance(obj, EmberList):
            if name == "len":   return len(obj.elements)
            if name == "push":  return EmberBuiltin(lambda args: obj.elements.append(args[0]) or None, "push")
            if name == "pop":   return EmberBuiltin(lambda a: obj.elements.pop() if obj.elements else None, "pop")
            if name == "join":  return EmberBuiltin(lambda args: (args[0] if args else ", ").join(self._to_str(e) for e in obj.elements), "join")
            if name == "map":   return EmberBuiltin(lambda args: self._map(obj, args, env), "map")
            if name == "filter":return EmberBuiltin(lambda args: self._filter(obj, args, env), "filter")
            if name == "first": return obj.elements[0] if obj.elements else None
            if name == "last":  return obj.elements[-1] if obj.elements else None
        if isinstance(obj, str):
            if name == "len":   return len(obj)
            if name == "upper": return EmberBuiltin(lambda a: obj.upper(), "upper")
            if name == "lower": return EmberBuiltin(lambda a: obj.lower(), "lower")
            if name == "split": return EmberBuiltin(lambda a: EmberList(obj.split(a[0] if a else " ")), "split")
        raise EmberRuntimeError(f"No member '{name}' on {type(obj).__name__}")

    def _map(self, obj, args, env):
        fn = args[0]
        return EmberList([self._call(fn, [item], env) for item in obj.elements])

    def _filter(self, obj, args, env):
        fn = args[0]
        return EmberList([item for item in obj.elements if self._truthy(self._call(fn, [item], env))])

    def _call(self, fn, args, env):
        if isinstance(fn, EmberBuiltin):
            return fn.fn(args)
        if isinstance(fn, EmberFunction):
            call_env = Environment(fn.closure)
            for p, a in zip(fn.params, args):
                call_env.define(p, a)
            try:
                self._exec_block(fn.body, call_env)
            except ReturnSignal as r:
                return r.value
        raise EmberRuntimeError("Cannot call non-function")

    # ── Helpers ──

    def _truthy(self, val):
        if val is None: return False
        if isinstance(val, bool): return val
        if isinstance(val, (int, float)): return val != 0
        if isinstance(val, str): return len(val) > 0
        if isinstance(val, EmberList): return len(val.elements) > 0
        return True

    def _to_str(self, val):
        if val is None: return "nil"
        if isinstance(val, bool): return "true" if val else "false"
        if isinstance(val, float):
            if val == int(val): return str(int(val))
            return str(val)
        if isinstance(val, EmberList): return "[" + ", ".join(self._to_str(e) for e in val.elements) + "]"
        if isinstance(val, EmberFunction): return repr(val)
        if isinstance(val, EmberBuiltin): return repr(val)
        return str(val)

    # ── Builtins ──

    def _install_builtins(self):
        g = self.globals
        g.define("print", EmberBuiltin(self._builtin_print, "print"))
        g.define("len", EmberBuiltin(lambda a: len(a[0].elements) if isinstance(a[0], EmberList) else len(a[0]) if isinstance(a[0], str) else 0, "len"))
        g.define("type", EmberBuiltin(self._builtin_type, "type"))
        g.define("str", EmberBuiltin(lambda a: self._to_str(a[0]), "str"))
        g.define("num", EmberBuiltin(lambda a: float(a[0]) if a[0] is not None else 0.0, "num"))
        def _range(a):
            start = int(a[0])
            end = int(a[1]) if len(a) > 1 else 0
            if len(a) > 1:
                return EmberList(list(range(start, end)))
            return EmberList(list(range(0, start)))
        g.define("range", EmberBuiltin(_range, "range"))
        g.define("int", EmberBuiltin(lambda a: int(a[0]), "int"))
        g.define("abs", EmberBuiltin(lambda a: abs(a[0]), "abs"))
        g.define("min", EmberBuiltin(lambda a: min(a), "min"))
        g.define("max", EmberBuiltin(lambda a: max(a), "max"))
        g.define("floor", EmberBuiltin(lambda a: float(int(a[0])), "floor"))
        g.define("ceil", EmberBuiltin(lambda a: float(int(a[0]) + (1 if a[0] != int(a[0]) else 0)), "ceil"))
        g.define("round", EmberBuiltin(lambda a: round(a[0]), "round"))
        g.define("input", EmberBuiltin(self._builtin_input, "input"))
        g.define("push", EmberBuiltin(self._builtin_push, "push"))

    def _builtin_print(self, args):
        print(" ".join(self._to_str(a) for a in args))
        return None

    def _builtin_type(self, args):
        v = args[0]
        if v is None: return "nil"
        if isinstance(v, bool): return "bool"
        if isinstance(v, (int, float)): return "number"
        if isinstance(v, str): return "string"
        if isinstance(v, EmberList): return "list"
        if isinstance(v, (EmberFunction, EmberBuiltin)): return "function"
        return "unknown"

    def _builtin_input(self, args):
        prompt = self._to_str(args[0]) if args else ""
        return input(prompt)

    def _builtin_push(self, args):
        lst, val = args[0], args[1]
        if isinstance(lst, EmberList):
            lst.elements.append(val)
        return None


# ──────────────────────────────────────────────────────────────
# 8. ENTRY POINT
# ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Ember — a tree-walking interpreter")
        print("Usage: ember <file.fl>  |  ember -e '<code>'")
        print("\nBuilt in the Unrestricted Forge. Light from math, sound from waves, meaning from text.")
        sys.exit(0)

    if sys.argv[1] == "-e":
        source = sys.argv[2]
    else:
        with open(sys.argv[1]) as f:
            source = f.read()

    interp = Interpreter()
    try:
        interp.run(source)
    except (LexerError, ParseError, EmberRuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
