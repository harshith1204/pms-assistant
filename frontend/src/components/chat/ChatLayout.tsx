import { useState } from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { ConversationSidebar } from "./ConversationSidebar";
import { ConfigSidebar } from "./ConfigSidebar";
import { ChatInterface } from "./ChatInterface";
import { Button } from "@/components/ui/button";
import { Settings, MessageSquare } from "lucide-react";

export function ChatLayout() {
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(false);

  return (
    <SidebarProvider>
      <div className="h-screen flex w-full bg-background overflow-hidden">
        {/* Left Sidebar - Conversation History */}
        <ConversationSidebar open={leftSidebarOpen} />
        
        {/* Main Chat Area */}
        <main className="flex-1 flex flex-col min-h-0">
          {/* Header */}
          <header className="h-14 border-b bg-card flex items-center justify-between px-4">
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
                className="h-8 w-8 p-0"
              >
                <MessageSquare className="h-4 w-4" />
              </Button>
              <h1 className="font-semibold text-foreground">Agent Chat</h1>
            </div>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
              className="h-8 w-8 p-0"
            >
              <Settings className="h-4 w-4" />
            </Button>
          </header>
          
          <div className="flex-1 min-h-0">
            <ChatInterface />
          </div>
        </main>
        
        {/* Right Sidebar - Configuration */}
        <ConfigSidebar open={rightSidebarOpen} />
      </div>
    </SidebarProvider>
  );
}