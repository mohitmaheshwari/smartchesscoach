import { useEffect, useMemo, useState } from "react";
import Editor from "@monaco-editor/react";
import Layout from "@/components/Layout";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Plus, RefreshCw, Save, Search, ShieldCheck, Eye } from "lucide-react";
import { toast } from "sonner";

const createBlankOpening = (openingKey = "new_opening") => ({
  opening_key: openingKey,
  opening_name: "New Opening",
  identity: "strategic",
  difficulty: "intermediate",
  core_concepts: [""],
  plans: {
    white: [""],
    black: [""],
  },
  traps: [],
  common_mistakes: [],
  ideas_tab: [],
  adaptive_layers: {
    beginner: {
      focus: "",
      explanation: "",
      next_step: "",
    },
    intermediate: {
      focus: "",
      explanation: "",
      next_step: "",
    },
    advanced: {
      focus: "",
      explanation: "",
      next_step: "",
    },
  },
  coach_voice_lines: [""],
});

const PreviewCard = ({ title, layer, base }) => (
  <Card className="h-full" data-testid={`opening-preview-${title.toLowerCase()}`}>
    <CardHeader className="pb-3">
      <CardTitle className="text-sm">{title} View</CardTitle>
    </CardHeader>
    <CardContent className="space-y-3 text-sm">
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Opening</p>
        <p className="font-medium">{base?.opening_name || "—"}</p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Identity</p>
        <p>{base?.identity || "—"}</p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Core concepts</p>
        <ul className="list-disc pl-4 space-y-1">
          {(base?.core_concepts || []).filter(Boolean).map((concept, index) => <li key={index}>{concept}</li>)}
        </ul>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Adaptive layer</p>
        <p className="font-medium">{layer?.focus || "—"}</p>
        <p className="text-muted-foreground">{layer?.explanation || ""}</p>
        {layer?.next_step && <p className="text-primary">Next: {layer.next_step}</p>}
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Coach voice</p>
        <p>{base?.coach_voice_lines?.[0] || "—"}</p>
      </div>
    </CardContent>
  </Card>
);

export default function AdminOpenings({ user }) {
  const [openings, setOpenings] = useState([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [editorValue, setEditorValue] = useState(JSON.stringify(createBlankOpening(), null, 2));
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validationErrors, setValidationErrors] = useState([]);
  const [previewData, setPreviewData] = useState(null);

  const parsedJson = useMemo(() => {
    try {
      return JSON.parse(editorValue);
    } catch {
      return null;
    }
  }, [editorValue]);

  const fetchOpenings = async () => {
    try {
      const response = await fetch(`${API}/admin/openings`, { credentials: "include" });
      if (!response.ok) throw new Error("Failed to load admin openings");
      const data = await response.json();
      setOpenings(data.openings || []);
      if (!selectedKey && data.openings?.length > 0) {
        setSelectedKey(data.openings[0].opening_key);
      }
    } catch (error) {
      toast.error(error.message || "Failed to load opening feedback");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOpenings();
  }, []);

  useEffect(() => {
    const fetchSelected = async () => {
      if (!selectedKey) return;
      try {
        const response = await fetch(`${API}/admin/openings/${selectedKey}`, { credentials: "include" });
        if (!response.ok) throw new Error("Opening feedback not found");
        const data = await response.json();
        setEditorValue(JSON.stringify(data.feedback, null, 2));
        setPreviewData(data.feedback);
        setValidationErrors([]);
      } catch (error) {
        toast.error(error.message || "Failed to load selected opening");
      }
    };
    fetchSelected();
  }, [selectedKey]);

  const handleValidate = async () => {
    if (!parsedJson) {
      toast.error("JSON is invalid. Please fix syntax first.");
      return;
    }

    setValidating(true);
    try {
      const response = await fetch(`${API}/admin/openings/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ feedback: parsedJson }),
      });
      const data = await response.json();
      if (data.valid) {
        setValidationErrors([]);
        toast.success("Opening JSON is valid.");
      } else {
        setValidationErrors(data.errors || []);
        toast.error("Validation failed. See errors below.");
      }
    } catch (error) {
      toast.error(error.message || "Validation failed");
    } finally {
      setValidating(false);
    }
  };

  const handleSave = async () => {
    if (!parsedJson) {
      toast.error("JSON is invalid. Please fix syntax before saving.");
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(`${API}/admin/openings/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ feedback: parsedJson }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail?.message || data.detail || "Save failed");
      }
      toast.success(`Saved ${data.opening_name}`);
      setSelectedKey(parsedJson.opening_key);
      setPreviewData(parsedJson);
      fetchOpenings();
    } catch (error) {
      toast.error(error.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = () => {
    if (!parsedJson) {
      toast.error("JSON is invalid. Please fix syntax first.");
      return;
    }
    setPreviewData(parsedJson);
    setValidationErrors([]);
  };

  const handleNewOpening = () => {
    const openingKey = window.prompt("Enter new opening_key", "new_opening_key");
    if (!openingKey) return;
    setSelectedKey("");
    setEditorValue(JSON.stringify(createBlankOpening(openingKey), null, 2));
    setPreviewData(null);
    setValidationErrors([]);
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="space-y-6 max-w-7xl mx-auto" data-testid="admin-openings-page">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-primary/10 border border-primary/20">
            <ShieldCheck className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Admin → Opening Feedback Manager</h1>
            <p className="text-muted-foreground">Edit, validate, save, and preview opening feedback JSON.</p>
          </div>
        </div>

        <Card>
          <CardContent className="p-4 flex flex-col lg:flex-row gap-3 lg:items-center lg:justify-between">
            <div className="flex-1 flex flex-col lg:flex-row gap-3">
              <select
                value={selectedKey}
                onChange={(e) => setSelectedKey(e.target.value)}
                className="w-full lg:max-w-sm rounded-md border border-input bg-background px-3 py-2 text-sm"
                data-testid="admin-openings-selector"
              >
                <option value="">Select opening</option>
                {openings.map((opening) => (
                  <option key={opening.opening_key} value={opening.opening_key}>
                    {opening.opening_name} ({opening.opening_key})
                  </option>
                ))}
              </select>
              <Button variant="outline" onClick={fetchOpenings} data-testid="admin-openings-refresh-btn">
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </div>
            <Button onClick={handleNewOpening} data-testid="admin-openings-new-btn">
              <Plus className="w-4 h-4 mr-2" />
              New Opening
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">JSON Editor</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="border border-border rounded-lg overflow-hidden" data-testid="admin-openings-editor-wrapper">
              <Editor
                height="480px"
                defaultLanguage="json"
                value={editorValue}
                onChange={(value) => setEditorValue(value || "")}
                options={{ minimap: { enabled: false }, fontSize: 13, wordWrap: "on" }}
              />
            </div>

            <div className="flex flex-wrap gap-3">
              <Button variant="outline" onClick={handleValidate} disabled={validating} data-testid="admin-openings-validate-btn">
                {validating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
                Validate
              </Button>
              <Button onClick={handleSave} disabled={saving} data-testid="admin-openings-save-btn">
                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                Save
              </Button>
              <Button variant="secondary" onClick={handlePreview} data-testid="admin-openings-preview-btn">
                <Eye className="w-4 h-4 mr-2" />
                Preview
              </Button>
            </div>

            {validationErrors.length > 0 && (
              <Card className="border-red-500/30 bg-red-500/5" data-testid="admin-openings-validation-errors">
                <CardContent className="p-4 space-y-2 text-sm text-red-400">
                  {validationErrors.map((error, index) => (
                    <div key={index}>{JSON.stringify(error)}</div>
                  ))}
                </CardContent>
              </Card>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:grid-cols-3">
          <PreviewCard title="Beginner" layer={previewData?.adaptive_layers?.beginner} base={previewData} />
          <PreviewCard title="Intermediate" layer={previewData?.adaptive_layers?.intermediate} base={previewData} />
          <PreviewCard title="Advanced" layer={previewData?.adaptive_layers?.advanced} base={previewData} />
        </div>
      </div>
    </Layout>
  );
}