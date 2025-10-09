import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Calendar, User, AlertCircle, CheckCircle2, Clock, Link as LinkIcon, Paperclip, Signal } from "lucide-react";
import { cn } from "@/lib/utils";

interface WorkItemData {
  title?: string;
  name?: string;
  description?: string;
  status?: string;
  state?: { name: string; color?: string };
  priority?: string;
  assignee?: string;
  assignees?: Array<{ id: string; display_name: string }>;
  due_date?: string;
  start_date?: string;
  target_date?: string;
  labels?: string[] | Array<{ name: string; color?: string }>;
  label_ids?: string[];
  id?: string;
  sequence_id?: number;
  project_id?: string;
  estimate_point?: number;
  link_count?: number;
  attachment_count?: number;
  sub_issues_count?: number;
  [key: string]: unknown;
}

interface WorkItemDisplayProps {
  data: WorkItemData;
}

export function WorkItemDisplay({ data }: WorkItemDisplayProps) {
  // Get display title
  const displayTitle = data.title || data.name;
  
  // Get display status
  const displayStatus = data.state?.name || data.status;
  const statusColor = data.state?.color;
  
  // Get display assignee
  const displayAssignee = data.assignee || data.assignees?.[0]?.display_name;
  
  const getPriorityIcon = (priority?: string) => {
    const level = priority?.toLowerCase();
    return (
      <Signal 
        className={cn(
          "h-3.5 w-3.5",
          level === "urgent" && "text-red-600",
          level === "high" && "text-orange-500",
          level === "medium" && "text-yellow-500",
          level === "low" && "text-blue-500",
          !level && "text-muted-foreground"
        )}
      />
    );
  };

  const getPriorityColor = (priority?: string) => {
    switch (priority?.toLowerCase()) {
      case "urgent":
        return "bg-red-500/10 text-red-600 border-red-500/20";
      case "high":
        return "bg-orange-500/10 text-orange-600 border-orange-500/20";
      case "medium":
        return "bg-yellow-500/10 text-yellow-600 border-yellow-500/20";
      case "low":
        return "bg-blue-500/10 text-blue-600 border-blue-500/20";
      default:
        return "bg-muted text-muted-foreground border-muted";
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status?.toLowerCase()) {
      case "completed":
      case "done":
        return <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />;
      case "in progress":
      case "active":
      case "started":
        return <Clock className="h-3.5 w-3.5 text-blue-600" />;
      default:
        return <AlertCircle className="h-3.5 w-3.5 text-muted-foreground" />;
    }
  };

  return (
    <Card className="p-0 bg-background border border-border hover:border-primary/30 transition-colors">
      <div className="p-4 space-y-3">
        {/* Header with ID and Title */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            {data.project_id && data.sequence_id && (
              <span className="text-xs font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded">
                {data.project_id}-{data.sequence_id}
              </span>
            )}
            {displayStatus && (
              <Badge 
                variant="outline" 
                className="flex items-center gap-1.5 text-xs"
                style={statusColor ? { 
                  borderColor: `${statusColor}40`,
                  color: statusColor,
                  backgroundColor: `${statusColor}10`
                } : undefined}
              >
                {getStatusIcon(displayStatus)}
                {displayStatus}
              </Badge>
            )}
          </div>
          
          {displayTitle && (
            <h3 className="text-base font-medium text-foreground leading-snug line-clamp-2">
              {displayTitle}
            </h3>
          )}
        </div>

        {/* Properties Row */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {data.priority && (
            <Badge variant="outline" className={cn("flex items-center gap-1.5", getPriorityColor(data.priority))}>
              {getPriorityIcon(data.priority)}
              {data.priority}
            </Badge>
          )}
          
          {displayAssignee && (
            <Badge variant="outline" className="flex items-center gap-1.5">
              <User className="h-3 w-3" />
              {displayAssignee}
            </Badge>
          )}
          
          {(data.target_date || data.due_date) && (
            <Badge variant="outline" className="flex items-center gap-1.5">
              <Calendar className="h-3 w-3" />
              {new Date(data.target_date || data.due_date!).toLocaleDateString()}
            </Badge>
          )}

          {data.estimate_point !== undefined && (
            <Badge variant="outline" className="flex items-center gap-1.5">
              <span className="font-mono">{data.estimate_point}</span>
              <span className="text-muted-foreground">pts</span>
            </Badge>
          )}
        </div>

        {/* Labels */}
        {data.labels && data.labels.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {data.labels.map((label, index) => {
              const labelObj = typeof label === 'string' ? { name: label } : label;
              return (
                <Badge 
                  key={index} 
                  className="text-xs px-2 py-0.5"
                  style={labelObj.color ? {
                    backgroundColor: `${labelObj.color}20`,
                    color: labelObj.color,
                    borderColor: `${labelObj.color}40`
                  } : undefined}
                >
                  {labelObj.name}
                </Badge>
              );
            })}
          </div>
        )}

        {/* Footer - Counts */}
        {(data.link_count || data.attachment_count || data.sub_issues_count) && (
          <>
            <Separator />
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              {data.sub_issues_count !== undefined && data.sub_issues_count > 0 && (
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>{data.sub_issues_count} sub-issues</span>
                </div>
              )}
              {data.link_count !== undefined && data.link_count > 0 && (
                <div className="flex items-center gap-1.5">
                  <LinkIcon className="h-3.5 w-3.5" />
                  <span>{data.link_count}</span>
                </div>
              )}
              {data.attachment_count !== undefined && data.attachment_count > 0 && (
                <div className="flex items-center gap-1.5">
                  <Paperclip className="h-3.5 w-3.5" />
                  <span>{data.attachment_count}</span>
                </div>
              )}
            </div>
          </>
        )}

        {/* Description */}
        {data.description && (
          <>
            <Separator />
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground">Description</p>
              <div 
                className="text-sm text-foreground/90 leading-relaxed prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: data.description }}
              />
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
