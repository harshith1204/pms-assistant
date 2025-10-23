import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Calendar, X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface DatePickerProps {
  startDate?: string;
  endDate?: string;
  onStartDateChange?: (date: string) => void;
  onEndDateChange?: (date: string) => void;
  onClose?: () => void;
  className?: string;
}

export const DatePicker: React.FC<DatePickerProps> = ({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  onClose,
  className
}) => {
  const handleStartDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onStartDateChange?.(e.target.value);
  };

  const handleEndDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onEndDateChange?.(e.target.value);
  };

  const formatDateRange = () => {
    if (!startDate && !endDate) return 'Select dates';

    const start = startDate ? new Date(startDate).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric'
    }) : 'Start';
    const end = endDate ? new Date(endDate).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric'
    }) : 'End';

    return `${start} → ${end}`;
  };

  return (
    <Card className={cn("w-80", className)}>
      <CardContent className="p-0">
        <div className="p-4 border-b flex items-center justify-between">
          <h3 className="font-medium">Select dates</h3>
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

        <div className="p-4 space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Start Date</label>
            <Input
              type="date"
              value={startDate || ''}
              onChange={handleStartDateChange}
              className="w-full"
            />
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">End Date</label>
            <Input
              type="date"
              value={endDate || ''}
              onChange={handleEndDateChange}
              className="w-full"
            />
          </div>

          {startDate && endDate && new Date(startDate) > new Date(endDate) && (
            <div className="text-sm text-destructive">
              End date must be after start date
            </div>
          )}

          <div className="text-sm text-muted-foreground">
            <Calendar className="h-4 w-4 inline mr-1" />
            {formatDateRange()}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};