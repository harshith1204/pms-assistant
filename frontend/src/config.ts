// HTTP APIs use stage environment URLs
export const API_HTTP_URL = import.meta.env.VITE_API_HTTP_URL || "https://stage-project.simpo.ai";

// WebSocket uses localhost for development
export const API_WS_URL = import.meta.env.VITE_API_WS_URL || "ws://localhost:7000/ws/chat";

// AI Template Service URL for generating content
export const AI_TEMPLATE_SERVICE_URL = "https://stage-aiplanboard.simpo.ai";

// Business API URL for general operations
export const BUSINESS_API_URL = "https://stage-api.simpo.ai";

