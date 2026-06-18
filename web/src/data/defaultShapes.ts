import type { Shape } from '../types';

export const defaultShapes: Shape[] = [
  {
    name: 'SG',
    area: 4,
    points: [[0, 0], [1, 0], [2, 0], [0, 1]],
    color: '#FF5E7E',
  },
  {
    name: 'square',
    area: 4,
    points: [[0, 0], [1, 0], [0, 1], [1, 1]],
    color: '#2F86F6',
  },
  {
    name: 'fire',
    area: 5,
    points: [[1, 0], [1, 1], [0, 2], [1, 2], [1, 3]],
    color: '#FF6B4A',
  },
  {
    name: 'laser',
    area: 5,
    points: [[3, 0], [0, 1], [1, 1], [2, 1], [3, 1]],
    color: '#E040FB',
  },
  {
    name: 'ar',
    area: 5,
    points: [[0, 0], [1, 0], [2, 0], [3, 0], [1, 1]],
    color: '#FFB300',
  },
  {
    name: 'utils',
    area: 3,
    points: [[0, 0], [1, 0], [0, 1]],
    color: '#00BCD4',
  },
  {
    name: 'i3',
    area: 3,
    points: [[0, 0], [0, 1], [0, 2]],
    color: '#8E24AA',
  },
  {
    name: 'i2',
    area: 2,
    points: [[0, 0], [0, 1]],
    color: '#AED581',
  },
  {
    name: 'i31',
    area: 3,
    points: [[0, 0], [1, 0], [2, 0]],
    color: '#26A69A',
  },
  {
    name: 'sr',
    area: 5,
    points: [[0, 0], [0, 1], [0, 2], [0, 3], [1, 3]],
    color: '#3F51B5',
  },
  {
    name: 'dot',
    area: 1,
    points: [[0, 0]],
    color: '#78909C',
  },
  {
    name: 'RL',
    area: 4,
    points: [[1, 0], [2, 0], [0, 1], [1, 1]],
    color: '#FFA726',
  },
  {
    name: 'T',
    area: 5,
    points: [[0, 0], [1, 0], [2, 0], [1, 1], [1, 2]],
    color: '#651FFF',
  },
  {
    name: '6',
    area: 6,
    points: [[0, 0], [1, 0], [2, 0], [0, 1], [1, 1], [2, 1]],
    color: '#FF2A6D',
  },
  {
    name: '5',
    area: 5,
    points: [[1, 0], [0, 1], [1, 1], [2, 1], [1, 2]],
    color: '#00E676',
  },
  {
    name: '4',
    area: 4,
    points: [[0, 0], [1, 0], [2, 0], [1, 1]],
    color: '#05DFD7',
  },
  {
    name: 'guangdan',
    area: 4,
    points: [[0, 0], [1, 0], [1, 1], [2, 1]],
    color: '#3357FF',
  }
];
export {};
