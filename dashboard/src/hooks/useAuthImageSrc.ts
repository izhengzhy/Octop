import { useLayoutEffect, useRef, useState } from "react";
import { requestBlob } from "../api/request";
import {
  asImageBlob,
  isDataUrl,
  needsAuthBlobFetch,
} from "../utils/toolMediaBlocks";

export type AuthImageLoadState = "loading" | "ready" | "error";

function apiPathFromUrl(url: string): string {
  if (url.startsWith("http")) {
    const parsed = new URL(url);
    return parsed.pathname.replace(/^\/api/, "") + parsed.search;
  }
  return url.replace(/^\/api/, "");
}

export async function fetchAuthImageBlob(
  url: string,
  filename?: string,
): Promise<Blob> {
  if (isDataUrl(url)) {
    const res = await fetch(url);
    return asImageBlob(await res.blob(), filename);
  }
  const blob = await requestBlob(apiPathFromUrl(url));
  return asImageBlob(blob, filename);
}

/** Load JWT-protected or data-URL images into a blob object URL. */
export function useAuthImageSrc(
  url: string,
  filename?: string,
): {
  src: string;
  loadState: AuthImageLoadState;
  setSrc: React.Dispatch<React.SetStateAction<string>>;
} {
  const needsFetch = needsAuthBlobFetch(url) || isDataUrl(url);
  const [src, setSrc] = useState(() => (needsFetch ? "" : url));
  const [loadState, setLoadState] = useState<AuthImageLoadState>(() =>
    needsFetch ? "loading" : "ready",
  );
  const objectUrlRef = useRef<string | undefined>(undefined);

  useLayoutEffect(() => {
    if (!needsAuthBlobFetch(url) && !isDataUrl(url)) {
      setSrc(url);
      setLoadState("ready");
      return;
    }

    let cancelled = false;
    setLoadState("loading");
    setSrc("");

    const load = async () => {
      try {
        const blob = await fetchAuthImageBlob(url, filename);
        if (cancelled) return;
        const objUrl = URL.createObjectURL(blob);
        objectUrlRef.current = objUrl;
        setSrc(objUrl);
        setLoadState("ready");
      } catch {
        if (!cancelled) {
          setSrc("");
          setLoadState("error");
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = undefined;
      }
    };
  }, [url, filename]);

  return { src, loadState, setSrc };
}
