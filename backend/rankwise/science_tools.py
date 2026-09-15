"""Constrained deterministic math, unit, and plotting tools."""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any

from .errors import ConfigurationError, ValidationError

EXPRESSION_PATTERN = re.compile(r"^[A-Za-z0-9_+\-*/^()., \t]+$")
NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
UNIT_PATTERN = re.compile(r"^[A-Za-z0-9_+\-*/^().% \t]+$")
SAFE_FUNCTIONS = {
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "sqrt",
    "exp",
    "log",
    "Abs",
}
SAFE_CONSTANTS = {"pi", "E"}


@dataclass(frozen=True, slots=True)
class PlotResult:
    png: bytes
    metadata: dict[str, Any]


class ScienceTools:
    max_expression_length = 500

    @staticmethod
    def _versions() -> dict[str, str]:
        values = {}
        for package in ("sympy", "pint", "matplotlib"):
            try:
                values[package] = version(package)
            except Exception:
                pass
        return values

    def _sympy_expression(self, expression: str, variables: list[str]):
        normalized = expression.strip()
        if not normalized or len(normalized) > self.max_expression_length:
            raise ValidationError("Expression must contain 1 to 500 characters")
        if "__" in normalized or not EXPRESSION_PATTERN.fullmatch(normalized):
            raise ValidationError("Expression contains unsupported syntax")
        if normalized.count("(") != normalized.count(")") or normalized.count("(") > 20:
            raise ValidationError("Expression parentheses are invalid or too deeply nested")
        if any(
            len(number.replace(".", "")) > 12 for number in re.findall(r"\d+(?:\.\d+)?", normalized)
        ):
            raise ValidationError("Numeric literals are too large")
        for exponent in re.findall(r"(?:\*\*|\^)\s*(\d+)", normalized):
            if int(exponent) > 12:
                raise ValidationError("Numeric exponents greater than 12 are not allowed")
        allowed_variables = set(variables)
        names = set(NAME_PATTERN.findall(normalized))
        unknown = names - allowed_variables - SAFE_FUNCTIONS - SAFE_CONSTANTS
        if unknown:
            raise ValidationError("Unknown expression names: " + ", ".join(sorted(unknown)))
        try:
            import sympy
        except ImportError as exc:
            raise ConfigurationError(
                "Install the 'science' dependency extra to use symbolic math"
            ) from exc
        local_values = {name: sympy.Symbol(name, real=True) for name in allowed_variables}
        local_values.update({name: getattr(sympy, name) for name in SAFE_FUNCTIONS})
        local_values.update({"pi": sympy.pi, "E": sympy.E})
        try:
            return sympy.sympify(normalized, locals=local_values), sympy, local_values
        except (TypeError, ValueError, SyntaxError) as exc:
            raise ValidationError("Expression could not be parsed") from exc

    def symbolic(
        self,
        *,
        operation: str,
        expression: str,
        variables: list[str],
        other_expression: str | None = None,
        variable: str | None = None,
    ) -> dict[str, Any]:
        if (
            not variables
            or len(variables) > 10
            or any(
                not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,30}", item)
                or item in SAFE_FUNCTIONS
                or item in SAFE_CONSTANTS
                for item in variables
            )
        ):
            raise ValidationError("variables must contain 1 to 10 valid symbol names")
        parsed, sympy, symbols = self._sympy_expression(expression, variables)
        normalized_operation = operation.strip().casefold()
        selected_variable = variable or variables[0]
        if selected_variable not in symbols:
            raise ValidationError("variable must be listed in variables")
        if normalized_operation == "simplify":
            result = sympy.simplify(parsed)
            status = "calculated"
        elif normalized_operation == "differentiate":
            result = sympy.diff(parsed, symbols[selected_variable])
            status = "calculated"
        elif normalized_operation == "integrate":
            result = sympy.integrate(parsed, symbols[selected_variable])
            status = "calculated"
        elif normalized_operation == "solve":
            result = sympy.solve(parsed, symbols[selected_variable])
            if len(result) > 100:
                raise ValidationError("The solve result exceeds 100 values")
            status = "calculated"
        elif normalized_operation == "compare":
            if not isinstance(other_expression, str):
                raise ValidationError("other_expression is required for comparison")
            other, _, _ = self._sympy_expression(other_expression, variables)
            difference = sympy.simplify(parsed - other)
            return {
                "tool": "verify_symbolic_math",
                "status": "verified",
                "equivalent": bool(difference == 0),
                "normalized_difference": str(difference),
                "variables": variables,
                "versions": self._versions(),
            }
        else:
            raise ValidationError(
                "operation must be simplify, compare, differentiate, integrate, or solve"
            )
        return {
            "tool": "verify_symbolic_math",
            "status": status,
            "operation": normalized_operation,
            "result": str(result),
            "variables": variables,
            "variable": selected_variable,
            "versions": self._versions(),
        }

    def convert_units(self, *, value: float, from_unit: str, to_unit: str) -> dict[str, Any]:
        if not math.isfinite(value) or abs(value) > 1e100:
            raise ValidationError("value must be finite and bounded")
        if (
            not from_unit.strip()
            or not to_unit.strip()
            or len(from_unit) > 100
            or len(to_unit) > 100
            or not UNIT_PATTERN.fullmatch(from_unit)
            or not UNIT_PATTERN.fullmatch(to_unit)
        ):
            raise ValidationError("Units contain unsupported syntax")
        try:
            import pint
        except ImportError as exc:
            raise ConfigurationError(
                "Install the 'science' dependency extra to use unit conversion"
            ) from exc
        registry = pint.UnitRegistry()
        try:
            converted = (value * registry(from_unit)).to(to_unit)
        except (pint.errors.PintError, ValueError, TypeError) as exc:
            raise ValidationError(f"Unit conversion failed: {type(exc).__name__}") from exc
        return {
            "tool": "calculate_with_units",
            "status": "calculated",
            "input": {"value": value, "unit": from_unit},
            "output": {"value": float(converted.magnitude), "unit": str(converted.units)},
            "dimensionality": str(converted.dimensionality),
            "versions": self._versions(),
        }

    def plot(
        self,
        *,
        expression: str,
        variable: str,
        start: float,
        end: float,
        samples: int,
    ) -> PlotResult:
        if not math.isfinite(start) or not math.isfinite(end) or start >= end:
            raise ValidationError("Plot domain must be finite and increasing")
        if abs(start) > 1e6 or abs(end) > 1e6 or end - start > 1e6:
            raise ValidationError("Plot domain exceeds configured bounds")
        if not 50 <= samples <= 2000:
            raise ValidationError("samples must be between 50 and 2000")
        parsed, sympy, symbols = self._sympy_expression(expression, [variable])
        try:
            import numpy as np
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from matplotlib.figure import Figure
        except ImportError as exc:
            raise ConfigurationError(
                "Install the 'science' dependency extra to use plotting"
            ) from exc
        x_values = np.linspace(start, end, samples)
        try:
            function = sympy.lambdify(symbols[variable], parsed, modules=["numpy"])
            y_values = np.asarray(function(x_values), dtype=float)
            if y_values.ndim == 0:
                y_values = np.full_like(x_values, float(y_values))
            y_values = np.broadcast_to(y_values, x_values.shape)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError("Expression could not be evaluated over the domain") from exc
        finite = np.isfinite(y_values)
        if not finite.any():
            raise ValidationError("Plot contains no finite values")
        figure = Figure(figsize=(7, 4), tight_layout=True)
        axis = figure.subplots()
        axis.plot(x_values[finite], y_values[finite])
        axis.axhline(0, color="black", linewidth=0.5)
        axis.axvline(0, color="black", linewidth=0.5)
        axis.set_xlabel(variable)
        axis.set_ylabel(f"f({variable})")
        axis.set_title(f"f({variable}) = {expression}")
        axis.grid(alpha=0.25)
        output = io.BytesIO()
        FigureCanvasAgg(figure).print_png(output)
        return PlotResult(
            png=output.getvalue(),
            metadata={
                "tool": "plot_function",
                "status": "calculated",
                "expression": expression,
                "variable": variable,
                "domain": [start, end],
                "samples": samples,
                "versions": self._versions(),
            },
        )

    def inspect_equation(self, equation: str) -> dict[str, Any]:
        """Parse a simple equality without claiming that a sourced law is an identity."""
        if equation.count("=") != 1:
            return {
                "tool": "verify_symbolic_math",
                "status": "not_applicable",
                "reason": "Expected one equality sign",
            }
        left, right = (part.strip() for part in equation.split("=", 1))
        variables = sorted(
            set(NAME_PATTERN.findall(left + " " + right)) - SAFE_FUNCTIONS - SAFE_CONSTANTS
        )
        if not variables:
            return {
                "tool": "verify_symbolic_math",
                "status": "not_applicable",
                "reason": "No symbolic variables found",
            }
        try:
            normalized_left = self.symbolic(
                operation="simplify", expression=left, variables=variables
            )["result"]
            normalized_right = self.symbolic(
                operation="simplify", expression=right, variables=variables
            )["result"]
        except (ValidationError, ConfigurationError) as exc:
            return {
                "tool": "verify_symbolic_math",
                "status": "unverified",
                "reason": exc.message,
            }
        return {
            "tool": "verify_symbolic_math",
            "status": "parsed_not_proven",
            "original": equation,
            "normalized_left": normalized_left,
            "normalized_right": normalized_right,
            "variables": variables,
            "versions": self._versions(),
        }
