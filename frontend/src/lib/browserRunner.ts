import type { CodeResult } from "./api";

const MAX_CODE = 20_000;
const MAX_OUTPUT = 20_000;
const TIMEOUT_MS = 2500;

/** Execute JavaScript in a disposable worker. Workers have no DOM/cookies; network/storage APIs are removed. */
export function buildBrowserWorkerSource(code: string): string {
  if (!code.trim() || code.length > MAX_CODE || code.includes("\0"))
    throw new Error(`JavaScript must be between 1 and ${MAX_CODE} characters.`);
  const prelude = `
const __lines = [];
const __format = (value) => { try { return typeof value === 'string' ? value : JSON.stringify(value); } catch { return String(value); } };
const console = Object.freeze({
  log: (...values) => __lines.push(values.map(__format).join(' ')),
  info: (...values) => __lines.push(values.map(__format).join(' ')),
  warn: (...values) => __lines.push('WARN: ' + values.map(__format).join(' ')),
  error: (...values) => __lines.push('ERROR: ' + values.map(__format).join(' ')),
});
for (const name of ['fetch','WebSocket','WebTransport','XMLHttpRequest','EventSource','importScripts','indexedDB','caches','Worker','SharedWorker','BroadcastChannel']) {
  try { Object.defineProperty(globalThis, name, { value: undefined, writable: false, configurable: false }); }
  catch { throw new Error('Browser sandbox could not disable ' + name); }
  if (globalThis[name] !== undefined) throw new Error('Browser sandbox isolation failed for ' + name);
}
`;
  return `${prelude}
(async () => {
${code}
})().then(
  (value) => globalThis.postMessage({ ok: true, stdout: __lines.join('\\n') + (value === undefined ? '' : '\\n' + __format(value)) }),
  (error) => globalThis.postMessage({ ok: false, stderr: String(error && error.stack || error) })
);`;
}

export function runBrowserJavaScript(code: string): Promise<CodeResult> {
  let source: string;
  try {
    source = buildBrowserWorkerSource(code);
  } catch (error) {
    return Promise.reject(error);
  }
  const url = URL.createObjectURL(
    new Blob([source], { type: "text/javascript" }),
  );
  return new Promise((resolve) => {
    const worker = new Worker(url, { name: "interview-code-sandbox" });
    let settled = false;
    const finish = (result: CodeResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      worker.terminate();
      URL.revokeObjectURL(url);
      resolve(result);
    };
    const timer = window.setTimeout(
      () =>
        finish({
          exit_code: null,
          stdout: "",
          stderr: "Execution stopped after 2.5 seconds.",
          timed_out: true,
        }),
      TIMEOUT_MS,
    );
    worker.onmessage = (
      event: MessageEvent<{ ok: boolean; stdout?: string; stderr?: string }>,
    ) =>
      finish({
        exit_code: event.data.ok ? 0 : 1,
        stdout: (event.data.stdout ?? "").slice(0, MAX_OUTPUT),
        stderr: (event.data.stderr ?? "").slice(0, MAX_OUTPUT),
        timed_out: false,
      });
    worker.onerror = (event) =>
      finish({
        exit_code: 1,
        stdout: "",
        stderr: event.message.slice(0, MAX_OUTPUT),
        timed_out: false,
      });
  });
}
