import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { Image } from "antd";
import { useTranslation } from "react-i18next";
import { requestBlob } from "../../../../api/request";
import { asImageBlob } from "../../../../utils/toolMediaBlocks";
import type { MediaKind } from "../utils/mediaKind";
import styles from "../index.module.less";

function guessVideoMime(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "webm") return "video/webm";
  if (ext === "mov" || ext === "m4v") return "video/quicktime";
  if (ext === "ogv") return "video/ogg";
  return "video/mp4";
}

function guessAudioMime(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "wav") return "audio/wav";
  if (ext === "ogg" || ext === "opus") return "audio/ogg";
  if (ext === "m4a" || ext === "aac") return "audio/mp4";
  if (ext === "flac") return "audio/flac";
  if (ext === "weba") return "audio/webm";
  return "audio/mpeg";
}

function MediaFallback({ label }: { label: string }) {
  return <span className={styles.mediaFallback}>{label}</span>;
}

function useWorkspaceBlob(
  agentId: string,
  path: string,
  filename: string,
  toBlob: (blob: Blob, filename: string) => Blob,
) {
  const [src, setSrc] = useState("");
  const objectUrlRef = useRef<string | undefined>(undefined);

  const apiPath = useMemo(
    () =>
      `/agents/${encodeURIComponent(
        agentId,
      )}/workspace/download?path=${encodeURIComponent(path)}`,
    [agentId, path],
  );

  useLayoutEffect(() => {
    let cancelled = false;
    setSrc("");

    const load = async () => {
      try {
        const blob = await requestBlob(apiPath);
        if (cancelled) return;
        const objUrl = URL.createObjectURL(toBlob(blob, filename));
        objectUrlRef.current = objUrl;
        setSrc(objUrl);
      } catch {
        if (!cancelled) setSrc("error");
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
  }, [apiPath, filename, toBlob]);

  return src;
}

function WorkspaceImage({
  agentId,
  path,
  filename,
}: {
  agentId: string;
  path: string;
  filename: string;
}) {
  const { t } = useTranslation();
  const src = useWorkspaceBlob(agentId, path, filename, asImageBlob);

  if (src === "error") {
    return (
      <MediaFallback label={t("workspace.mediaLoadFailed", "无法加载预览")} />
    );
  }

  if (!src) {
    return <MediaFallback label="…" />;
  }

  return (
    <div className={styles.mediaPreviewFrame}>
      <Image src={src} alt={filename} className={styles.mediaPreviewImage} />
    </div>
  );
}

function WorkspaceVideo({
  agentId,
  path,
  filename,
}: {
  agentId: string;
  path: string;
  filename: string;
}) {
  const { t } = useTranslation();
  const toBlob = useMemo(
    () => (blob: Blob, name: string) =>
      blob.type && blob.type !== "application/octet-stream"
        ? blob
        : new Blob([blob], { type: guessVideoMime(name) }),
    [],
  );
  const src = useWorkspaceBlob(agentId, path, filename, toBlob);

  if (src === "error") {
    return (
      <MediaFallback label={t("workspace.mediaLoadFailed", "无法加载预览")} />
    );
  }

  if (!src) {
    return <MediaFallback label="…" />;
  }

  return (
    <div className={styles.mediaPreviewFrame}>
      <video
        className={styles.mediaPreviewVideo}
        src={src}
        controls
        preload="metadata"
        playsInline
      />
    </div>
  );
}

function WorkspaceAudio({
  agentId,
  path,
  filename,
}: {
  agentId: string;
  path: string;
  filename: string;
}) {
  const { t } = useTranslation();
  const toBlob = useMemo(
    () => (blob: Blob, name: string) =>
      blob.type && blob.type !== "application/octet-stream"
        ? blob
        : new Blob([blob], { type: guessAudioMime(name) }),
    [],
  );
  const src = useWorkspaceBlob(agentId, path, filename, toBlob);

  if (src === "error") {
    return (
      <MediaFallback label={t("workspace.mediaLoadFailed", "无法加载预览")} />
    );
  }

  if (!src) {
    return <MediaFallback label="…" />;
  }

  return (
    <div className={styles.mediaPreviewFrame}>
      <audio
        className={styles.mediaPreviewAudio}
        src={src}
        controls
        preload="metadata"
      />
    </div>
  );
}

export default function MediaPreview({
  agentId,
  path,
  kind,
}: {
  agentId: string;
  path: string;
  kind: MediaKind;
}) {
  const filename = path.split("/").filter(Boolean).pop() || path;

  switch (kind) {
    case "image":
      return (
        <WorkspaceImage agentId={agentId} path={path} filename={filename} />
      );
    case "video":
      return (
        <WorkspaceVideo agentId={agentId} path={path} filename={filename} />
      );
    case "audio":
      return (
        <WorkspaceAudio agentId={agentId} path={path} filename={filename} />
      );
    default:
      return null;
  }
}
