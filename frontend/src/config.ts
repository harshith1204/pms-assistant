export const API_HTTP_URL = import.meta.env.VITE_API_HTTP_URL || "http://localhost:8000";
export const API_WS_URL = import.meta.env.VITE_API_WS_URL || `${API_HTTP_URL.replace(/^http/, "ws")}/ws/chat`;

// Stage Project API Configuration
export const STAGE_API_BASE_URL = import.meta.env.VITE_STAGE_API_BASE_URL || "https://stage-project.simpo.ai";

// Hardcoded IDs - will be replaced with dynamic loading from parent website later
export const getMemberId = () => {
  return import.meta.env.VITE_MEMBER_UUID || '1f01b572-b7a0-6e64-b890-2d102d936e6e';
};

export const getBusinessId = () => {
  return import.meta.env.VITE_BUSINESS_UUID || '1f067040-82d8-6384-a1fc-996e5f7d7335';
};

