import React from "react";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Copy, Flag, Target, Lightbulb, Boxes, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";
import { cn } from "@/lib/utils";

export type FeatureCardProps = {
  title: string;
  description?: string;
  displayBugNo?: string;
  problemStatement?: string;
  objective?: string;
  successCriteria?: string[];
  goals?: string[];
  painPoints?: string[];
  inScope?: string[];
  outOfScope?: string[];
  functionalRequirements?: { requirementId: string; priorityLevel: string; description: string }[];
  nonFunctionalRequirements?: { requirementId: string; priorityLevel: string; description: string }[];
  dependencies?: string[];
  risks?: { riskId: string; problemLevel: string; impactLevel: string; description: string; strategy: string }[];
  priority?: string | null;
  state?: string | null;
  epic?: string | null;
  module?: string | null;
  labels?: string[];
  link?: string | null;
  onCopy?: (field: "title" | "description" | "link") => void;
  className?: string;
};

export const FeatureCard: React.FC<FeatureCardProps> = ({
  title,
  description = "",
  displayBugNo,
  problemStatement,
  objective,
  successCriteria = [],
  goals = [],
  painPoints = [],
  inScope = [],
  outOfScope = [],
  functionalRequirements = [],
  nonFunctionalRequirements = [],
  dependencies = [],
  risks = [],
  priority,
  state,
  epic,
  module,
  labels = [],
  link,
  onCopy,
  className
}) => {
  const [copied, setCopied] = React.useState<null | "title" | "description" | "link">(null);

  const handleCopy = async (field: "title" | "description" | "link") => {
    try {
      const text = field === "title" ? title : field === "description" ? description : link || "";
      if (!text) return;
      await navigator.clipboard.writeText(text);
      setCopied(field);
      onCopy?.(field);
      window.setTimeout(() => setCopied(null), 2000);
    } catch {
      // Clipboard write failed, ignore silently
    }
  };

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Lightbulb className="h-4 w-4" />
              <span>Feature</span>
              {displayBugNo && (
                <Badge variant="outline" className="text-xs">{displayBugNo}</Badge>
              )}
            </div>
            <div className="mt-0.5 text-base font-semibold leading-snug break-words">{title}</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {priority && priority !== "NONE" && (
                <Badge variant="outline" className="text-xs gap-1">
                  <Flag className="h-3 w-3" />
                  {priority}
                </Badge>
              )}
              {state && (
                <Badge variant="outline" className="text-xs gap-1">
                  <Target className="h-3 w-3" />
                  {state}
                </Badge>
              )}
              {epic && (
                <Badge variant="secondary" className="text-xs gap-1">
                  <Target className="h-3 w-3" />
                  {epic}
                </Badge>
              )}
              {module && (
                <Badge variant="secondary" className="text-xs gap-1">
                  <Boxes className="h-3 w-3" />
                  {module}
                </Badge>
              )}
              {labels.map((label) => (
                <Badge key={label} variant="secondary" className="text-xs">
                  {label}
                </Badge>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1 text-xs">
            {link && (
              <a
                href={link}
                target="_blank"
                rel="noopener noreferrer"
                className={cn("px-2 py-1 rounded hover:bg-muted transition-colors text-primary")}
              >
                View feature
              </a>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2"
              onClick={() => handleCopy(link ? "link" : "title")}
              title="Copy"
            >
              <Copy className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        {description && (
          <div>
            <h4 className="text-sm font-medium mb-1">Description</h4>
            <SafeMarkdown content={description} className="prose prose-sm max-w-none dark:prose-invert" />
          </div>
        )}

        {problemStatement && (
          <div>
            <h4 className="text-sm font-medium mb-1">Problem Statement</h4>
            <p className="text-sm text-muted-foreground">{problemStatement}</p>
          </div>
        )}

        {objective && (
          <div>
            <h4 className="text-sm font-medium mb-1">Objective</h4>
            <p className="text-sm text-muted-foreground">{objective}</p>
          </div>
        )}

        {successCriteria.length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-1">Success Criteria</h4>
            <ul className="list-disc list-inside text-sm text-muted-foreground">
              {successCriteria.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          </div>
        )}

        {(goals.length > 0 || painPoints.length > 0) && (
          <div className="grid grid-cols-2 gap-4">
            {goals.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-1">Goals</h4>
                <ul className="list-disc list-inside text-sm text-muted-foreground">
                  {goals.map((g, i) => <li key={i}>{g}</li>)}
                </ul>
              </div>
            )}
            {painPoints.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-1">Pain Points</h4>
                <ul className="list-disc list-inside text-sm text-muted-foreground">
                  {painPoints.map((p, i) => <li key={i}>{p}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}

        {(inScope.length > 0 || outOfScope.length > 0) && (
          <div className="grid grid-cols-2 gap-4">
            {inScope.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-1 flex items-center gap-1">
                  <CheckCircle className="h-3.5 w-3.5 text-green-600" />
                  In Scope
                </h4>
                <ul className="list-disc list-inside text-sm text-muted-foreground">
                  {inScope.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}
            {outOfScope.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-1 flex items-center gap-1">
                  <XCircle className="h-3.5 w-3.5 text-red-600" />
                  Out of Scope
                </h4>
                <ul className="list-disc list-inside text-sm text-muted-foreground">
                  {outOfScope.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}

        {(functionalRequirements.length > 0 || nonFunctionalRequirements.length > 0) && (
          <div className="grid grid-cols-2 gap-4">
            {functionalRequirements.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-1">Functional Requirements</h4>
                <div className="space-y-1">
                  {functionalRequirements.map((fr, i) => (
                    <div key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                      <Badge variant="outline" className="text-xs shrink-0">{fr.requirementId}</Badge>
                      <span>{fr.description}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {nonFunctionalRequirements.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-1">Non-Functional Requirements</h4>
                <div className="space-y-1">
                  {nonFunctionalRequirements.map((nfr, i) => (
                    <div key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                      <Badge variant="outline" className="text-xs shrink-0">{nfr.requirementId}</Badge>
                      <span>{nfr.description}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {dependencies.length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-1">Dependencies</h4>
            <ul className="list-disc list-inside text-sm text-muted-foreground">
              {dependencies.map((d, i) => <li key={i}>{d}</li>)}
            </ul>
          </div>
        )}

        {risks.length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-1 flex items-center gap-1">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
              Risks & Mitigation
            </h4>
            <div className="space-y-2">
              {risks.map((risk, i) => (
                <div key={i} className="border rounded-lg p-2 text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="outline" className="text-xs">{risk.riskId}</Badge>
                    {risk.problemLevel && (
                      <Badge variant={risk.problemLevel === "HIGH" ? "destructive" : "secondary"} className="text-xs">
                        {risk.problemLevel} probability
                      </Badge>
                    )}
                    {risk.impactLevel && (
                      <Badge variant={risk.impactLevel === "HIGH" ? "destructive" : "secondary"} className="text-xs">
                        {risk.impactLevel} impact
                      </Badge>
                    )}
                  </div>
                  {risk.description && (
                    <p className="text-muted-foreground mb-1"><strong>Risk:</strong> {risk.description}</p>
                  )}
                  {risk.strategy && (
                    <p className="text-muted-foreground"><strong>Mitigation:</strong> {risk.strategy}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default FeatureCard;
