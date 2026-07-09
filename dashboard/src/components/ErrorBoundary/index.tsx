import { Component, type ReactNode } from "react";
import { Result, Button, Space } from "antd";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  retryCount: number;
}

const MAX_RETRIES = 3;

/**
 * Global error boundary — catches unhandled errors in the React tree
 * and displays a friendly fallback UI with retry / home actions.
 */
export default class GlobalErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null, retryCount: 0 };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[GlobalErrorBoundary]", error, info.componentStack);
  }

  handleRetry = () => {
    if (this.state.retryCount >= MAX_RETRIES) return;
    this.setState((prev) => ({
      hasError: false,
      error: null,
      retryCount: prev.retryCount + 1,
    }));
  };

  handleHome = () => {
    window.location.href = "/chat";
  };

  render() {
    if (this.state.hasError) {
      const canRetry = this.state.retryCount < MAX_RETRIES;
      return (
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            minHeight: "100dvh",
          }}
        >
          <Result
            status="error"
            title="Something went wrong"
            subTitle={
              this.state.error?.message || "An unexpected error occurred."
            }
            extra={
              <Space>
                {canRetry && (
                  <Button type="primary" onClick={this.handleRetry}>
                    Retry
                  </Button>
                )}
                <Button onClick={this.handleHome}>Back to Home</Button>
              </Space>
            }
          />
        </div>
      );
    }
    return this.props.children;
  }
}
