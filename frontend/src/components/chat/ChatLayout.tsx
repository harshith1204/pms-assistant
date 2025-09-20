import { ChatInterface } from "./ChatInterface";
import { ModelSelector } from "./ModelSelector";

export function ChatLayout() {
  return (
    <div className="h-screen flex w-full bg-background overflow-hidden">
      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-h-0">
        {/* Header */}
        <header className="h-14 border-b bg-card flex items-center justify-between px-4">
          <div className="flex items-center gap-2">
          </div>
          <ModelSelector />
        </header>

        <div className="flex-1 min-h-0">
          <ChatInterface />
        </div>
      </main>
    </div>
  );
}