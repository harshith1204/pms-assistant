import React, { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Loader2, CalendarClock, Search, Check, Calendar } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { getAllCycles, type Cycle } from "@/api/cycles";

export type CycleSelectorProps = {
  projectId?: string;
  selectedCycle?: Cycle | null;
  onCycleSelect: (cycle: Cycle | null) => void;
  trigger?: React.ReactNode;
  className?: string;
};

export const CycleSelector: React.FC<CycleSelectorProps> = ({
  projectId,
  selectedCycle,
  onCycleSelect,
  trigger,
  className
}) => {
  const [open, setOpen] = useState(false);
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    if (open) {
      loadCycles();
    }
  }, [open, projectId]);

  const loadCycles = async () => {
    setLoading(true);
    try {
      const response = await getAllCycles(projectId);
      setCycles(response.data);
    } catch (error) {
      console.error("Failed to load cycles:", error);
      setCycles([]);
    } finally {
      setLoading(false);
    }
  };

  const filteredCycles = cycles.filter(cycle =>
    cycle.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (cycle.description && cycle.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const handleCycleSelect = (cycle: Cycle) => {
    onCycleSelect(cycle);
    setOpen(false);
  };

  const handleClearSelection = () => {
    onCycleSelect(null);
    setOpen(false);
  };

  const formatDateRange = (cycle: Cycle) => {
    if (!cycle.startDate && !cycle.endDate) return null;

    const startDate = cycle.startDate ? new Date(cycle.startDate).toLocaleDateString() : null;
    const endDate = cycle.endDate ? new Date(cycle.endDate).toLocaleDateString() : null;

    if (startDate && endDate) {
      return `${startDate} → ${endDate}`;
    } else if (startDate) {
      return `From ${startDate}`;
    } else if (endDate) {
      return `Until ${endDate}`;
    }
    return null;
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm" className={cn("gap-2", className)}>
            <CalendarClock className="h-4 w-4" />
            {selectedCycle ? selectedCycle.title : "Select Cycle"}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CalendarClock className="h-5 w-5" />
            Select Cycle
          </DialogTitle>
        </DialogHeader>

        <div className="flex items-center gap-2 py-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
            <Input
              placeholder="Search cycles..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>
          {selectedCycle && (
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
          ) : filteredCycles.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {searchTerm ? "No cycles found matching your search." : "No cycles available."}
            </div>
          ) : (
            <div className="space-y-3">
              {filteredCycles.map((cycle) => (
                <Card
                  key={cycle.id}
                  className={cn(
                    "cursor-pointer transition-colors hover:bg-muted/50",
                    selectedCycle?.id === cycle.id && "ring-2 ring-primary"
                  )}
                  onClick={() => handleCycleSelect(cycle)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 mt-0.5">
                        {selectedCycle?.id === cycle.id && (
                          <Check className="h-4 w-4 text-primary" />
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-medium truncate">{cycle.title}</h4>
                          {selectedCycle?.id === cycle.id && (
                            <Check className="h-4 w-4 text-primary flex-shrink-0" />
                          )}
                        </div>

                        {formatDateRange(cycle) && (
                          <div className="flex items-center gap-1 mb-2">
                            <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="text-xs text-muted-foreground">
                              {formatDateRange(cycle)}
                            </span>
                          </div>
                        )}

                        {cycle.description && (
                          <p className="text-sm text-muted-foreground line-clamp-2">
                            {cycle.description}
                          </p>
                        )}

                        {cycle.link && (
                          <div className="mt-2">
                            <a
                              href={cycle.link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-primary hover:underline"
                              onClick={(e) => e.stopPropagation()}
                            >
                              View cycle →
                            </a>
                          </div>
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

export default CycleSelector;