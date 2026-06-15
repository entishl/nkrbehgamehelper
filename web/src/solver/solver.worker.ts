import { solvePacking } from './solverLogic';
import type { SolverInput } from '../types';

self.onmessage = (e: MessageEvent<SolverInput>) => {
  const input = e.data;

  try {
    const result = solvePacking(input, (bestArea) => {
      // Send progress updates back to the UI thread
      self.postMessage({ type: 'progress', bestArea });
    });

    self.postMessage({ type: 'result', result });
  } catch (error: any) {
    self.postMessage({
      type: 'error',
      error: error?.message || 'An error occurred during calculations.',
    });
  }
};
export {};
