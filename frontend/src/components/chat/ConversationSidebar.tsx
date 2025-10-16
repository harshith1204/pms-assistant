import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Plus, Search, MessageCircle, Clock, Trash2, Settings } from "lucide-react";

interface ConversationSidebarProps {
  open: boolean;
}

interface Conversation {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: string;
  isActive?: boolean;
}

const mockConversations: Conversation[] = [
  {
    id: "1",
    title: "Database Integration Help",
    lastMessage: "The error indicates the database name is invalid...",
    timestamp: "2 minutes ago",
    isActive: true,
  },
  {
    id: "2", 
    title: "Project Setup Questions",
    lastMessage: "I can help you set up your project structure...",
    timestamp: "1 hour ago",
  },
  {
    id: "3",
    title: "API Development",
    lastMessage: "Let's create a REST API with proper authentication...",
    timestamp: "Yesterday",
  },
  {
    id: "4",
    title: "UI Design Discussion",
    lastMessage: "Here's a modern approach to your dashboard design...",
    timestamp: "2 days ago",
  },
];

export function ConversationSidebar({ open }: ConversationSidebarProps) {
  const navigate = useNavigate();
  const { conversationId } = useParams();
  const [searchQuery, setSearchQuery] = useState("");
  const [conversations, setConversations] = useState(mockConversations);

  const filteredConversations = conversations.filter(conv =>
    conv.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    conv.lastMessage.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const deleteConversation = (id: string) => {
    setConversations(prev => prev.filter(conv => conv.id !== id));
    // If deleting the active conversation, navigate to home
    if (id === conversationId) {
      navigate('/chat');
    }
  };

  const handleNewConversation = () => {
    navigate('/chat');
  };

  const handleConversationClick = (id: string) => {
    navigate(`/chat/${id}`);
  };

  if (!open) return null;

  return (
    <aside className={cn(
      "w-80 border-r bg-card flex flex-col transition-all duration-200",
      !open && "w-0 overflow-hidden"
    )}>
      {/* Header */}
      <div className="p-4 border-b">
        <Button 
          className="w-full justify-start gap-2 mb-3" 
          size="sm"
          onClick={handleNewConversation}
        >
          <Plus className="h-4 w-4" />
          New Conversation
        </Button>
        
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Conversations List */}
      <ScrollArea className="flex-1">
        <div className="p-2">
          {filteredConversations.map((conversation, index) => {
            const isActive = conversationId === conversation.id;
            return (
              <div key={conversation.id}>
                <div 
                  className={cn(
                    "group relative p-3 rounded-lg cursor-pointer transition-colors hover:bg-muted/50",
                    isActive && "bg-muted"
                  )}
                  onClick={() => handleConversationClick(conversation.id)}
                >
                  <div className="flex items-start gap-3">
                    <div className={cn(
                      "rounded-full p-1.5 mt-0.5",
                      isActive ? "bg-primary" : "bg-muted-foreground/20"
                    )}>
                      <MessageCircle className={cn(
                        "h-3 w-3",
                        isActive ? "text-primary-foreground" : "text-muted-foreground"
                      )} />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-sm truncate">
                        {conversation.title}
                      </h3>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {conversation.lastMessage}
                      </p>
                      <div className="flex items-center gap-1 mt-2">
                        <Clock className="h-3 w-3 text-muted-foreground" />
                        <span className="text-xs text-muted-foreground">
                          {conversation.timestamp}
                        </span>
                      </div>
                    </div>
                    
                    <Button
                      variant="ghost"
                      size="sm"
                      className="opacity-0 group-hover:opacity-100 h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteConversation(conversation.id);
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
                
                {index < filteredConversations.length - 1 && (
                  <Separator className="my-1" />
                )}
              </div>
            );
          })}
        </div>
      </ScrollArea>

      {/* Footer with Settings button */}
      <div className="p-4 border-t">
        <Button 
          variant="outline" 
          className="w-full justify-start gap-2" 
          size="sm"
          onClick={() => navigate('/settings')}
        >
          <Settings className="h-4 w-4" />
          Settings
        </Button>
      </div>
    </aside>
  );
}