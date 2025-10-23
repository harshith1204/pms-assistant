import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { X, Search, Check } from "lucide-react";
import { cn } from "@/lib/utils";

export interface PickerOption {
  id: string;
  name: string;
  [key: string]: any;
}

export interface PickerProps {
  title: string;
  options: PickerOption[];
  selectedOptions: PickerOption[];
  onSelectionChange: (options: PickerOption[]) => void;
  multiple?: boolean;
  searchable?: boolean;
  placeholder?: string;
  className?: string;
  renderOption?: (option: PickerOption, isSelected: boolean) => React.ReactNode;
}

export const Picker: React.FC<PickerProps> = ({
  title,
  options,
  selectedOptions,
  onSelectionChange,
  multiple = true,
  searchable = true,
  placeholder = "Search...",
  className,
  renderOption
}) => {
  const [searchTerm, setSearchTerm] = React.useState("");
  const [isOpen, setIsOpen] = React.useState(false);

  const filteredOptions = React.useMemo(() => {
    if (!searchTerm) return options;
    return options.filter(option =>
      option.name.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [options, searchTerm]);

  const handleOptionClick = (option: PickerOption) => {
    if (multiple) {
      const isSelected = selectedOptions.some(selected => selected.id === option.id);
      if (isSelected) {
        onSelectionChange(selectedOptions.filter(selected => selected.id !== option.id));
      } else {
        onSelectionChange([...selectedOptions, option]);
      }
    } else {
      onSelectionChange([option]);
      setIsOpen(false);
    }
  };

  const handleRemoveSelected = (optionId: string) => {
    onSelectionChange(selectedOptions.filter(selected => selected.id !== optionId));
  };

  const handleClearAll = () => {
    onSelectionChange([]);
  };

  return (
    <div className={cn("relative", className)}>
      {/* Selected items display */}
      {selectedOptions.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {selectedOptions.map(option => (
            <Badge key={option.id} variant="secondary" className="text-xs">
              {option.name}
              <button
                onClick={() => handleRemoveSelected(option.id)}
                className="ml-1 hover:bg-destructive/20 rounded-full p-0.5"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
          {multiple && selectedOptions.length > 1 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearAll}
              className="h-6 px-2 text-xs"
            >
              Clear all
            </Button>
          )}
        </div>
      )}

      {/* Trigger button */}
      <Button
        variant="outline"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full justify-between"
      >
        <span>
          {selectedOptions.length > 0
            ? `${selectedOptions.length} selected`
            : `Select ${title.toLowerCase()}`
          }
        </span>
        {isOpen ? <X className="h-4 w-4" /> : <Search className="h-4 w-4" />}
      </Button>

      {/* Dropdown */}
      {isOpen && (
        <Card className="absolute top-full left-0 right-0 mt-1 z-50 max-h-64">
          <CardContent className="p-0">
            {searchable && (
              <div className="p-3 border-b">
                <Input
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder={placeholder}
                  className="h-8"
                />
              </div>
            )}

            <ScrollArea className="max-h-48">
              <div className="p-1">
                {filteredOptions.map(option => {
                  const isSelected = selectedOptions.some(selected => selected.id === option.id);
                  return (
                    <div
                      key={option.id}
                      className={cn(
                        "flex items-center gap-2 p-2 rounded cursor-pointer hover:bg-accent transition-colors",
                        isSelected && "bg-primary/5"
                      )}
                      onClick={() => handleOptionClick(option)}
                    >
                      {renderOption ? (
                        renderOption(option, isSelected)
                      ) : (
                        <>
                          <div className={cn(
                            "flex-shrink-0 w-4 h-4 border rounded flex items-center justify-center",
                            isSelected ? "bg-primary border-primary" : "border-muted-foreground"
                          )}>
                            {isSelected && <Check className="h-3 w-3 text-primary-foreground" />}
                          </div>
                          <span className="flex-1 text-sm">{option.name}</span>
                        </>
                      )}
                    </div>
                  );
                })}
                {filteredOptions.length === 0 && (
                  <div className="p-4 text-center text-muted-foreground text-sm">
                    No options found
                  </div>
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}

      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
};