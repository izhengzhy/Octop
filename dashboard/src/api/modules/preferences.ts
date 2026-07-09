import { request } from "../request";

export interface RemoteBrowserBookmark {
  url: string;
  title: string;
}

export interface UserPreferences {
  locale: string;
  remote_browser_bookmarks: RemoteBrowserBookmark[];
}

export type PatchPreferencesBody = {
  locale?: string;
  remote_browser_bookmarks?: RemoteBrowserBookmark[];
};

export const preferencesApi = {
  get: () => request<UserPreferences>("/preferences"),

  patch: (body: PatchPreferencesBody) =>
    request<UserPreferences>("/preferences", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  setLocale: (locale: string) =>
    request<UserPreferences>("/preferences", {
      method: "PATCH",
      body: JSON.stringify({ locale }),
    }),
};
