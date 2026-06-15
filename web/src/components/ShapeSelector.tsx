import React from 'react';
import type { Shape } from '../types';
import { Lock, Unlock, Plus, Minus, Settings, FileSpreadsheet, Trash2 } from 'lucide-react';

interface ShapeSelectorProps {
  shapesData: Shape[];
  counts: Record<string, number>;
  locks: Record<string, boolean>;
  onCountChange: (name: string, count: number) => void;
  onLockToggle: (name: string) => void;
  onClear: () => void;
  onOpenBatch: () => void;
  onOpenManager: () => void;
}

// Subcomponent to render a shape as SVG
export const ShapeSvgPreview: React.FC<{ points: [number, number][]; color: string; size?: number }> = ({
  points,
  color,
  size = 40,
}) => {
  if (points.length === 0) return null;

  const minX = Math.min(...points.map(([x]) => x));
  const maxX = Math.max(...points.map(([x]) => x));
  const minY = Math.min(...points.map(([, y]) => y));
  const maxY = Math.max(...points.map(([, y]) => y));

  const w = maxX - minX + 1;
  const h = maxY - minY + 1;

  const maxDim = Math.max(w, h);
  const padding = 4;
  const cellSize = (size - padding * 2) / maxDim;
  const offsetX = (size - w * cellSize) / 2;
  const offsetY = (size - h * cellSize) / 2;

  return (
    <svg width={size} height={size} className="bg-black/20 rounded-md">
      {points.map(([x, y], idx) => {
        const rx = offsetX + (x - minX) * cellSize;
        const ry = offsetY + (y - minY) * cellSize;
        return (
          <rect
            key={idx}
            x={rx}
            y={ry}
            width={cellSize - 0.75}
            height={cellSize - 0.75}
            fill={color}
            rx={cellSize > 6 ? 1.5 : 0.5}
          />
        );
      })}
    </svg>
  );
};

export const ShapeSelector: React.FC<ShapeSelectorProps> = ({
  shapesData,
  counts,
  locks,
  onCountChange,
  onLockToggle,
  onClear,
  onOpenBatch,
  onOpenManager,
}) => {
  // Compute total selected area
  const totalArea = shapesData.reduce((acc, shape) => {
    const count = counts[shape.name] || 0;
    return acc + count * shape.area;
  }, 0);

  const handleIncrement = (name: string) => {
    const current = counts[name] || 0;
    onCountChange(name, current + 1);
  };

  const handleDecrement = (name: string) => {
    const current = counts[name] || 0;
    if (current > 0) {
      onCountChange(name, current - 1);
    }
  };

  const handleInputChange = (name: string, val: string) => {
    const num = parseInt(val, 10);
    if (!isNaN(num) && num >= 0) {
      onCountChange(name, num);
    } else if (val === '') {
      onCountChange(name, 0);
    }
  };

  return (
    <div className="glass-panel shape-selector-container">
      <h3 className="panel-title">
        形状选择与配置
      </h3>

      {/* Scrollable grid container for shapes */}
      <div className="shapes-scroll-area">
        {shapesData.map((shape) => {
          const count = counts[shape.name] || 0;
          const isLocked = !!locks[shape.name];

          return (
            <div
              key={shape.name}
              className={`shape-card ${count > 0 ? 'shape-card-active' : 'shape-card-inactive'}`}
            >
              {/* Left: Lock, SVG and Name underneath SVG */}
              <div className="shape-card-left">
                <button
                  type="button"
                  onClick={() => onLockToggle(shape.name)}
                  className={`lock-toggle-btn ${
                    isLocked ? 'lock-toggle-btn-locked' : 'lock-toggle-btn-unlocked'
                  }`}
                  title={isLocked ? '锁定：必须放置该形状' : '未锁定'}
                >
                  {isLocked ? <Lock size={14} /> : <Unlock size={14} />}
                </button>
                <ShapeSvgPreview points={shape.points} color={shape.color} size={36} />
              </div>

              {/* Right: Quantity controls */}
              <div className="shape-card-right">
                <div className="quantity-control">
                  <button
                    type="button"
                    onClick={() => handleDecrement(shape.name)}
                    className="quantity-btn"
                  >
                    <Minus size={14} />
                  </button>
                  <input
                    type="text"
                    value={count}
                    onChange={(e) => handleInputChange(shape.name, e.target.value)}
                    className="quantity-input"
                  />
                  <button
                    type="button"
                    onClick={() => handleIncrement(shape.name)}
                    className="quantity-btn"
                  >
                    <Plus size={14} />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Area calculations */}
      <div className="board-area-badge">
        <span>选定形状总面积:</span>
        <span className="area-number">{totalArea}</span>
      </div>

      {/* Control Buttons */}
      <div className="actions-row-grid">
        <button
          onClick={onClear}
          className="btn-secondary"
          title="清空所有数量"
        >
          <Trash2 size={13} />
          <span>清空</span>
        </button>
        <button
          onClick={onOpenBatch}
          className="btn-secondary"
          title="JSON 批量设置数量"
        >
          <FileSpreadsheet size={13} />
          <span>一键输入</span>
        </button>
        <button
          onClick={onOpenManager}
          className="btn-secondary"
          title="形状库管理与自定义绘制"
        >
          <Settings size={13} />
          <span>形状管理</span>
        </button>
      </div>
    </div>
  );
};
