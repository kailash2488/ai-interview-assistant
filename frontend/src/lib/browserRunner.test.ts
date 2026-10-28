import { buildBrowserWorkerSource } from "./browserRunner";

it("builds a worker that disables network, storage and nested execution APIs", () => {
  const source = buildBrowserWorkerSource('console.log("safe")');
  for (const blocked of [
    "fetch",
    "WebSocket",
    "WebTransport",
    "XMLHttpRequest",
    "indexedDB",
    "caches",
    "Worker",
    "BroadcastChannel",
  ]) {
    expect(source).toContain(`'${blocked}'`);
  }
  expect(source).toContain("configurable: false");
  expect(source).toContain('console.log("safe")');
});

it("rejects empty, oversized and null-byte programs", () => {
  expect(() => buildBrowserWorkerSource("")).toThrow(/between 1 and 20000/);
  expect(() => buildBrowserWorkerSource("x".repeat(20_001))).toThrow(
    /between 1 and 20000/,
  );
  expect(() => buildBrowserWorkerSource("ok\0bad")).toThrow(
    /between 1 and 20000/,
  );
});
