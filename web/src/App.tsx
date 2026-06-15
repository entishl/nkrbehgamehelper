import { useState, useEffect, useRef } from 'react';
import { defaultShapes } from './data/defaultShapes';
import type { Shape, SolverInput, SolverResult, Point } from './types';
import { BoardEditor } from './components/BoardEditor';
import { ShapeSelector } from './components/ShapeSelector';
import { Visualizer } from './components/Visualizer';
import { ShapeManager } from './components/ShapeManager';
import { Play, Square, RefreshCw, FileText, Heart, X } from 'lucide-react';

export default function App() {
  // --- States ---
  const [shapesData, setShapesData] = useState<Shape[]>(() => {
    const saved = localStorage.getItem('shapesData');
    return saved ? JSON.parse(saved) : defaultShapes;
  });

  const [counts, setCounts] = useState<Record<string, number>>(() => {
    const saved = localStorage.getItem('shapeCounts');
    return saved ? JSON.parse(saved) : {};
  });

  const [locks, setLocks] = useState<Record<string, boolean>>(() => {
    const saved = localStorage.getItem('shapeLocks');
    return saved ? JSON.parse(saved) : {};
  });

  const [gridStatus, setGridStatus] = useState<number[][]>(() => {
    const saved = localStorage.getItem('gridStatus');
    // Default layout: row 2-6 and col 3-5 is active
    return saved
      ? JSON.parse(saved)
      : Array.from({ length: 9 }, (_, r) =>
          Array.from({ length: 9 }, (_, c) => (r >= 2 && r <= 6 && c >= 3 && c <= 5 ? 1 : 0))
        );
  });

  const [timeLimitSec, setTimeLimitSec] = useState<number | "">( () => {
    const saved = localStorage.getItem('timeLimitSec');
    if (saved) {
      const parsed = parseInt(saved, 10);
      return isNaN(parsed) ? 10 : parsed;
    }
    return 10;
  });

  const [allowRotation, setAllowRotation] = useState<boolean>(() => {
    const saved = localStorage.getItem('allowRotation');
    return saved ? saved === 'true' : true;
  });

  const [isCalculating, setIsCalculating] = useState<boolean>(false);
  const [bestAreaSoFar, setBestAreaSoFar] = useState<number>(0);
  const [solverResult, setSolverResult] = useState<SolverResult | null>(null);

  // Modals
  const [isBatchOpen, setIsBatchOpen] = useState<boolean>(false);
  const [isManagerOpen, setIsManagerOpen] = useState<boolean>(false);
  const [batchText, setBatchText] = useState<string>('');

  const workerRef = useRef<Worker | null>(null);

  // --- Sync to LocalStorage ---
  useEffect(() => {
    localStorage.setItem('shapesData', JSON.stringify(shapesData));
  }, [shapesData]);

  useEffect(() => {
    localStorage.setItem('shapeCounts', JSON.stringify(counts));
  }, [counts]);

  useEffect(() => {
    localStorage.setItem('shapeLocks', JSON.stringify(locks));
  }, [locks]);

  useEffect(() => {
    localStorage.setItem('gridStatus', JSON.stringify(gridStatus));
  }, [gridStatus]);

  useEffect(() => {
    if (typeof timeLimitSec === 'number') {
      localStorage.setItem('timeLimitSec', String(timeLimitSec));
    }
  }, [timeLimitSec]);

  useEffect(() => {
    localStorage.setItem('allowRotation', String(allowRotation));
  }, [allowRotation]);

  // Clean up worker on unmount
  useEffect(() => {
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
      }
    };
  }, []);

  // --- Handlers ---
  const handleCountChange = (name: string, count: number) => {
    setCounts((prev) => ({ ...prev, [name]: count }));
  };

  const handleLockToggle = (name: string) => {
    setLocks((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  const handleClearCounts = () => {
    setCounts({});
  };

  const handleResetAll = () => {
    if (confirm('确定要重置所有配置和网格吗？')) {
      setCounts({});
      setLocks({});
      // Reset grid to default (row 2-6, col 3-5 is active)
      setGridStatus(
        Array.from({ length: 9 }, (_, r) =>
          Array.from({ length: 9 }, (_, c) => (r >= 2 && r <= 6 && c >= 3 && c <= 5 ? 1 : 0))
        )
      );
      setShapesData(defaultShapes);
      setTimeLimitSec(10);
      setAllowRotation(true);
      setSolverResult(null);
      setBestAreaSoFar(0);
    }
  };

  // Run Solver in Web Worker
  const handleCalculate = () => {
    // 1. Gather shapes to pack
    const shapesToPackExpanded: Shape[] = [];
    Object.entries(counts).forEach(([name, count]) => {
      const shape = shapesData.find((s) => s.name === name);
      if (shape && count > 0) {
        for (let i = 0; i < count; i++) {
          shapesToPackExpanded.push(shape);
        }
      }
    });

    if (shapesToPackExpanded.length === 0) {
      alert('请先选择要放置的形状和数量！');
      return;
    }

    // 2. Gather allowed cells
    const allowedCells: Point[] = [];
    gridStatus.forEach((row, r) => {
      row.forEach((val, c) => {
        if (val === 1) {
          allowedCells.push([c, r]);
        }
      });
    });

    if (allowedCells.length === 0) {
      alert('棋盘容器没有可用单元格，请在左上角网格中划选可用区域！');
      return;
    }

    // 3. Must-place shapes
    const mustPlaceNames = Object.entries(locks)
      .filter(([_, locked]) => locked)
      .map(([name]) => name);

    // Check if any must-place shapes are not in the selected counts
    const missingMustPlace = mustPlaceNames.filter(name => !counts[name] || counts[name] === 0);
    if (missingMustPlace.length > 0) {
      alert(`锁定的形状 "${missingMustPlace.join(', ')}" 数量为0。请先增加它们的数量，或者取消锁定！`);
      return;
    }

    // Check if total must place area exceeds board area
    const totalMustPlaceArea = mustPlaceNames.reduce((acc, name) => {
      const shape = shapesData.find(s => s.name === name);
      const count = counts[name] || 0;
      return acc + (shape ? shape.area * count : 0);
    }, 0);

    if (totalMustPlaceArea > allowedCells.length) {
      alert(`所有锁定的形状总面积 (${totalMustPlaceArea}) 超过了可用棋盘面积 (${allowedCells.length})，必定无解！`);
      return;
    }

    // 4. Trigger calculations
    setIsCalculating(true);
    setBestAreaSoFar(0);
    setSolverResult(null);

    const solverInput: SolverInput = {
      shapesToPack: shapesToPackExpanded,
      allowedCells,
      boardSize: [9, 9],
      mustPlaceNames,
      timeLimitSec: typeof timeLimitSec === 'number' ? Math.max(5, Math.min(300, timeLimitSec)) : 10,
      allowRotation,
    };

    // Instantiate Worker (using Vite URL constructor)
    const worker = new Worker(new URL('./solver/solver.worker.ts', import.meta.url), {
      type: 'module',
    });
    workerRef.current = worker;

    worker.postMessage(solverInput);

    worker.onmessage = (e) => {
      const { type, bestArea, result, error } = e.data;
      if (type === 'progress') {
        setBestAreaSoFar(bestArea);
      } else if (type === 'result') {
        setSolverResult(result);
        setIsCalculating(false);
        worker.terminate();
        workerRef.current = null;
      } else if (type === 'error') {
        alert('计算过程出错:\n' + error);
        setIsCalculating(false);
        worker.terminate();
        workerRef.current = null;
      }
    };
  };

  const handleCancelCalculate = () => {
    if (workerRef.current) {
      workerRef.current.terminate();
      workerRef.current = null;
      setIsCalculating(false);
      // Construct a partial result indicating search was canceled
      setSolverResult({
        placedShapes: solverResult?.placedShapes || [],
        unplacedShapes: solverResult?.unplacedShapes || [],
        status: 'UNKNOWN',
      });
    }
  };

  // Clear unplaced shapes (reducing inputs counts)
  const handleClearUnplaced = () => {
    if (!solverResult || solverResult.unplacedShapes.length === 0) return;

    // Count how many of each shape were unplaced
    const unplacedCounts: Record<string, number> = {};
    solverResult.unplacedShapes.forEach((name) => {
      unplacedCounts[name] = (unplacedCounts[name] || 0) + 1;
    });

    // Reduce inputs counts
    setCounts((prev) => {
      const newCounts = { ...prev };
      Object.entries(unplacedCounts).forEach(([name, count]) => {
        if (newCounts[name]) {
          newCounts[name] = Math.max(0, newCounts[name] - count);
        }
      });
      return newCounts;
    });

    // Clear unplaced list in results
    setSolverResult((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        unplacedShapes: [],
      };
    });
  };

  // Apply Batch JSON Import
  const handleApplyBatchText = () => {
    if (!batchText.trim()) {
      setIsBatchOpen(false);
      return;
    }

    try {
      const parsed = JSON.parse(batchText);
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        throw new Error('JSON 数据必须是一个对象 (e.g. {"SG": 2, "square": 1})');
      }

      // Reset all counts
      const newCounts: Record<string, number> = {};
      const ignoredKeys: string[] = [];

      Object.entries(parsed).forEach(([key, val]) => {
        const shapeExists = shapesData.some((s) => s.name === key);
        if (shapeExists) {
          const count = parseInt(String(val), 10);
          if (!isNaN(count) && count >= 0) {
            newCounts[key] = count;
          }
        } else {
          ignoredKeys.push(key);
        }
      });

      setCounts(newCounts);
      setIsBatchOpen(false);
      setBatchText('');

      if (ignoredKeys.length > 0) {
        alert(`批量设置成功！\n\n以下形状未在系统中找到，已被忽略：\n${ignoredKeys.join(', ')}`);
      } else {
        alert('批量导入成功！请核对设置的数量。');
      }
    } catch (err: any) {
      alert('解析 JSON 失败，请检查格式是否正确！\n错误原因: ' + err.message);
    }
  };

  // Shape Manager Actions
  const handleAddCustomShape = (newShape: Shape) => {
    setShapesData((prev) => {
      // Check if shape with same name exists, if so overwrite, else add
      const idx = prev.findIndex((s) => s.name === newShape.name);
      if (idx >= 0) {
        const updated = [...prev];
        updated[idx] = newShape;
        return updated;
      }
      return [...prev, newShape];
    });
  };

  const handleDeleteShape = (name: string) => {
    setShapesData((prev) => prev.filter((s) => s.name !== name));
    // Clear counts and locks for deleted shape
    setCounts((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
    setLocks((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  // Render list of unplaced shapes with details
  const fullUnplacedShapes = solverResult
    ? solverResult.unplacedShapes
        .map((name) => shapesData.find((s) => s.name === name))
        .filter((s): s is Shape => !!s)
    : [];

  const boardArea = gridStatus.reduce((acc, row) => acc + row.reduce((rAcc, val) => rAcc + val, 0), 0);

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="app-title-group">
          <h1 className="app-title">
            二维不规则形状装箱求解器
          </h1>
          <p className="app-subtitle">
            纯前端多线程回溯算法版 · 完美适配 9x9 棋盘拼图
          </p>
        </div>

        <button
          onClick={handleResetAll}
          className="btn-secondary"
          title="将网格、形状、数量全部恢复到默认状态"
        >
          <RefreshCw size={13} />
          <span>恢复默认配置</span>
        </button>
      </header>

      {/* Main Grid Panels */}
      <main className="layout-grid">
        {/* Left Column: Container and Controls */}
        <div className="layout-column">
          {/* Grid editor */}
          <BoardEditor gridStatus={gridStatus} onChange={setGridStatus} />

          {/* Settings panel */}
          <div className="glass-panel">
            <h3 className="panel-title">
              优化算法配置
            </h3>

            {/* Time limit */}
            <div className="config-group">
              <div className="config-item">
                <label className="config-label">
                  计算时间限制 (秒):
                </label>
                <input
                  type="number"
                  min="5"
                  max="300"
                  value={timeLimitSec}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === '') {
                      setTimeLimitSec('');
                    } else {
                      const num = parseInt(val, 10);
                      setTimeLimitSec(isNaN(num) ? '' : num);
                    }
                  }}
                  onBlur={() => {
                    if (timeLimitSec === '' || timeLimitSec < 5) {
                      setTimeLimitSec(5);
                    } else if (timeLimitSec > 300) {
                      setTimeLimitSec(300);
                    }
                  }}
                  className="config-input-number"
                />
              </div>

              {/* Allow rotation */}
              <div className="config-item">
                <label className="config-label">
                  允许形状旋转 (90°倍数):
                </label>
                <input
                  type="checkbox"
                  checked={allowRotation}
                  onChange={(e) => setAllowRotation(e.target.checked)}
                  className="config-checkbox"
                />
              </div>
            </div>

            {/* Action buttons */}
            <div className="calculate-btn-wrapper">
              {isCalculating ? (
                <button
                  onClick={handleCancelCalculate}
                  className="btn-danger pulse-glow"
                  style={{ width: '100%', padding: '12px' }}
                >
                  <Square size={16} fill="white" />
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <span style={{ fontSize: '13px', fontWeight: 'bold' }}>正在计算... 点击停止</span>
                    {bestAreaSoFar > 0 && (
                      <span style={{ fontSize: '10px', opacity: 0.8 }}>
                        当前最佳覆盖面积: {bestAreaSoFar} / {boardArea}
                      </span>
                    )}
                  </div>
                </button>
              ) : (
                <button
                  onClick={handleCalculate}
                  className="btn-metal"
                  style={{ width: '100%', padding: '12px' }}
                >
                  <Play size={16} fill="white" />
                  <span style={{ fontSize: '14px', fontWeight: 'bold' }}>开始布局计算</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Middle Column: Shape Selector */}
        <div className="layout-column">
          <ShapeSelector
            shapesData={shapesData}
            counts={counts}
            locks={locks}
            onCountChange={handleCountChange}
            onLockToggle={handleLockToggle}
            onClear={handleClearCounts}
            onOpenBatch={() => setIsBatchOpen(true)}
            onOpenManager={() => setIsManagerOpen(true)}
          />
        </div>

        {/* Right Column: Visualizer Output */}
        <div className="layout-column">
          <Visualizer
            placedShapes={solverResult?.placedShapes || []}
            unplacedShapes={fullUnplacedShapes}
            allowedCells={gridStatus.reduce<Point[]>((acc, row, r) => {
              row.forEach((val, c) => {
                if (val === 1) acc.push([c, r]);
              });
              return acc;
            }, [])}
            status={solverResult ? solverResult.status : null}
            onClearUnplaced={handleClearUnplaced}
          />
        </div>
      </main>

      {/* Footer / Copyright */}
      <footer className="app-footer">
        <span>Made with</span>
        <Heart size={10} className="text-rose-500 fill-rose-500" />
        <span>for packing enthusiasts</span>
      </footer>

      {/* --- Batch Dialog Modal --- */}
      {isBatchOpen && (
        <div className="modal-overlay">
          <div className="modal-container">
            <div className="modal-header">
              <h3 className="modal-title">
                <FileText size={18} className="text-[var(--accent-purple)]" />
                <span>一键导入形状数量</span>
              </h3>
              <button
                onClick={() => {
                  setIsBatchOpen(false);
                  setBatchText('');
                }}
                className="modal-close-btn"
              >
                <X size={18} />
              </button>
            </div>
            
            <div className="modal-body">
              <p className="modal-desc">
                请在此处粘贴 JSON 文本 (例如：<code style={{ background: 'rgba(0,0,0,0.3)', padding: '2px 4px', borderRadius: '4px', color: 'var(--accent-pink)' }}>{"{ \"SG\": 2, \"square\": 1 }"}</code>)。现有形状数量将被覆盖，找不到的形状名称将被忽略。
              </p>
              
              <textarea
                rows={6}
                value={batchText}
                onChange={(e) => setBatchText(e.target.value)}
                placeholder='{ "SG": 2, "square": 1 }'
                className="modal-textarea"
              />

              <div className="modal-footer">
                <button
                  onClick={() => {
                    setIsBatchOpen(false);
                    setBatchText('');
                  }}
                  className="btn-secondary"
                >
                  取消
                </button>
                <button
                  onClick={handleApplyBatchText}
                  className="btn-primary"
                >
                  应用导入
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* --- Shape Manager Modal --- */}
      {isManagerOpen && (
        <ShapeManager
          shapesData={shapesData}
          onAddShape={handleAddCustomShape}
          onDeleteShape={handleDeleteShape}
          onClose={() => setIsManagerOpen(false)}
        />
      )}
    </div>
  );
}
