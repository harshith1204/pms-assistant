import React, { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Target, Search, Check } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { getEpics, type Epic } from "@/api/epics";

export type EpicSelectorProps = {
  projectId: string;
  selectedEpic?: Epic | null;
  onEpicSelect: (epic: Epic | null) => void;
  trigger?: React.ReactNode;
  className?: string;
};

export const EpicSelector: React.FC<EpicSelectorProps> = ({
  projectId,
  selectedEpic,
  onEpicSelect,
  trigger,
  className,
}) => {
  const [open, setOpen] = useState(false);
  const [epics, setEpics] = useState<Epic[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    if (open && projectId) {
      loadEpics();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, projectId]);

  const loadEpics = async () => {
    setLoading(true);
    try {
      const response = await getEpics(projectId);
      setEpics(Array.isArray(response) ? response : []);
    } catch (error) {
      setEpics([]);
    } finally {
      setLoading(false);
    }
  };

  const filteredEpics = epics.filter(epic =>
    epic.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    epic.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleEpicSelect = (epic: Epic) => {
    onEpicSelect(epic);
    setOpen(false);
  };

  const handleClearSelection = () => {
    onEpicSelect(null);
    setOpen(false);
  };

  const formatDateRange = (epic: Epic) => {
    if (!epic.startDate && !epic.endDate) return null;

    try {
      const startDate = epic.startDate ? new Date(epic.startDate).toLocaleDateString() : null;
      const endDate = epic.endDate ? new Date(epic.endDate).toLocaleDateString() : null;

      if (startDate && endDate) {
        return `${startDate} → ${endDate}`;
      } else if (startDate) {
        return `From ${startDate}`;
      } else if (endDate) {
        return `Until ${endDate}`;
      }
    } catch (error) {
      // Error formatting date range
    }
    return null;
  };

  const getSelectedEpicText = () => {
    if (!selectedEpic) {
      return "Epic";
    }
    return selectedEpic.title;
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm" className={cn("gap-2", className)}>
            <Target className="h-4 w-4" />
            {getSelectedEpicText()}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Target className="h-5 w-5" />
            Select Epic
          </DialogTitle>
        </DialogHeader>

        <div className="flex items-center gap-2 py-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
            <Input
              placeholder="Search epics..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>
          {selectedEpic && (
            <Button variant="outline" size="sm" onClick={handleClearSelection}>
              Clear
            </Button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : filteredEpics.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {searchTerm ? "No epics found matching your search." : "No epics available."}
            </div>
          ) : (
            <div className="space-y-3">
              {filteredEpics.map((epic) => (
                <Card
                  key={epic.id}
                  className={cn(
                    "cursor-pointer transition-colors hover:bg-muted/50",
                    selectedEpic?.id === epic.id && "ring-2 ring-primary"
                  )}
                  onClick={() => handleEpicSelect(epic)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 mt-0.5">
                        {selectedEpic?.id === epic.id && (
                          <Check className="h-4 w-4 text-primary" />
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-medium truncate flex-1">{epic.title}</h4>
                          {epic.bugNo && (
                            <Badge variant="outline" className="text-xs">
                              {epic.bugNo}
                            </Badge>
                          )}
                        </div>

                        <div className="flex items-center gap-2 mb-2">
                          {epic.priority && epic.priority !== "NONE" && (
                            <Badge variant="secondary" className="text-xs">
                              {epic.priority}
                            </Badge>
                          )}
                          {epic.state?.name && (
                            <Badge variant="outline" className="text-xs">
                              {epic.state.name}
                            </Badge>
                          )}
                        </div>

                        {formatDateRange(epic) && (
                          <div className="flex items-center gap-1 mb-2">
                            <span className="text-xs text-muted-foreground">
                              {formatDateRange(epic)}
                            </span>
                          </div>
                        )}

                        {epic.description && (
                          <p className="text-sm text-muted-foreground line-clamp-2">
                            {epic.description}
                          </p>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EpicSelector;
