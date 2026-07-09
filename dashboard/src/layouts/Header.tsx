import { useEffect, useState } from "react";
import { Layout } from "antd";
import { Menu as MenuIcon, Github } from "lucide-react";
import PwaInstallPrompt from "../components/PwaInstallPrompt";
import pwaStyles from "../components/PwaInstallPrompt/index.module.less";
import AppVersionBadge from "../components/AppVersionBadge";
import BetaBadge from "../components/BetaBadge";
import CurrentVersionBadge from "../components/CurrentVersionBadge";
import ThemeSwitcher from "../components/ThemeSwitcher";
import AvatarDropdown from "../components/AvatarDropdown";
import { authApi } from "../api/modules/auth";
import type { OctopUser } from "../api/modules/auth";
import { useTheme } from "../context/ThemeContext";
import { typeSize } from "../utils/mobileTypeScale";

const { Header: AntHeader } = Layout;

interface HeaderProps {
  selectedKey?: string;
  collapsed?: boolean;
  onToggle?: () => void;
  isMobile?: boolean;
}

export default function Header({ onToggle, isMobile }: HeaderProps) {
  const { isDark } = useTheme();
  const [user, setUser] = useState<OctopUser | null>(null);

  useEffect(() => {
    authApi
      .me()
      .then(setUser)
      .catch(() => {});
  }, []);

  const logoSrc = isDark ? "/logo_name_dark.png" : "/logo_name.png";

  return (
    <AntHeader
      style={{
        height: "var(--fn-header-height)",
        padding: isMobile ? "0 12px" : "0 20px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "var(--fn-header-bg)",
        backdropFilter: "blur(var(--fn-header-blur))",
        WebkitBackdropFilter: "blur(var(--fn-header-blur))",
        borderBottom: "1px solid var(--fn-border-primary)",
        transition: "background var(--fn-transition)",
        flexShrink: 0,
        zIndex: 20,
      }}
    >
      {/* Left: mobile toggle + logo */}
      <div
        style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}
      >
        {isMobile && onToggle && (
          <button
            onClick={onToggle}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: typeSize(34, isMobile),
              height: typeSize(34, isMobile),
              border: "none",
              borderRadius: "var(--fn-radius-md)",
              background: "transparent",
              color: "var(--fn-text-tertiary)",
              cursor: "pointer",
              transition: "all var(--fn-transition-fast)",
              flexShrink: 0,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--fn-bg-tertiary)";
              e.currentTarget.style.color = "var(--fn-text-secondary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--fn-text-tertiary)";
            }}
          >
            <MenuIcon size={20} strokeWidth={1.8} />
          </button>
        )}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            minWidth: 0,
            flexShrink: 1,
          }}
        >
          <img
            src={logoSrc}
            alt="octop"
            style={{
              height: isMobile ? 36 : 42,
              width: "auto",
              maxWidth: isMobile ? 230 : 280,
              objectFit: "contain",
              flexShrink: 0,
              display: "block",
            }}
          />
          <BetaBadge isMobile={isMobile} />
          <CurrentVersionBadge isMobile={isMobile} />
          <AppVersionBadge isMobile={isMobile} />
        </div>
      </div>

      {/* Right: GitHub + PWA install + avatar dropdown */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: isMobile ? 4 : 10,
          flexShrink: 0,
        }}
      >
        {!isMobile && (
          <a
            href="https://github.com/TencentCloud/Octop"
            target="_blank"
            rel="noopener noreferrer"
            className={pwaStyles.installBtn}
          >
            <Github
              size={16}
              strokeWidth={1.8}
              className={pwaStyles.installIcon}
            />
            <span className={pwaStyles.label}>GitHub</span>
          </a>
        )}
        <PwaInstallPrompt compact={isMobile} />
        {!isMobile && <ThemeSwitcher compact />}
        <AvatarDropdown user={user} onUserChange={setUser} />
      </div>
    </AntHeader>
  );
}
