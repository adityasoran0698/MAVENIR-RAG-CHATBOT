import { useState, useRef, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import MessageBubble from "./components/MessageBubble";
import PdfMessageCard from "./components/PdfMessageCard";
import Composer from "./components/Composer";
import EmptyState from "./components/EmptyState";
import {
  streamChat,
  uploadPdf,
  getThreadStatus,
  getThreadHistory,
  createThread,
} from "./lib/api";
import {
  getStoredThreadId,
  storeThreadId,
  clearStoredThreadId,
} from "./lib/thread";
import "./App.css";

export default function App() {
  const [threadId, setThreadId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [chunkCount, setChunkCount] = useState(0);
  const [connError, setConnError] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loadingThread, setLoadingThread] = useState(true);
  const scrollRef = useRef(null);

  // On first load: resume an existing thread from localStorage, or mint a
  // new one. Then fetch that thread's status (indexed docs) and full
  // message history so the user picks up exactly where they left off.
  useEffect(() => {
    async function init() {
      try {
        let id = getStoredThreadId();
        if (!id) {
          const res = await createThread();
          id = res.thread_id;
          storeThreadId(id);
        }
        setThreadId(id);

        const [status, history] = await Promise.all([
          getThreadStatus(id),
          getThreadHistory(id),
        ]);

        setDocuments(status.documents || []);
        setChunkCount(status.num_chunks || 0);

        if (history.messages?.length) {
          setMessages(
            history.messages.map((m) => ({
              role: m.role,
              content: m.content,
              // History resume doesn't carry per-message grounding metadata
              // (that's only known at generation time) - render plainly.
            })),
          );
        }
      } catch (err) {
        setConnError(true);
      } finally {
        setLoadingThread(false);
      }
    }
    init();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, sending]);

  const handleSend = useCallback(
    async (text) => {
      console.log("HANDLE SEND CALLED:", text);
      if (!threadId || !text.trim() || sending) return;

      // Add user message immediately
      const userMsg = {
        role: "user",
        content: text,
      };

      // Create empty assistant message.
      // Tokens will be added to this message as they arrive.
      const assistantMsg = {
        role: "assistant",
        content: "",
        streaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);

      setSending(true);
      setConnError(false);

      try {
        await streamChat(
          text,
          threadId,

          // ==========================================
          // TOKEN RECEIVED
          // ==========================================
          (token) => {
            setMessages((prev) => {
              const updated = [...prev];
              const lastIndex = updated.length - 1;

              if (updated[lastIndex]?.role === "assistant") {
                updated[lastIndex] = {
                  ...updated[lastIndex],
                  content: updated[lastIndex].content + token,
                };
              }

              return updated;
            });
          },

          // ==========================================
          // STREAM EVENTS
          // ==========================================
          (event) => {
            // ----------------------------------------
            // Metadata received after generation
            // ----------------------------------------
            if (event.type === "meta") {
              setMessages((prev) => {
                const updated = [...prev];
                const lastIndex = updated.length - 1;

                if (updated[lastIndex]?.role === "assistant") {
                  updated[lastIndex] = {
                    ...updated[lastIndex],

                    mode: event.mode,

                    grounded: event.grounded,

                    sources: event.sources || [],

                    flaggedClaims: event.flagged_claims || [],
                  };
                }

                return updated;
              });
            }

            // ----------------------------------------
            // Streaming completed
            // ----------------------------------------
            if (event.type === "done") {
              setMessages((prev) => {
                const updated = [...prev];
                const lastIndex = updated.length - 1;

                if (updated[lastIndex]?.role === "assistant") {
                  updated[lastIndex] = {
                    ...updated[lastIndex],
                    streaming: false,
                  };
                }

                return updated;
              });

              setSending(false);
            }
          },
        );
      } catch (err) {
        console.error("Streaming error:", err);

        setConnError(true);

        setMessages((prev) => {
          const updated = [...prev];
          const lastIndex = updated.length - 1;

          if (updated[lastIndex]?.role === "assistant") {
            updated[lastIndex] = {
              role: "assistant",
              content: `Couldn't reach the backend. ${err.message}`,
              error: true,
              streaming: false,
            };
          }

          return updated;
        });

        setSending(false);
      }
    },
    [threadId, sending],
  );

  const handleUpload = useCallback(
    async (file, onProgress) => {
      if (!threadId) return;
      const result = await uploadPdf(threadId, file, onProgress);
      setDocuments(result.documents);
      setChunkCount(result.num_chunks);
      // Show the uploaded PDF as a message inside the chat thread itself.
      setMessages((prev) => [
        ...prev,
        {
          role: "pdf",
          filename: result.filename,
          numChunks: result.num_chunks,
        },
      ]);
    },
    [threadId],
  );

  const handleNewChat = async () => {
    setSidebarOpen(false);
    try {
      const res = await createThread();
      storeThreadId(res.thread_id);
      setThreadId(res.thread_id);
      setMessages([]);
      setDocuments([]);
      setChunkCount(0);
    } catch {
      setConnError(true);
    }
  };

  const hasIndex = documents.length > 0;

  return (
    <div className="app">
      {sidebarOpen && (
        <div className="sidebar-scrim" onClick={() => setSidebarOpen(false)} />
      )}
      <div className={`sidebar-wrap ${sidebarOpen ? "sidebar-wrap-open" : ""}`}>
        <Sidebar
          documents={documents}
          chunkCount={chunkCount}
          onUpload={handleUpload}
          onNewChat={handleNewChat}
        />
      </div>

      <main className="chat-panel">
        <div className="mobile-topbar">
          <button
            className="mobile-menu-btn"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open sidebar"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M4 7h16M4 12h16M4 17h16"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </button>
          <span className="mobile-topbar-title">3GPP assistant</span>
        </div>

        {connError && (
          <div className="conn-banner">
            Can't reach the backend — make sure it's running.
          </div>
        )}

        <div className="chat-scroll" ref={scrollRef}>
          {loadingThread ? (
            <div className="thread-loading">Loading conversation…</div>
          ) : messages.length === 0 ? (
            <EmptyState indexed={hasIndex} onSuggestion={handleSend} />
          ) : (
            <div className="chat-messages">
              {messages.map((m, i) =>
                m.role === "pdf" ? (
                  <PdfMessageCard
                    key={i}
                    filename={m.filename}
                    numChunks={m.numChunks}
                  />
                ) : (
                  <MessageBubble key={i} message={m} />
                ),
              )}
            </div>
          )}
        </div>

        <Composer
          onSend={handleSend}
          disabled={sending || loadingThread}
          indexed={hasIndex}
        />
      </main>
    </div>
  );
}
