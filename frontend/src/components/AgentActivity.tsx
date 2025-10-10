import { useMemo, useState } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Dot,
  Loader2,
  XCircle,
  Clipboard,
  FileInput,
  FileOutput,
} from "lucide-react";

export type ActivityStep = {
  id: string;
  title: string;
  status: "running" | "success" | "error" | "note";
  subtitle?: string;
  input?: string;
  output?: string;
  startedAt?: string; // ISO timestamp
  endedAt?: string; // ISO timestamp
};

export type AgentActivityProps = {
  summary: string;
  bullets?: string[];
  doneLabel?: string;
  body?: string;
  defaultOpen?: boolean;
  className?: string;
  steps?: ActivityStep[];
};

export const AgentActivity = ({
  summary,
  bullets = [],
  doneLabel = "Done",
  body,
  defaultOpen = false,
  className,
  steps = [],
}: AgentActivityProps) => {
  const [open, setOpen] = useState<boolean>(defaultOpen);
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({});

  const hasSteps = steps && steps.length > 0;

  const toggleExpanded = (id: string) => {
    setExpandedSteps((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const formatDuration = (start?: string, end?: string) => {
    if (!start) return undefined;
    try {
      const startMs = new Date(start).getTime();
      const endMs = end ? new Date(end).getTime() : Date.now();
      const diff = Math.max(0, endMs - startMs);
      if (diff < 1000) return `${diff}ms`;
      const seconds = Math.round(diff / 1000);
      if (seconds < 60) return `${seconds}s`;
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return `${mins}m ${secs}s`;
    } catch {
      return undefined;
    }
  };

  const StepsList = useMemo(() => (
    <div className="space-y-2">
      {steps.map((step) => {
        const isOpen = !!expandedSteps[step.id];
        const duration = formatDuration(step.startedAt, step.endedAt);
        const isInteractive = !!(step.input || step.output);
        return (
          <div key={step.id} className="rounded-md border border-muted/40 bg-muted/10">
            <div className="flex items-center gap-2 p-2">
              {/* Status icon */}
              <div className="shrink-0">
                {step.status === "running" && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
                {step.status === "success" && <CheckCircle2 className="h-4 w-4 text-emerald-600" />}
                {step.status === "error" && <XCircle className="h-4 w-4 text-red-600" />}
                {step.status === "note" && <Dot className="h-5 w-5 text-muted-foreground" />}
              </div>

              {/* Title and meta */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <div className="truncate text-sm font-medium text-foreground/90">{step.title}</div>
                  {duration && (
                    <div className="text-[11px] text-muted-foreground">{duration}</div>
                  )}
                </div>
                {step.subtitle && (
                  <div className="truncate text-xs text-muted-foreground">{step.subtitle}</div>
                )}
              </div>

              {/* Expand/copy controls */}
              {isInteractive && (
                <div className="flex items-center gap-1">
                  {(step.input || step.output) && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/20"
                      onClick={() => toggleExpanded(step.id)}
                    >
                      {isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                      <span className="ml-1">Details</span>
                    </Button>
                  )}
                </div>
              )}
            </div>

            {/* Details */}
            {isOpen && (
              <div className="border-t border-muted/40 p-2 space-y-2 bg-background/40">
                {step.input && (
                  <div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                      <FileInput className="h-3.5 w-3.5" /> <span>Input</span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 px-1 ml-auto text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted/20"
                        onClick={async () => {
                          try { await navigator.clipboard.writeText(step.input!); } catch {}
                        }}
                      >
                        <Clipboard className="h-3 w-3 mr-1" /> Copy
                      </Button>
                    </div>
                    <pre className="whitespace-pre-wrap text-xs leading-relaxed text-foreground/90 bg-muted/20 rounded p-2 max-h-40 overflow-auto">{step.input}</pre>
                  </div>
                )}
                {step.output && (
                  <div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                      <FileOutput className="h-3.5 w-3.5" /> <span>Output</span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 px-1 ml-auto text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted/20"
                        onClick={async () => {
                          try { await navigator.clipboard.writeText(step.output!); } catch {}
                        }}
                      >
                        <Clipboard className="h-3 w-3 mr-1" /> Copy
                      </Button>
                    </div>
                    <pre className="whitespace-pre-wrap text-xs leading-relaxed text-foreground/90 bg-muted/20 rounded p-2 max-h-40 overflow-auto">{step.output}</pre>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  ), [steps, expandedSteps]);

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
          {hasSteps ? (
            <>{StepsList}</>
          ) : (
            <>
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
            </>
          )}
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
};

