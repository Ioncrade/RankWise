from __future__ import annotations

import pytest
from rankwise.errors import ValidationError
from rankwise.science_tools import ScienceTools


def test_symbolic_operations_are_deterministic() -> None:
    tools = ScienceTools()
    derivative = tools.symbolic(
        operation="differentiate",
        expression="x^3 + 2*x",
        variables=["x"],
    )
    assert derivative["result"] == "3*x**2 + 2"
    solved = tools.symbolic(operation="solve", expression="x^2 - 4", variables=["x"])
    assert solved["result"] == "[-2, 2]"


def test_science_tools_reject_unbounded_or_unknown_syntax() -> None:
    tools = ScienceTools()
    with pytest.raises(ValidationError, match="unsupported syntax"):
        tools.symbolic(operation="simplify", expression="x.__class__", variables=["x"])
    with pytest.raises(ValidationError, match="greater than 12"):
        tools.symbolic(operation="simplify", expression="x^1000", variables=["x"])
    with pytest.raises(ValidationError, match="Unknown"):
        tools.symbolic(operation="simplify", expression="evil(x)", variables=["x"])


def test_units_and_plot_are_bounded() -> None:
    tools = ScienceTools()
    result = tools.convert_units(value=9.81, from_unit="meter/second^2", to_unit="foot/second^2")
    assert result["output"]["value"] == pytest.approx(32.185, rel=0.001)
    with pytest.raises(ValidationError, match="DimensionalityError"):
        tools.convert_units(value=1, from_unit="meter", to_unit="second")
    plot = tools.plot(expression="x^2", variable="x", start=-2, end=2, samples=100)
    assert plot.png.startswith(b"\x89PNG")
    assert plot.metadata["samples"] == 100
    with pytest.raises(ValidationError, match="samples"):
        tools.plot(expression="x", variable="x", start=0, end=1, samples=2)
