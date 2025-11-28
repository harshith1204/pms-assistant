import { useRef, useState, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { SuggestedPrompts } from "./SuggestedPrompts";
import { Input } from "./ui/input";
import { VoiceRecorder } from "./VoiceRecorder";

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isLoading?: boolean;
  showSuggestedPrompts?: boolean;
}

export const ChatInput = ({ onSendMessage, isLoading = false, showSuggestedPrompts = true }: ChatInputProps) => {
  const [message, setMessage] = useState("");
  const textareaRef = useRef(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      onSendMessage(message);
      setMessage("");
    }
  };

  const handleChange = (e) => {
    setMessage(e.target.value);
    autoResizeTextarea(e.target);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && e.shiftKey) {
      return;
    }

    if (e.key === 'Enter') {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const autoResizeTextarea = (textarea) => {
    textarea.style.height = '36px';
    textarea.style.height = Math.min(textarea.scrollHeight, 180) + 'px';
  };

  useEffect(() => {
    if (textareaRef.current) {
      autoResizeTextarea(textareaRef.current);
    }
  }, []);

  const handleSelectPrompt = (prompt: string) => {
    setMessage(prompt);
  };

  const handleTranscription = (transcribedText: string) => {
    // Append transcribed text to existing message or replace if empty
    const newMessage = message.trim()
      ? `${message} ${transcribedText}`
      : transcribedText;
    setMessage(newMessage);
  };

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit}>
        <div
          className={cn(
            "relative flex items-center rounded-2xl border border-input bg-card py-2 px-3",
            "shadow-lg transition-all duration-200",
            "focus-within:border-primary focus-within:shadow-[0_0_20px_rgba(168,85,247,0.2)]",
            "md:w-[75%] m-auto w-[96%] mt-4 md:mt-0",
          )}
        >
          <VoiceRecorder
            onTranscription={handleTranscription}
            disabled={isLoading}
            className="h-7 w-7 shrink-0 mr-2"
          />
          <textarea
            value={message}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask me to create pages, tasks, or help with project management..."
            className="min-h-[36px] flex items-center max-h-[180px] resize-none border-0 bg-transparent px-0 py-0.5 text-base text-foreground scrollbar-thin flex-1 outline-none focus:outline-none focus:ring-0 focus:ring-offset-0 ring-0 ring-offset-0"
            disabled={isLoading}
            ref={textareaRef} 
          />
          <Button
            type="submit"
            size="icon"
            disabled={!message.trim() || isLoading}
            className={cn(
              "h-7 w-7 shrink-0 rounded-full ml-2",
              "bg-gradient-to-r from-primary to-accent",
              "hover:shadow-[0_0_20px_rgba(168,85,247,0.4)]",
              "transition-all duration-200",
              "disabled:opacity-50"
            )}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </form>

      {showSuggestedPrompts && <SuggestedPrompts onSelectPrompt={handleSelectPrompt} />}
    </div>
  );
};
