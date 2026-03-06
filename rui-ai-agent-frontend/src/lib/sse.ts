import { API_BASE_URL } from "./http";

export type SseHandlers = {
  onChunk: (chunk: string) => void;
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

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (!value) continue;

        const chunkText = decoder.decode(value, { stream: true });
        if (!chunkText) continue;

        // 累积文本并按行解析 SSE 格式（只取 data: 前缀的行）
        buffer += chunkText;
        let idx: number;
        while ((idx = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, idx).replace(/\r$/, "");
          buffer = buffer.slice(idx + 1);
          if (!line) continue;
          if (line.startsWith("data:")) {
            const payload = line.slice(5); // 去掉 "data:"
            if (payload) {
              handlers.onChunk(payload);
            }
          }
        }
      }

      // 结束时把可能剩余的一小段 data 行也处理掉
      if (buffer.trim().length > 0) {
        const line = buffer.replace(/\r/g, "");
        if (line.startsWith("data:")) {
          const payload = line.slice(5);
          if (payload) handlers.onChunk(payload);
        }
      }

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
