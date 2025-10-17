import { useEffect, useState } from "react";
import { ChatLayout } from "@/components/chat/ChatLayout";
import { adoptToken, getMe, getCurrentUser } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const Index = () => {
  const [providedToken, setProvidedToken] = useState("");
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    // Attempt to hydrate from server session (cookie)
    getMe().finally(() => setInitialized(true));
  }, []);

  const handleAdopt = async () => {
    if (!providedToken.trim()) return;
    await adoptToken(providedToken.trim());
    setProvidedToken("");
  };

  if (!initialized) return null;

  if (!getCurrentUser()) {
    return (
      <div className="h-screen w-full flex items-center justify-center p-4">
        <Card className="max-w-xl w-full">
          <CardHeader>
            <CardTitle>Authenticate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                Paste your JWT below. We will mint a server-signed access token
                and store it only as an HttpOnly cookie. It will not be saved in localStorage.
              </p>
              <Input
                placeholder="Paste JWT here"
                value={providedToken}
                onChange={(e) => setProvidedToken(e.target.value)}
              />
              <div className="flex justify-end">
                <Button onClick={handleAdopt} disabled={!providedToken.trim()}>
                  Continue
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <ChatLayout />;
};

export default Index;
