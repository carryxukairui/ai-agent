import { API_BASE_URL } from "./http";

/** event 为后端发送的 SSE event 类型，如 "thinking" | "result"；未带 event 的流为 undefined */
export type SseHandlers = {
  onChunk: (chunk: string, event?: string) => void;
  onError?: (err: unknown) => void;
  onOpen?: () => void;
};

function buildUrl(path: string, params: Record<string, string | undefined>) {
  // 注意：new URL("/xxx", "http://host/api") 会把 "/api" 覆盖掉，导致丢失 context-path。
  // 这里用字符串拼接，确保最终是 `${API_BASE_URL}/...`
  const base = API_BASE_URL.replace(/\/+$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(`${base}${p}`);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== "") url.searchParams.set(k, v);
  });
  return url.toString();
}

/**
 * 使用 fetch + ReadableStream 直接按网络分块读取，
 * 避免依赖 EventSource 对单条 SSE 事件的缓冲策略，
 * 以便尽可能“来一块就渲染一块”。
 */
export function openSse(
  path: string,
  params: Record<string, string | undefined>,
  handlers: SseHandlers
) {
  const url = buildUrl(path, params);

  let aborted = false;
  const controller = new AbortController();

  (async () => {
    try {
      const resp = await fetch(url, {
        method: "GET",
        signal: controller.signal,
        headers: {
          Accept: "text/event-stream",
        },
      });

      if (!resp.ok || !resp.body) {
        handlers.onError?.(
          new Error(`SSE 请求失败：${resp.status} ${resp.statusText}`)
        );
        return;
      }

      handlers.onOpen?.();

      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      /** 当前事件的 event 类型 */
      let currentEvent: string | undefined;
      /** 同一事件内的多行 data 累积（SSE 规范：多行 data 拼接为一个 payload） */
      let dataLines: string[] = [];

      function flushEvent() {
        if (dataLines.length > 0) {
          const payload = dataLines.join("\n");
          if (payload) handlers.onChunk(payload, currentEvent);
          dataLines = [];
        }
        currentEvent = undefined;
      }

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (!value) continue;

        const chunkText = decoder.decode(value, { stream: true });
        if (!chunkText) continue;

        buffer += chunkText;
        let idx: number;
        while ((idx = buffer.indexOf("\n")) >= 0) {
          const raw = buffer.slice(0, idx).replace(/\r$/, "");
          buffer = buffer.slice(idx + 1);
          const line = raw.trim();
          if (!line) {
            flushEvent();
            continue;
          }
          if (line.startsWith("event:")) {
            flushEvent();
            currentEvent = line.slice(6).trim() || undefined;
            continue;
          }
          if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).replace(/^\s/, ""));
            continue;
          }
        }
      }

      if (buffer.trim().length > 0) {
        for (const raw of buffer.split(/\r?\n/)) {
          const line = raw.trim();
          if (!line) {
            flushEvent();
            continue;
          }
          if (line.startsWith("event:")) {
            flushEvent();
            currentEvent = line.slice(6).trim() || undefined;
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).replace(/^\s/, ""));
          }
        }
      }
      flushEvent();

      // 正常结束：前端目前没有 onDone 回调，这里用 onError 通知结束，
      // 以便 ChatRoom 里复用 onError 将 streaming/sending 置为 false。
      handlers.onError?.(new Error("SSE completed"));
    } catch (err) {
      if (aborted) return;
      handlers.onError?.(err);
    }
  })();

  return {
    close: () => {
      aborted = true;
      controller.abort();
    },
    url,
  };
}
