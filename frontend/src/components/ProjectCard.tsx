import React from "react";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Copy, Globe, Lock, Users, FolderOpen } from "lucide-react";
import { cn } from "@/lib/utils";

export type ProjectCardProps = {
  name: string;
  projectDisplayId?: string;
  description?: string;
  imageUrl?: string;
  icon?: string;
  access?: "PUBLIC" | "PRIVATE";
  leadName?: string;
  link?: string | null;
  onCopy?: (field: "name" | "description" | "link") => void;
  className?: string;
};

export const ProjectCard: React.FC<ProjectCardProps> = ({
  name,
  projectDisplayId,
  description = "",
  imageUrl,
  icon = "😊",
  access = "PUBLIC",
  leadName,
  link,
  onCopy,
  className
}) => {
  const [copied, setCopied] = React.useState<null | "name" | "description" | "link">(null);

  const handleCopy = async (field: "name" | "description" | "link") => {
    try {
      const text = field === "name" ? name : field === "description" ? description : link || "";
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
    <Card className={cn("overflow-hidden", className)}>
      {imageUrl && (
        <div className="relative h-32 bg-gradient-to-r from-gray-700 to-gray-900">
          <img
            src={imageUrl}
            alt={`${name} cover`}
            className="w-full h-full object-cover opacity-70"
          />
          <div className="absolute bottom-2 left-2 h-10 w-10 text-2xl bg-white/90 rounded-lg flex items-center justify-center">
            {icon}
          </div>
        </div>
      )}
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <FolderOpen className="h-4 w-4" />
              <span>Project</span>
              {projectDisplayId && (
                <Badge variant="outline" className="text-xs">{projectDisplayId}</Badge>
              )}
            </div>
            <div className="mt-0.5 text-base font-semibold leading-snug break-words flex items-center gap-2">
              {!imageUrl && <span className="text-xl">{icon}</span>}
              {name}
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge variant={access === "PUBLIC" ? "secondary" : "outline"} className="text-xs gap-1">
                {access === "PUBLIC" ? (
                  <>
                    <Globe className="h-3 w-3" />
                    Public
                  </>
                ) : (
                  <>
                    <Lock className="h-3 w-3" />
                    Private
                  </>
                )}
              </Badge>
              {leadName && (
                <Badge variant="outline" className="text-xs gap-1">
                  <Users className="h-3 w-3" />
                  Lead: {leadName}
                </Badge>
              )}
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
                View project
              </a>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2"
              onClick={() => handleCopy(link ? "link" : "name")}
              title="Copy"
            >
              <Copy className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardHeader>
      {description && (
        <CardContent className="pt-0">
          <p className="text-sm text-muted-foreground">{description}</p>
        </CardContent>
      )}
    </Card>
  );
};

export default ProjectCard;
