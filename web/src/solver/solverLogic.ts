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

  // 1. Initialize board occupancy bitmasks (0 = free, 1 = occupied)
  const totalCells = width * height;
  let initOcc0 = -1;
  let initOcc1 = -1;
  let initOcc2 = -1;

  let boardArea = 0;
  for (const [cx, cy] of allowedCells) {
    if (cx >= 0 && cx < width && cy >= 0 && cy < height) {
      const idx = cy * width + cx;
      if (idx < 32) {
        if ((initOcc0 & (1 << idx)) !== 0) {
          initOcc0 &= ~(1 << idx);
          boardArea++;
        }
      } else if (idx < 64) {
        const bit = idx - 32;
        if ((initOcc1 & (1 << bit)) !== 0) {
          initOcc1 &= ~(1 << bit);
          boardArea++;
        }
      } else if (idx < 81) {
        const bit = idx - 64;
        if ((initOcc2 & (1 << bit)) !== 0) {
          initOcc2 &= ~(1 << bit);
          boardArea++;
        }
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
  const deadline = performance.now() + timeLimitSec * 1000;
  let isTimedOut = false;
  let nodeCount = 0;

  const currentPlacedList: CurrentPlaced[] = [];
  const remainingCount = uniqueShapes.map((s) => s.count);
  let emptyCellsRemaining = boardArea;
  let remainingShapeArea = uniqueShapes.reduce((sum, s) => sum + s.area * s.count, 0);
  let mustRemaining = uniqueShapes.reduce((sum, s) => sum + (s.mustPlace ? s.count : 0), 0);
  let mustRemainingArea = uniqueShapes.reduce(
    (sum, s) => sum + (s.mustPlace ? s.area * s.count : 0),
    0
  );

  // 4. Precompute candidate placements for each anchor cell
  interface PlacementCandidate {
    typeId: number;
    rotation: number;
    m0: number;
    m1: number;
    m2: number;
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
      
      let isAnchorOccupied: boolean;
      if (anchorIdx < 32) isAnchorOccupied = (initOcc0 & (1 << anchorIdx)) !== 0;
      else if (anchorIdx < 64) isAnchorOccupied = (initOcc1 & (1 << (anchorIdx - 32))) !== 0;
      else isAnchorOccupied = (initOcc2 & (1 << (anchorIdx - 64))) !== 0;

      if (isAnchorOccupied) {
        continue; // If initially occupied, cannot be anchor
      }

      for (let typeId = 0; typeId < uniqueShapes.length; typeId++) {
        const shape = uniqueShapes[typeId];
        for (const orientation of shape.orientations) {
          let isValid = true;
          let m0 = 0;
          let m1 = 0;
          let m2 = 0;
          for (let pIdx = 0; pIdx < orientation.points.length; pIdx++) {
            const [px, py] = orientation.points[pIdx];
            const cx = ex + px;
            const cy = ey + py;
            if (cx < 0 || cx >= width || cy < 0 || cy >= height) {
              isValid = false;
              break;
            }
            const targetIdx = cy * width + cx;
            
            let isTargetOccupied: boolean;
            if (targetIdx < 32) isTargetOccupied = (initOcc0 & (1 << targetIdx)) !== 0;
            else if (targetIdx < 64) isTargetOccupied = (initOcc1 & (1 << (targetIdx - 32))) !== 0;
            else isTargetOccupied = (initOcc2 & (1 << (targetIdx - 64))) !== 0;

            if (isTargetOccupied) {
              isValid = false;
              break;
            }

            // Build masks
            if (targetIdx < 32) {
              m0 |= (1 << targetIdx);
            } else if (targetIdx < 64) {
              m1 |= (1 << (targetIdx - 32));
            } else {
              m2 |= (1 << (targetIdx - 64));
            }
          }
          if (isValid) {
            candidatesByAnchor[anchorIdx].push({
              typeId,
              rotation: orientation.rotation,
              m0,
              m1,
              m2,
              area: shape.area,
              points: orientation.points,
            });
          }
        }
      }
    }
  }

  function dfs(currentArea: number, o0: number, o1: number, o2: number) {
    if ((++nodeCount & 1023) === 0 && performance.now() > deadline) {
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

    if (mustRemainingArea > emptyCellsRemaining) {
      return; // Cannot place all remaining must-place shapes
    }

    // LSB O(1) scan: Find the first empty cell using bitmasks
    let emptyIdx: number;
    if (o0 !== -1) {
      const val = ~o0;
      emptyIdx = 31 - Math.clz32(val & -val);
    } else if (o1 !== -1) {
      const val = ~o1;
      emptyIdx = 32 + (31 - Math.clz32(val & -val));
    } else if (o2 !== -1) {
      const val = ~o2;
      emptyIdx = 64 + (31 - Math.clz32(val & -val));
    } else {
      emptyIdx = totalCells;
    }

    if (emptyIdx >= totalCells) {
      return; // No more empty cells
    }

    // Branch 1: Try covering the empty cell emptyIdx with precomputed candidates
    const candidates = candidatesByAnchor[emptyIdx];
    for (let i = 0; i < candidates.length; i++) {
      const p = candidates[i];
      if (remainingCount[p.typeId] === 0) continue;

      // Check if candidate overlaps with current occupancy
      if (((o0 & p.m0) | (o1 & p.m1) | (o2 & p.m2)) === 0) {
        // Place it
        remainingCount[p.typeId]--;
        emptyCellsRemaining -= p.area;
        remainingShapeArea -= p.area;
        const shape = uniqueShapes[p.typeId];
        if (shape.mustPlace) {
          mustRemaining--;
          mustRemainingArea -= p.area;
        }

        currentPlacedList.push({
          name: shape.name,
          x: emptyIdx % width,
          y: Math.floor(emptyIdx / width),
          rotation: p.rotation,
          points: p.points,
          color: shape.color,
        });

        // Recursion with updated masks (no explicit backtrack needed for bitmasks)
        dfs(currentArea + p.area, o0 | p.m0, o1 | p.m1, o2 | p.m2);

        // Backtrack other states
        currentPlacedList.pop();
        if (shape.mustPlace) {
          mustRemaining++;
          mustRemainingArea += p.area;
        }
        remainingShapeArea += p.area;
        emptyCellsRemaining += p.area;
        remainingCount[p.typeId]++;

        if (bestArea === boardArea || isTimedOut) return;
      }
    }

    // Branch 2: Abandon this empty cell
    let nextO0 = o0;
    let nextO1 = o1;
    let nextO2 = o2;
    if (emptyIdx < 32) {
      nextO0 |= (1 << emptyIdx);
    } else if (emptyIdx < 64) {
      nextO1 |= (1 << (emptyIdx - 32));
    } else {
      nextO2 |= (1 << (emptyIdx - 64));
    }
    emptyCellsRemaining -= 1;

    dfs(currentArea, nextO0, nextO1, nextO2);

    emptyCellsRemaining += 1;
  }

  // Execute DFS starting from initial occupancy masks
  dfs(0, initOcc0, initOcc1, initOcc2);

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
