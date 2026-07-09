/** Map workspace tree entry path to dashboard `/…` form for API calls. */
export function workspaceEntryPath(infoPath: string): string {
  if (infoPath.startsWith("/")) return infoPath;
  const normalized = infoPath.replace(/\\/g, "/").replace(/^\/+/, "");
  return normalized ? `/${normalized}` : "/";
}
