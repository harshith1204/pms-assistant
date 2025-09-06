import { useState } from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { ConversationSidebar } from "./ConversationSidebar";
import { ChatInterface } from "./ChatInterface";
import { ModelSelector } from "./ModelSelector";
import { Button } from "@/components/ui/button";
import { MessageSquare } from "lucide-react";

export function ChatLayout() {
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);

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
            <ModelSelector />
          </header>
          
          <div className="flex-1 min-h-0">
            <ChatInterface />
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}