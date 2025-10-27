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
        // Normalize and set business details from wrapper
        // event.data.data may be: object, JSON string, or double-encoded JSON string
        try {
          const raw = event.data.data;
          let value: any = raw;
          if (typeof value === 'string') {
            try {
              value = JSON.parse(value);
            } catch {}
          }
          if (typeof value === 'string') {
            // Could still be double-encoded JSON
            try {
              const second = JSON.parse(value);
              value = second;
            } catch {}
          }
          if (typeof value === 'object' && value) {
            localStorage.setItem('bDetails', JSON.stringify(value));
          } else if (typeof value === 'string') {
            localStorage.setItem('bDetails', value);
          }
        } catch {
          // Fallback to raw string
          if (typeof event.data.data === 'string') {
            localStorage.setItem('bDetails', event.data.data);
          }
        }
      } else if (event.data.type === 'staffType') {
        localStorage.setItem('staffType', event.data.data);
      } else if (event.data.type === 'staffId') {
        localStorage.setItem('staffId', event.data.data);
        console.log('[Project Lens] Received staffId from wrapper:', event.data.data);
      } else if (event.data.type === 'staffName') {
        localStorage.setItem('staffName', event.data.data);
      } else if (event.data.type === 'staff_data') {
        // Parent responds with staffId and businessId
        if (event.data.staffId !== undefined) {
          const v = typeof event.data.staffId === 'string' ? event.data.staffId : JSON.stringify(event.data.staffId);
          localStorage.setItem('staffId', v);
          console.log('[Project Lens] Received staff_data.staffId:', v);
        }
        if (event.data.businessId !== undefined) {
          const v = typeof event.data.businessId === 'string' ? event.data.businessId : JSON.stringify(event.data.businessId);
          localStorage.setItem('businessId', v);
          console.log('[Project Lens] Received staff_data.businessId:', v);
        }
      } else if (event.data.type === 'business_staff_data') {
        // Combined payload from parent with business and staff info
        if (event.data.staffId !== undefined) {
          const v = typeof event.data.staffId === 'string' ? event.data.staffId : JSON.stringify(event.data.staffId);
          localStorage.setItem('staffId', v);
          console.log('[Project Lens] Received business_staff_data.staffId:', v);
        }
        if (event.data.businessId !== undefined) {
          const v = typeof event.data.businessId === 'string' ? event.data.businessId : JSON.stringify(event.data.businessId);
          localStorage.setItem('businessId', v);
          console.log('[Project Lens] Received business_staff_data.businessId:', v);
        }
        if (event.data.businessName !== undefined) {
          localStorage.setItem('businessName', String(event.data.businessName));
        }
      }

      // After handling each message, if we have any business details payload, try to log extracted businessId
      if (event.data.type === 'localStorage') {
        try {
          const raw = localStorage.getItem('bDetails');
          if (raw) {
            let obj: any = raw;
            try { obj = JSON.parse(raw); } catch {}
            const candidate = (
              obj?.businessId ||
              obj?.id ||
              obj?.business_id ||
              obj?.business?.id ||
              obj?.business?._id ||
              obj?.organizationId ||
              obj?.orgId ||
              (typeof obj === 'string' ? obj : '')
            );
            if (candidate) {
              console.log('[Project Lens] Extracted businessId candidate from bDetails:', candidate);
            }
          }
        } catch {}
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  // Send ready message when app loads
  useEffect(() => {
    const sendReadyMessage = () => {
      window.parent.postMessage({ type: 'project_lens_ready' }, '*');
      // Request IDs explicitly in case wrapper requires a request cycle
      window.parent.postMessage({ type: 'get_staff_data' }, '*');
      console.log('[Project Lens] Sent project_lens_ready and get_staff_data requests to wrapper');
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
