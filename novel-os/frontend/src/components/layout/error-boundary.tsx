import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex min-h-[100dvh] items-center justify-center bg-background">
          <div className="mx-auto max-w-md space-y-4 rounded-lg border border-border bg-card p-8 text-center shadow-sm">
            <div className="flex justify-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
                <AlertCircle className="size-6 text-destructive" />
              </div>
            </div>
            <h2 className="text-lg font-semibold tracking-tight">页面出现异常</h2>
            <p className="text-sm text-muted-foreground">
              {this.state.error?.message || "发生了未知错误，请尝试刷新页面。"}
            </p>
            <button
              onClick={this.handleReset}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover active:translate-y-[1px] active:scale-[0.98]"
            >
              <RefreshCw className="size-4" />
              重试
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
