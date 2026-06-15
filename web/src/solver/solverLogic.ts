import type { Point, Shape, PlacedShape, SolverInput, SolverResult } from '../types';

/**
 * Normalize points so that the top-leftmost occupied cell in row-major order is (0, 0).
 */
export function normalizePoints(points: Point[]): Point[] {
  if (points.length === 0) return [];
  // Sort row-major: y first, then x
  const sorted = [...points].sort((a, b) => (a[1] !== b[1] ? a[1] - b[1] : a[0] - b[0]));
  const [firstX, firstY] = sorted[0];
  
  return sorted.map(([x, y]) => [x - firstX, y - firstY] as Point);
}

/**
 * Rotate points clockwise by 0/90/180/270 degrees and normalize them.
 */
export function rotatePoints(points: Point[], rotation: number): Point[] {
  if (rotation === 0) return normalizePoints(points);
  
  let rotated: Point[];
  if (rotation === 90) {
    rotated = points.map(([x, y]) => [-y, x]);
  } else if (rotation === 180) {
    rotated = points.map(([x, y]) => [-x, -y]);
  } else if (rotation === 270) {
    rotated = points.map(([x, y]) => [y, -x]);
  } else {
    throw new Error('Rotation must be 0, 90, 180, or 270');
  }
  
  return normalizePoints(rotated);
}

export interface Orientation {
  rotation: number;
  points: Point[];
}

/**
 * Return unique orientations for a shape.
 */
export function generateUniqueOrientations(points: Point[], allowRotation: boolean = true): Orientation[] {
  const orientations: Orientation[] = [];
  const seen = new Set<string>();
  const rotations = allowRotation ? [0, 90, 180, 270] : [0];

  // We should start from normalized points to ensure rotations are standard
  const initialNormalized = normalizePoints(points);

  for (const rotation of rotations) {
    const rotated = rotatePoints(initialNormalized, rotation);
    const key = rotated.map(([x, y]) => `${x},${y}`).join(';');
    if (seen.has(key)) continue;
    seen.add(key);

    orientations.push({
      rotation,
      points: rotated,
    });
  }

  return orientations;
}

interface UniquePreparedShape extends Shape {
  orientations: Orientation[];
  mustPlace: boolean;
  count: number;
}

interface CurrentPlaced {
  name: string;
  x: number;
  y: number;
  rotation: number;
  points: Point[];
  color: string;
}

/**
 * Main shape packing solver using Cell-Centric DFS.
 */
export function solvePacking(
  input: SolverInput,
  onProgress?: (bestArea: number) => void
): SolverResult {
  const { shapesToPack, allowedCells, boardSize, mustPlaceNames, timeLimitSec, allowRotation } = input;
  const [width, height] = boardSize;

  // 1. Initialize board occupancy grid (1D Uint8Array)
  const totalCells = width * height;
  const boardOccupied = new Uint8Array(totalCells);
  boardOccupied.fill(1); // Default to occupied/blocked (1 = true)

  let boardArea = 0;
  for (const [cx, cy] of allowedCells) {
    if (cx >= 0 && cx < width && cy >= 0 && cy < height) {
      const idx = cy * width + cx;
      if (boardOccupied[idx] === 1) {
        boardOccupied[idx] = 0; // Set to free/allowed (0 = false)
        boardArea++;
      }
    }
  }

  // 2. Identify must-place shapes
  const mustPlaceSet = new Set(mustPlaceNames);

  // 3. Prepare unique shapes with counts
  const uniqueShapes: UniquePreparedShape[] = [];
  const nameToUniqueIndex = new Map<string, number>();

  for (const shape of shapesToPack) {
    const idx = nameToUniqueIndex.get(shape.name);
    if (idx === undefined) {
      const orientations = generateUniqueOrientations(shape.points, allowRotation);
      const uniqueShape: UniquePreparedShape = {
        name: shape.name,
        points: shape.points,
        area: shape.area,
        color: shape.color,
        orientations,
        mustPlace: mustPlaceSet.has(shape.name),
        count: 1,
      };
      uniqueShapes.push(uniqueShape);
      nameToUniqueIndex.set(shape.name, uniqueShapes.length - 1);
    } else {
      uniqueShapes[idx].count++;
    }
  }

  // Sort unique shapes: mustPlace first, then by area descending.
  uniqueShapes.sort((a, b) => {
    if (a.mustPlace && !b.mustPlace) return -1;
    if (!a.mustPlace && b.mustPlace) return 1;
    return b.area - a.area;
  });

  let bestArea = 0;
  let bestPlaced: CurrentPlaced[] = [];
  const startTime = Date.now();
  const timeLimitMs = timeLimitSec * 1000;
  let isTimedOut = false;

  const currentPlacedList: CurrentPlaced[] = [];
  const remainingCount = uniqueShapes.map((s) => s.count);
  let emptyCellsRemaining = boardArea;
  let remainingShapeArea = uniqueShapes.reduce((sum, s) => sum + s.area * s.count, 0);
  let mustRemaining = uniqueShapes.reduce((sum, s) => sum + (s.mustPlace ? s.count : 0), 0);

  // 4. Precompute candidate placements for each anchor cell
  interface PlacementCandidate {
    typeId: number;
    rotation: number;
    cells: Int32Array;
    area: number;
    points: Point[];
  }

  const candidatesByAnchor: PlacementCandidate[][] = Array.from(
    { length: totalCells },
    () => []
  );

  for (let ey = 0; ey < height; ey++) {
    for (let ex = 0; ex < width; ex++) {
      const anchorIdx = ey * width + ex;
      if (boardOccupied[anchorIdx] === 1) {
        continue; // If initially occupied, cannot be anchor
      }

      for (let typeId = 0; typeId < uniqueShapes.length; typeId++) {
        const shape = uniqueShapes[typeId];
        for (const orientation of shape.orientations) {
          let isValid = true;
          const cells = new Int32Array(orientation.points.length);
          for (let pIdx = 0; pIdx < orientation.points.length; pIdx++) {
            const [px, py] = orientation.points[pIdx];
            const cx = ex + px;
            const cy = ey + py;
            if (cx < 0 || cx >= width || cy < 0 || cy >= height) {
              isValid = false;
              break;
            }
            const targetIdx = cy * width + cx;
            if (boardOccupied[targetIdx] === 1) {
              isValid = false;
              break;
            }
            cells[pIdx] = targetIdx;
          }
          if (isValid) {
            candidatesByAnchor[anchorIdx].push({
              typeId,
              rotation: orientation.rotation,
              cells,
              area: shape.area,
              points: orientation.points,
            });
          }
        }
      }
    }
  }

  function dfs(currentArea: number, startIdx: number) {
    if (Date.now() - startTime > timeLimitMs) {
      isTimedOut = true;
      return;
    }

    if (currentArea > bestArea && mustRemaining === 0) {
      bestArea = currentArea;
      bestPlaced = currentPlacedList.map((item) => ({ ...item }));
      if (onProgress) {
        onProgress(bestArea);
      }
    }

    if (bestArea === boardArea) {
      return; // Found optimal perfect cover
    }

    // Pruning: Calculate maximum possible area we can achieve from here
    const maxPossibleArea = currentArea + Math.min(emptyCellsRemaining, remainingShapeArea);
    if (maxPossibleArea <= bestArea) {
      return; // Cannot beat best Area
    }

    // Find the first empty cell (row-major scan)
    let emptyIdx = startIdx;
    while (emptyIdx < totalCells && boardOccupied[emptyIdx] === 1) {
      emptyIdx++;
    }

    if (emptyIdx >= totalCells) {
      return; // No more empty cells
    }

    // Branch 1: Try covering the empty cell emptyIdx with precomputed candidates
    const candidates = candidatesByAnchor[emptyIdx];
    for (let i = 0; i < candidates.length; i++) {
      const p = candidates[i];
      if (remainingCount[p.typeId] === 0) continue;

      let canPlace = true;
      // cells[0] is emptyIdx itself, which is already known to be free (0)
      for (let cIdx = 1; cIdx < p.cells.length; cIdx++) {
        if (boardOccupied[p.cells[cIdx]] === 1) {
          canPlace = false;
          break;
        }
      }

      if (canPlace) {
        // Place it
        for (let cIdx = 0; cIdx < p.cells.length; cIdx++) {
          boardOccupied[p.cells[cIdx]] = 1;
        }
        remainingCount[p.typeId]--;
        emptyCellsRemaining -= p.area;
        remainingShapeArea -= p.area;
        const shape = uniqueShapes[p.typeId];
        if (shape.mustPlace) mustRemaining--;

        currentPlacedList.push({
          name: shape.name,
          x: emptyIdx % width,
          y: Math.floor(emptyIdx / width),
          rotation: p.rotation,
          points: p.points,
          color: shape.color,
        });

        dfs(currentArea + p.area, emptyIdx + 1);

        // Backtrack
        currentPlacedList.pop();
        if (shape.mustPlace) mustRemaining++;
        remainingShapeArea += p.area;
        emptyCellsRemaining += p.area;
        remainingCount[p.typeId]++;
        for (let cIdx = 0; cIdx < p.cells.length; cIdx++) {
          boardOccupied[p.cells[cIdx]] = 0;
        }

        if (bestArea === boardArea || isTimedOut) return;
      }
    }

    // Branch 2: Abandon this empty cell
    boardOccupied[emptyIdx] = 1; // Mark as permanently abandoned
    emptyCellsRemaining -= 1;

    dfs(currentArea, emptyIdx + 1);

    boardOccupied[emptyIdx] = 0; // Restore
    emptyCellsRemaining += 1;
  }

  // Execute DFS starting from index 0
  dfs(0, 0);

  // Determine solver status
  let status: 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'UNKNOWN';
  if (isTimedOut) {
    status = bestPlaced.length > 0 ? 'FEASIBLE' : 'UNKNOWN';
  } else if (bestArea === boardArea) {
    status = 'OPTIMAL';
  } else if (bestPlaced.length === 0) {
    status = 'INFEASIBLE';
  } else {
    status = 'OPTIMAL';
  }

  // Calculate unplaced shapes
  const placedCounts = new Map<string, number>();
  for (const p of bestPlaced) {
    placedCounts.set(p.name, (placedCounts.get(p.name) || 0) + 1);
  }

  const unplacedShapes: string[] = [];
  const actualShapesCount = new Map<string, number>();
  for (const s of shapesToPack) {
    actualShapesCount.set(s.name, (actualShapesCount.get(s.name) || 0) + 1);
  }

  for (const [name, totalCount] of actualShapesCount.entries()) {
    const placedCount = placedCounts.get(name) || 0;
    const unplacedCount = totalCount - placedCount;
    for (let i = 0; i < unplacedCount; i++) {
      unplacedShapes.push(name);
    }
  }

  // Format placed shapes for response
  const formattedPlaced: PlacedShape[] = bestPlaced.map((p) => ({
    name: p.name,
    position: [p.x, p.y] as Point,
    points: p.points,
    color: p.color,
    rotation: p.rotation,
  }));

  return {
    placedShapes: formattedPlaced,
    unplacedShapes,
    status,
  };
}
