import React, { useRef, useEffect } from 'react';

interface BoardEditorProps {
  gridStatus: number[][]; // 9x9 matrix of 0 (inactive/blocked) or 1 (active/allowed)
  onChange: (newGridStatus: number[][]) => void;
}

export const BoardEditor: React.FC<BoardEditorProps> = ({ gridStatus, onChange }) => {
  const isDraggingRef = useRef<boolean>(false);
  const targetValueRef = useRef<number>(1);

  // Stop dragging on mouseup globally
  useEffect(() => {
    const handleGlobalMouseUp = () => {
      isDraggingRef.current = false;
    };
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => {
      window.removeEventListener('mouseup', handleGlobalMouseUp);
    };
  }, []);

  const updateCell = (row: number, col: number, value: number) => {
    const newGrid = gridStatus.map((r, rIdx) =>
      r.map((cVal, cIdx) => (rIdx === row && cIdx === col ? value : cVal))
    );
    onChange(newGrid);
  };

  const handleMouseDown = (row: number, col: number, e: React.MouseEvent) => {
    // Prevent default browser dragging behaviors
    e.preventDefault();
    isDraggingRef.current = true;
    const currentVal = gridStatus[row][col];
    // Toggle the clicked cell, and set the target for subsequent dragged cells
    const targetVal = currentVal === 1 ? 0 : 1;
    targetValueRef.current = targetVal;
    updateCell(row, col, targetVal);
  };

  const handleMouseEnter = (row: number, col: number) => {
    if (isDraggingRef.current) {
      updateCell(row, col, targetValueRef.current);
    }
  };

  const handleUnlockAll = () => {
    const newGrid = Array.from({ length: 9 }, () => new Array(9).fill(1));
    onChange(newGrid);
  };

  const handleResetContainer = () => {
    // Default layout: rectangle from row index 2-6 and column index 3-5 is active
    const newGrid = Array.from({ length: 9 }, (_, r) =>
      Array.from({ length: 9 }, (_, c) => (r >= 2 && r <= 6 && c >= 3 && c <= 5 ? 1 : 0))
    );
    onChange(newGrid);
  };

  const boardArea = gridStatus.reduce((acc, row) => acc + row.reduce((rAcc, val) => rAcc + val, 0), 0);

  return (
    <div className="glass-panel board-editor-container">
      <h3 className="panel-title">
        棋盘容器编辑 (9x9)
      </h3>
      
      {/* Grid container */}
      <div className="board-grid-wrapper">
        {gridStatus.map((row, rIdx) =>
          row.map((cellVal, cIdx) => (
            <div
              key={`${rIdx}-${cIdx}`}
              className={`grid-cell ${
                cellVal === 1 ? 'grid-cell-active' : 'grid-cell-inactive'
              }`}
              onMouseDown={(e) => handleMouseDown(rIdx, cIdx, e)}
              onMouseEnter={() => handleMouseEnter(rIdx, cIdx)}
            />
          ))
        )}
      </div>

      <div className="board-area-badge">
        <span>棋盘总面积:</span>
        <span className="area-number">{boardArea}</span>
      </div>

      <div className="button-row">
        <button
          onClick={handleUnlockAll}
          className="btn-secondary"
        >
          全开 (Max)
        </button>
        <button
          onClick={handleResetContainer}
          className="btn-secondary"
        >
          重置默认
        </button>
      </div>
    </div>
  );
};
