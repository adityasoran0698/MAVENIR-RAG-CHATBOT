const STORAGE_KEY = 'gpp_thread_id'

export function getStoredThreadId() {
  return localStorage.getItem(STORAGE_KEY)
}

export function storeThreadId(threadId) {
  localStorage.setItem(STORAGE_KEY, threadId)
}

export function clearStoredThreadId() {
  localStorage.removeItem(STORAGE_KEY)
}
