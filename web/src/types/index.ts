export type Point = [number, number];

export interface Shape {
  name: string;
  points: Point[];
  area: number;
  color: string;
}

export interface PlacedShape {
  name: string;
  position: Point; // [x, y]
  points: Point[]; // Relative points in current orientation
  color: string;
  rotation: number; // 0, 90, 180, 270
}

export interface SolverInput {
  shapesToPack: Shape[];
  allowedCells: Point[];
  boardSize: [number, number]; // [width, height]
  mustPlaceNames: string[];
  timeLimitSec: number;
  allowRotation: boolean;
}

export interface SolverResult {
  placedShapes: PlacedShape[];
  unplacedShapes: string[]; // Names of shapes not placed
  status: 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'UNKNOWN';
}
