import { useState } from "react";
import { useParams, useLocation, useNavigate } from "react-router-dom";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { ConversationSidebar } from "./ConversationSidebar";
import { ChatInterface } from "./ChatInterface";
import { ModelSelector } from "./ModelSelector";
import { Button } from "@/components/ui/button";
import { MessageSquare, Settings, ArrowLeft } from "lucide-react";

export function ChatLayout() {
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const { conversationId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  
  const isSettingsPage = location.pathname === '/settings';
  const pageTitle = isSettingsPage ? 'Settings' : 'Agent Chat';

  return (
    <SidebarProvider>
      <div className="h-screen flex w-full bg-background overflow-hidden">
        {/* Left Sidebar - Conversation History (hide on settings page) */}
        {!isSettingsPage && <ConversationSidebar open={leftSidebarOpen} />}
        
        {/* Main Chat Area */}
        <main className="flex-1 flex flex-col min-h-0">
          {/* Header */}
          <header className="h-14 border-b bg-card flex items-center justify-between px-4">
            <div className="flex items-center gap-2">
              {isSettingsPage ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/chat')}
                  className="h-8 w-8 p-0"
                >
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
                  className="h-8 w-8 p-0"
                >
                  <MessageSquare className="h-4 w-4" />
                </Button>
              )}
              <h1 className="font-semibold text-foreground">{pageTitle}</h1>
            </div>
            {!isSettingsPage && <ModelSelector />}
          </header>
          
          <div className="flex-1 min-h-0">
            {isSettingsPage ? (
              <div className="h-full flex items-center justify-center p-8">
                <div className="text-center space-y-4">
                  <Settings className="h-12 w-12 mx-auto text-muted-foreground" />
                  <h2 className="text-2xl font-semibold">Settings Page</h2>
                  <p className="text-muted-foreground max-w-md">
                    Settings functionality will be implemented here. 
                    You can now navigate between conversations and settings without issues.
                  </p>
                  <Button 
                    onClick={() => navigate('/chat')}
                    className="mt-4"
                  >
                    <ArrowLeft className="h-4 w-4 mr-2" />
                    Back to Chat
                  </Button>
                </div>
              </div>
            ) : (
              <ChatInterface key={conversationId || 'new'} />
            )}
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}