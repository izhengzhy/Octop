import { createElement, type ReactNode } from "react";
import { Modal } from "antd";
import type { ModalFuncProps } from "antd";
import { Play } from "lucide-react";

const MOBILE_BREAKPOINT = 768;

function detectMobile(): boolean {
  return typeof window !== "undefined" && window.innerWidth < MOBILE_BREAKPOINT;
}

/** Mobile-friendly wrapper around antd `Modal.confirm` (stacked full-width buttons). */
export function showConfirmModal(
  props: ModalFuncProps,
  options?: { isMobile?: boolean },
): void {
  const isMobile = options?.isMobile ?? detectMobile();

  Modal.confirm({
    centered: true,
    ...(isMobile
      ? {
          width: Math.min(400, Math.max(280, window.innerWidth - 32)),
          rootClassName: "octop-confirm-modal--mobile",
        }
      : {}),
    ...props,
  });
}

export interface ActionConfirmModalProps {
  title: string;
  description: string;
  highlight?: string;
  okText: string;
  cancelText: string;
  onOk: () => void | Promise<void>;
}

function ActionConfirmContent({
  description,
  highlight,
}: Pick<ActionConfirmModalProps, "description" | "highlight">): ReactNode {
  return createElement(
    "div",
    { className: "octop-action-confirm" },
    createElement(
      "div",
      { className: "octop-action-confirm__icon", "aria-hidden": "true" },
      createElement(Play, { size: 22, strokeWidth: 2.2 }),
    ),
    createElement(
      "p",
      { className: "octop-action-confirm__desc" },
      description,
    ),
    highlight
      ? createElement(
          "div",
          { className: "octop-action-confirm__highlight" },
          highlight,
        )
      : null,
  );
}

/** Styled confirmation for high-visibility actions (e.g. execute task now). */
export function showActionConfirmModal(
  props: ActionConfirmModalProps,
  options?: { isMobile?: boolean },
): void {
  const isMobile = options?.isMobile ?? detectMobile();
  const rootClassName = [
    "octop-confirm-modal--action",
    isMobile ? "octop-confirm-modal--mobile" : "",
  ]
    .filter(Boolean)
    .join(" ");

  Modal.confirm({
    centered: true,
    title: props.title,
    icon: null,
    content: createElement(ActionConfirmContent, {
      description: props.description,
      highlight: props.highlight,
    }),
    okText: props.okText,
    cancelText: props.cancelText,
    okType: "primary",
    onOk: props.onOk,
    width: isMobile
      ? Math.min(400, Math.max(280, window.innerWidth - 32))
      : 420,
    rootClassName,
  });
}
