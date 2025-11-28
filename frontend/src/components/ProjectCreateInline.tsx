import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { X, Image } from "lucide-react";
import { cn } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getBusinessId, getMemberId, getStaffName } from "@/config";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

// Common cover images
const COVER_IMAGES = [
  "https://d2yx15pncgmu63.cloudfront.net/prod-images/524681c1750191737292Website-Design-Background-Feb-09-2022-03-13-55-73-AM.webp",
  "https://images.unsplash.com/photo-1497366216548-37526070297c?w=800&auto=format&fit=crop&q=60",
  "https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=800&auto=format&fit=crop&q=60",
  "https://images.unsplash.com/photo-1486312338219-ce68d2c6f44d?w=800&auto=format&fit=crop&q=60",
  "https://images.unsplash.com/photo-1531498860502-7c67cf02f657?w=800&auto=format&fit=crop&q=60",
];

// Common emojis for project icons
const COMMON_EMOJIS = ["😊", "🚀", "💼", "📊", "🎯", "⚡", "🔥", "💡", "🎨", "📱", "🖥️", "🌐", "📈", "🔧", "⚙️", "🎮", "📝", "📚", "🏆", "🌟"];

export type ProjectCreateInlineProps = {
  name?: string;
  projectId?: string;
  description?: string;
  imageUrl?: string;
  icon?: string;
  access?: "PUBLIC" | "PRIVATE";
  leadId?: string;
  leadName?: string;
  onSave?: (values: {
    name: string;
    projectId: string;
    description: string;
    imageUrl: string;
    icon: string;
    access: "PUBLIC" | "PRIVATE";
    leadId: string;
    leadName: string;
  }) => void;
  onDiscard?: () => void;
  className?: string;
};

export const ProjectCreateInline: React.FC<ProjectCreateInlineProps> = ({
  name = "",
  projectId = "",
  description = "",
  imageUrl = COVER_IMAGES[0],
  icon = "😊",
  access = "PUBLIC",
  leadId = "",
  leadName = "",
  onSave,
  onDiscard,
  className,
}) => {
  const [projectName, setProjectName] = React.useState<string>(name);
  const [projectDisplayId, setProjectDisplayId] = React.useState<string>(projectId);
  const [desc, setDesc] = React.useState<string>(description);
  const [coverImage, setCoverImage] = React.useState<string>(imageUrl);
  const [projectIcon, setProjectIcon] = React.useState<string>(icon);
  const [accessType, setAccessType] = React.useState<"PUBLIC" | "PRIVATE">(access);
  const [selectedLeadId, setSelectedLeadId] = React.useState<string>(leadId || getMemberId());
  const [selectedLeadName, setSelectedLeadName] = React.useState<string>(leadName || getStaffName());

  const handleSave = () => {
    onSave?.({
      name: projectName.trim(),
      projectId: projectDisplayId.trim().toUpperCase(),
      description: desc,
      imageUrl: coverImage,
      icon: projectIcon,
      access: accessType,
      leadId: selectedLeadId,
      leadName: selectedLeadName,
    });
  };

  return (
    <Card className={cn("border-muted/70 overflow-hidden", className)}>
      <div className="relative h-40 bg-gradient-to-r from-gray-700 to-gray-900">
        <img
          src={coverImage}
          alt="Project cover"
          className="w-full h-full object-cover opacity-70"
        />
        <Button
          variant="ghost"
          size="sm"
          className="absolute top-2 right-2 h-8 text-white bg-black/30 hover:bg-black/50"
          onClick={() => {
            const currentIndex = COVER_IMAGES.indexOf(coverImage);
            const nextIndex = (currentIndex + 1) % COVER_IMAGES.length;
            setCoverImage(COVER_IMAGES[nextIndex]);
          }}
        >
          <Image className="h-4 w-4 mr-1" />
          Change Cover
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="absolute top-2 right-32 h-8 text-white bg-black/30 hover:bg-black/50"
          onClick={onDiscard}
        >
          <X className="h-4 w-4" />
        </Button>
        
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="absolute bottom-2 left-2 h-10 w-10 text-2xl bg-white/90 hover:bg-white rounded-lg"
            >
              {projectIcon}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-64 p-2" align="start">
            <div className="grid grid-cols-5 gap-2">
              {COMMON_EMOJIS.map((emoji) => (
                <Button
                  key={emoji}
                  variant="ghost"
                  size="sm"
                  className={cn("h-10 w-10 text-xl", projectIcon === emoji && "bg-primary/10")}
                  onClick={() => setProjectIcon(emoji)}
                >
                  {emoji}
                </Button>
              ))}
            </div>
          </PopoverContent>
        </Popover>
      </div>

      <CardContent className="p-5 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Project Name <span className="text-red-500">*</span></label>
            <Input
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="Enter project name"
              className="h-10"
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-2 block">Project ID <span className="text-red-500">*</span></label>
            <Input
              value={projectDisplayId}
              onChange={(e) => setProjectDisplayId(e.target.value.toUpperCase())}
              placeholder="Enter project ID"
              className="h-10 uppercase"
            />
          </div>
        </div>

        <div>
          <label className="text-sm font-medium mb-2 block">Description</label>
          <Textarea
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            placeholder="Enter project description"
            className="min-h-[80px] resize-y"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Project Lead</label>
            <Select
              value={selectedLeadId}
              onValueChange={(value) => {
                setSelectedLeadId(value);
                // In a real app, you'd look up the name from the members list
              }}
            >
              <SelectTrigger className="h-10">
                <SelectValue placeholder="Select Project Lead" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={getMemberId()}>{getStaffName() || "Current User"}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm font-medium mb-2 block">Access Type</label>
            <div className="flex gap-2">
              <Button
                variant={accessType === "PUBLIC" ? "default" : "outline"}
                className="flex-1 h-10"
                onClick={() => setAccessType("PUBLIC")}
              >
                Public
              </Button>
              <Button
                variant={accessType === "PRIVATE" ? "default" : "outline"}
                className="flex-1 h-10"
                onClick={() => setAccessType("PRIVATE")}
              >
                Private
              </Button>
            </div>
          </div>
        </div>

        <div className="pt-4 border-t flex items-center justify-end">
          <div className="flex items-center gap-2">
            {onDiscard && (
              <Button variant="outline" onClick={onDiscard}>Cancel</Button>
            )}
            <Button 
              onClick={handleSave} 
              disabled={!projectName.trim() || !projectDisplayId.trim()}
            >
              Create Project
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default ProjectCreateInline;
