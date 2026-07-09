import { request } from "../request";

export interface PluginConfigField {
  name: string;
  label?: string;
  type?: string;
  required?: boolean;
  placeholder?: string;
  help?: string;
}

export interface InstalledPlugin {
  id: string;
  version?: string;
  name?: string;
  kind?: string;
  description?: string;
  path?: string;
  loaded?: boolean;
  error?: string;
  tools?: {
    name: string;
    description?: string;
    config_fields?: PluginConfigField[];
  }[];
}

export interface AgentPluginTool {
  plugin_id: string;
  name: string;
  description?: string;
  config_fields: PluginConfigField[];
  enabled: boolean;
  config: Record<string, unknown>;
}

export type AgentPluginsConfig = Record<
  string,
  {
    tools?: Record<
      string,
      {
        enabled?: boolean;
        config?: Record<string, unknown>;
      }
    >;
  }
>;

export const pluginsApi = {
  list(): Promise<InstalledPlugin[]> {
    return request<InstalledPlugin[]>("/plugins");
  },

  install(
    url: string,
  ): Promise<{ id: string; version: string; name: string; kind: string }> {
    return request("/plugins/install", {
      method: "POST",
      body: JSON.stringify({ url }),
    });
  },

  uninstall(pluginId: string): Promise<{ status: string; id: string }> {
    return request(`/plugins/${encodeURIComponent(pluginId)}`, {
      method: "DELETE",
    });
  },

  listAgentTools(agentId: string): Promise<{ tools: AgentPluginTool[] }> {
    return request(`/plugins/agents/${encodeURIComponent(agentId)}/tools`);
  },

  patchAgentTools(
    agentId: string,
    plugins: AgentPluginsConfig,
  ): Promise<{ status: string }> {
    return request(`/plugins/agents/${encodeURIComponent(agentId)}/tools`, {
      method: "PATCH",
      body: JSON.stringify({ plugins }),
    });
  },
};
