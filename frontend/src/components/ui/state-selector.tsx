import React from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { X, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StateOption {
  id: string;
  name: string;
  stateName?: string;
  stateId?: string;
}

export interface StateSelectorProps {
  title: string;
  states: StateOption[];
  selectedState: StateOption | null;
  onStateChange: (state: StateOption | null) => void;
  onClose?: () => void;
  className?: string;
}

export const StateSelector: React.FC<StateSelectorProps> = ({
  title,
  states,
  selectedState,
  onStateChange,
  onClose,
  className
}) => {
  return (
    <Card className={cn("w-64", className)}>
      <CardContent className="p-0">
        <div className="p-3 border-b flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4" />
            <span className="font-medium text-sm">{title}</span>
          </div>
          {onClose && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>

        <ScrollArea className="max-h-48">
          <div className="p-2">
            {states.map(state => (
              <button
                key={state.id}
                className={cn(
                  "w-full text-left px-3 py-2 rounded-md text-sm transition-colors hover:bg-accent",
                  selectedState?.id === state.id && "bg-primary/10 text-primary"
                )}
                onClick={() => onStateChange(state)}
              >
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-green-500 flex-shrink-0"></div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{state.name}</div>
                    {state.stateName && (
                      <div className="text-xs text-muted-foreground truncate">
                        {state.stateName}
                      </div>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};