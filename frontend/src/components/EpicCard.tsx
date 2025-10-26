import React from \"react\";
import { Card, CardContent, CardHeader } from \"@/components/ui/card\";
import { Button } from \"@/components/ui/button\";
import { Badge } from \"@/components/ui/badge\";
import { Copy, CalendarClock, Tag, Flag } from \"lucide-react\";
import SafeMarkdown from \"@/components/SafeMarkdown\";
import { cn } from \"@/lib/utils\";

export type EpicCardProps = {
  title: string;
  description?: string;
  projectName?: string;
  status?: string;
  priority?: string;
  startDate?: string;
  endDate?: string;
  link?: string;
  onCopy?: (field: \"title\" | \"description\" | \"link\") => void;
  className?: string;
};

export const EpicCard: React.FC<EpicCardProps> = ({
  title,
  description = \"\",
  projectName,
  status,
  priority,
  startDate,
  endDate,
  link,
  onCopy,
  className
}) => {
  const [copied, setCopied] = React.useState<null | \"title\" | \"description\" | \"link\">(null);

  const handleCopy = async (field: \"title\" | \"description\" | \"link\") => {
    try {
      const text = field === \"title\" ? title : field === \"description\" ? description : link || \"\";
      if (!text) return;
      await navigator.clipboard.writeText(text);
      setCopied(field);
      onCopy?.(field);
      window.setTimeout(() => setCopied(null), 2000);
    } catch {}
  };

  const getPriorityColor = (priority?: string) => {
    switch (priority?.toUpperCase()) {
      case \"URGENT\":
        return \"bg-red-500\";
      case \"HIGH\":
        return \"bg-orange-500\";
      case \"MEDIUM\":
        return \"bg-yellow-500\";
      case \"LOW\":
        return \"bg-green-500\";
      default:
        return \"bg-gray-500\";
    }
  };

  const getStatusColor = (status?: string) => {
    switch (status?.toUpperCase()) {
      case \"NEW\":
        return \"bg-blue-100 text-blue-800\";
      case \"IN_PROGRESS\":
        return \"bg-yellow-100 text-yellow-800\";
      case \"COMPLETED\":
        return \"bg-green-100 text-green-800\";
      case \"CANCELLED\":
        return \"bg-gray-100 text-gray-800\";
      default:
        return \"bg-gray-100 text-gray-800\";
    }
  };

  return (
    <Card className={className}>
      <CardHeader className=\"pb-3\">
        <div className=\"flex items-center justify-between gap-2\">
          <div className=\"min-w-0\">
            <div className=\"flex items-center gap-2\">
              <span className=\"text-sm font-medium text-muted-foreground\">Epic</span>
              {projectName && (
                <span className=\"text-xs text-muted-foreground\">
                  • {projectName}
                </span>
              )}
            </div>
            <div className=\"mt-0.5 text-base font-semibold leading-snug break-words\">{title}</div>
            <div className=\"mt-2 flex flex-wrap gap-2\">
              {status && (
                <Badge variant=\"outline\" className={`text-xs ${getStatusColor(status)}`}>
                  {status}
                </Badge>
              )}
              {priority && (
                <Badge variant=\"outline\" className=\"text-xs gap-1\">
                  <Flag className={`h-3 w-3 ${getPriorityColor(priority)}`} />
                  {priority}
                </Badge>
              )}
              {(startDate || endDate) && (
                <Badge variant=\"outline\" className=\"text-xs gap-1\">
                  <CalendarClock className=\"h-3 w-3\" />
                  {startDate && <span>{new Date(startDate).toLocaleDateString()}</span>}
                  {startDate && endDate && <span> → </span>}
                  {endDate && <span>{new Date(endDate).toLocaleDateString()}</span>}
                </Badge>
              )}
            </div>
          </div>
          <div className=\"flex items-center gap-1 text-xs\">
            {link && (
              <a
                href={link}
                target=\"_blank\"
                rel=\"noopener noreferrer\"
                className={cn(\"px-2 py-1 rounded hover:bg-muted transition-colors text-primary\")}
              >
                View epic
              </a>
            )}
            {link && (
              <Button
                variant=\"ghost\"
                size=\"sm\"
                className=\"h-7 px-2\"
                onClick={() => handleCopy(\"link\")}
                title=\"Copy link\"
              >
                <Copy className=\"h-3.5 w-3.5\" />
              </Button>
            )}
            {!link && (
              <Button
                variant=\"ghost\"
                size=\"sm\"
                className=\"h-7 px-2\"
                onClick={() => handleCopy(\"title\")}
                title=\"Copy title\"
              >
                <Copy className=\"h-3.5 w-3.5\" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      {description && (
        <CardContent className=\"pt-0\">
          <SafeMarkdown content={description} className=\"prose prose-sm max-w-none dark:prose-invert\" />
        </CardContent>
      )}
    </Card>
  );
};

export default EpicCard;