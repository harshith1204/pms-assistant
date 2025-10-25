import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { DayPicker } from "react-day-picker";

import { cn } from "@/lib/utils";

export type CalendarProps = React.ComponentProps<typeof DayPicker>;

function Calendar({ className, classNames, showOutsideDays = true, ...props }: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn("p-4", className)}
      classNames={{
        months: "flex flex-col lg:flex-row space-y-4 lg:space-y-0 lg:space-x-4",
        month: "space-y-3",
        caption: "flex justify-between items-center px-2",
        caption_label: "text-sm font-semibold text-foreground",
        nav: "flex items-center space-x-1",
        nav_button: cn(
          "inline-flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors",
          "bg-transparent border-0 p-0"
        ),
        nav_button_previous: "",
        nav_button_next: "",
        table: "w-full border-collapse",
        head_row: "grid grid-cols-7 mb-2",
        head_cell: "h-8 w-8 text-center text-xs font-medium text-muted-foreground uppercase tracking-wide",
        row: "grid grid-cols-7 gap-0",
        cell: "h-8 w-8 text-center text-sm p-0 relative",
        day: cn(
          "inline-flex items-center justify-center h-8 w-8 rounded-md text-sm font-medium transition-colors cursor-pointer",
          "text-foreground hover:bg-muted hover:text-foreground focus:bg-muted focus:text-foreground"
        ),
        day_range_end: "rounded-r-md",
        day_selected: cn(
          "bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground",
          "focus:bg-primary focus:text-primary-foreground"
        ),
        day_today: "bg-accent text-accent-foreground font-semibold",
        day_outside: "text-muted-foreground/50 hover:text-muted-foreground/75",
        day_disabled: "text-muted-foreground/30 cursor-not-allowed hover:bg-transparent",
        day_range_middle: "bg-accent/50 text-accent-foreground",
        day_hidden: "invisible",
        ...classNames,
      }}
      components={{
        IconLeft: ({ ..._props }) => <ChevronLeft className="h-4 w-4" />,
        IconRight: ({ ..._props }) => <ChevronRight className="h-4 w-4" />,
      }}
      {...props}
    />
  );
}
Calendar.displayName = "Calendar";

export { Calendar };
