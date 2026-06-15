import React from 'react';
import type { PlacedShape, Shape, Point } from '../types';
import { ShapeSvgPreview } from './ShapeSelector';
import { CheckCircle2, AlertTriangle, HelpCircle, Trash2 } from 'lucide-react';

interface VisualizerProps {
  placedShapes: PlacedShape[];
  unplacedShapes: Shape[]; // Shapes with full details
  allowedCells: Point[];
  status: 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'UNKNOWN' | null;
  onClearUnplaced: () => void;
}

const STATUS_TEXT_MAP = {
  OPTIMAL: {
    text: '已找到理论最优解',
    colorClass: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    icon: <CheckCircle2 size={16} className="text-emerald-400" />,
  },
  FEASIBLE: {
    text: '超时，找到可行解（不一定理论最优）',
    colorClass: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    icon: <AlertTriangle size={16} className="text-amber-400" />,
  },
  INFEASIBLE: {
    text: '无可行的放置方案',
    colorClass: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
    icon: <AlertTriangle size={16} className="text-rose-400" />,
  },
  UNKNOWN: {
    text: '求解失败或计算异常',
    colorClass: 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20',
    icon: <HelpCircle size={16} className="text-zinc-400" />,
  },
};

export const Visualizer: React.FC<VisualizerProps> = ({
  placedShapes,
  unplacedShapes,
  allowedCells,
  status,
  onClearUnplaced,
}) => {
  const GRID_SIZE = 9;
  const VIEW_SIZE = 288; // 9 * 32px per cell
  const CELL_SCALE = VIEW_SIZE / GRID_SIZE; // 32px

  const allowedCellsSet = new Set(allowedCells.map(([x, y]) => `${x},${y}`));

  // Generate unique lines for the bold borders of each placed shape
  const renderShapeBorders = (shape: PlacedShape, idx: number) => {
    const [px, py] = shape.position;
    const absPoints = shape.points.map(([dx, dy]) => [px + dx, py + dy] as Point);
    const absPointsSet = new Set(absPoints.map(([x, y]) => `${x},${y}`));

    const borderLines: React.ReactNode[] = [];

    absPoints.forEach(([x, y]) => {
      const x0 = x * CELL_SCALE;
      const y0 = y * CELL_SCALE;
      const x1 = (x + 1) * CELL_SCALE;
      const y1 = (y + 1) * CELL_SCALE;

      // Top Edge
      if (!absPointsSet.has(`${x},${y - 1}`)) {
        borderLines.push(
          <line
            key={`t-${x}-${y}-${idx}`}
            x1={x0}
            y1={y0}
            x2={x1}
            y2={y0}
            stroke="black"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        );
      }
      // Bottom Edge
      if (!absPointsSet.has(`${x},${y + 1}`)) {
        borderLines.push(
          <line
            key={`b-${x}-${y}-${idx}`}
            x1={x0}
            y1={y1}
            x2={x1}
            y2={y1}
            stroke="black"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        );
      }
      // Left Edge
      if (!absPointsSet.has(`${x - 1},${y}`)) {
        borderLines.push(
          <line
            key={`l-${x}-${y}-${idx}`}
            x1={x0}
            y1={y0}
            x2={x0}
            y2={y1}
            stroke="black"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        );
      }
      // Right Edge
      if (!absPointsSet.has(`${x + 1},${y}`)) {
        borderLines.push(
          <line
            key={`r-${x}-${y}-${idx}`}
            x1={x1}
            y1={y0}
            x2={x1}
            y2={y1}
            stroke="black"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        );
      }
    });

    return borderLines;
  };

  // Group unplaced shapes by name to show count badge
  const unplacedGroups = unplacedShapes.reduce<Record<string, { shape: Shape; count: number }>>(
    (acc, shape) => {
      if (!acc[shape.name]) {
        acc[shape.name] = { shape, count: 0 };
      }
      acc[shape.name].count += 1;
      return acc;
    },
    {}
  );

  const statusInfo = status ? STATUS_TEXT_MAP[status] : null;

  return (
    <div className="glass-panel visualizer-container">
      <h3 className="panel-title">
        布局优化结果展示
      </h3>

      {/* Solver status banner */}
      {statusInfo && (
        <div className={`status-badge ${
          status === 'OPTIMAL' ? 'status-optimal' :
          status === 'FEASIBLE' ? 'status-feasible' :
          status === 'INFEASIBLE' ? 'status-infeasible' :
          'status-unknown'
        }`}>
          {statusInfo.icon}
          <span>{statusInfo.text}</span>
        </div>
      )}

      {/* Main Board Visualizer */}
      <div className="board-output-wrapper">
        <svg
          width={VIEW_SIZE}
          height={VIEW_SIZE}
          style={{ overflow: 'visible', userSelect: 'none', borderRadius: '12px' }}
        >
          {/* 1. Background Grid Cells */}
          {Array.from({ length: GRID_SIZE }).map((_, r) =>
            Array.from({ length: GRID_SIZE }).map((_, c) => {
              const isActive = allowedCellsSet.has(`${c},${r}`);
              return (
                <rect
                  key={`${r}-${c}`}
                  x={c * CELL_SCALE}
                  y={r * CELL_SCALE}
                  width={CELL_SCALE - 0.5}
                  height={CELL_SCALE - 0.5}
                  fill={isActive ? 'hsla(0, 0%, 95%, 0.95)' : 'hsl(220, 25%, 5%)'}
                  stroke="hsl(220, 20%, 15%)"
                  strokeWidth="0.5"
                  rx="2.5"
                />
              );
            })
          )}

          {/* 2. Placed Shape Fills */}
          {placedShapes.map((shape, idx) => {
            const [px, py] = shape.position;
            return (
              <g key={`fill-${idx}`}>
                {shape.points.map(([dx, dy], pIdx) => (
                  <rect
                    key={pIdx}
                    x={(px + dx) * CELL_SCALE}
                    y={(py + dy) * CELL_SCALE}
                    width={CELL_SCALE}
                    height={CELL_SCALE}
                    fill={shape.color}
                    stroke={shape.color}
                    strokeWidth="0.5"
                  />
                ))}
              </g>
            );
          })}

          {/* 3. Placed Shape Border Outlines */}
          {placedShapes.map((shape, idx) => (
            <g key={`border-${idx}`}>{renderShapeBorders(shape, idx)}</g>
          ))}
        </svg>

        {/* Infeasible solution water-mark */}
        {status === 'INFEASIBLE' && (
          <div className="infeasible-overlay">
            <span className="infeasible-banner">
              无可解方案
            </span>
          </div>
        )}
      </div>

      {/* Unplaced shapes drawer */}
      <div className="unplaced-drawer">
        {unplacedShapes.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div className="unplaced-header">
              <span className="unplaced-label">
                未成功放入的形状:
              </span>
              <button
                onClick={onClearUnplaced}
                className="unplaced-deduct-btn"
                title="扣除输入中对应的未放置形状数量"
              >
                <Trash2 size={12} />
                <span>扣除未放置数量</span>
              </button>
            </div>
            
            <div className="unplaced-shapes-list">
              {Object.values(unplacedGroups).map(({ shape, count }) => (
                <div
                  key={shape.name}
                  className="unplaced-shape-card"
                >
                  <ShapeSvgPreview points={shape.points} color={shape.color} size={24} />
                  <div className="unplaced-shape-info">
                    <span className="unplaced-shape-name">
                      {shape.name}
                    </span>
                    <span className="unplaced-shape-count">
                      数量: {count}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ fontSize: '12px', textAlign: 'center', color: 'var(--text-dim)', padding: '8px 0' }}>
            {status ? '全部形状已成功装入容器！' : '等待点击计算求解...'}
          </div>
        )}
      </div>
    </div>
  );
};
