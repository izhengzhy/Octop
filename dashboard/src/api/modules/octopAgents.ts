import { request } from "../request";

export const octopAgentsApi = {
  markRead: (agentId: string) =>
    request<void>(`/agents/${encodeURIComponent(agentId)}/read`, {
      method: "POST",
    }),
};
