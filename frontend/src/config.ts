export const API_HTTP_URL = import.meta.env.VITE_API_HTTP_URL || "http://localhost:8000";
export const API_WS_URL = import.meta.env.VITE_API_WS_URL || `${API_HTTP_URL.replace(/^http/, "ws")}/ws/chat`;

// Stage Project API Configuration
export const STAGE_API_BASE_URL = import.meta.env.VITE_STAGE_API_BASE_URL || "https://stage-project.simpo.ai";

// Get staff and business details dynamically from postMessage/localStorage (set by parent wrapper)
// Note: Hardcoded fallbacks are intentionally commented out to avoid accidental misuse
// const DEFAULT_MEMBER_ID = '...';
// const DEFAULT_BUSINESS_ID = '...';

export const getMemberId = () => {
  const stored = localStorage.getItem('staffId');
  if (!stored) return '';
  // Support values sent as JSON strings (e.g., '"uuid"')
  try {
    const parsed = JSON.parse(stored);
    if (typeof parsed === 'string') return parsed.trim();
  } catch {}
  return stored.trim();
};

export const getBusinessId = () => {
  // Prefer a directly stored businessId if provided
  const direct = localStorage.getItem('businessId');
  if (direct && direct.trim()) {
    try {
      const parsed = JSON.parse(direct);
      if (typeof parsed === 'string' && parsed.trim()) return parsed.trim();
    } catch {}
    return direct.trim();
  }

  // Otherwise, parse from bDetails payload provided by wrapper
  const raw = localStorage.getItem('bDetails');
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      const candidate = (
        parsed?.businessId ||
        parsed?.id ||
        parsed?.business_id ||
        parsed?.business?.id ||
        parsed?.business?._id ||
        parsed?.organizationId ||
        parsed?.orgId
      );
      return (candidate && String(candidate).trim()) || '';
    } catch {
      // Some wrappers may send businessId as a simple string in bDetails
      const s = raw.trim();
      return s || '';
    }
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

