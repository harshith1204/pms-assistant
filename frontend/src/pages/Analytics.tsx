import { useState } from "react";
import { selectDashboard, type SelectResponse } from "@/api/analytics";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

export default function Analytics() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [embedUrl, setEmbedUrl] = useState<string | undefined>();
  const [params, setParams] = useState<Record<string, any>>({});
  const [error, setError] = useState<string | null>(null);
  const [fallback, setFallback] = useState<SelectResponse | null>(null);

  const submit = async (override?: Record<string, any>) => {
    try {
      setLoading(true);
      setError(null);
      setFallback(null);
      const p = override ?? params;
      const res = await selectDashboard(prompt, p);
      if (res.type === "dashboard_embed_url") {
        setEmbedUrl(res.embed_url);
        setParams(res.params || {});
      } else {
        setEmbedUrl(undefined);
        setFallback(res);
      }
    } catch (e: any) {
      setError(e?.message || "Failed to generate dashboard");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <div className="flex-1 flex flex-col gap-3 p-4">
        <div className="flex gap-2">
          <Input
            placeholder="e.g., Revenue by region last quarter"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          <Button onClick={() => submit()} disabled={loading || !prompt.trim()}>
            {loading ? "Generating..." : "Generate"}
          </Button>
        </div>
        <div className="min-h-[44px] flex items-center gap-3">
          {/* Simple param chips for known keys */}
          {Object.entries(params).map(([k, v]) => (
            <Card key={k} className="px-3 py-1 text-sm"><CardContent className="p-0 py-1">{k}: {typeof v === 'object' ? JSON.stringify(v) : String(v)}</CardContent></Card>
          ))}
        </div>
        <div className="flex-1 border rounded-xl overflow-hidden bg-muted/20">
          {embedUrl ? (
            <iframe title="Analytics" src={embedUrl} style={{ width: "100%", height: "100%", border: 0 }} />
          ) : error ? (
            <div className="p-6 text-destructive">{error}</div>
          ) : fallback ? (
            <div className="p-6 text-sm">
              <div className="mb-3">No perfect dashboard match. Suggestions: {Array.isArray(fallback.alternatives) ? fallback.alternatives.join(", ") : "None"}</div>
              <Button variant="secondary" onClick={() => submit(params)}>Try Again</Button>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-muted-foreground">Enter a prompt to generate a dashboard</div>
          )}
        </div>
      </div>
    </div>
  );
}
