import { useMemo, useState } from "react";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Loader2, PencilLine } from "lucide-react";

const CORRECTION_TYPES = [
  { value: "opening_line_wrong", label: "Opening line wrong" },
  { value: "trap_line_wrong", label: "Trap line wrong" },
  { value: "variation_name_wrong", label: "Variation name wrong" },
  { value: "trap_name_wrong", label: "Trap name wrong" },
  { value: "plan_idea_text_wrong", label: "Plan / idea text wrong" },
];

export const OpeningCorrectionDialog = ({
  sourceContext,
  openingKey,
  openingName,
  variationName,
  trapName,
  currentMoves,
  currentFen,
  triggerLabel = "Correct opening data",
  triggerVariant = "outline",
  compact = false,
  onSubmitted,
}) => {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [correctionType, setCorrectionType] = useState(trapName ? "trap_line_wrong" : "opening_line_wrong");
  const [correctedPgn, setCorrectedPgn] = useState("");
  const [correctedSanText, setCorrectedSanText] = useState("");
  const [correctedName, setCorrectedName] = useState("");
  const [correctedExplanation, setCorrectedExplanation] = useState("");
  const [notes, setNotes] = useState("");

  const movePreview = useMemo(() => (currentMoves || []).join(" "), [currentMoves]);

  const submitCorrection = async () => {
    if (!openingKey) {
      toast.error("No opening context available to correct yet.");
      return;
    }

    if (!correctedPgn && !correctedSanText && !correctedName && !correctedExplanation) {
      toast.error("Please enter corrected PGN, SAN moves, name, or explanation.");
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(`${API}/openings/corrections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          source_context: sourceContext,
          opening_key: openingKey,
          opening_name: openingName,
          variation_name: variationName,
          trap_name: trapName,
          correction_type: correctionType,
          current_moves: currentMoves || [],
          current_fen: currentFen,
          corrected_pgn: correctedPgn || null,
          corrected_san_text: correctedSanText || null,
          corrected_name: correctedName || null,
          corrected_explanation: correctedExplanation || null,
          notes: notes || null,
        })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || data.message || "Failed to save opening correction");
      }

      toast.success(data.message || "Opening correction saved.");
      setOpen(false);
      setCorrectedPgn("");
      setCorrectedSanText("");
      setCorrectedName("");
      setCorrectedExplanation("");
      setNotes("");
      onSubmitted?.(data.correction);
    } catch (error) {
      console.error("Opening correction save error:", error);
      toast.error(error.message || "Failed to save opening correction");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant={triggerVariant}
          size={compact ? "sm" : "default"}
          className={compact ? "h-8" : undefined}
          data-testid="opening-correction-trigger-btn"
        >
          <PencilLine className="w-4 h-4 mr-2" />
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl" data-testid="opening-correction-dialog">
        <DialogHeader>
          <DialogTitle>Correct opening / trap data</DialogTitle>
          <DialogDescription>
            Submit the right PGN or SAN line and I’ll overwrite this opening data immediately for the live app.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="text-sm font-medium">Opening</label>
              <Input value={openingName || openingKey || ""} readOnly data-testid="opening-correction-opening-name" />
            </div>
            <div>
              <label className="text-sm font-medium">Trap / Variation</label>
              <Input value={trapName || variationName || ""} readOnly data-testid="opening-correction-trap-name" />
            </div>
          </div>

          <div>
            <label className="text-sm font-medium">What is wrong?</label>
            <select
              value={correctionType}
              onChange={(e) => setCorrectionType(e.target.value)}
              className="w-full mt-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
              data-testid="opening-correction-type-select"
            >
              {CORRECTION_TYPES.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-sm font-medium">Current moves detected by the app</label>
            <Textarea value={movePreview} readOnly className="mt-1 h-20" data-testid="opening-correction-current-moves" />
          </div>

          <div>
            <label className="text-sm font-medium">Correct PGN</label>
            <Textarea
              value={correctedPgn}
              onChange={(e) => setCorrectedPgn(e.target.value)}
              placeholder="Paste the correct PGN here"
              className="mt-1 h-28"
              data-testid="opening-correction-pgn-input"
            />
          </div>

          <div>
            <label className="text-sm font-medium">Correct SAN moves</label>
            <Textarea
              value={correctedSanText}
              onChange={(e) => setCorrectedSanText(e.target.value)}
              placeholder="Example: e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nf6 Nc3 Bb4 e5 Qa5"
              className="mt-1 h-24"
              data-testid="opening-correction-san-input"
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="text-sm font-medium">Corrected name</label>
              <Input
                value={correctedName}
                onChange={(e) => setCorrectedName(e.target.value)}
                placeholder="Correct trap or variation name"
                data-testid="opening-correction-name-input"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Current FEN</label>
              <Input value={currentFen || ""} readOnly data-testid="opening-correction-fen-input" />
            </div>
          </div>

          <div>
            <label className="text-sm font-medium">Correct explanation / plan note</label>
            <Textarea
              value={correctedExplanation}
              onChange={(e) => setCorrectedExplanation(e.target.value)}
              placeholder="Explain what the correct idea / trap / plan should be"
              className="mt-1 h-24"
              data-testid="opening-correction-explanation-input"
            />
          </div>

          <div>
            <label className="text-sm font-medium">Notes</label>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Anything else I should know about this correction"
              className="mt-1 h-20"
              data-testid="opening-correction-notes-input"
            />
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={submitCorrection} disabled={saving} data-testid="opening-correction-submit-btn">
              {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              Save correction
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};