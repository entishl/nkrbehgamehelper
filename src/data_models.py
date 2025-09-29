from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Tuple


@dataclass
class Shape:
    """Represents a single shape with its name and matrix representation."""
    name: str
    points: List[List[int]]
    area: int
    color: str


@dataclass
class Rectangle:
    """Represents a rectangle with its dimensions."""
    width: int
    height: int


@dataclass
class PlacedShape:
    """Represents a shape that has been placed on the grid."""
    name: str
    x: int
    y: int
    points: List[Tuple[int, int]]
    color: str


class PackingStatus(Enum):
    """Represents the status of a packing operation."""

    OPTIMAL = auto()
    """An optimal solution was found."""

    FEASIBLE = auto()
    """A feasible solution was found, but it is not necessarily optimal."""

    INFEASIBLE = auto()
    """The model was proven to be infeasible."""

    UNKNOWN = auto()
    """The solver stopped before proving feasibility or infeasibility."""

    MODEL_INVALID = auto()
    """The model is invalid."""


@dataclass
class PackingResult:
    """Represents the result of a packing operation."""
    board_size: Tuple[int, int]
    status: PackingStatus
    placed_shapes: List[PlacedShape] = field(default_factory=list)
    unplaced_shapes: List[str] = field(default_factory=list)