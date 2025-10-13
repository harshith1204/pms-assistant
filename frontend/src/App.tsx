import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useEffect } from "react";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import Settings from "./pages/Settings";
import { PersonalizationProvider } from "@/context/PersonalizationContext";

const queryClient = new QueryClient();

const App = () => {
  // Listen for messages from the wrapper
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data.type === 'set_path') {
        // Store the current path for navigation
        localStorage.setItem('wrapper_path', event.data.path);
      } else if (event.data.type === 'localStorage') {
        // Set localStorage data from wrapper
        localStorage.setItem('bDetails', event.data.data);
      } else if (event.data.type === 'staffType') {
        localStorage.setItem('staffType', event.data.data);
      } else if (event.data.type === 'staffId') {
        localStorage.setItem('staffId', event.data.data);
      } else if (event.data.type === 'staffName') {
        localStorage.setItem('staffName', event.data.data);
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  // Send ready message when app loads
  useEffect(() => {
    const sendReadyMessage = () => {
      window.parent.postMessage({ type: 'project_lens_ready' }, '*');
    };

    // Send ready message after a short delay to ensure app is fully loaded
    const timeoutId = setTimeout(sendReadyMessage, 100);

    return () => clearTimeout(timeoutId);
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <PersonalizationProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/settings" element={<Settings />} />
              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </PersonalizationProvider>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

export default App;
