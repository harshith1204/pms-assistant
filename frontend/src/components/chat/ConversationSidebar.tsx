import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Plus, Search, MessageCircle, Clock, Trash2, RefreshCw } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface ConversationSidebarProps {
  open: boolean;
  activeConversationId?: string | null;
  onSelectConversation?: (id: string) => void;
  onNewConversation?: () => void;
}

interface Conversation {
  id: string;
  title: string;
  summary?: string;
  created_at?: Date;
  updated_at?: Date;
  isActive?: boolean;
}

export function ConversationSidebar({ open, activeConversationId, onSelectConversation, onNewConversation }: ConversationSidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const fetchConversations = async () => {
    setLoading(true);
    try {
      const response = await fetch(`http://${window.location.hostname}:8000/conversations`);
      const data = await response.json();
      
      const formattedConversations = data.conversations.map((conv: any) => ({
        id: conv.id,
        title: conv.title || "New Conversation",
        summary: conv.summary || "",
        created_at: conv.created_at ? new Date(conv.created_at) : new Date(),
        updated_at: conv.updated_at ? new Date(conv.updated_at) : new Date(),
        isActive: conv.id === activeConversationId,
      }));
      
      setConversations(formattedConversations);
    } catch (error) {
      console.error("Error fetching conversations:", error);
      toast({
        title: "Error",
        description: "Failed to load conversations",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchConversations();
    }
  }, [open]);

  useEffect(() => {
    // Update active conversation when it changes
    setConversations(prev => prev.map(conv => ({
      ...conv,
      isActive: conv.id === activeConversationId
    })));
  }, [activeConversationId]);

  const filteredConversations = conversations.filter(conv =>
    conv.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (conv.summary && conv.summary.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const deleteConversation = async (id: string) => {
    try {
      await fetch(`http://${window.location.hostname}:8000/conversations/${id}`, {
        method: "DELETE",
      });
      
      setConversations(prev => prev.filter(conv => conv.id !== id));
      
      toast({
        title: "Success",
        description: "Conversation deleted",
      });
    } catch (error) {
      console.error("Error deleting conversation:", error);
      toast({
        title: "Error",
        description: "Failed to delete conversation",
        variant: "destructive",
      });
    }
  };

  const formatTimestamp = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
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
          onClick={onNewConversation}
        >
          <Plus className="h-4 w-4" />
          New Conversation
        </Button>
        
        <Button 
          variant="outline"
          className="w-full justify-start gap-2 mb-3" 
          size="sm"
          onClick={fetchConversations}
          disabled={loading}
        >
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          Refresh
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
          {filteredConversations.map((conversation, index) => (
            <div key={conversation.id}>
              <div 
                className={cn(
                  "group relative p-3 rounded-lg cursor-pointer transition-colors hover:bg-muted/50",
                  conversation.isActive && "bg-muted"
                )}
                onClick={() => onSelectConversation?.(conversation.id)}
              >
                <div className="flex items-start gap-3">
                  <div className={cn(
                    "rounded-full p-1.5 mt-0.5",
                    conversation.isActive ? "bg-primary" : "bg-muted-foreground/20"
                  )}>
                    <MessageCircle className={cn(
                      "h-3 w-3",
                      conversation.isActive ? "text-primary-foreground" : "text-muted-foreground"
                    )} />
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-sm truncate">
                      {conversation.title}
                    </h3>
                    {conversation.summary && (
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {conversation.summary}
                      </p>
                    )}
                    <div className="flex items-center gap-1 mt-2">
                      <Clock className="h-3 w-3 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">
                        {conversation.updated_at ? formatTimestamp(conversation.updated_at) : "Unknown"}
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
          ))}
        </div>
      </ScrollArea>
    </aside>
  );
}