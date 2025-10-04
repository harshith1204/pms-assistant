import { useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Brain } from "lucide-react";

export function ModelSelector() {
  const [model, setModel] = useState("llama3-8b-8192");

  const availableModels = [
    { value: "llama3-8b-8192", label: "Llama 3 8B" },
    { value: "llama3-70b-8192", label: "Llama 3 70B" },
    { value: "mixtral-8x7b-32768", label: "Mixtral 8x7B" },
    { value: "gemma-7b-it", label: "Gemma 7B" },
  ];

  return (
    <div className="flex items-center gap-2 px-2">
      <Brain className="h-4 w-4 text-primary" />
      <Select value={model} onValueChange={setModel}>
        <SelectTrigger className="h-8 w-32">
          <SelectValue />
        </SelectTrigger>
        <SelectContent position="popper" side="bottom" sideOffset={8} className="z-50 bg-popover text-popover-foreground border border-border shadow-md">
          {availableModels.map((model) => (
            <SelectItem key={model.value} value={model.value}>
              {model.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
