import * as React from "react";
import { DateRange } from "react-day-picker";

import { cn } from "@/lib/utils";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export interface DateRangePickerProps {
  date?: DateRange;
  onDateChange?: (date: DateRange | undefined) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  icon?: React.ReactNode;
}

export function DateRangePicker({
  date,
  onDateChange,
  placeholder = "Duration",
  className,
  disabled = false,
  icon,
}: DateRangePickerProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  const handleSelect = (range: DateRange | undefined) => {
    onDateChange?.(range);
    // Close the popover when both start and end dates are selected
    if (range?.from && range?.to) {
      setIsOpen(false);
    }
  };

  const formatDateRange = (dateRange: DateRange | undefined): string => {
    if (!dateRange?.from) return placeholder;

    if (dateRange.to) {
      return `${dateRange.from.toLocaleDateString()} - ${dateRange.to.toLocaleDateString()}`;
    }

    return dateRange.from.toLocaleDateString();
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <div
          className={cn(
            "inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs text-muted-foreground bg-background cursor-pointer hover:bg-muted/50 hover:border-primary/20 transition-colors",
            !date && "text-muted-foreground",
            date && "text-foreground border-primary/20 bg-primary/5",
            disabled && "cursor-not-allowed opacity-50",
            className
          )}
          onClick={() => !disabled && setIsOpen(!isOpen)}
        >
          {icon}
          <span className="whitespace-nowrap">{formatDateRange(date)}</span>
        </div>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          initialFocus
          mode="range"
          defaultMonth={date?.from}
          selected={date}
          onSelect={handleSelect}
          numberOfMonths={2}
        />
      </PopoverContent>
    </Popover>
  );
}
