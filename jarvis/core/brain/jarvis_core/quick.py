"""Instant answers.

Questions the house can answer from its own data (the clock, the weather station, the
forecast, dinner, the devices), sums, and "say that again" are answered here in a few
milliseconds, without a language model or the internet. Matching is deliberately strict:
anything not recognised exactly, such as the weather somewhere else, goes to the model.
"""
import ast
import math
import operator
import re

from .report import now

_LEAD = re.compile(r"^(?:(?:hey|ok|okay)\s+)?(?:jarvis\s+)?(?:please\s+)?(?:can you\s+|could you\s+)?"
                   r"(?:tell me\s+|do you know\s+)?")
_TAIL = re.compile(r"\s+(?:please|jarvis)$")


def normalise(text: str) -> str:
    t = text.lower().replace("’", "'").replace(",", " ")
    t = re.sub(r"[?!.]+$", "", t.strip())
    t = " ".join(t.split())
    t = _LEAD.sub("", t)
    return _TAIL.sub("", t).strip()


def _full(pattern: str, text: str) -> bool:
    return re.fullmatch(pattern, text) is not None


TIME = r"(?:what(?:'s| is) the time|what time is it|whats the time|the time|time)(?: now| right now)?"
DATE = (r"(?:what(?:'s| is) (?:the date|today's date|the day)(?: today)?|what day is it(?: today)?"
        r"|what(?:'s| is) today|which day is it|today's date|the date)")
TEMPERATURE = (r"(?:what(?:'s| is) the (?:temperature|temp)(?: outside| out there| now| right now)?"
               r"|how (?:cold|warm|hot) is it(?: outside| out there)?(?: now| right now| today)?)")
WEATHER = (r"(?:what(?:'s| is) the weather(?: like)?(?: outside| today| now| like today| like outside)?"
           r"|how(?:'s| is) the weather(?: today| outside)?|(?:the )?weather|what(?:'s| is) it like outside)")
RAIN = (r"(?:is it (?:going to|gonna) rain|will it rain|is there (?:going to be )?rain"
        r"|do i need (?:an umbrella|a coat))(?: today| tomorrow| later| later today| tonight)?")
SUN = r"(?:(?:what time is|when is|when's|what time's) )?(?:the )?(?P<which>sunrise|sunset)(?: today)?"
DINNER = r"(?:is dinner ready|is (?:the )?food ready|is dinner (?:done|on|cooked)|has dinner been called)"
DEVICES = (r"(?:is everything (?:working|ok|okay|online|running)|are (?:all )?(?:the )?devices (?:online|working|ok|okay)"
           r"|what(?:'s| is) offline|is anything (?:offline|broken|down))")
REPEAT = (r"(?:say that again|repeat that|repeat|what did you (?:just )?say|pardon|come again|sorry what"
          r"|say again)")


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ---------------------------------------------------------------- sums

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Mod: operator.mod, ast.Pow: operator.pow}


def _evaluate(node):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _evaluate(node.operand)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 100 or abs(left) > 1e6):
            raise ValueError("too big")
        return _OPS[type(node.op)](left, right)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sqrt"
            and len(node.args) == 1 and not node.keywords):
        return math.sqrt(_evaluate(node.args[0]))
    raise ValueError("not a sum")


def _number(v: float) -> str:
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        v = int(v)
    if isinstance(v, int):
        return f"{v:,}"
    return f"{v:,.6g}" if abs(v) < 1e15 else f"{v:.6g}"


def _sum(text: str) -> str | None:
    m = re.fullmatch(r"(?:what(?:'s| is) |calculate |work out |how much is )?(?P<expr>.+)", text)
    said = m.group("expr")
    e = re.sub(r"(?<=\d) (?=\d{3}\b)", "", said)                        # "1 000" -> "1000"
    e = re.sub(r"(?:the )?square root of (\d+(?:\.\d+)?)", r"sqrt(\1)", e)
    e = re.sub(r"(\d+(?:\.\d+)?) ?(?:percent|%) of (\d+(?:\.\d+)?)", r"(\1/100*\2)", e)
    for word, symbol in (("multiplied by", "*"), ("times", "*"), (" x ", " * "), ("divided by", "/"),
                         ("over", "/"), ("plus", "+"), ("minus", "-"), ("to the power of", "**"),
                         ("squared", "**2"), ("cubed", "**3"), ("^", "**")):
        e = e.replace(word, symbol)
    if not re.fullmatch(r"[\d.\s+\-*/()%sqrt]+", e) or not re.search(r"\d", e):
        return None
    if not re.search(r"[+\-*/%]|sqrt", e) or re.fullmatch(r"\s*-?\d+(?:\.\d+)?\s*", e):
        return None                                                     # a plain number is not a sum
    try:
        value = _evaluate(ast.parse(e, mode="eval"))
    except ZeroDivisionError:
        return "You can't divide by zero."
    except (ValueError, SyntaxError, TypeError, OverflowError):
        return None
    if isinstance(value, complex) or abs(value) > 1e18:
        return None
    return f"{said} is {_number(value)}."


# ---------------------------------------------------------------- weather

def _station(snapshot: dict) -> dict | None:
    w = snapshot.get("weather")
    return w if w and not w["stale"] else None


def _temperature(snapshot: dict) -> str | None:
    w = _station(snapshot)
    return f"It's {w['temp_c']:.1f} degrees outside." if w else None


def _weather(snapshot: dict, forecast) -> str | None:
    parts = []
    w = _station(snapshot)
    if w:
        parts.append(f"It's {w['temp_c']:.1f} degrees outside.")
    if forecast and forecast.days:
        d = forecast.days[0]
        parts.append(f"Today: {d['desc']}, a high of {d['high']:.0f}, {d['rain']:.0f} percent chance of rain.")
    return " ".join(parts) or None


def _rain(text: str, forecast) -> str | None:
    if not (forecast and forecast.days):
        return None
    tomorrow = "tomorrow" in text and len(forecast.days) > 1
    d = forecast.days[1 if tomorrow else 0]
    when = "tomorrow" if tomorrow else "today"
    p = d["rain"]
    if "coat" in text:
        if p >= 40 or d["high"] < 12:
            return f"Yes, take a coat: a high of {d['high']:.0f} {when}, and a {p:.0f} percent chance of rain."
        return f"Probably not: a high of {d['high']:.0f} {when}, and only a {p:.0f} percent chance of rain."
    if p >= 60:
        return f"Probably: a {p:.0f} percent chance of rain {when}."
    if p <= 20:
        return f"Unlikely: only a {p:.0f} percent chance of rain {when}."
    return f"Maybe: a {p:.0f} percent chance of rain {when}."


# ---------------------------------------------------------------- the house

def _dinner(snapshot: dict) -> str:
    return {"idle": "Dinner hasn't been called yet.",
            "calling": "Yes, dinner is ready.",
            "acknowledged": "Yes, dinner is ready, and someone is on their way."}.get(
        snapshot.get("dinner", {}).get("state"), "I don't know.")


def _devices(snapshot: dict) -> str:
    nodes = snapshot.get("nodes", {})
    off = sorted(n for n, s in nodes.items() if not s.get("online"))
    if not off:
        return "Everything is online."
    return "Offline: " + ", ".join(off) + "."


def answer(text: str, snapshot: dict, forecast=None, last_answer: str = "") -> tuple[str, str] | None:
    """(answer, kind) when the question can be answered instantly, else None."""
    q = normalise(text)
    if not q:
        return None
    t = now()
    if _full(REPEAT, q):
        return (last_answer, "repeat") if last_answer else None
    if _full(TIME, q):
        return f"It's {t:%H:%M}.", "time"
    if _full(DATE, q):
        return f"It's {t:%A} the {_ordinal(t.day)} of {t:%B} {t.year}.", "date"
    if _full(TEMPERATURE, q):
        a = _temperature(snapshot)
        return (a, "weather") if a else None
    if _full(WEATHER, q):
        a = _weather(snapshot, forecast)
        return (a, "weather") if a else None
    if _full(RAIN, q):
        a = _rain(q, forecast)
        return (a, "forecast") if a else None
    m = re.fullmatch(SUN, q)
    if m and forecast and forecast.sunrise:
        which = m.group("which")
        return f"{which.capitalize()} is at {forecast.sunrise if which == 'sunrise' else forecast.sunset}.", "sun"
    if _full(DINNER, q):
        return _dinner(snapshot), "dinner"
    if _full(DEVICES, q):
        return _devices(snapshot), "devices"
    a = _sum(q)
    if a:
        return a, "sum"
    return None
