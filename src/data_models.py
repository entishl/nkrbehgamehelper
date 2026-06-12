from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Tuple


@dataclass
class Shape:
    """Represents a single shape with its name and occupied points."""
    name: str
    points: List[Tuple[int, int]]
    area: int
    color: str


@dataclass
class Rectangle:
    """Represents a rectangle with its dimensions."""
    width: int
    height: int
    x_offset: int
    y_offset: int


@dataclass
class PlacedShape:
    """Represents a shape placed on the board."""
    name: str
    x: int
    y: int
    points: List[Tuple[int, int]]
    color: str
    rotation: int = 0


class PackingStatus(Enum):
    """The status of the packing solution."""
    OPTIMAL = auto()
    FEASIBLE = auto()
    INFEASIBLE = auto()
    UNKNOWN = auto()


@dataclass
class PackingResult:
    """The result of a packing attempt."""
    placed_shapes: List[PlacedShape] = field(default_factory=list)
    unplaced_shapes: List[str] = field(default_factory=list)
    board_size: Tuple[int, int] = (0, 0)
    status: PackingStatus = PackingStatus.UNKNOWN
