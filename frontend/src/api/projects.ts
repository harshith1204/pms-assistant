import { API_HTTP_URL } from "@/config";

export type Project = {
  projectId: string;
  projectName: string;
  projectDescription: string | null;
  imageUrl: string;
  icon: string;
  projectDisplayId: string;
  businessId: string;
  businessName: string | null;
  features: {
    cycles: boolean;
    modules: boolean;
    pages: boolean;
    intake: boolean;
    view: boolean;
    timeTracking: boolean;
    estimations: boolean;
    epic: boolean;
  };
  accessType: string;
  timeZone: string | null;
  lead: {
    id: string;
    name: string;
  } | null;
  defaultAssignee: {
    id: string;
    name: string;
  } | null;
  status: string;
  createdTimeStamp: string;
  guestAccess: boolean;
};

export type GetProjectsResponse = {
  data: Project[];
};

// Hardcoded values for now - will be replaced with dynamic loading from parent website later
const getMemberId = () => {
  return '1eff7f64-08ea-6fdc-99d0-3f7ae8229af5'; // MEMBER_UUID from .env
};

const getBusinessId = () => {
  return '1eff7f64-09ef-670e-8c7c-2b9676f8dbb6'; // BUSINESS_UUID from .env
};

export async function getProjects(): Promise<GetProjectsResponse> {
  const businessId = getBusinessId();
  const memberId = getMemberId();

  const res = await fetch(
    `https://stage-project.simpo.ai/project/memberId?businessId=${businessId}&memberId=${memberId}`,
    {
      method: "GET",
      headers: { "accept": "application/json" },
    }
  );

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to fetch projects (${res.status})`);
  }

  return res.json();
}
