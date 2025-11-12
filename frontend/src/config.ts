export const API_HTTP_URL = import.meta.env.VITE_API_HTTP_URL || "http://localhost:8000";
export const API_WS_URL = import.meta.env.VITE_API_WS_URL || `${API_HTTP_URL.replace(/^http/, "ws")}/ws/chat`;

// Stage Project API Configuration
export const STAGE_API_BASE_URL = import.meta.env.VITE_STAGE_API_BASE_URL || "https://stage-project.simpo.ai";

// Get staff and business details dynamically from postMessage/localStorage (set by parent wrapper)
// Note: Hardcoded fallbacks are intentionally commented out to avoid accidental misuse
const DEFAULT_MEMBER_ID = '1effc4a4-3c0f-67a5-99d0-374369aad116';
const DEFAULT_BUSINESS_ID = '1eedcb26-d23a-688a-bd63-579d19dab229';

export const getMemberId = () => {
  const stored = localStorage.getItem('staffId');
  if (!stored) return DEFAULT_MEMBER_ID;
  // Support values sent as JSON strings (e.g., '"uuid"')
  try {
    const parsed = JSON.parse(stored);
    if (typeof parsed === 'string') return parsed.trim();
  } catch {}
  return stored.trim();
};

export const getBusinessId = () => {
  const raw = localStorage.getItem('bDetails');
  if (!raw) return DEFAULT_BUSINESS_ID;

  try {
    const parsed = JSON.parse(raw);
    // bDetails is a business object with an 'id' field
    if (parsed && typeof parsed === 'object' && parsed.id) {
      return String(parsed.id).trim();
    }
    // Fallback: some wrappers may send businessId as a simple string
    if (typeof parsed === 'string' && parsed.trim()) {
      return parsed.trim();
    }
  } catch {
    // Not JSON, treat as direct string
    return raw.trim();
  }

  return '';
};

export const getStaffType = () => {
  return localStorage.getItem('staffType') || import.meta.env.VITE_STAFF_TYPE || '';
};

export const getStaffName = () => {
  return localStorage.getItem('staffName') || import.meta.env.VITE_STAFF_NAME || '';
};

export const getBusinessDetails = () => {
  const fromStorage = localStorage.getItem('bDetails');
  if (fromStorage) {
    try {
      return JSON.parse(fromStorage);
    } catch {
      return { id: fromStorage };
    }
  }
  return null;
};

