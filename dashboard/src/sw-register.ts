/**
 * Service Worker registration and lifecycle management.
 *
 * autoUpdate flow:
 *   - vite-plugin-pwa is configured with `registerType: "autoUpdate"` plus
 *     workbox `skipWaiting: true` + `clientsClaim: true`, so a freshly built
 *     SW installs + activates + takes control of open tabs without user
 *     intervention.
 *   - Once the new SW takes control (`controllerchange` fires), we reload
 *     the open tab so it picks up the new index.html and chunks.
 *   - The "pwa:update-ready" event is still dispatched (so any UI listener
 *     can show a toast) but a reload happens automatically a moment later.
 */

let pendingRegistration: ServiceWorkerRegistration | null = null;
let reloadingForUpdate = false;

function notifyUpdateReady(): void {
  window.dispatchEvent(new CustomEvent("pwa:update-ready"));
}

/**
 * Force-reload to pick up the new SW's assets.
 *
 * Kept exported so UI code (e.g. an "Update available" toast) can still
 * trigger an immediate refresh even if `controllerchange` was missed.
 */
export function applyUpdate(): void {
  if (reloadingForUpdate) return;
  reloadingForUpdate = true;
  if (pendingRegistration?.waiting) {
    pendingRegistration.waiting.postMessage({ type: "SKIP_WAITING" });
  }
  window.location.reload();
}

export async function registerSW(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;

  try {
    const registration = await navigator.serviceWorker.register("/sw.js", {
      scope: "/",
    });

    // When the SW that controls this page changes (i.e. the new one called
    // skipWaiting + clientsClaim), reload so the new index.html / chunks
    // become visible. Guarded so we only reload once per session.
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (reloadingForUpdate) return;
      reloadingForUpdate = true;
      window.location.reload();
    });

    if (registration.waiting) {
      pendingRegistration = registration;
      notifyUpdateReady();
    }

    registration.addEventListener("updatefound", () => {
      const installing = registration.installing;
      if (!installing) return;
      installing.addEventListener("statechange", () => {
        if (
          installing.state === "installed" &&
          navigator.serviceWorker.controller
        ) {
          pendingRegistration = registration;
          notifyUpdateReady();
        }
      });
    });

    setInterval(() => registration.update(), 60 * 60 * 1000);
  } catch (err) {
    console.error("[SW] Registration failed:", err);
  }
}
