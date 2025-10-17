import { useEffect, useMemo, useState } from "react";
import { usePersonalization } from "@/context/PersonalizationContext";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Lock, AlertCircle } from "lucide-react";
import { Input } from "@/components/ui/input";
import { clearToken, getToken, setToken, subscribe } from "@/auth/token";

const Settings = () => {
  const { settings, updateSettings, resetSettings } = usePersonalization();
  const [tokenInput, setTokenInput] = useState<string>("");
  const [hasToken, setHasToken] = useState<boolean>(!!getToken());

  useEffect(() => {
    setTokenInput("");
    const unsub = subscribe((t) => setHasToken(!!t));
    return () => unsub();
  }, []);


  return (
    <div className="min-h-screen w-full flex items-start justify-center pt-0 pb-5">
      <div className="w-full max-w-3xl space-y-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">AI Agent Personalization</h1>
          <p className="text-sm text-muted-foreground">Control how the agent remembers and responds, and provide long-term context it can learn from.</p>
        </div>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Authentication</CardTitle>
            <CardDescription>Provide a JWT so the app can authorize with the backend.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-0">
            <div className="space-y-2">
              <Label htmlFor="jwt">JWT</Label>
              <Input
                id="jwt"
                type="password"
                placeholder={hasToken ? "Token is set" : "Paste your JWT here"}
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => {
                  const trimmed = tokenInput.trim();
                  if (trimmed) {
                    setToken(trimmed);
                    setTokenInput("");
                  }
                }}
              >
                Save token
              </Button>
              <Button variant="outline" onClick={() => clearToken()} disabled={!hasToken}>
                Logout
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Memory & Context Features</CardTitle>
            <CardDescription>How these features enhance your AI agent's capabilities.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 pt-0">
            <div className="bg-muted/30 rounded-lg p-2 space-y-1">
              <h4 className="font-medium text-sm">Key Benefits</h4>
              <div className="text-xs text-muted-foreground space-y-0.5">
                <p>• Remembers context and preferences</p>
                <p>• Retains ongoing work across sessions</p>
                <p>• Understands your goals and work style</p>
                <p>• Delivers personalized, consistent help</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Memory</CardTitle>
            <CardDescription>Choose whether your agent should retain context across sessions.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-0">
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="remember">Remember long-term context</Label>
                <p className="text-xs text-muted-foreground">Enable to let the agent learn from your saved context.</p>
              </div>
              <Switch id="remember" checked={settings.rememberLongTermContext} onCheckedChange={(checked) => updateSettings({ rememberLongTermContext: checked })} />
            </div>
          </CardContent>
        </Card>

        <Card className={`relative ${!settings.rememberLongTermContext ? "bg-muted/30 border-dashed" : ""}`}>
          {!settings.rememberLongTermContext && (
            <div className="absolute inset-0 bg-background/80 backdrop-blur-[1px] z-10 flex items-center justify-center rounded-lg">
              <div className="flex items-center gap-2 px-4 py-2 bg-muted rounded-md border text-sm text-muted-foreground">
                <Lock className="h-4 w-4" />
                <span>Enable memory to access</span>
              </div>
            </div>
          )}
          <CardHeader className={`pb-3 ${!settings.rememberLongTermContext ? "opacity-50" : ""}`}>
            <div className="flex items-center gap-2">
              <CardTitle className={!settings.rememberLongTermContext ? "text-muted-foreground" : ""}>
                Long-term Context
              </CardTitle>
              {!settings.rememberLongTermContext && (
                <div className="flex items-center gap-1 px-2 py-1 bg-muted/50 rounded-full text-xs text-muted-foreground">
                  <AlertCircle className="h-3 w-3" />
                  Disabled
                </div>
              )}
            </div>
            <CardDescription className={!settings.rememberLongTermContext ? "text-muted-foreground" : ""}>
              {!settings.rememberLongTermContext
                ? "Enable memory above to provide long-term context for the agent."
                : "Provide background, preferences, team norms, or product details the agent should consider."
              }
            </CardDescription>
          </CardHeader>
          <CardContent className={`space-y-3 pt-0 ${!settings.rememberLongTermContext ? "opacity-50" : ""}`}>
            <Textarea
              value={settings.longTermContext}
              onChange={(e) => updateSettings({ longTermContext: e.target.value })}
              placeholder={!settings.rememberLongTermContext ? "Enable memory to edit context..." : "e.g., Our team prefers concise weekly updates; we use Jira and GitHub Projects; primary KPIs are activation and retention; tone should be professional but empathetic; we release on Thursdays."}
              className="min-h-[120px]"
              disabled={!settings.rememberLongTermContext}
            />
            <div className="flex gap-2">
              <Button
                variant="secondary"
                onClick={() => updateSettings({ longTermContext: "" })}
                disabled={!settings.rememberLongTermContext}
              >
                Clear
              </Button>
              <Button
                variant="outline"
                onClick={resetSettings}
                disabled={!settings.rememberLongTermContext}
              >
                Reset all
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Settings;

