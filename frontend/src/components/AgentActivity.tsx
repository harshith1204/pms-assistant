import { useState } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, CheckCircle2, Dot } from "lucide-react";
import { cn } from "@/lib/utils";

export type AgentActivityProps = {
  summary: string;
  bullets?: string[];
  doneLabel?: string;
  body?: string;
  defaultOpen?: boolean;
  className?: string;
};

export const AgentActivity = ({
  summary,
  bullets = [],
  doneLabel = "Done",
  body,
  defaultOpen = false,
  className,
}: AgentActivityProps) => {
  const [open, setOpen] = useState<boolean>(defaultOpen);

  return (
    <div className={cn("space-y-2", className)}>
      <Collapsible open={open} onOpenChange={setOpen}>
        <div className="flex items-center gap-2">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs text-muted-foreground hover:bg-muted/20 hover:text-muted-foreground hover:font-semibold">
              {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              <span className="ml-1">{summary}</span>
            </Button>
          </CollapsibleTrigger>
        </div>

        <CollapsibleContent className="mt-2 space-y-2 ml-5">
          {bullets.length > 0 && (
            <div className="space-y-1">
              {bullets.map((b, idx) => (
                <div key={idx} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <Dot className="h-5 w-5 shrink-0" />
                  <span>{b}</span>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <span>{doneLabel}</span>
          </div>

          {body && (
            <p className="text-sm leading-relaxed text-foreground/90 mt-1">{body}</p>
          )}
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
};

