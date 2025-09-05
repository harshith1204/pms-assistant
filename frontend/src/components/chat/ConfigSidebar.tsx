import { useState } from "react";
import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Brain, Database, Wrench, Zap } from "lucide-react";

interface ConfigSidebarProps {
  open: boolean;
}

export function ConfigSidebar({ open }: ConfigSidebarProps) {
  const [temperature, setTemperature] = useState([0.4]);
  const [contextWindow, setContextWindow] = useState([4096]);
  const [model, setModel] = useState("gpt-4");
  const [showThoughts, setShowThoughts] = useState(true);
  const [enableMCP, setEnableMCP] = useState(true);
  const [selectedTools, setSelectedTools] = useState(["list-collections", "list-databases"]);

  const availableModels = [
    { value: "gpt-4", label: "GPT-4" },
    { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
    { value: "claude-3", label: "Claude 3" },
    { value: "gemini-pro", label: "Gemini Pro" },
  ];

  const mcpTools = [
    { id: "list-collections", name: "List Collections", description: "MongoDB collection listing", category: "database" },
    { id: "list-databases", name: "List Databases", description: "Database enumeration", category: "database" },
    { id: "web-search", name: "Web Search", description: "Search the internet", category: "utility" },
    { id: "code-analysis", name: "Code Analysis", description: "Analyze code structure", category: "development" },
    { id: "file-operations", name: "File Operations", description: "Read/write files", category: "utility" },
  ];

  const toggleTool = (toolId: string) => {
    setSelectedTools(prev => 
      prev.includes(toolId) 
        ? prev.filter(id => id !== toolId)
        : [...prev, toolId]
    );
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case "database": return <Database className="h-3 w-3" />;
      case "development": return <Brain className="h-3 w-3" />;
      case "utility": return <Wrench className="h-3 w-3" />;
      default: return <Zap className="h-3 w-3" />;
    }
  };

  if (!open) return null;

  return (
    <aside className={cn(
      "w-80 h-full flex flex-col flex-shrink-0 border-l bg-card transition-all duration-200 z-30 overflow-hidden",
      !open && "w-0 overflow-hidden"
    )}>
      <ScrollArea className="h-full pr-2">
        <div className="p-4 space-y-4">
          
          {/* Model Configuration */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Brain className="h-4 w-4 text-primary" />
                Model Configuration
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label className="text-xs font-medium">Model</Label>
                <Select value={model} onValueChange={setModel}>
                  <SelectTrigger className="h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent position="popper" side="bottom" sideOffset={4} className="z-50 bg-popover text-popover-foreground border border-border shadow-md">
                    {availableModels.map((model) => (
                      <SelectItem key={model.value} value={model.value}>
                        {model.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <Label className="text-xs font-medium">Temperature</Label>
                  <span className="text-xs text-muted-foreground">{temperature[0]}</span>
                </div>
                <Slider
                  value={temperature}
                  onValueChange={setTemperature}
                  max={1}
                  min={0}
                  step={0.1}
                  className="py-2"
                />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <Label className="text-xs font-medium">Context Window</Label>
                  <span className="text-xs text-muted-foreground">{contextWindow[0]}</span>
                </div>
                <Slider
                  value={contextWindow}
                  onValueChange={setContextWindow}
                  max={8192}
                  min={1024}
                  step={512}
                  className="py-2"
                />
              </div>
            </CardContent>
          </Card>

          {/* Agent Features */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Zap className="h-4 w-4 text-accent" />
                Agent Features
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-xs font-medium">Show Thoughts</Label>
                  <p className="text-xs text-muted-foreground">Display reasoning process</p>
                </div>
                <Switch checked={showThoughts} onCheckedChange={setShowThoughts} />
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-xs font-medium">Enable MCP Tools</Label>
                  <p className="text-xs text-muted-foreground">Model Context Protocol integration</p>
                </div>
                <Switch checked={enableMCP} onCheckedChange={setEnableMCP} />
              </div>
            </CardContent>
          </Card>

          {/* MCP Tools */}
          {enableMCP && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Wrench className="h-4 w-4 text-primary" />
                  MCP Tools
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {mcpTools.map((tool) => (
                    <div
                      key={tool.id}
                      className={cn(
                        "flex items-center justify-between p-2 rounded-md border cursor-pointer transition-colors min-h-[60px]",
                        selectedTools.includes(tool.id) 
                          ? "bg-primary/5 border-primary/20" 
                          : "hover:bg-muted/50"
                      )}
                      onClick={() => toggleTool(tool.id)}
                    >
                      <div className="flex items-center gap-2 flex-1 min-w-0 overflow-hidden">
                        {getCategoryIcon(tool.category)}
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium truncate">{tool.name}</p>
                          <p className="text-xs text-muted-foreground truncate">{tool.description}</p>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Badge 
                          variant="outline" 
                          className="text-xs h-5 whitespace-nowrap"
                        >
                          {tool.category}
                        </Badge>
                        <Switch 
                          checked={selectedTools.includes(tool.id)}
                          onCheckedChange={() => toggleTool(tool.id)}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Connection Status */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Database className="h-4 w-4 text-accent" />
                Connections
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div>
                  <span className="text-xs font-medium">MongoDB MCP Server</span>
                </div>
                <Badge variant="outline" className="text-xs h-5">Connected</Badge>
              </div>
              
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
                  <span className="text-xs font-medium">MCP Server - Smithery</span>
                </div>
                <Badge variant="outline" className="text-xs h-5">Disconnected</Badge>
              </div>
            </CardContent>
          </Card>

        </div>
      </ScrollArea>
    </aside>
  );
}