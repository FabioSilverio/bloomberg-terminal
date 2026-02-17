import '@testing-library/jest-dom/vitest';

class ResizeObserverMock {
  observe() {
    return undefined;
  }

  unobserve() {
    return undefined;
  }

  disconnect() {
    return undefined;
  }
}

Object.assign(globalThis, {
  ResizeObserver: ResizeObserverMock
});
