"""Declarative field / signature framework (DSPy-compatible)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FieldKind(str, Enum):
    """Whether a signature field is consumed (INPUT) or produced (OUTPUT)."""

    INPUT = "input"
    OUTPUT = "output"


@dataclass(frozen=True)
class Field:
    """A single typed field on a :class:`Signature`."""

    kind: FieldKind
    desc: str = ""
    annotation: Any = str


def InputField(desc: str = "", annotation: Any = str) -> Any:
    """Declare an input field on a signature (DSPy-compatible spelling)."""
    return Field(FieldKind.INPUT, desc, annotation)


def OutputField(desc: str = "", annotation: Any = str) -> Any:
    """Declare an output field on a signature (DSPy-compatible spelling)."""
    return Field(FieldKind.OUTPUT, desc, annotation)


class Signature:
    """Base class for declarative typed stage signatures."""

    @classmethod
    def fields(cls) -> dict[str, Field]:
        """Return every declared field, annotated with its declared type."""
        annotations: dict[str, Any] = {}
        for klass in reversed(cls.__mro__):
            annotations.update(getattr(klass, "__annotations__", {}))

        result: dict[str, Field] = {}
        for klass in reversed(cls.__mro__):
            for name, value in vars(klass).items():
                if isinstance(value, Field):
                    anno = annotations.get(name, value.annotation)
                    result[name] = Field(value.kind, value.desc, anno)
        return result

    @classmethod
    def inputs(cls) -> dict[str, Field]:
        """Return only the INPUT fields."""
        return {n: f for n, f in cls.fields().items() if f.kind is FieldKind.INPUT}

    @classmethod
    def outputs(cls) -> dict[str, Field]:
        """Return only the OUTPUT fields."""
        return {n: f for n, f in cls.fields().items() if f.kind is FieldKind.OUTPUT}

    @classmethod
    def instructions(cls) -> str:
        """Return the stage instruction (the class docstring, stripped)."""
        return (cls.__doc__ or "").strip()

    @classmethod
    def validate_inputs(cls, **kwargs: Any) -> None:
        """Raise ValueError if any declared input is missing from kwargs."""
        missing = [name for name in cls.inputs() if name not in kwargs]
        if missing:
            raise ValueError(f"{cls.__name__} missing required input field(s): {sorted(missing)}")


__all__ = [
    "FieldKind",
    "Field",
    "InputField",
    "OutputField",
    "Signature",
]
