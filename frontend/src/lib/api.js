const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function sendChat(query, threadId) {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, thread_id: threadId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function streamChat(text, threadId, onToken, onEvent) {
  const response = await fetch(`${BASE_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      query: text,
      thread_id: threadId,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();

    throw new Error(errorText || `Request failed with ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Streaming is not supported by this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();

    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");

    buffer = events.pop() || "";

    for (const event of events) {
      const line = event.split("\n").find((line) => line.startsWith("data:"));

      if (!line) continue;

      const raw = line.replace(/^data:\s*/, "");

      if (!raw) continue;

      let payload;

      try {
        payload = JSON.parse(raw);
      } catch {
        continue;
      }

      // Token received
      if (payload.type === "token") {
        if (typeof payload.content === "string") {
          onToken(payload.content);
        }
      }

      // Backend error
      if (payload.type === "error") {
        throw new Error(
          payload.detail || payload.message || "Streaming request failed",
        );
      }

      // Metadata / done
      if (payload.type === "meta" || payload.type === "done") {
        onEvent?.(payload);
      }
    }
  }
}
export async function uploadPdf(threadId, file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(
      "POST",
      `${BASE_URL}/upload?thread_id=${encodeURIComponent(threadId)}`,
    );

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        let detail = `Upload failed (${xhr.status})`;
        try {
          detail = JSON.parse(xhr.responseText).detail || detail;
        } catch {}
        reject(new Error(detail));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(formData);
  });
}

export async function getThreadStatus(threadId) {
  const res = await fetch(`${BASE_URL}/thread/${threadId}/status`);
  if (!res.ok) throw new Error("Failed to fetch thread status");
  return res.json();
}

export async function getThreadHistory(threadId) {
  const res = await fetch(`${BASE_URL}/thread/${threadId}/history`);
  if (!res.ok) throw new Error("Failed to fetch thread history");
  return res.json();
}

export async function createThread() {
  const res = await fetch(`${BASE_URL}/thread/new`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to create thread");
  return res.json();
}

export async function checkHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}
