"""Tiny S-expression reader/writer for KiCad files (keeps quoted strings distinct from bare atoms)."""
import re


class Q(str):
    """A quoted string atom."""


_tok = re.compile(r'\s*(\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+)')


def parse(text):
    pos = 0
    stack = [[]]
    n = len(text)
    while pos < n:
        m = _tok.match(text, pos)
        if not m:
            break
        t = m.group(1)
        pos = m.end()
        if t == "(":
            stack.append([])
        elif t == ")":
            lst = stack.pop()
            stack[-1].append(lst)
        elif t.startswith('"'):
            stack[-1].append(Q(t[1:-1].replace('\\"', '"').replace("\\\\", "\\")))
        else:
            stack[-1].append(t)
    return stack[0][0] if len(stack[0]) == 1 else stack[0]


def dump(x, indent=0):
    """Serialise preserving element order (KiCad's parser is order-sensitive)."""
    if isinstance(x, list):
        if not x:
            return "()"
        if all(not isinstance(e, list) for e in x):
            return "(" + " ".join(dump(e) for e in x) + ")"
        out = "("
        first = True
        for e in x:
            if isinstance(e, list):
                out += "\n" + "  " * (indent + 1) + dump(e, indent + 1)
            else:
                out += ("" if first else " ") + dump(e)
            first = False
        return out + ")"
    if isinstance(x, Q):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(x, float):
        s = f"{x:.4f}".rstrip("0").rstrip(".")
        return s if s not in ("-0", "") else "0"
    return str(x)


def find(lst, key):
    return [e for e in lst if isinstance(e, list) and e and e[0] == key]


def find1(lst, key):
    r = find(lst, key)
    return r[0] if r else None
