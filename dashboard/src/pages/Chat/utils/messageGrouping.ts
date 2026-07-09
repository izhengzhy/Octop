import type { ChatMessage } from "../hooks/useChat";

export interface MessageGroup {
  isGroup: boolean;
  messages: ChatMessage[];
}

/** Group consecutive assistant messages for unified turn rendering. */
export function groupConsecutiveAssistantMessages(
  messages: ChatMessage[],
): MessageGroup[] {
  const groups: MessageGroup[] = [];
  let currentGroup: ChatMessage[] = [];

  for (const msg of messages) {
    if (msg.role === "assistant") {
      currentGroup.push(msg);
    } else {
      if (currentGroup.length > 0) {
        groups.push({ isGroup: true, messages: currentGroup });
        currentGroup = [];
      }
      groups.push({ isGroup: false, messages: [msg] });
    }
  }

  if (currentGroup.length > 0) {
    groups.push({ isGroup: true, messages: currentGroup });
  }

  return groups;
}
