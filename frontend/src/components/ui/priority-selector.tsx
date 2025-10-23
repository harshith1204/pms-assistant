import React from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { X, Flag } from "lucide-react";
import { cn } from "@/lib/utils";

export type PriorityLevel = 'None' | 'Low' | 'Medium' | 'High' | 'Urgent';

export interface PrioritySelectorProps {
  selectedPriority: PriorityLevel;
  onPriorityChange: (priority: PriorityLevel) => void;
  onClose?: () => void;
  className?: string;
}

export const PrioritySelector: React.FC<PrioritySelectorProps> = ({
  selectedPriority,
  onPriorityChange,
  onClose,
  className
}) => {
  const priorities: { level: PriorityLevel; color: string; bgColor: string }[] = [
    { level: 'None', color: 'text-gray-600', bgColor: 'bg-gray-100' },
    { level: 'Low', color: 'text-green-600', bgColor: 'bg-green-100' },
    { level: 'Medium', color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
    { level: 'High', color: 'text-orange-600', bgColor: 'bg-orange-100' },
    { level: 'Urgent', color: 'text-red-600', bgColor: 'bg-red-100' },
  ];

  return (
    <Card className={cn("w-48", className)}>
      <CardContent className="p-0">
        <div className="p-3 border-b flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Flag className="h-4 w-4" />
            <span className="font-medium text-sm">Priority</span>
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

        <div className="p-2">
          {priorities.map(({ level, color, bgColor }) => (
            <button
              key={level}
              className={cn(
                "w-full text-left px-3 py-2 rounded-md text-sm transition-colors hover:bg-accent",
                selectedPriority === level && "bg-primary/10 text-primary"
              )}
              onClick={() => onPriorityChange(level)}
            >
              <div className="flex items-center gap-2">
                <div className={cn("w-3 h-3 rounded-full", bgColor)}></div>
                <span>{level}</span>
              </div>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};