export const API_HTTP_URL = import.meta.env.VITE_API_HTTP_URL || "http://localhost:8000";
export const API_WS_URL = import.meta.env.VITE_API_WS_URL || `${API_HTTP_URL.replace(/^http/, "ws")}/ws/chat`;

// Stage Project API Configuration
export const STAGE_API_BASE_URL = import.meta.env.VITE_STAGE_API_BASE_URL || "https://stage-project.simpo.ai";

// Get staff and business details dynamically from localStorage (set by parent wrapper)
// Fallback to hard-coded defaults only (no env fallbacks for IDs)

export const DEFAULT_MEMBER_ID = '1f01b572-b7a0-6e64-b890-2d102d936e6e';
export const DEFAULT_BUSINESS_ID = '1f067040-82d8-6384-a1fc-996e5f7d7335';

export const getMemberId = () => {
  const fromStorage = (localStorage.getItem('staffId') || '').trim();
  return fromStorage || DEFAULT_MEMBER_ID;
};

export const getBusinessId = () => {
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
      return (candidate && String(candidate).trim()) || DEFAULT_BUSINESS_ID;
    } catch {
      const s = raw.trim();
      return s || DEFAULT_BUSINESS_ID;
    }
  }
  return DEFAULT_BUSINESS_ID;
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

