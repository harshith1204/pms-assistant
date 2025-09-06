import { useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Brain } from "lucide-react";

export function ModelSelector() {
  const [model, setModel] = useState("gpt-4");

  const availableModels = [
    { value: "qwen3:0.6b", label: "Qwen 3" },
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
