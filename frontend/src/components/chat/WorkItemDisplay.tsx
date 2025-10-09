import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Calendar, User, AlertCircle, CheckCircle2, Clock } from "lucide-react";

interface WorkItemData {
  title?: string;
  description?: string;
  status?: string;
  priority?: string;
  assignee?: string;
  due_date?: string;
  labels?: string[];
  id?: string;
  [key: string]: unknown;
}

interface WorkItemDisplayProps {
  data: WorkItemData;
}

export function WorkItemDisplay({ data }: WorkItemDisplayProps) {
  const getPriorityColor = (priority?: string) => {
    switch (priority?.toLowerCase()) {
      case "high":
      case "urgent":
        return "bg-red-500/10 text-red-500 border-red-500/20";
      case "medium":
        return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
      case "low":
        return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      default:
        return "bg-muted text-muted-foreground border-muted";
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status?.toLowerCase()) {
      case "completed":
      case "done":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "in progress":
      case "active":
        return <Clock className="h-4 w-4 text-blue-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
    }
  };

  return (
    <Card className="p-4 bg-gradient-to-br from-background to-muted/20 border-2 border-primary/20">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 space-y-1">
            {data.title && (
              <h3 className="text-lg font-semibold text-foreground leading-tight">
                {data.title}
              </h3>
            )}
            {data.id && (
              <p className="text-xs text-muted-foreground font-mono">ID: {data.id}</p>
            )}
          </div>
          
          {data.status && (
            <Badge variant="outline" className="flex items-center gap-1">
              {getStatusIcon(data.status)}
              {data.status}
            </Badge>
          )}
        </div>

        {/* Metadata */}
        <div className="flex flex-wrap gap-2">
          {data.priority && (
            <Badge variant="outline" className={getPriorityColor(data.priority)}>
              Priority: {data.priority}
            </Badge>
          )}
          
          {data.assignee && (
            <Badge variant="outline" className="flex items-center gap-1">
              <User className="h-3 w-3" />
              {data.assignee}
            </Badge>
          )}
          
          {data.due_date && (
            <Badge variant="outline" className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {new Date(data.due_date).toLocaleDateString()}
            </Badge>
          )}
        </div>

        {/* Labels */}
        {data.labels && data.labels.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {data.labels.map((label, index) => (
              <Badge key={index} variant="secondary" className="text-xs">
                {label}
              </Badge>
            ))}
          </div>
        )}

        {/* Description */}
        {data.description && (
          <>
            <Separator />
            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">Description</p>
              <div className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                {data.description}
              </div>
            </div>
          </>
        )}

        {/* Additional fields - show any other properties */}
        {(() => {
          const standardFields = ['title', 'description', 'status', 'priority', 'assignee', 'due_date', 'labels', 'id'];
          const additionalFields = Object.entries(data).filter(
            ([key]) => !standardFields.includes(key) && data[key] !== undefined && data[key] !== null
          );
          
          if (additionalFields.length === 0) return null;
          
          return (
            <>
              <Separator />
              <div className="space-y-2">
                <p className="text-sm font-medium text-muted-foreground">Additional Information</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {additionalFields.map(([key, value]) => (
                    <div key={key} className="p-2 bg-background/50 rounded border">
                      <span className="font-medium capitalize">{key.replace(/_/g, ' ')}:</span>{' '}
                      <span className="text-muted-foreground">
                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          );
        })()}
      </div>
    </Card>
  );
}

