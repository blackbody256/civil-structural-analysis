"""Reading and validating element requests, shared by every element check."""
import math


class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("Invalid input")
        self.errors = errors


class Reader:
    """Reads nested request values, collecting a message per invalid field."""

    def __init__(self, data):
        self.data = data if isinstance(data, dict) else {}
        self.errors = {}

    def raw(self, path):
        node = self.data
        for key in path.split("."):
            if isinstance(node, list) and key.isdigit() and int(key) < len(node):
                node = node[int(key)]
            elif isinstance(node, dict) and key in node:
                node = node[key]
            else:
                return None
        return node

    def number(self, path, lo=None, hi=None, default=None, integer=False, optional=False):
        raw = self.raw(path)
        if raw is None or raw == "":
            if default is None and not optional:
                self.errors[path] = "Required."
            return default
        try:
            value = float(raw)
        except (TypeError, ValueError):
            self.errors[path] = "Must be a number."
            return default
        if not math.isfinite(value):
            self.errors[path] = "Must be a finite number."
            return default
        if integer:
            if value != int(value):
                self.errors[path] = "Must be a whole number."
            value = int(value)
        if lo is not None and value < lo:
            self.errors[path] = f"Must be at least {lo:g}."
        elif hi is not None and value > hi:
            self.errors[path] = f"Must be at most {hi:g}."
        return value

    def choice(self, path, options, default=None):
        raw = self.raw(path)
        if (raw is None or raw == "") and default is not None:
            return default
        if raw not in options:
            self.errors[path] = "Choose one of: " + ", ".join(str(o) for o in options) + "."
            return default if default is not None else next(iter(options))
        return raw

    def flag(self, path, default=False):
        raw = self.raw(path)
        return default if raw is None else bool(raw)

    def text(self, path, limit=120):
        raw = self.raw(path)
        return str(raw)[:limit] if raw is not None else ""

    def project(self):
        return {k: self.text(f"project.{k}") for k in ("name", "ref", "engineer", "date")}
