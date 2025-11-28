import { PROJECT_ENDPOINTS } from "@/api/endpoints";
import { getBusinessId, getMemberId, getStaffName } from "@/config";

export type CreateProjectRequest = {
  name: string;
  projectId?: string; // Display ID like "PROJ-1"
  description?: string;
  imageUrl?: string;
  icon?: string;
  access?: "PUBLIC" | "PRIVATE";
  leadId?: string;
  leadName?: string;
  leadMail?: string;
  startDate?: string;
  endDate?: string;
  createdBy?: { id: string; name: string };
};

export type CreateProjectResponse = {
  id: string;
  projectDisplayId: string;
  name: string;
  description: string;
  imageUrl?: string;
  icon?: string;
  access?: string;
  link?: string;
};

export async function createProject(payload: CreateProjectRequest): Promise<CreateProjectResponse> {
  const endpoint = PROJECT_ENDPOINTS.CREATE_PROJECT();

  const memberId = getMemberId();
  const staffName = getStaffName();
  const businessId = getBusinessId();

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { 
      "Content-Type": "application/json",
      "accept": "application/json"
    },
    body: JSON.stringify({
      business: {
        id: businessId,
        name: ""
      },
      name: payload.name,
      description: payload.description || "",
      imageUrl: payload.imageUrl || "https://d2yx15pncgmu63.cloudfront.net/prod-images/524681c1750191737292Website-Design-Background-Feb-09-2022-03-13-55-73-AM.webp",
      icon: payload.icon || "😊",
      access: payload.access || "PUBLIC",
      lead: {
        id: payload.leadId || memberId,
        name: payload.leadName || staffName
      },
      leadMail: payload.leadMail || "",
      createdBy: payload.createdBy || { id: memberId, name: staffName },
      startDate: payload.startDate,
      endDate: payload.endDate
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create project (${res.status})`);
  }

  return res.json();
}
