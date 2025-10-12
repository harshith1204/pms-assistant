export const API_HTTP_URL = import.meta.env.VITE_API_HTTP_URL || "http://localhost:8000";
export const API_WS_URL = import.meta.env.VITE_API_WS_URL || `${API_HTTP_URL.replace(/^http/, "ws")}/ws/chat`;

