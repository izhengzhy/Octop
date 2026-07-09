import {
  forwardRef,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  useState,
  useLayoutEffect,
} from "react";
import { Spin } from "antd";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";
import { useTranslation } from "react-i18next";
import type { ChatMessage } from "../hooks/useChat";
import type { ComposerTagLookups } from "./UserMessageComposerTags";
import MessageBubble from "./MessageBubble";
import AssistantTurnView from "./AssistantTurnView";
import ThinkingBubble from "./ThinkingBubble";
import ScrollToBottomButton from "./ScrollToBottomButton";
import ContinuingIndicator from "./ContinuingIndicator";
import { findLastBrowserTurnGroupIndex } from "../utils/messageContent";
import {
  groupConsecutiveAssistantMessages,
  type MessageGroup,
} from "../utils/messageGrouping";
import styles from "../index.module.less";

/** Virtualize long threads; short chats keep the simpler DOM path. */
const VIRTUALIZE_THRESHOLD = 30;

const VirtuosoList = forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(function VirtuosoList({ style, children, className, ...props }, ref) {
  return (
    <div
      ref={ref}
      {...props}
      style={style}
      className={[styles.messageListInner, className].filter(Boolean).join(" ")}
    >
      {children}
    </div>
  );
});

const virtuosoComponents = { List: VirtuosoList };

interface MessageListProps {
  messages: ChatMessage[];
  agentId?: string | null;
  composerLookups?: ComposerTagLookups;
  loading?: boolean;
  historyHasMore?: boolean;
  historyLoadingMore?: boolean;
  onLoadMoreHistory?: () => void;
  isStreaming?: boolean;
  sessionKey?: string;
  onCancel?: () => void;
  onRegenerate?: (messageId: string) => void;
  onEditUserMessage?: (messageId: string, newText: string) => void;
  onAcpPermissionSelect?: (message: string) => void;
  onHitlDecision?: (
    decisions: Array<{ type: string; message?: string }>,
  ) => void;
  onOpenBrowser?: () => void;
  onRunShellCommand?: (code: string) => void;
  shellCommandDisabled?: boolean;
  shellCommandDisabledTitle?: string;
  compactProcess?: boolean;
}

interface GroupRenderContext {
  agentId?: string | null;
  composerLookups?: ComposerTagLookups;
  isStreaming?: boolean;
  lastBrowserGroupIndex: number;
  lastAssistantGroupIndex: number;
  onRegenerate?: (messageId: string) => void;
  onEditUserMessage?: (messageId: string, newText: string) => void;
  onAcpPermissionSelect?: (message: string) => void;
  onHitlDecision?: (
    decisions: Array<{ type: string; message?: string }>,
  ) => void;
  onOpenBrowser?: () => void;
  onRunShellCommand?: (code: string) => void;
  shellCommandDisabled?: boolean;
  shellCommandDisabledTitle?: string;
  compactProcess?: boolean;
  registerBubbleRef: (messageId: string, el: HTMLDivElement | null) => void;
}

function renderMessageGroup(
  group: MessageGroup,
  groupIndex: number,
  ctx: GroupRenderContext,
) {
  const openBrowserHandler =
    ctx.onOpenBrowser && groupIndex === ctx.lastBrowserGroupIndex
      ? ctx.onOpenBrowser
      : undefined;
  const isTurnInProgress =
    ctx.isStreaming && groupIndex === ctx.lastAssistantGroupIndex;

  if (!group.isGroup || group.messages.length === 1) {
    const msg = group.messages[0];
    if (msg.role === "assistant") {
      return (
        <div
          ref={(el) => {
            ctx.registerBubbleRef(msg.id, el);
          }}
        >
          <AssistantTurnView
            messages={[msg]}
            agentId={ctx.agentId}
            isStreaming={ctx.isStreaming}
            isTurnInProgress={isTurnInProgress}
            onRegenerate={ctx.onRegenerate}
            onEditUserMessage={ctx.onEditUserMessage}
            onAcpPermissionSelect={ctx.onAcpPermissionSelect}
            onHitlDecision={ctx.onHitlDecision}
            onOpenBrowser={openBrowserHandler}
            onRunShellCommand={ctx.onRunShellCommand}
            shellCommandDisabled={ctx.shellCommandDisabled}
            shellCommandDisabledTitle={ctx.shellCommandDisabledTitle}
            compactProcess={ctx.compactProcess}
          />
        </div>
      );
    }
    return (
      <div
        ref={(el) => {
          ctx.registerBubbleRef(msg.id, el);
        }}
      >
        <MessageBubble
          message={msg}
          agentId={ctx.agentId}
          composerLookups={ctx.composerLookups}
          onRegenerate={ctx.onRegenerate}
          onEditUserMessage={ctx.onEditUserMessage}
        />
      </div>
    );
  }

  const groupKey = group.messages.map((m) => m.id).join("|");
  return (
    <div
      key={groupKey}
      ref={(el) => {
        for (const msg of group.messages) {
          ctx.registerBubbleRef(msg.id, el);
        }
      }}
    >
      <AssistantTurnView
        messages={group.messages}
        agentId={ctx.agentId}
        isStreaming={ctx.isStreaming}
        isTurnInProgress={isTurnInProgress}
        onRegenerate={ctx.onRegenerate}
        onEditUserMessage={ctx.onEditUserMessage}
        onAcpPermissionSelect={ctx.onAcpPermissionSelect}
        onHitlDecision={ctx.onHitlDecision}
        onOpenBrowser={openBrowserHandler}
        onRunShellCommand={ctx.onRunShellCommand}
        shellCommandDisabled={ctx.shellCommandDisabled}
        shellCommandDisabledTitle={ctx.shellCommandDisabledTitle}
        compactProcess={ctx.compactProcess}
      />
    </div>
  );
}

export default function MessageList(props: MessageListProps) {
  const {
    messages,
    agentId,
    composerLookups,
    loading,
    historyHasMore,
    historyLoadingMore,
    onLoadMoreHistory,
    isStreaming,
    sessionKey,
    onCancel,
    onRegenerate,
    onEditUserMessage,
    onAcpPermissionSelect,
    onHitlDecision,
    onOpenBrowser,
    onRunShellCommand,
    shellCommandDisabled,
    shellCommandDisabledTitle,
    compactProcess,
  } = props;

  const { t } = useTranslation();
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollerRef = useRef<HTMLElement | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const bubbleRefsMap = useRef<Map<string, HTMLDivElement>>(new Map());
  const lastAnchoredIdRef = useRef<string | null>(null);
  const prevInitialLoadingRef = useRef(false);
  const scrollHeightBeforePrependRef = useRef<number | null>(null);
  const loadMoreRequestedRef = useRef(false);
  const canLoadOlderRef = useRef(false);
  const [atBottom, setAtBottom] = useState(true);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [useVirtualLocked, setUseVirtualLocked] = useState(false);

  const messageGroups = useMemo(
    () => groupConsecutiveAssistantMessages(messages),
    [messages],
  );

  const useVirtual =
    useVirtualLocked || messageGroups.length >= VIRTUALIZE_THRESHOLD;

  const requestOlderMessages = useCallback(() => {
    if (
      !canLoadOlderRef.current ||
      !historyHasMore ||
      historyLoadingMore ||
      loading ||
      !onLoadMoreHistory ||
      loadMoreRequestedRef.current
    ) {
      return;
    }
    const scroller = useVirtual ? scrollerRef.current : containerRef.current;
    if (scroller instanceof HTMLElement) {
      scrollHeightBeforePrependRef.current = scroller.scrollHeight;
    }
    loadMoreRequestedRef.current = true;
    setAtBottom(false);
    onLoadMoreHistory();
  }, [
    historyHasMore,
    historyLoadingMore,
    loading,
    onLoadMoreHistory,
    useVirtual,
  ]);

  useEffect(() => {
    if (!loading && messages.length > 0) {
      canLoadOlderRef.current = true;
    }
  }, [loading, messages.length]);

  useEffect(() => {
    if (!historyLoadingMore) {
      loadMoreRequestedRef.current = false;
    }
  }, [historyLoadingMore]);

  useLayoutEffect(() => {
    if (scrollHeightBeforePrependRef.current === null) return;
    const scroller = useVirtual ? scrollerRef.current : containerRef.current;
    if (scroller instanceof HTMLElement) {
      const delta =
        scroller.scrollHeight - scrollHeightBeforePrependRef.current;
      scroller.scrollTop += delta;
    }
    scrollHeightBeforePrependRef.current = null;
  }, [messages, useVirtual]);

  const historyHeader = useMemo(() => {
    if (!historyHasMore && !historyLoadingMore) return null;
    return (
      <div className={styles.historyLoadMore}>
        {historyLoadingMore ? (
          <>
            <Spin size="small" />
            <span>{t("chat.loadingEarlierMessages")}</span>
          </>
        ) : (
          <span>{t("chat.scrollForEarlierMessages")}</span>
        )}
      </div>
    );
  }, [historyHasMore, historyLoadingMore, t]);

  const lastBrowserGroupIndex = useMemo(
    () => findLastBrowserTurnGroupIndex(messageGroups),
    [messageGroups],
  );

  const lastAssistantGroupIndex = useMemo(() => {
    for (let i = messageGroups.length - 1; i >= 0; i--) {
      if (messageGroups[i].messages.some((m) => m.role === "assistant"))
        return i;
    }
    return -1;
  }, [messageGroups]);

  const registerBubbleRef = useCallback(
    (messageId: string, el: HTMLDivElement | null) => {
      if (el) bubbleRefsMap.current.set(messageId, el);
      else bubbleRefsMap.current.delete(messageId);
    },
    [],
  );

  const scrollToBottom = useCallback(
    (instant = false) => {
      if (useVirtual) {
        if (messageGroups.length > 0) {
          virtuosoRef.current?.scrollToIndex({
            index: messageGroups.length - 1,
            align: "end",
            behavior: instant ? "auto" : "smooth",
          });
        }
        setAtBottom(true);
        setShowScrollBtn(false);
        return;
      }
      const end = endRef.current;
      if (!end) return;
      end.scrollIntoView({
        behavior: instant ? "instant" : "smooth",
        block: "end",
      });
      setShowScrollBtn(false);
    },
    [messageGroups.length, useVirtual],
  );

  const scrollToAnchor = useCallback((anchorEl: HTMLElement) => {
    const container = containerRef.current;
    if (!container) return;
    const elRect = anchorEl.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const targetScrollTop =
      container.scrollTop + (elRect.top - containerRect.top) - 16;
    container.scrollTo({
      top: Math.max(0, targetScrollTop),
      behavior: "smooth",
    });
    setShowScrollBtn(false);
  }, []);

  const stableSessionKey = sessionKey || "__default__";

  useEffect(() => {
    setUseVirtualLocked(false);
    loadMoreRequestedRef.current = false;
    canLoadOlderRef.current = false;
    lastAnchoredIdRef.current = null;
    scrollHeightBeforePrependRef.current = null;
  }, [stableSessionKey]);

  useEffect(() => {
    if (messageGroups.length >= VIRTUALIZE_THRESHOLD) {
      setUseVirtualLocked(true);
    }
  }, [messageGroups.length]);

  useEffect(() => {
    if (prevInitialLoadingRef.current && !loading && messages.length > 0) {
      scrollToBottom(true);
    }
    prevInitialLoadingRef.current = !!loading;
  }, [loading, messages.length, scrollToBottom]);

  useEffect(() => {
    if (!isStreaming) return;

    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUserMsg) return;
    if (lastAnchoredIdRef.current === lastUserMsg.id) return;
    lastAnchoredIdRef.current = lastUserMsg.id;

    if (useVirtual) {
      const index = messageGroups.findIndex((g) =>
        g.messages.some((m) => m.id === lastUserMsg.id),
      );
      if (index >= 0) {
        virtuosoRef.current?.scrollToIndex({
          index,
          align: "start",
          offset: 16,
          behavior: "smooth",
        });
      }
      return;
    }

    const el = bubbleRefsMap.current.get(lastUserMsg.id);
    if (el) scrollToAnchor(el);
  }, [isStreaming, messages, messageGroups, scrollToAnchor, useVirtual]);

  useEffect(() => {
    if (useVirtual || !isStreaming || !atBottom) return;
    scrollToBottom(true);
  }, [messages, isStreaming, atBottom, useVirtual, scrollToBottom]);

  useEffect(() => {
    if (useVirtual) return;
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const bottom =
        container.scrollHeight - container.scrollTop - container.clientHeight <=
        80;
      setAtBottom(bottom);
      setShowScrollBtn(!bottom);
      if (container.scrollTop <= 80) {
        requestOlderMessages();
      }
    };

    handleScroll();
    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => container.removeEventListener("scroll", handleScroll);
  }, [useVirtual, messageGroups.length, requestOlderMessages]);

  const handleScrollBtnClick = useCallback(() => {
    scrollToBottom();
  }, [scrollToBottom]);

  const handleAtBottomChange = useCallback((bottom: boolean) => {
    setAtBottom(bottom);
    setShowScrollBtn(!bottom);
  }, []);

  const groupContext = useMemo<GroupRenderContext>(
    () => ({
      agentId,
      composerLookups,
      isStreaming,
      lastBrowserGroupIndex,
      lastAssistantGroupIndex,
      onRegenerate,
      onEditUserMessage,
      onAcpPermissionSelect,
      onHitlDecision,
      onOpenBrowser,
      onRunShellCommand,
      shellCommandDisabled,
      shellCommandDisabledTitle,
      compactProcess,
      registerBubbleRef,
    }),
    [
      agentId,
      composerLookups,
      isStreaming,
      lastBrowserGroupIndex,
      lastAssistantGroupIndex,
      onRegenerate,
      onEditUserMessage,
      onAcpPermissionSelect,
      onHitlDecision,
      onOpenBrowser,
      onRunShellCommand,
      shellCommandDisabled,
      shellCommandDisabledTitle,
      compactProcess,
      registerBubbleRef,
    ],
  );

  if (loading) {
    return (
      <div className={styles.messageListLoading}>
        <Spin />
      </div>
    );
  }

  const lastMsg = messages[messages.length - 1];
  const showThinking = isStreaming && (!lastMsg || lastMsg.role === "user");
  const showContinuing =
    isStreaming &&
    !showThinking &&
    lastMsg?.role === "assistant" &&
    lastMsg.status === "done";

  const footer = (
    <>
      {showThinking && (
        <ThinkingBubble onCancel={onCancel} sessionKey={stableSessionKey} />
      )}
      {showContinuing && <ContinuingIndicator onCancel={onCancel} />}
    </>
  );

  return (
    <div className={styles.messageListWrapper}>
      {useVirtual ? (
        <Virtuoso
          key={stableSessionKey}
          ref={virtuosoRef}
          className={styles.messageList}
          style={{ height: "100%" }}
          data={messageGroups}
          initialTopMostItemIndex={Math.max(0, messageGroups.length - 1)}
          increaseViewportBy={{ top: 600, bottom: 800 }}
          followOutput={
            isStreaming && atBottom && !historyLoadingMore ? "auto" : false
          }
          atBottomStateChange={handleAtBottomChange}
          atTopThreshold={200}
          startReached={requestOlderMessages}
          scrollerRef={(el) => {
            scrollerRef.current = el instanceof HTMLElement ? el : null;
          }}
          components={{
            ...virtuosoComponents,
            Header: () => (historyHeader ? <div>{historyHeader}</div> : null),
            Footer: () =>
              showThinking || showContinuing ? <div>{footer}</div> : null,
          }}
          itemContent={(index, group) =>
            renderMessageGroup(group, index, groupContext)
          }
        />
      ) : (
        <div className={styles.messageList} ref={containerRef}>
          <div className={styles.messageListInner}>
            {historyHeader}
            {messageGroups.map((group, groupIndex) => (
              <div key={group.messages.map((m) => m.id).join("|")}>
                {renderMessageGroup(group, groupIndex, groupContext)}
              </div>
            ))}
            {footer}
            <div ref={endRef} style={{ height: 1 }} aria-hidden="true" />
          </div>
        </div>
      )}

      <ScrollToBottomButton
        visible={showScrollBtn}
        onClick={handleScrollBtnClick}
      />
    </div>
  );
}
