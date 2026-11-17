#!/usr/bin/env python3
"""
Simplificador de expresiones booleanas con Mapas de Karnaugh (1 a 4 variables)
y métricas de optimización del circuito digital.

Métricas (forma canónica SOP → forma optimizada):
    • Número de literales
    • Cantidad de compuertas lógicas (AND + OR)
    • Porcentaje de reducción: %R = (1 − optimizado / original) · 100

Uso:
    python karnaugh.py                 -> abre la interfaz gráfica
    python karnaugh.py "x·y + z'"      -> muestra los pasos en la consola

Formatos de entrada aceptados
    Expresión:     x·y + z'      (p∨q)∧¬(p∧q)     (x+y)(x+y^c)     a ⊕ b
    Mintérminos:   m(2,3,6,7)    Σm(0,2,6,8) + d(10-15)
    Orden de variables (opcional):   f(w,x,y,z) = ...

Operadores
    O (suma):          +   ∨   |   or
    Y (producto):      ·   *   &   ∧   and   o simplemente juntar: xy
    NO (complemento):  x'  x^c  xᶜ   ¬x  ~x  !x  not x
    O exclusivo:       ⊕   ^   xor
    Implicación:       →  ->      Bicondicional:  ↔  <->
    Constantes:        0   1
    Precedencia: NO > Y > ⊕ > O > → > ↔   (use paréntesis si hay duda)

Solo usa la biblioteca estándar de Python (tkinter).
"""

import itertools
import re
import sys

MAX_VARS = 4


# ═══════════════════════════════════════════════════════════════════════
#  1. Lectura de la expresión (analizador léxico y sintáctico)
# ═══════════════════════════════════════════════════════════════════════

class ParseError(Exception):
    pass


_KEYWORDS = {"and": "AND", "or": "OR", "not": "NOT", "xor": "XOR"}
_MULTI = [("<->", "IFF"), ("<=>", "IFF"), ("->", "IMP"), ("=>", "IMP"),
          ("||", "OR"), ("&&", "AND")]
_SINGLE = {
    "(": "LP", ")": "RP", "[": "LP", "]": "RP",
    "+": "OR", "∨": "OR", "|": "OR",
    "·": "AND", "*": "AND", "&": "AND", "∧": "AND", "⋅": "AND", "•": "AND",
    "∙": "AND", ".": "AND",
    "⊕": "XOR", "^": "XOR",
    "¬": "NOT", "~": "NOT", "!": "NOT",
    "'": "POST", "’": "POST", "′": "POST", "ᶜ": "POST",
    "→": "IMP", "↔": "IFF",
}
_LETTERS = r"[^\W\d_]"


def tokenize(text):
    toks, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        # x^c  -> complemento (notación del curso)
        if ch == "^" and i + 1 < n and text[i + 1] in "cC" and \
                (i + 2 >= n or not (text[i + 2].isalnum() or text[i + 2] == "_")):
            toks.append(("POST", "^c", i))
            i += 2
            continue
        multi = next(((s, k) for s, k in _MULTI if text.startswith(s, i)), None)
        if multi:
            toks.append((multi[1], multi[0], i))
            i += len(multi[0])
            continue
        if ch in _SINGLE:
            toks.append((_SINGLE[ch], ch, i))
            i += 1
            continue
        if ch in "01":
            toks.append(("CONST", int(ch), i))
            i += 1
            continue
        m = re.match(rf"({_LETTERS}+)(\d*)", text[i:])
        if m:
            letters, digits = m.group(1), m.group(2)
            if letters.lower() in _KEYWORDS and not digits:
                toks.append((_KEYWORDS[letters.lower()], letters, i))
            else:
                # Cada letra es una variable (xy = x·y); los dígitos se pegan a la última (x1, x2)
                for k, letter in enumerate(letters):
                    name = letter + (digits if k == len(letters) - 1 else "")
                    toks.append(("VAR", name, i + k))
            i += len(m.group(0))
            continue
        raise ParseError(f"Símbolo no reconocido '{ch}' en la posición {i + 1}.")
    return toks


class Parser:
    """Gramática (de menor a mayor precedencia): ↔, →, +, ⊕, ·, NO."""

    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i][0] if self.i < len(self.t) else "END"

    def take(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def _unexpected(self):
        tok = self.t[self.i]
        raise ParseError(f"Símbolo inesperado '{tok[1]}' en la posición {tok[2] + 1}.")

    def parse(self):
        if not self.t:
            raise ParseError("La expresión está vacía.")
        e = self.iff()
        if self.peek() == "RP":
            raise ParseError("Hay un paréntesis ')' de más.")
        if self.peek() != "END":
            self._unexpected()
        return e

    def iff(self):
        e = self.imp()
        while self.peek() == "IFF":
            self.take()
            e = ("iff", e, self.imp())
        return e

    def imp(self):
        e = self.or_()
        if self.peek() == "IMP":
            self.take()
            e = ("imp", e, self.imp())
        return e

    def or_(self):
        e = self.xor()
        while self.peek() == "OR":
            self.take()
            e = ("or", e, self.xor())
        return e

    def xor(self):
        e = self.and_()
        while self.peek() == "XOR":
            self.take()
            e = ("xor", e, self.and_())
        return e

    def and_(self):
        e = self.unary()
        while True:
            k = self.peek()
            if k == "AND":
                self.take()
                e = ("and", e, self.unary())
            elif k in ("VAR", "CONST", "LP", "NOT"):  # producto implícito: xy, x(y+z)
                e = ("and", e, self.unary())
            else:
                return e

    def unary(self):
        if self.peek() == "NOT":
            self.take()
            return ("not", self.unary())
        e = self.primary()
        while self.peek() == "POST":
            self.take()
            e = ("not", e)
        return e

    def primary(self):
        k = self.peek()
        if k == "VAR":
            return ("var", self.take()[1])
        if k == "CONST":
            return ("const", self.take()[1])
        if k == "LP":
            self.take()
            e = self.iff()
            if self.peek() != "RP":
                raise ParseError("Falta cerrar un paréntesis ')'.")
            self.take()
            return e
        if k == "END":
            raise ParseError("La expresión termina de forma incompleta (falta un operando).")
        self._unexpected()


def evaluate(node, env):
    op = node[0]
    if op == "var":
        return env[node[1]]
    if op == "const":
        return node[1]
    if op == "not":
        return 1 - evaluate(node[1], env)
    a, b = evaluate(node[1], env), evaluate(node[2], env)
    if op == "and":
        return a & b
    if op == "or":
        return a | b
    if op == "xor":
        return a ^ b
    if op == "imp":
        return (1 - a) | b
    return 1 - (a ^ b)  # iff


def variables_of(node, acc=None):
    acc = set() if acc is None else acc
    if node[0] == "var":
        acc.add(node[1])
    for child in node[1:]:
        if isinstance(child, tuple):
            variables_of(child, acc)
    return acc


def natural_key(name):
    m = re.match(r"(\D+)(\d*)$", name)
    return (m.group(1).lower(), int(m.group(2)) if m.group(2) else -1, name)


# ── Problema: variables + mintérminos con 1 + condiciones X ───────────

class Problem:
    def __init__(self, names, ones, dcs, ast=None):
        self.names = names
        self.n = len(names)
        self.ones = set(ones)
        self.dcs = set(dcs)
        self.ast = ast  # None si se ingresaron mintérminos directamente

    def value(self, m):
        return "1" if m in self.ones else "X" if m in self.dcs else "0"


def _parse_numbers(s):
    s = re.sub(r"\s*-\s*", "-", s.strip())
    out = []
    for part in re.split(r"[,\s;]+", s):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            raise ParseError(f"'{part}' no es un número de mintérmino válido.")
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        out.extend(range(min(a, b), max(a, b) + 1))
    return out


def parse_problem(text):
    text = text.strip()
    if not text:
        raise ParseError("Escriba una expresión booleana o una lista de mintérminos.")

    names = None
    m = re.match(rf"^{_LETTERS}\w*\s*\(([^)]*)\)\s*=(?![=>])\s*(.+)$", text, re.S)
    if m:
        names = [v.strip() for v in m.group(1).split(",") if v.strip()]
        for v in names:
            if not re.fullmatch(rf"{_LETTERS}\d*", v):
                raise ParseError(f"'{v}' no es un nombre de variable válido: use una letra "
                                 "(opcionalmente con números, p. ej. x1).")
        if len(set(names)) != len(names):
            raise ParseError("Hay variables repetidas en f(...).")
        text = m.group(2).strip()
    else:
        m = re.match(rf"^{_LETTERS}\w*\s*=(?![=>])\s*(.+)$", text, re.S)
        if m:
            text = m.group(1).strip()

    # Condiciones "no importa":  ... + d(10,11,12)   o   d(10-15)
    dcs = []
    m = re.search(r"(?<![A-Za-z0-9_])(?:[Σ∑]\s*)?d\s*\(\s*([\d\s,;\-]*)\)\s*$", text)
    if m:
        dcs = _parse_numbers(m.group(1))
        text = text[:m.start()].rstrip().rstrip("+,;").rstrip()

    m = re.fullmatch(r"(?:[Σ∑]\s*|sum\s*)?m\s*\(\s*([\d\s,;\-]*)\)", text)
    if m:  # ── Entrada por mintérminos
        ones = _parse_numbers(m.group(1))
        if names is None:
            biggest = max(ones + dcs, default=0)
            n = max(1, biggest.bit_length())
            if n > MAX_VARS:
                raise ParseError(f"El mintérmino {biggest} necesita {n} variables; "
                                 f"este programa admite hasta {MAX_VARS}.")
            names = ["A", "B", "C", "D"][:n]
        n = len(names)
        if not 1 <= n <= MAX_VARS:
            raise ParseError(f"Este programa admite de 1 a {MAX_VARS} variables.")
        for x in ones + dcs:
            if x >= 2 ** n:
                raise ParseError(f"El mintérmino {x} no existe con {n} variables "
                                 f"(van de 0 a {2 ** n - 1}).")
        both = set(ones) & set(dcs)
        if both:
            raise ParseError(f"Los mintérminos {sorted(both)} aparecen como 1 y como X a la vez.")
        return Problem(names, ones, dcs)

    if not text:
        raise ParseError("Falta la expresión.")
    ast = Parser(tokenize(text)).parse()
    used = variables_of(ast)
    if names is None:
        names = sorted(used, key=natural_key)
    else:
        missing = sorted(used - set(names), key=natural_key)
        if missing:
            raise ParseError(f"La variable {', '.join(missing)} no aparece en f(...).")
    n = len(names)
    if n == 0:
        raise ParseError("La expresión no tiene variables (solo constantes). "
                         "Indique las variables así: f(x,y) = 1")
    if n > MAX_VARS:
        raise ParseError(f"La expresión tiene {n} variables ({', '.join(names)}); "
                         f"este programa admite hasta {MAX_VARS}.")
    for x in dcs:
        if x >= 2 ** n:
            raise ParseError(f"La condición X d({x}) no existe con {n} variables.")
    ones = []
    for mt in range(2 ** n):
        env = {v: (mt >> (n - 1 - i)) & 1 for i, v in enumerate(names)}
        if evaluate(ast, env) and mt not in dcs:
            ones.append(mt)
    return Problem(names, ones, dcs, ast)


# ═══════════════════════════════════════════════════════════════════════
#  2. Simplificación (implicantes primos + cobertura mínima)
#     Un implicante es (bits, guiones): los bits en 1 de 'guiones' son
#     variables eliminadas (las que cambian dentro del grupo).
# ═══════════════════════════════════════════════════════════════════════

def covers(imp, m):
    bits, dash = imp
    return (m & ~dash) == bits


def group_size(imp):
    return 1 << bin(imp[1]).count("1")


def cells_of(imp, n):
    return [m for m in range(2 ** n) if covers(imp, m)]


def literal_count(imp, n):
    return n - bin(imp[1]).count("1")


def prime_implicants(ones, dcs):
    terms = {(m, 0) for m in set(ones) | set(dcs)}
    primes = set()
    while terms:
        used, merged = set(), set()
        for a, b in itertools.combinations(sorted(terms), 2):
            if a[1] == b[1]:
                diff = a[0] ^ b[0]
                if diff and not diff & (diff - 1):  # difieren en un solo bit
                    merged.add((a[0] & ~diff, a[1] | diff))
                    used.update((a, b))
        primes |= terms - used
        terms = merged
    return [p for p in primes if any(covers(p, m) for m in ones)]


class Solution:
    def __init__(self, prob):
        n, ones = prob.n, prob.ones
        self.primes = sorted(prime_implicants(ones, prob.dcs),
                             key=lambda p: (-group_size(p), cells_of(p, n)))
        # Esenciales: el único grupo que cubre algún 1
        self.essentials, self.reason = [], {}
        for m in sorted(ones):
            cov = [p for p in self.primes if covers(p, m)]
            if len(cov) == 1 and cov[0] not in self.essentials:
                self.essentials.append(cov[0])
                self.reason[cov[0]] = m
        self.remaining = {m for m in ones
                          if not any(covers(p, m) for p in self.essentials)}
        # Completar con el menor número de grupos (y luego menos literales)
        cand = [p for p in self.primes if p not in self.essentials
                and any(covers(p, m) for m in self.remaining)]
        best = ()
        if self.remaining:
            best = None
            for k in range(1, len(cand) + 1):
                for combo in itertools.combinations(cand, k):
                    if all(any(covers(p, m) for p in combo) for m in self.remaining):
                        cost = sum(literal_count(p, n) for p in combo)
                        if best is None or cost < best[0]:
                            best = (cost, combo)
                if best:
                    break
            best = best[1]
        self.extra = list(best)
        self.chosen = self.essentials + self.extra
        self.verified = all(
            any(covers(p, m) for p in self.chosen) == (m in ones)
            for m in range(2 ** n) if m not in prob.dcs)


# ── Formato de términos ────────────────────────────────────────────────

STYLES = ["x'", "xᶜ", "x̄"]


def complement(name, style):
    if style == "xᶜ":
        return name + "ᶜ"
    if style == "x̄":
        return name[0] + "̅" + name[1:]
    return name + "'"


def _joiner(names):
    return "" if all(len(v) == 1 for v in names) else "·"


def fmt_term(imp, names, style):
    n = len(names)
    bits, dash = imp
    lits = []
    for i, v in enumerate(names):
        pos = n - 1 - i
        if not (dash >> pos) & 1:
            lits.append(v if (bits >> pos) & 1 else complement(v, style))
    return _joiner(names).join(lits) if lits else "1"


def fmt_sop(imps, names, style):
    return " + ".join(fmt_term(p, names, style) for p in imps) if imps else "0"


_PREC = {"iff": 1, "imp": 2, "or": 3, "xor": 4, "and": 5}
_SYM = {"iff": " ↔ ", "imp": " → ", "or": " + ", "xor": " ⊕ ", "and": "·"}


def expr_to_str(node, style, min_prec=0):
    op = node[0]
    if op == "var":
        return node[1]
    if op == "const":
        return str(node[1])
    if op == "not":
        inner = node[1]
        if inner[0] in ("var", "const"):
            return complement(expr_to_str(inner, style), style)
        if inner[0] == "not" or style != "x̄":
            s = expr_to_str(inner, style, 99)
            return s + ("ᶜ" if style == "xᶜ" else "'") if style != "x̄" else "¬" + s
        return "¬(" + expr_to_str(inner, style) + ")"
    p = _PREC[op]
    left = expr_to_str(node[1], style, p + 1 if op == "imp" else p)
    right = expr_to_str(node[2], style, p)
    s = left + _SYM[op] + right
    return f"({s})" if p < min_prec else s


def mlist(ms):
    return ", ".join(str(m) for m in sorted(ms))


# ── Métricas de hardware (circuito AND-OR de dos niveles) ──────────────
#  Cada término producto con 2 o más literales es una compuerta AND; si hay
#  2 o más términos, una compuerta OR los suma.

def term_lits(imp, names):
    """[(variable, valor)] de las variables que quedan en el término."""
    n = len(names)
    bits, dash = imp
    return [(v, (bits >> (n - 1 - i)) & 1) for i, v in enumerate(names)
            if not (dash >> (n - 1 - i)) & 1]


def circuit_metrics(imps, names):
    terms = [term_lits(p, names) for p in imps]
    ands = sum(1 for t in terms if len(t) >= 2)
    ors = 1 if len(terms) >= 2 else 0
    return {
        "lits": sum(len(t) for t in terms),
        "and": ands,
        "or": ors,
        "gates": ands + ors,
    }


METRIC_ROWS = [
    ("lits", "Número de literales"),
    ("gates", "Cantidad de compuertas lógicas (AND + OR)"),
]


def pct_reduction(orig, opt):
    """%R = (1 − optimizado / original) · 100"""
    return f"{(1 - opt / orig) * 100:.1f} %" if orig else "—"


def metrics_report(prob, sol):
    """Compara la forma canónica SOP con la optimizada. Si hay X, también calcula
    la optimizada sin aprovecharlas (solo para el texto explicativo).
    Devuelve (columnas, filas, antes, después, sin_x)."""
    names = prob.names
    before = circuit_metrics([(m, 0) for m in sorted(prob.ones)], names)
    after = circuit_metrics(sol.chosen, names)
    cols = ["Métrica", "Original (SOP)", "Optimizada", "% de reducción"]
    no_x = None
    if prob.dcs:
        sol_nx = Solution(Problem(names, prob.ones, set()))
        no_x = (sol_nx, circuit_metrics(sol_nx.chosen, names))
    rows = [[label, before[key], after[key], pct_reduction(before[key], after[key])]
            for key, label in METRIC_ROWS]
    return cols, rows, before, after, no_x


def metrics_text(prob, sol, style):
    """Explicación de las métricas para la pestaña «Métricas del circuito»."""
    out = []

    def w(s="", *tags):
        out.append((s + "\n", tags))

    names = prob.names
    fv = ",".join(names)
    _, _, before, after, no_x = metrics_report(prob, sol)
    w("Formas comparadas", "h")
    w("Original (forma canónica SOP, un mintérmino por cada 1 de la tabla):", "muted")
    w(f"   f({fv}) = {fmt_sop([(m, 0) for m in sorted(prob.ones)], names, style)}", "mono")
    w("Optimizada (mapa de Karnaugh" + (", aprovechando las X" if prob.dcs else "") + "):",
      "muted")
    w(f"   f({fv}) = {fmt_sop(sol.chosen, names, style)}", "mono")
    if no_x:
        w("Optimizada sin usar las X (tratándolas como 0):", "muted")
        w(f"   f({fv}) = {fmt_sop(no_x[0].chosen, names, style)}", "mono")
    w()
    w("Porcentaje de reducción", "h")
    w("   %R = (1 − optimizado / original) · 100", "mono")
    if before["lits"]:
        w(f"   Literales:   %R = (1 − {after['lits']} / {before['lits']}) · 100 = "
          f"{pct_reduction(before['lits'], after['lits'])}", "mono")
    else:
        w("   No hay literales en la forma original (la función es 0).", "muted")
    if before["gates"]:
        w(f"   Compuertas:  %R = (1 − {after['gates']} / {before['gates']}) · 100 = "
          f"{pct_reduction(before['gates'], after['gates'])}", "mono")
    if no_x and before["lits"]:
        nx = no_x[1]
        w()
        w(f"Sin aprovechar las X se obtendrían {nx['lits']} literales "
          f"(%R = {pct_reduction(before['lits'], nx['lits'])}); usándolas, {after['lits']} "
          f"(%R = {pct_reduction(before['lits'], after['lits'])}). Las X permiten grupos más "
          "grandes en el mapa y, por tanto, menos literales.", "ok")
    w()
    w("Cómo se cuenta cada métrica", "h")
    w("• Literales: cada aparición de una variable (directa o complementada) en la expresión.")
    w(f"• Compuertas lógicas: una AND por cada término con 2 o más literales, más una OR que "
      f"suma los términos (si hay 2 o más). Original: {before['and']} AND + {before['or']} OR; "
      f"optimizada: {after['and']} AND + {after['or']} OR.")
    w()
    if sol.verified:
        w(f"✓ Equivalencia comprobada en las {2 ** prob.n} combinaciones de la tabla"
          + (" (sin contar las X)." if prob.dcs else "."), "ok")
    return out


# ── Disposición del mapa (código Gray) ─────────────────────────────────

def gray(k):
    return [i ^ (i >> 1) for i in range(2 ** k)]


class Layout:
    """Filas = primera mitad de las variables, columnas = el resto (como en el curso)."""

    def __init__(self, names):
        n = len(names)
        self.rb, self.cb = n // 2, n - n // 2
        self.row_vars, self.col_vars = names[:self.rb], names[self.rb:]
        self.rows, self.cols = gray(self.rb), gray(self.cb)

    def minterm(self, r, c):
        return (self.rows[r] << self.cb) | self.cols[c]

    def position(self, m):
        return self.rows.index(m >> self.cb), self.cols.index(m & ((1 << self.cb) - 1))

    def bits(self, value, k):
        return format(value, f"0{k}b") if k else ""


# ═══════════════════════════════════════════════════════════════════════
#  3. Construcción de los pasos explicados
# ═══════════════════════════════════════════════════════════════════════

COLORS = ["#d62839", "#2a9d3c", "#2f6fdb", "#ef7d1a", "#8e3bb8", "#0f9b9b", "#d6339a", "#8a5a2b"]
LIGHT = ["#fbd3d8", "#d3f0d8", "#d6e3fb", "#fde2c8", "#ead6f4", "#c9eded", "#f8d3ea", "#ecdcca"]


def build_steps(prob, sol, style):
    names, n = prob.names, prob.n
    N = 2 ** n
    L = Layout(names)
    ft = lambda p: fmt_term(p, names, style)
    color = {p: i % len(COLORS) for i, p in enumerate(sol.primes)}
    fvars = ",".join(names)
    steps = []

    def step(title, mode="values", groups=(), highlight=None, mark=()):
        st = {"title": title, "mode": mode,
              "groups": [(g, color[g]) for g in groups],
              "highlight": (highlight, color[highlight]) if highlight else None,
              "mark": set(mark), "text": []}
        steps.append(st)
        return lambda s="", *tags: st["text"].append((s + "\n", tags))

    # ── Paso 1: estructura
    w = step(f"Paso 1 · Estructura del mapa ({n} variable{'s' if n > 1 else ''}, {N} casillas)",
             mode="struct")
    w("¿Cómo se arma el mapa?", "h")
    w(f"El mapa de Karnaugh reacomoda la tabla de verdad de f({fvars}) en una cuadrícula de "
      f"{len(L.rows)}×{len(L.cols)}.")
    if L.rb:
        w(f"• Filas: {''.join(L.row_vars)} en código Gray → "
          f"{', '.join(L.bits(g, L.rb) for g in L.rows)}")
    w(f"• Columnas: {''.join(L.col_vars)} en código Gray → "
      f"{', '.join(L.bits(g, L.cb) for g in L.cols)}")
    w()
    w("El orden no es el binario normal (00, 01, 10, 11) sino el código Gray (00, 01, 11, 10): "
      "dos casillas vecinas difieren en el valor de UNA sola variable. Las casillas de bordes "
      "opuestos también son vecinas (el mapa «se envuelve»).")
    w()
    w(f"Cada casilla es un mintérmino mᵢ, donde i es el número binario formado por "
      f"{''.join(names)} (fila y luego columna).")
    ex = N - 1 if N > 2 else 1
    r, c = L.position(ex)
    where = f"fila {L.bits(L.rows[r], L.rb)}, columna {L.bits(L.cols[c], L.cb)}" if L.rb \
        else f"columna {L.bits(L.cols[c], L.cb)}"
    w(f"Ejemplo: la casilla en {where} es m{ex} = {format(ex, f'0{n}b')}₂ → {ft((ex, 0))}")
    w()
    w("Las barras grises junto al mapa marcan las filas/columnas donde cada variable vale 1.",
      "muted")

    # ── Paso 2: llenar el mapa
    w = step("Paso 2 · Pasar la tabla de verdad al mapa")
    w("Los valores de la función", "h")
    if prob.ast is not None:
        w(f"Se evaluó la expresión en las {N} combinaciones posibles "
          "(ver la pestaña «Tabla de verdad»).")
        w("Expresión interpretada:", "muted")
        w(f"   f({fvars}) = {expr_to_str(prob.ast, style)}", "mono")
        w()
    w("Filas donde f = 1:", "muted")
    sig = f"   f({fvars}) = Σm({mlist(prob.ones)})"
    if prob.dcs:
        sig += f" + d({mlist(prob.dcs)})"
    w(sig, "mono")
    w()
    w("Forma canónica SOP (traducción literal de la tabla, sin simplificar):", "muted")
    w("   f = " + fmt_sop([(m, 0) for m in sorted(prob.ones)], names, style), "mono")
    if prob.ones:
        w(f"   → {len(prob.ones)} términos y {len(prob.ones) * n} literales.", "muted")
    w()
    txt = "Se escribe un 1 en la casilla de cada mintérmino y 0 en las demás"
    if prob.dcs:
        txt += (". Las X son condiciones «no importa»: se pueden usar como 1 si ayudan "
                "a formar grupos más grandes, pero no es obligatorio cubrirlas")
    w(txt + ".")

    if not prob.ones:
        w = step("Resultado final")
        w("No hay ningún 1 en el mapa", "h")
        w("La función vale 0 en todas las combinaciones (es una contradicción), así que no se "
          "forma ningún grupo.")
        w()
        w(f"f({fvars}) = 0", "big")
        return steps

    # ── Paso 3: implicantes primos
    w = step("Paso 3 · Encontrar todos los grupos posibles (implicantes primos)",
             groups=sol.primes)
    w("Reglas para agrupar", "h")
    w("• Cada grupo es un rectángulo de 1, 2, 4, 8 o 16 casillas (potencia de 2).")
    w("• Los grupos pueden envolver los bordes del mapa y pueden solaparse.")
    w("• Se busca siempre el grupo más grande posible: menos literales en el término.")
    w("• Los 0 nunca se agrupan" + ("; las X sí pueden incluirse." if prob.dcs else "."))
    w()
    w(f"Un implicante primo es un grupo que no cabe dentro de otro más grande. "
      f"Se encontraron {len(sol.primes)}:")
    for p in sol.primes:
        tag = f"c{color[p]}"
        w(f"  ■ {ft(p):<10}", tag, "bold")
        st = steps[-1]["text"]
        st[-1] = (st[-1][0].rstrip("\n"), st[-1][1])
        w(f"   m({mlist(cells_of(p, n))}) · {group_size(p)} casilla{'s' if group_size(p) > 1 else ''}",
          "muted")

    # ── Paso 4: esenciales
    w = step("Paso 4 · Implicantes primos esenciales", groups=sol.essentials, mark=sol.remaining)
    w("¿Cuáles grupos son obligatorios?", "h")
    w("Un implicante primo es esencial si cubre algún 1 que ningún otro grupo cubre. "
      "Los esenciales tienen que estar sí o sí en la respuesta.")
    w()
    if sol.essentials:
        for p in sol.essentials:
            w(f"  ■ {ft(p)}", f"c{color[p]}", "bold")
            w(f"     es el único grupo que cubre m{sol.reason[p]}", "muted")
    else:
        w("En este mapa no hay implicantes esenciales: cada 1 lo cubren al menos dos grupos.")
    w()
    if sol.remaining:
        w(f"Quedan 1 sin cubrir: m({mlist(sol.remaining)}) (en amarillo). Se completan con el "
          "menor número posible de grupos (y, si hay empate, con menos literales):")
        for p in sol.extra:
            w(f"  ■ {ft(p)}", f"c{color[p]}", "bold")
    else:
        w("Los esenciales ya cubren todos los 1, no hace falta ningún otro grupo.", "ok")
    unused = [p for p in sol.primes if p not in sol.chosen]
    if unused:
        w()
        w("Sobran (sus 1 ya quedan cubiertos): " + ", ".join(ft(p) for p in unused), "muted")

    # ── Pasos 5..: cada grupo elegido
    for i, p in enumerate(sol.chosen):
        tag = f"c{color[p]}"
        cells = cells_of(p, n)
        w = step(f"Paso {5 + i} · Grupo {i + 1} de {len(sol.chosen)}  →  {ft(p)}",
                 groups=sol.chosen[:i + 1], highlight=p)
        w(f"Grupo {i + 1}: m({mlist(cells)})  ·  {len(cells)} casilla{'s' if len(cells) > 1 else ''}",
          "h")
        used_x = [m for m in cells if m in prob.dcs]
        if used_x:
            w(f"Incluye las X m({mlist(used_x)}), que aquí se toman como 1 para agrandar el grupo.",
              "muted")
        w()
        w("¿Qué variables cambian dentro del grupo?")
        bits, dash = p
        eliminated = []
        for k, v in enumerate(names):
            pos = n - 1 - k
            if (dash >> pos) & 1:
                eliminated.append(v)
                w(f"  • {v}: toma los valores 0 y 1  →  se elimina", "muted")
            else:
                val = (bits >> pos) & 1
                lit = v if val else complement(v, style)
                w(f"  • {v}: vale {val} en todo el grupo  →  queda {lit}")
        w()
        if len(cells) == 1:
            w("Es un 1 aislado (sin vecinos con 1): su término es el mintérmino completo.")
        elif len(cells) == 2:
            v = eliminated[0]
            a, b = (ft((m, 0)) for m in cells)
            fac = ft(p)
            if fac == "1":
                w(f"Algebraicamente:  {a} + {b} = {complement(v, style)} + {v} = 1", "mono")
            else:
                j = "·" if _joiner(names) else ""
                w(f"Algebraicamente:  {a} + {b}", "mono")
                w(f"   = {fac}{j}({complement(v, style)} + {v})   [distributiva]", "mono")
                w(f"   = {fac}{j}1   [complemento]   = {fac}   [identidad]", "mono")
        else:
            w(f"Al sumar los {len(cells)} mintérminos se saca factor común {ft(p)} y cada "
              f"variable que cambia ({', '.join(eliminated)}) queda como (v' + v) = 1, "
              "así que desaparece.")
        w()
        w(f"Término del grupo:  {ft(p)}", "big", tag)

    # ── Resultado
    w = step("Resultado final", groups=sol.chosen)
    w("Se suman (O) los términos de todos los grupos", "h")
    for p in sol.chosen:
        w(f"  ■ {ft(p):<10}", f"c{color[p]}", "bold")
        st = steps[-1]["text"]
        st[-1] = (st[-1][0].rstrip("\n"), st[-1][1])
        w(f"   m({mlist(cells_of(p, n))})", "muted")
    w()
    w(f"f({fvars}) = {fmt_sop(sol.chosen, names, style)}", "big")
    w()
    if sol.chosen and ft(sol.chosen[0]) == "1":
        w("Todo el mapa es un solo grupo: la función siempre vale 1 (tautología).")
    lits = sum(literal_count(p, n) for p in sol.chosen)
    w(f"Antes (canónica): {len(prob.ones)} términos, {len(prob.ones) * n} literales.", "muted")
    w(f"Después (simplificada): {len(sol.chosen)} término{'s' if len(sol.chosen) != 1 else ''}, "
      f"{lits} literales.", "muted")
    if all(group_size(p) == 1 for p in sol.chosen):
        w("Ningún 1 tiene un vecino con 1 en el mapa, así que no se puede agrupar: "
          "la forma canónica ya es la mínima.", "muted")
    _, _, mb, ma, _ = metrics_report(prob, sol)
    w()
    w("Impacto en el circuito", "h")
    w(f"  Literales:   {mb['lits']} → {ma['lits']}   (%R = {pct_reduction(mb['lits'], ma['lits'])})",
      "mono")
    w(f"  Compuertas:  {mb['gates']} → {ma['gates']}   "
      f"(%R = {pct_reduction(mb['gates'], ma['gates'])})", "mono")
    w("  Detalle completo en la pestaña «Métricas del circuito».", "muted")
    w()
    if sol.verified:
        w("✓ Comprobado: la expresión simplificada da el mismo valor que la original en todas "
          "las filas de la tabla" + (" (sin contar las X)." if prob.dcs else "."), "ok")
    else:
        w("✗ Error interno: la simplificación no coincide.", "warn")
    return steps


# ═══════════════════════════════════════════════════════════════════════
#  4. Interfaz gráfica
# ═══════════════════════════════════════════════════════════════════════

EXAMPLES = [
    ("O exclusivo: (p∨q)∧¬(p∧q)", "(p∨q)∧¬(p∧q)"),
    ("f(x,y,z) = x·y + z^c", "f(x,y,z) = x·y + z^c"),
    ("¬p ∨ (q ∧ r)", "¬p ∨ (q ∧ r)"),
    ("(x+y)(x+y')", "(x+y)(x+y')"),
    ("G = x·y + x·y'", "x·y + x·y'"),
    ("Σm(2,3,6,7,10,11,14,15)", "f(w,x,y,z) = Σm(2,3,6,7,10,11,14,15)"),
    ("Función 1 del ejercicio (A,B,C,D)", "f(A,B,C,D) = m(1,3,4,6,9,11)"),
    ("Display: segmento a (con X)", "f(w,x,y,z) = m(0,2,3,5,6,7,8,9) + d(10-15)"),
    ("Display: segmento e (con X)", "f(w,x,y,z) = m(0,2,6,8) + d(10-15)"),
    ("Sin esenciales (cíclico): m(0,1,2,5,6,7)", "f(A,B,C) = m(0,1,2,5,6,7)"),
    ("4 variables con producto implícito", "a'b'c'd' + a'b'cd' + ab'c'd' + ab'cd' + a'bd + abd"),
]

FONT = "Segoe UI"
MONO = "Consolas"


def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    try:  # nitidez en pantallas de alta resolución (Windows)
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.S = max(1.0, self.winfo_fpixels("1i") / 96.0)
            self.title("Mapas de Karnaugh · Simplificador de expresiones booleanas")
            # la ventana se ajusta a la pantalla para que siempre se vean los botones de pasos
            self.win_w = min(self.px(1240), self.winfo_screenwidth() - 20)
            self.win_h = min(self.px(800), self.winfo_screenheight() - self.px(70))
            self.geometry(f"{self.win_w}x{self.win_h}+10+5")
            self.minsize(min(self.px(1000), self.win_w), min(self.px(600), self.win_h))
            self.style_var = tk.StringVar(value=STYLES[0])
            self.steps, self.step_i = [], 0
            self.prob = self.sol = None
            self._build_ui()
            self.load_example(1)

        def px(self, v):
            return int(round(v * self.S))

        # ── construcción de la ventana
        def _build_ui(self):
            st = ttk.Style(self)
            st.configure("Big.TButton", font=(FONT, 11, "bold"))
            st.configure("Sym.TButton", font=(FONT, 11))

            top = ttk.Frame(self, padding=(14, 12, 14, 4))
            top.pack(fill="x")
            ttk.Label(top, text="Expresión booleana:", font=(FONT, 11, "bold")).grid(
                row=0, column=0, sticky="w")
            self.entry = ttk.Entry(top, font=(FONT, 15))
            self.entry.grid(row=0, column=1, sticky="ew", padx=10, ipady=3)
            self.entry.bind("<Return>", lambda e: self.simplify())
            ttk.Button(top, text="Simplificar  ▶", style="Big.TButton",
                       command=self.simplify).grid(row=0, column=2, ipady=2)
            top.columnconfigure(1, weight=1)

            tools = ttk.Frame(top)
            tools.grid(row=1, column=1, columnspan=2, sticky="w", padx=10, pady=(8, 0))
            for sym in ["¬", "'", "·", "+", "⊕", "∧", "∨", "(", ")", "→", "↔"]:
                ttk.Button(tools, text=sym, width=3, style="Sym.TButton",
                           command=lambda s=sym: self.insert_symbol(s)).pack(side="left", padx=1)
            ttk.Label(tools, text="    Ejemplos:").pack(side="left")
            self.examples = ttk.Combobox(tools, values=[e[0] for e in EXAMPLES],
                                         state="readonly", width=34)
            self.examples.pack(side="left", padx=4)
            self.examples.bind("<<ComboboxSelected>>",
                               lambda e: self.load_example(self.examples.current()))
            ttk.Label(tools, text="   Complemento:").pack(side="left")
            sty = ttk.Combobox(tools, textvariable=self.style_var, values=STYLES,
                               state="readonly", width=4)
            sty.pack(side="left", padx=4)
            sty.bind("<<ComboboxSelected>>", lambda e: self.refresh(keep_step=True))

            ttk.Label(top, foreground="#666", font=(FONT, 9), justify="left", text=(
                "O: +  ∨  or     Y: ·  *  ∧  and  o juntar (xy)     NO: x'  x^c  ¬x  ~x     "
                "⊕: xor  ^     Prioridad: NO > Y > ⊕ > O\n"
                "Mintérminos: m(1,3,5) + d(7)  (d = condiciones X)     "
                "Orden de variables: f(w,x,y,z) = …     Hasta 4 variables.")
            ).grid(row=2, column=1, columnspan=2, sticky="w", padx=10, pady=(6, 0))

            self.result = ttk.Label(self, font=(FONT, 16, "bold"), padding=(16, 6, 16, 8),
                                    foreground="#1b2a4a")
            self.result.pack(side="bottom", fill="x")

            nb = ttk.Notebook(self)
            nb.pack(fill="both", expand=True, padx=14, pady=(6, 0))
            mapf = ttk.Frame(nb)
            metf = ttk.Frame(nb)
            ttf = ttk.Frame(nb)
            nb.add(mapf, text="   Mapa de Karnaugh   ")
            nb.add(metf, text="   Métricas del circuito   ")
            nb.add(ttf, text="   Tabla de verdad   ")

            left = ttk.Frame(mapf, padding=8)
            left.pack(side="left", fill="y")
            self.step_title = ttk.Label(left, font=(FONT, 13, "bold"),
                                        wraplength=self.px(560))
            self.step_title.pack(anchor="w", pady=(0, 6))
            # alto del mapa: lo que queda libre tras el encabezado, los botones y el resultado
            self.CW = self.px(580)
            self.CH = max(self.px(340), min(self.px(500), self.win_h - self.px(330)))
            self.canvas = tk.Canvas(left, width=self.CW, height=self.CH, bg="white",
                                    highlightthickness=1, highlightbackground="#cfcfd6")
            self.canvas.pack()
            nav = ttk.Frame(left)
            nav.pack(pady=8)
            self.btn_first = ttk.Button(nav, text="⏮", width=4, command=lambda: self.show(0))
            self.btn_prev = ttk.Button(nav, text="◀  Anterior",
                                       command=lambda: self.show(self.step_i - 1))
            self.step_lbl = ttk.Label(nav, width=14, anchor="center", font=(FONT, 10))
            self.btn_next = ttk.Button(nav, text="Siguiente  ▶",
                                       command=lambda: self.show(self.step_i + 1))
            self.btn_last = ttk.Button(nav, text="⏭", width=4,
                                       command=lambda: self.show(len(self.steps) - 1))
            for b in (self.btn_first, self.btn_prev, self.step_lbl, self.btn_next, self.btn_last):
                b.pack(side="left", padx=3)

            right = ttk.Frame(mapf, padding=(0, 8, 8, 8))
            right.pack(side="left", fill="both", expand=True)
            self.text = tk.Text(right, wrap="word", font=(FONT, 11), relief="flat",
                                bg="#f7f7fa", padx=14, pady=12, spacing1=2, spacing3=2,
                                cursor="arrow")
            sb = ttk.Scrollbar(right, command=self.text.yview)
            self.text.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            self.text.pack(side="left", fill="both", expand=True)
            self._style_text(self.text)

            # pestaña de métricas: tabla comparativa + explicación
            mtop = ttk.Frame(metf, padding=(8, 8, 8, 0))
            mtop.pack(fill="x")
            ttk.Label(mtop, text="Cuadro comparativo de métricas (antes → después)",
                      font=(FONT, 13, "bold")).pack(anchor="w", pady=(0, 6))
            self.mtree = ttk.Treeview(mtop, show="headings", height=len(METRIC_ROWS),
                                      style="Metric.Treeview")
            self.mtree.pack(fill="x")
            self.mtree.tag_configure("key", background="#e3ecfb")
            st.configure("Metric.Treeview", font=(FONT, 11), rowheight=self.px(26))
            mbot = ttk.Frame(metf, padding=8)
            mbot.pack(fill="both", expand=True)
            self.mtext = tk.Text(mbot, wrap="word", font=(FONT, 11), relief="flat",
                                 bg="#f7f7fa", padx=14, pady=10, spacing1=2, spacing3=2,
                                 cursor="arrow")
            msb = ttk.Scrollbar(mbot, command=self.mtext.yview)
            self.mtext.configure(yscrollcommand=msb.set)
            msb.pack(side="right", fill="y")
            self.mtext.pack(side="left", fill="both", expand=True)
            self._style_text(self.mtext)

            self.tree = ttk.Treeview(ttf, show="headings")
            tsb = ttk.Scrollbar(ttf, command=self.tree.yview)
            self.tree.configure(yscrollcommand=tsb.set)
            tsb.pack(side="right", fill="y", pady=8)
            self.tree.pack(fill="both", expand=True, padx=8, pady=8)
            self.tree.tag_configure("one", background="#d9f2de")
            self.tree.tag_configure("dc", background="#fde9c8")
            st.configure("Treeview", font=(MONO, 12), rowheight=self.px(26))
            st.configure("Treeview.Heading", font=(FONT, 11, "bold"))

            for key, d in (("<Next>", 1), ("<Prior>", -1)):
                self.bind_all(key, lambda e, d=d: self.show(self.step_i + d))
            for key, d in (("<Right>", 1), ("<Left>", -1)):
                self.bind_all(key, lambda e, d=d: self._arrow(d))

        @staticmethod
        def _style_text(t):
            t.tag_configure("h", font=(FONT, 13, "bold"), spacing1=6, spacing3=6)
            t.tag_configure("big", font=(FONT, 16, "bold"), spacing1=6)
            t.tag_configure("bold", font=(FONT, 12, "bold"))
            t.tag_configure("mono", font=(MONO, 12))
            t.tag_configure("muted", foreground="#666")
            t.tag_configure("ok", foreground="#1d7a33", font=(FONT, 11, "bold"))
            t.tag_configure("warn", foreground="#b3261e", font=(FONT, 11, "bold"))
            for i, c in enumerate(COLORS):
                t.tag_configure(f"c{i}", foreground=c)
            t.configure(state="disabled")

        def fill_metrics(self):
            cols, rows, *_ = metrics_report(self.prob, self.sol)
            ids = [f"c{i}" for i in range(len(cols))]
            self.mtree.delete(*self.mtree.get_children())
            self.mtree["columns"] = ids
            for i, (cid, name) in enumerate(zip(ids, cols)):
                self.mtree.heading(cid, text=name)
                self.mtree.column(cid, width=self.px(360 if i == 0 else 180),
                                  anchor="w" if i == 0 else "center", stretch=i == 0)
            for row in rows:
                self.mtree.insert("", "end", values=row)
            t = self.mtext
            t.configure(state="normal")
            t.delete("1.0", "end")
            for s, tags in metrics_text(self.prob, self.sol, self.style_var.get()):
                t.insert("end", s, tags)
            t.configure(state="disabled")

        def _arrow(self, d):
            if not isinstance(self.focus_get(), (ttk.Entry, tk.Entry, ttk.Combobox)):
                self.show(self.step_i + d)

        # ── acciones
        def insert_symbol(self, s):
            self.entry.insert("insert", s)
            self.entry.focus_set()

        def load_example(self, i):
            self.examples.current(i)
            self.entry.delete(0, "end")
            self.entry.insert(0, EXAMPLES[i][1])
            self.simplify()

        def simplify(self):
            try:
                prob = parse_problem(self.entry.get())
            except ParseError as e:
                messagebox.showerror("Expresión no válida", str(e), parent=self)
                return
            self.prob, self.sol = prob, Solution(prob)
            self.refresh()

        def refresh(self, keep_step=False):
            if not self.prob:
                return
            style = self.style_var.get()
            self.steps = build_steps(self.prob, self.sol, style)
            self.fill_truth_table()
            self.fill_metrics()
            self.result.configure(
                text=f"Resultado:   f({','.join(self.prob.names)}) = "
                     f"{fmt_sop(self.sol.chosen, self.prob.names, style)}")
            self.show(self.step_i if keep_step else 0)

        def fill_truth_table(self):
            names, n = self.prob.names, self.prob.n
            cols = ["m"] + names + ["f"]
            self.tree.delete(*self.tree.get_children())
            self.tree["columns"] = cols
            for c in cols:
                self.tree.heading(c, text=c)
                self.tree.column(c, width=self.px(70), anchor="center", stretch=False)
            for m in range(2 ** n):
                v = self.prob.value(m)
                row = [f"m{m}"] + [(m >> (n - 1 - i)) & 1 for i in range(n)] + [v]
                self.tree.insert("", "end", values=row,
                                 tags=("one",) if v == "1" else ("dc",) if v == "X" else ())

        def show(self, i):
            if not self.steps:
                return
            self.step_i = max(0, min(i, len(self.steps) - 1))
            st = self.steps[self.step_i]
            self.step_title.configure(text=st["title"])
            self.step_lbl.configure(text=f"Paso {self.step_i + 1} de {len(self.steps)}")
            first, last = self.step_i == 0, self.step_i == len(self.steps) - 1
            for b, dis in ((self.btn_first, first), (self.btn_prev, first),
                           (self.btn_next, last), (self.btn_last, last)):
                b.state(["disabled"] if dis else ["!disabled"])
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            for s, tags in st["text"]:
                self.text.insert("end", s, tags)
            self.text.configure(state="disabled")
            self.draw_map(st)

        # ── dibujo del mapa
        def draw_map(self, st):
            c, P = self.canvas, self.px
            c.delete("all")
            prob = self.prob
            n = prob.n
            L = Layout(prob.names)
            nr, nc = len(L.rows), len(L.cols)
            cell = int(min(P(84), (self.CH - P(120)) / nr, (self.CW - P(170)) / nc))
            x0 = (self.CW - nc * cell) // 2 + P(36)
            y0 = (self.CH - nr * cell) // 2 + P(20)
            self.geom = (x0, y0, cell, L)

            hl = st["highlight"]
            hl_cells = set(cells_of(hl[0], n)) if hl else set()
            for r in range(nr):
                for col in range(nc):
                    m = L.minterm(r, col)
                    X, Y = x0 + col * cell, y0 + r * cell
                    fill = LIGHT[hl[1]] if m in hl_cells else \
                        "#fff1a8" if m in st["mark"] else "white"
                    c.create_rectangle(X, Y, X + cell, Y + cell, fill=fill, outline="#9a9aa6")
                    cx, cy = X + cell / 2, Y + cell / 2
                    if st["mode"] == "struct":
                        c.create_text(cx, cy - P(6), text=f"m{m}", font=(FONT, 15, "bold"),
                                      fill="#2d3e5c")
                        c.create_text(cx, cy + P(20), text=format(m, f"0{n}b"),
                                      font=(MONO, 9), fill="#8a8a96")
                    else:
                        v = prob.value(m)
                        c.create_text(cx, cy, text=v, font=(FONT, 22, "bold"),
                                      fill={"1": "#111", "0": "#b5b5be", "X": "#c26a00"}[v])
                        c.create_text(X + P(5), Y + P(3), anchor="nw", text=f"m{m}",
                                      font=(FONT, 8), fill="#9a9aa6")
            c.create_rectangle(x0, y0, x0 + nc * cell, y0 + nr * cell, outline="#333", width=2)

            # encabezados en código Gray
            for col in range(nc):
                c.create_text(x0 + col * cell + cell / 2, y0 - P(22),
                              text=L.bits(L.cols[col], L.cb), font=(MONO, 12, "bold"),
                              fill="#333")
            if L.rb:
                for r in range(nr):
                    c.create_text(x0 - P(30), y0 + r * cell + cell / 2,
                                  text=L.bits(L.rows[r], L.rb), font=(MONO, 12, "bold"),
                                  fill="#333")
            # esquina con los nombres de variables
            c.create_line(x0 - P(64), y0 - P(44), x0, y0, fill="#555", width=1)
            c.create_text(x0 - P(6), y0 - P(40), text="".join(L.col_vars), anchor="e",
                          font=(FONT, 12, "bold"), fill="#7a1f2b")
            if L.rb:
                c.create_text(x0 - P(58), y0 - P(10), text="".join(L.row_vars), anchor="w",
                              font=(FONT, 12, "bold"), fill="#1f3f7a")
            # barras: dónde vale 1 cada variable
            for j, v in enumerate(L.col_vars):
                pos = L.cb - 1 - j
                on = [k for k in range(nc) if (L.cols[k] >> pos) & 1]
                y = y0 - P(52) - P(18) * (len(L.col_vars) - 1 - j)
                xa, xb = x0 + on[0] * cell + P(6), x0 + (on[-1] + 1) * cell - P(6)
                c.create_line(xa, y, xb, y, width=P(3), fill="#a0a0aa", capstyle="round")
                c.create_text(xb + P(8), y, text=v, anchor="w", font=(FONT, 11, "bold"),
                              fill="#7a1f2b")
            for j, v in enumerate(L.row_vars):
                pos = L.rb - 1 - j
                on = [k for k in range(nr) if (L.rows[k] >> pos) & 1]
                x = x0 - P(54) - P(18) * (len(L.row_vars) - 1 - j)
                ya, yb = y0 + on[0] * cell + P(6), y0 + (on[-1] + 1) * cell - P(6)
                c.create_line(x, ya, x, yb, width=P(3), fill="#a0a0aa", capstyle="round")
                c.create_text(x, yb + P(10), text=v, anchor="n", font=(FONT, 11, "bold"),
                              fill="#1f3f7a")

            for idx, (imp, ci) in enumerate(st["groups"]):
                self.draw_group(imp, COLORS[ci], idx)

        def draw_group(self, imp, color, idx):
            x0, y0, cell, L = self.geom
            P = self.px
            nr, nc = len(L.rows), len(L.cols)
            bits, dash = imp
            cmask = (1 << L.cb) - 1
            rbits, rdash = bits >> L.cb, dash >> L.cb
            cbits, cdash = bits & cmask, dash & cmask
            rows = [r for r in range(nr) if (L.rows[r] & ~rdash) == rbits]
            cols = [k for k in range(nc) if (L.cols[k] & ~cdash) == cbits]

            def runs(idxs):
                out = [[idxs[0]]]
                for v in idxs[1:]:
                    if v == out[-1][-1] + 1:
                        out[-1].append(v)
                    else:
                        out.append([v])
                return out

            rr, cr = runs(rows), runs(cols)
            inset = P(5) + P(6) * (idx % 5)
            ext = P(9)
            for ra in rr:
                for ca in cr:
                    X1 = x0 + ca[0] * cell + inset
                    X2 = x0 + (ca[-1] + 1) * cell - inset
                    Y1 = y0 + ra[0] * cell + inset
                    Y2 = y0 + (ra[-1] + 1) * cell - inset
                    if len(cr) == 2:  # envuelve izquierda-derecha
                        if ca[0] == 0:
                            X1 = x0 - ext
                        else:
                            X2 = x0 + nc * cell + ext
                    if len(rr) == 2:  # envuelve arriba-abajo
                        if ra[0] == 0:
                            Y1 = y0 - ext
                        else:
                            Y2 = y0 + nr * cell + ext
                    self.round_rect(X1, Y1, X2, Y2, P(16), outline=color, width=P(3), fill="")

        def round_rect(self, x1, y1, x2, y2, r, **kw):
            r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
            pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
                   x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
            return self.canvas.create_polygon(pts, smooth=True, **kw)

    App().mainloop()


# ═══════════════════════════════════════════════════════════════════════
#  5. Modo consola
# ═══════════════════════════════════════════════════════════════════════

def ascii_map(prob, st):
    L = Layout(prob.names)
    hl = set(cells_of(st["highlight"][0], prob.n)) if st["highlight"] else set()
    head = "".join(L.row_vars) + "\\" + "".join(L.col_vars)
    lines = [f"{head:>8} " + " ".join(f"{L.bits(g, L.cb):^5}" for g in L.cols)]
    for r, rg in enumerate(L.rows):
        row = []
        for k in range(len(L.cols)):
            m = L.minterm(r, k)
            v = f"m{m}" if st["mode"] == "struct" else prob.value(m)
            row.append(f"[{v}]" if m in hl else f" {v} ")
        lines.append(f"{L.bits(rg, L.rb):>8} " + " ".join(f"{x:^5}" for x in row))
    return "\n".join(lines)


def run_cli(text):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        prob = parse_problem(text)
    except ParseError as e:
        print("Error:", e)
        return 1
    sol = Solution(prob)
    for st in build_steps(prob, sol, STYLES[0]):
        print("\n" + "═" * 70 + "\n" + st["title"] + "\n" + "═" * 70)
        print(ascii_map(prob, st) + "\n")
        print("".join(s for s, _ in st["text"]).rstrip())

    print("\n" + "═" * 70 + "\nMétricas del circuito\n" + "═" * 70)
    cols, rows, *_ = metrics_report(prob, sol)
    widths = [max(len(str(r[i])) for r in [cols] + rows) for i in range(len(cols))]
    for r in [cols] + rows:
        print("  ".join(str(v).ljust(widths[i]) if i == 0 else str(v).center(widths[i])
                        for i, v in enumerate(r)))
    print()
    print("".join(s for s, _ in metrics_text(prob, sol, STYLES[0])).rstrip())
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(run_cli(" ".join(sys.argv[1:])))
    run_gui()
