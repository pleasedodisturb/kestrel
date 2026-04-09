import { Component, type ReactNode } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "@/components/Layout";
import { Pipeline } from "@/pages/Pipeline";
import { ApplicationDetail } from "@/pages/ApplicationDetail";
import { Analytics } from "@/pages/Analytics";
import { FollowUps } from "@/pages/FollowUps";
import { Skills } from "@/pages/Skills";
import { Learning } from "@/pages/Learning";
import { SettingsPage } from "@/pages/SettingsPage";
import { Discovery } from "@/pages/Discovery";
import { VoiceDiscussion } from "@/pages/VoiceDiscussion";
import { AIHealthDashboard } from "@/pages/AIHealthDashboard";
import ContactsPage from "@/pages/ContactsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
    },
  },
});

class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="flex min-h-screen items-center justify-center bg-gray-50">
          <div className="max-w-md rounded-lg border border-red-200 bg-white p-8 text-center shadow-sm">
            <h1 className="text-lg font-semibold text-gray-900">
              Something went wrong
            </h1>
            <p className="mt-2 text-sm text-gray-600">
              {this.state.error?.message ?? "An unexpected error occurred."}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.href = "/";
              }}
              className="mt-4 rounded-md bg-gray-900 px-4 py-2 text-sm text-white hover:bg-gray-800"
            >
              Return to Dashboard
            </button>
          </div>
        </main>
      );
    }
    const { children } = this.props;
    return children;
  }
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Pipeline />} />
              <Route path="/applications/:id" element={<ApplicationDetail />} />
              <Route path="/discovery" element={<Discovery />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/follow-ups" element={<FollowUps />} />
              <Route path="/contacts" element={<ContactsPage />} />
              <Route path="/skills" element={<Skills />} />
              <Route path="/learning" element={<Learning />} />
              <Route path="/voice" element={<VoiceDiscussion />} />
              <Route path="/ai-health" element={<AIHealthDashboard />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
