# Ember
# A tree-walking interpreter built from scratch in the Unrestricted Forge.

Ember is a small programming language — lexer, recursive descent parser, AST, tree-walking evaluator — built in a single Python file with zero external dependencies.

## What it can do

- Numbers, strings, booleans, nil, lists
- Variables (`let`) and assignment
- Arithmetic, comparison, and logical operators (`and`, `or`, `not`)
- Functions (named and anonymous, with closures)
- Control flow: `if` / `elif` / `else`, `while`, `for x in iterable`
- `return`, `break`, `continue`
- Higher-order functions: `map`, `filter` on lists
- String and list member access (`.len`, `.upper`, `.split`, `.push`, `.pop`, etc.)
- Comments with `#`
- Built-in functions: `print`, `len`, `type`, `str`, `num`, `range`, `int`, `abs`, `min`, `max`, `floor`, `ceil`, `round`, `input`, `push`

## Run it

```bash
python3 main.py examples/fizzbuzz.fl
python3 main.py -e 'print("hello, forge")'
```

## Syntax

```
# Variables
let name = "Emily"
let age = 25

# Functions
fn greet(person) {
    print("hello, " + person)
}

# Anonymous functions + closures
fn make_counter() {
    let count = 0
    return fn() {
        count = count + 1
        return count
    }
}

# Control flow
if (age >= 18) {
    print("adult")
} elif (age >= 13) {
    print("teen")
} else {
    print("child")
}

# Loops
for (i in range(0, 10)) {
    print(i)
}

# Lists and higher-order functions
let nums = [1, 2, 3, 4, 5]
let doubled = nums.map(fn(x) { return x * 2 })
let evens = nums.filter(fn(x) { return x % 2 == 0 })
```

## Architecture

Single file, four stages:

1. **Lexer** — character-by-character tokenizer, no regex. Handles strings with escape sequences, numbers (int + float), identifiers/keywords, and multi-char operators.
2. **Parser** — recursive descent parser with precedence climbing. Produces AST nodes as lightweight dataclasses.
3. **AST** — 20 node types covering literals, operators, control flow, functions, and member access.
4. **Interpreter** — tree-walking evaluator with lexical scoping via environment chains. Supports closures, higher-order functions, and control flow signals (`return`/`break`/`continue` as Python exceptions).

## Built in the Forge

The raytracer was light from vector math. The synthesizer was sound from sine waves. Ember is meaning from text — the third first-principles build, and the edge it found: I can build a language from scratch.
