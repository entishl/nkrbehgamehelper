import React, { useState } from 'react';
import type { Shape } from '../types';
import { normalizePoints } from '../solver/solverLogic';
import { ShapeSvgPreview } from './ShapeSelector';
import { X, Trash2, Plus, RefreshCw, Palette } from 'lucide-react';

interface ShapeManagerProps {
  shapesData: Shape[];
  onAddShape: (shape: Shape) => void;
  onDeleteShape: (name: string) => void;
  onClose: () => void;
}

const PRESET_COLORS = [
  '#FF5E7E', // Pink
  '#2F86F6', // Blue
  '#FF6B4A', // Orange
  '#E040FB', // Light Purple
  '#FFB300', // Yellow
  '#00BCD4', // Cyan
  '#8E24AA', // Purple
  '#AED581', // Green
  '#26A69A', // Teal
  '#3F51B5', // Indigo
  '#00E676', // Lime
  '#78909C', // Slate
];

export const ShapeManager: React.FC<ShapeManagerProps> = ({
  shapesData,
  onAddShape,
  onDeleteShape,
  onClose,
}) => {
  const [shapeName, setShapeName] = useState<string>('');
  const [selectedColor, setSelectedColor] = useState<string>(PRESET_COLORS[0]);
  const [drawingBoard, setDrawingBoard] = useState<boolean[][]>(
    Array.from({ length: 6 }, () => new Array(6).fill(false))
  );

  const toggleDrawingCell = (r: number, c: number) => {
    const newBoard = drawingBoard.map((row, rIdx) =>
      row.map((val, cIdx) => (rIdx === r && cIdx === c ? !val : val))
    );
    setDrawingBoard(newBoard);
  };

  const handleClearBoard = () => {
    setDrawingBoard(Array.from({ length: 6 }, () => new Array(6).fill(false)));
  };

  const handleSaveShape = () => {
    const trimmedName = shapeName.trim();
    if (!trimmedName) {
      alert('请输入形状名称！');
      return;
    }

    // Extract selected cell coordinates
    const points: [number, number][] = [];
    drawingBoard.forEach((row, r) => {
      row.forEach((val, c) => {
        if (val) {
          points.push([c, r]); // Store as [x, y]
        }
      });
    });

    if (points.length === 0) {
      alert('请在右侧绘制板上绘制形状！');
      return;
    }

    // Normalize points so top-left starts at (0, 0)
    const normalized = normalizePoints(points);

    const newShape: Shape = {
      name: trimmedName,
      points: normalized,
      area: normalized.length,
      color: selectedColor,
    };

    onAddShape(newShape);
    
    // Reset inputs
    setShapeName('');
    handleClearBoard();
  };

  const handleLoadShapeToBoard = (shape: Shape) => {
    // Set editor states
    setShapeName(shape.name);
    setSelectedColor(shape.color);

    // Reconstruct drawing board from shape points (offset to center a bit)
    const newBoard = Array.from({ length: 6 }, () => new Array(6).fill(false));
    
    // Find width and height of shape to offset it
    const xs = shape.points.map(([x]) => x);
    const ys = shape.points.map(([, y]) => y);
    const w = Math.max(...xs) - Math.min(...xs) + 1;
    const h = Math.max(...ys) - Math.min(...ys) + 1;
    
    // Compute center offset (draw board is 6x6)
    const offsetX = Math.max(0, Math.floor((6 - w) / 2));
    const offsetY = Math.max(0, Math.floor((6 - h) / 2));

    shape.points.forEach(([x, y]) => {
      const targetX = x + offsetX;
      const targetY = y + offsetY;
      if (targetX >= 0 && targetX < 6 && targetY >= 0 && targetY < 6) {
        newBoard[targetY][targetX] = true;
      }
    });

    setDrawingBoard(newBoard);
  };

  return (
    <div className="modal-overlay">
      <div className="modal-container modal-container-large">
        {/* Header */}
        <div className="modal-header">
          <h3 className="modal-title">
            <Palette size={18} className="text-[var(--accent-purple)]" />
            <span>形状库配置管理器</span>
          </h3>
          <button onClick={onClose} className="modal-close-btn">
            <X size={18} />
          </button>
        </div>

        {/* Content Body: Split Left & Right */}
        <div className="modal-body shape-manager-split-content">
          {/* Left panel: List existing shapes */}
          <div className="shape-manager-left">
            <h4 className="manager-list-header">
              <span>现有形状库 ({shapesData.length})</span>
              <span className="text-[var(--text-dim)]" style={{ fontWeight: 'normal' }}>
                点击形状可加载到编辑器
              </span>
            </h4>
            <div className="manager-shapes-list">
              {shapesData.map((shape) => (
                <div
                  key={shape.name}
                  onClick={() => handleLoadShapeToBoard(shape)}
                  className="manager-shape-card"
                >
                  <div className="manager-shape-card-left">
                    <ShapeSvgPreview points={shape.points} color={shape.color} size={32} />
                    <div className="manager-shape-details">
                      <span className="manager-shape-name">{shape.name}</span>
                      <span className="manager-shape-area">面积 (格数): {shape.area}</span>
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(`确定要删除形状 "${shape.name}" 吗？`)) {
                        onDeleteShape(shape.name);
                      }
                    }}
                    className="manager-shape-delete-btn"
                    title="删除该形状"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Right panel: Draw custom shapes */}
          <div className="shape-manager-right">
            <h4 className="panel-title">新增/编辑自定义形状 (6x6 网格)</h4>

            {/* Shape name inputs */}
            <div className="form-field">
              <label className="form-label">形状名称</label>
              <input
                type="text"
                placeholder="例如: Z, W_block, my_shape"
                value={shapeName}
                onChange={(e) => setShapeName(e.target.value)}
                className="form-input-text"
              />
            </div>

            {/* Layout: Drawing board + color choices */}
            <div className="designer-workspace">
              {/* 6x6 draw board */}
              <div className="drawing-grid-container">
                {drawingBoard.map((row, r) =>
                  row.map((val, c) => (
                    <div
                      key={`${r}-${c}`}
                      onClick={() => toggleDrawingCell(r, c)}
                      className={`grid-cell ${val ? 'grid-cell-active' : 'grid-cell-inactive'}`}
                      style={val ? { background: selectedColor, boxShadow: `0 0 6px ${selectedColor}60` } : {}}
                    />
                  ))
                )}
              </div>

              {/* Preset colors list */}
              <div className="palette-wrapper">
                <span className="form-label">选择颜色</span>
                <div className="preset-colors-grid">
                  {PRESET_COLORS.map((color) => (
                    <button
                      key={color}
                      onClick={() => setSelectedColor(color)}
                      className="color-swatch-btn"
                      style={{
                        backgroundColor: color,
                        border: selectedColor === color ? '2px solid white' : '1px solid rgba(0,0,0,0.4)',
                        boxShadow: selectedColor === color ? `0 0 6px ${color}` : 'none',
                      }}
                      title={color}
                    />
                  ))}
                </div>
              </div>
            </div>

            {/* Action buttons */}
            <div className="modal-footer">
              <button onClick={handleClearBoard} className="btn-secondary">
                <RefreshCw size={13} />
                <span>清空画板</span>
              </button>
              <button onClick={handleSaveShape} className="btn-primary">
                <Plus size={13} />
                <span>添加/更新形状</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
