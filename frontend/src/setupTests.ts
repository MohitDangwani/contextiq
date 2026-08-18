import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom doesn't implement ResizeObserver, which @xyflow/react (Phase 12's
// lineage graph) uses to measure nodes/handles before it will draw edges
// or fit the view. This polyfill fires synchronously on observe() so that
// layout-dependent rendering resolves within a single test tick instead of
// silently never firing (as it also does in a backgrounded/non-composited
// browser tab -- the real-world case this polyfill stands in for here).
class ResizeObserverMock {
  private callback: ResizeObserverCallback;
  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }
  observe(target: Element) {
    this.callback([{ target, contentRect: target.getBoundingClientRect() } as ResizeObserverEntry], this as unknown as ResizeObserver);
  }
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("ResizeObserver", ResizeObserverMock);

// jsdom's getBoundingClientRect always returns all-zero rects; React Flow
// treats a zero-size node as "not yet measured" and never draws its edges.
Object.defineProperty(HTMLElement.prototype, "getBoundingClientRect", {
  configurable: true,
  value: () => ({ x: 0, y: 0, width: 180, height: 60, top: 0, left: 0, right: 180, bottom: 60, toJSON: () => {} }),
});

// jsdom doesn't implement DOMMatrixReadOnly at all. @xyflow/system's
// updateNodeInternals() -- the function that computes handle bounds edges
// are drawn from -- calls `new window.DOMMatrixReadOnly(style.transform)`
// and reads `.m22` (the zoom/scale component) unconditionally. Without
// this, the call throws inside a ResizeObserver callback, which React
// swallows silently (no console output) -- edges just never appear, with
// no visible error to explain why. Minimal polyfill: parse the `m22`
// value out of a CSS `matrix(...)` string, default to 1 (no scale).
class DOMMatrixReadOnlyPolyfill {
  m22: number;
  constructor(transform?: string) {
    const match = transform?.match(/matrix\(([^)]+)\)/);
    const values = match?.[1].split(",").map((v) => parseFloat(v.trim()));
    this.m22 = values?.[3] ?? 1;
  }
}
vi.stubGlobal("DOMMatrixReadOnly", DOMMatrixReadOnlyPolyfill);
