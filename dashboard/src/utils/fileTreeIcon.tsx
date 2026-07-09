/**
 * Map workspace filenames / extensions to coloured lucide icons for file trees.
 */

import type { LucideIcon } from "lucide-react";
import {
  Archive,
  BookOpen,
  Braces,
  Code2,
  Database,
  FileCode,
  FileJson,
  FileText,
  Fingerprint,
  Globe,
  Heart,
  Image,
  Key,
  Palette,
  Rocket,
  ScrollText,
  Settings,
  Sparkles,
  Table,
  Terminal,
  User,
  Wrench,
} from "lucide-react";

const DEFAULT_COLOR = "var(--fn-text-tertiary)";

interface IconSpec {
  Icon: LucideIcon;
  color: string;
}

function basename(path: string): string {
  return path.split("/").filter(Boolean).pop() || path;
}

function extension(path: string): string {
  const name = basename(path);
  const dot = name.lastIndexOf(".");
  if (dot <= 0) return "";
  return name.slice(dot + 1).toLowerCase();
}

/** Canonical agent config filenames — same palette as Experts page. */
const NAME_MAP: Record<string, IconSpec> = {
  "SOUL.md": { Icon: Sparkles, color: "#7c3aed" },
  "IDENTITY.md": { Icon: Fingerprint, color: "#db2777" },
  "USER.md": { Icon: User, color: "#2563eb" },
  "AGENTS.md": { Icon: BookOpen, color: "#059669" },
  "TOOLS.md": { Icon: Wrench, color: "#f59e0b" },
  "BOOTSTRAP.md": { Icon: Rocket, color: "#d97706" },
  "HEARTBEAT.md": { Icon: Heart, color: "#ef4444" },
  "MEMORY.md": { Icon: Database, color: "#0891b2" },
  Makefile: { Icon: Wrench, color: "#78716c" },
  Dockerfile: { Icon: FileCode, color: "#0ea5e9" },
};

const EXT_MAP: Record<string, IconSpec> = {
  // Docs / text
  md: { Icon: FileText, color: "#3b82f6" },
  markdown: { Icon: FileText, color: "#3b82f6" },
  txt: { Icon: FileText, color: "#64748b" },
  rst: { Icon: FileText, color: "#64748b" },

  // Data / config
  json: { Icon: FileJson, color: "#ca8a04" },
  jsonl: { Icon: Braces, color: "#a16207" },
  yaml: { Icon: FileCode, color: "#db2777" },
  yml: { Icon: FileCode, color: "#db2777" },
  toml: { Icon: Settings, color: "#6b7280" },
  xml: { Icon: FileCode, color: "#ea580c" },
  csv: { Icon: Table, color: "#16a34a" },
  env: { Icon: Key, color: "#84cc16" },

  // Scripts / shell
  sh: { Icon: Terminal, color: "#22c55e" },
  bash: { Icon: Terminal, color: "#22c55e" },
  zsh: { Icon: Terminal, color: "#22c55e" },
  fish: { Icon: Terminal, color: "#22c55e" },

  // Python / JS / TS ecosystem
  py: { Icon: Code2, color: "#3572A5" },
  pyi: { Icon: Code2, color: "#3572A5" },
  ipynb: { Icon: Code2, color: "#3572A5" },
  js: { Icon: Code2, color: "#eab308" },
  jsx: { Icon: Code2, color: "#eab308" },
  mjs: { Icon: Code2, color: "#eab308" },
  cjs: { Icon: Code2, color: "#eab308" },
  ts: { Icon: Code2, color: "#3178c6" },
  tsx: { Icon: Code2, color: "#3178c6" },

  // Other languages
  go: { Icon: Code2, color: "#00ADD8" },
  rs: { Icon: Code2, color: "#dea584" },
  java: { Icon: Code2, color: "#b07219" },
  kt: { Icon: Code2, color: "#a97bff" },
  rb: { Icon: Code2, color: "#cc342d" },
  php: { Icon: Code2, color: "#777bb4" },
  c: { Icon: Code2, color: "#555555" },
  cpp: { Icon: Code2, color: "#f34b7d" },
  h: { Icon: Code2, color: "#555555" },
  cs: { Icon: Code2, color: "#178600" },
  swift: { Icon: Code2, color: "#fa7343" },
  lua: { Icon: Code2, color: "#000080" },
  r: { Icon: Code2, color: "#276dc3" },
  sql: { Icon: Database, color: "#336791" },

  // Web
  html: { Icon: Globe, color: "#e44d26" },
  htm: { Icon: Globe, color: "#e44d26" },
  css: { Icon: Palette, color: "#264de4" },
  scss: { Icon: Palette, color: "#cd6799" },
  less: { Icon: Palette, color: "#1d365d" },

  // Logs / misc
  log: { Icon: ScrollText, color: "#94a3b8" },

  // Images / archives
  png: { Icon: Image, color: "#8b5cf6" },
  jpg: { Icon: Image, color: "#8b5cf6" },
  jpeg: { Icon: Image, color: "#8b5cf6" },
  gif: { Icon: Image, color: "#8b5cf6" },
  svg: { Icon: Image, color: "#8b5cf6" },
  webp: { Icon: Image, color: "#8b5cf6" },
  zip: { Icon: Archive, color: "#78716c" },
  tar: { Icon: Archive, color: "#78716c" },
  gz: { Icon: Archive, color: "#78716c" },
  "7z": { Icon: Archive, color: "#78716c" },
};

function resolveSpec(path: string): IconSpec {
  const name = basename(path);
  const byName = NAME_MAP[name];
  if (byName) return byName;

  const ext = extension(path);
  if (ext && EXT_MAP[ext]) return EXT_MAP[ext];

  return { Icon: FileText, color: DEFAULT_COLOR };
}

export function fileTreeIcon(path: string, size = 13) {
  const { Icon, color } = resolveSpec(path);
  return <Icon size={size} color={color} strokeWidth={2} aria-hidden />;
}
