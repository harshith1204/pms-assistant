import React, { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Lightbulb, Search, Check } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { getFeatures, type Feature } from "@/api/features";

export type FeatureSelectorProps = {
  projectId: string;
  selectedFeature?: Feature | null;
  onFeatureSelect: (feature: Feature | null) => void;
  trigger?: React.ReactNode;
  className?: string;
};

export const FeatureSelector: React.FC<FeatureSelectorProps> = ({
  projectId,
  selectedFeature,
  onFeatureSelect,
  trigger,
  className,
}) => {
  const [open, setOpen] = useState(false);
  const [features, setFeatures] = useState<Feature[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    if (open && projectId) {
      loadFeatures();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, projectId]);

  const loadFeatures = async () => {
    setLoading(true);
    try {
      const response = await getFeatures(projectId);
      setFeatures(Array.isArray(response) ? response : []);
    } catch (error) {
      setFeatures([]);
    } finally {
      setLoading(false);
    }
  };

  const getFeatureTitle = (feature: Feature) => {
    return feature.basicInfo?.title || feature.title || "Untitled Feature";
  };

  const getFeatureDescription = (feature: Feature) => {
    return feature.basicInfo?.description || "";
  };

  const filteredFeatures = features.filter(feature => {
    const title = getFeatureTitle(feature).toLowerCase();
    const description = getFeatureDescription(feature).toLowerCase();
    const search = searchTerm.toLowerCase();
    return title.includes(search) || description.includes(search);
  });

  const handleFeatureSelect = (feature: Feature) => {
    onFeatureSelect(feature);
    setOpen(false);
  };

  const handleClearSelection = () => {
    onFeatureSelect(null);
    setOpen(false);
  };

  const formatDateRange = (feature: Feature) => {
    if (!feature.startDate && !feature.endDate) return null;

    try {
      const startDate = feature.startDate ? new Date(feature.startDate).toLocaleDateString() : null;
      const endDate = feature.endDate ? new Date(feature.endDate).toLocaleDateString() : null;

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

  const getSelectedFeatureText = () => {
    if (!selectedFeature) {
      return "Feature";
    }
    return getFeatureTitle(selectedFeature);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm" className={cn("gap-2", className)}>
            <Lightbulb className="h-4 w-4" />
            {getSelectedFeatureText()}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5" />
            Select Feature
          </DialogTitle>
        </DialogHeader>

        <div className="flex items-center gap-2 py-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
            <Input
              placeholder="Search features..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>
          {selectedFeature && (
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
          ) : filteredFeatures.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {searchTerm ? "No features found matching your search." : "No features available."}
            </div>
          ) : (
            <div className="space-y-3">
              {filteredFeatures.map((feature) => (
                <Card
                  key={feature.id}
                  className={cn(
                    "cursor-pointer transition-colors hover:bg-muted/50",
                    selectedFeature?.id === feature.id && "ring-2 ring-primary"
                  )}
                  onClick={() => handleFeatureSelect(feature)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 mt-0.5">
                        {selectedFeature?.id === feature.id && (
                          <Check className="h-4 w-4 text-primary" />
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-medium truncate flex-1">{getFeatureTitle(feature)}</h4>
                          {feature.displayBugNo && (
                            <Badge variant="outline" className="text-xs">
                              {feature.displayBugNo}
                            </Badge>
                          )}
                        </div>

                        <div className="flex items-center gap-2 mb-2">
                          {feature.basicInfo?.status && (
                            <Badge variant="secondary" className="text-xs">
                              {feature.basicInfo.status}
                            </Badge>
                          )}
                          {feature.priority && feature.priority !== "NONE" && (
                            <Badge variant="outline" className="text-xs">
                              {feature.priority}
                            </Badge>
                          )}
                        </div>

                        {formatDateRange(feature) && (
                          <div className="flex items-center gap-1 mb-2">
                            <span className="text-xs text-muted-foreground">
                              {formatDateRange(feature)}
                            </span>
                          </div>
                        )}

                        {feature.problemInfo?.objective && (
                          <p className="text-sm text-muted-foreground line-clamp-2">
                            {feature.problemInfo.objective}
                          </p>
                        )}

                        {feature.epic?.name && (
                          <div className="mt-2">
                            <Badge variant="outline" className="text-xs">
                              Epic: {feature.epic.name}
                            </Badge>
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

export default FeatureSelector;
