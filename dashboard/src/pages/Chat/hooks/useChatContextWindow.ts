import { useMemo } from "react";
import type { ResolvedModel, TokenUsage } from "../../../api/types";
import { modelOptionValue } from "../../../utils/modelOptions";
import type { ChatMessage } from "./useChat";

export function useChatContextWindow(
  messages: ChatMessage[],
  contextUsage: TokenUsage | null | undefined,
  selectedModel: string | null,
  availableModels: ResolvedModel[],
  agentDefaultModel?: string | null,
) {
  const contextMaxTokens = useMemo(() => {
    if (selectedModel) {
      const match = availableModels.find(
        (m) => modelOptionValue(m) === selectedModel,
      );
      const window = match?.context_window ?? match?.contextWindow;
      if (window && window > 0) return window;
    }
    if (agentDefaultModel) {
      const match = availableModels.find(
        (m) => modelOptionValue(m) === agentDefaultModel,
      );
      const window = match?.context_window ?? match?.contextWindow;
      if (window && window > 0) return window;
    }
    return 128_000;
  }, [selectedModel, availableModels, agentDefaultModel]);

  const contextUsedTokens = useMemo(() => {
    if (
      typeof contextUsage?.input_tokens === "number" &&
      contextUsage.input_tokens > 0
    ) {
      return contextUsage.input_tokens;
    }
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const usage = messages[i].usage;
      if (typeof usage?.input_tokens === "number" && usage.input_tokens > 0) {
        return usage.input_tokens;
      }
    }
    return null;
  }, [contextUsage, messages]);

  return { contextMaxTokens, contextUsedTokens };
}
