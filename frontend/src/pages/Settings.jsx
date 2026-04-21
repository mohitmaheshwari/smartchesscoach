/**
 * Settings — quiet editorial form.
 *
 * Implements the redesign spec at
 *   chessguru-design-system/project/redesign/08_Settings.{html,jsx}
 * — a single centered column, no cards, no tabs, no decoration. Sections
 * separated by hairline borders; toggles and selects stand to the right
 * of each row.
 *
 * All the functional behavior from the previous Settings page is preserved:
 *   - email notification preferences (GET/PUT /api/settings/email-notifications)
 *   - test email send (POST /api/settings/test-email)
 *   - theme toggle (via ThemeContext)
 *   - logout (POST /api/auth/logout)
 *   - user profile info (name / email / chess.com / lichess usernames)
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Switch } from "@/components/ui/switch";
import Layout from "@/components/Layout";
import { useTheme } from "@/context/ThemeContext";
import { toast } from "sonner";
import { Loader2, Send } from "lucide-react";

// ─── Row: title + description on the left, control on the right ──────────────
// `last` omits the bottom hairline (used for the last row in a section).
function Row({ title, desc, children, last = false }) {
  return (
    <div
      className={`grid grid-cols-[1fr_auto] gap-6 items-center pb-6 ${
        last ? "" : "border-b border-border/60"
      }`}
    >
      <div className="min-w-0">
        <div className="text-[13.5px] text-foreground">{title}</div>
        {desc && (
          <div className="text-[12px] text-muted-foreground mt-0.5 leading-snug">
            {desc}
          </div>
        )}
      </div>
      <div className="shrink-0 flex items-center">{children}</div>
    </div>
  );
}

// ─── Section: serif title + description + spaced rows ────────────────────────
function Section({ title, desc, children }) {
  return (
    <section className="mb-14">
      <h2 className="font-serif text-[18px] text-foreground font-medium mb-1">
        {title}
      </h2>
      <p className="text-[12.5px] text-muted-foreground mb-7">{desc}</p>
      <div className="space-y-7">{children}</div>
    </section>
  );
}

const Settings = ({ user }) => {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [loggingOut, setLoggingOut] = useState(false);
  const [emailSettings, setEmailSettings] = useState({
    game_analyzed: true,
    weekly_summary: true,
    weakness_alert: true,
  });
  const [loadingEmail, setLoadingEmail] = useState(true);
  const [savingEmail, setSavingEmail] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);

  useEffect(() => {
    fetchEmailSettings();
  }, []);

  const fetchEmailSettings = async () => {
    try {
      const res = await fetch(API + "/settings/email-notifications", {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setEmailSettings(data.notifications);
      }
    } catch (e) {
      console.error("Failed to fetch email settings:", e);
    } finally {
      setLoadingEmail(false);
    }
  };

  const updateEmailSetting = async (key, value) => {
    const newSettings = { ...emailSettings, [key]: value };
    setEmailSettings(newSettings);
    setSavingEmail(true);
    try {
      const res = await fetch(API + "/settings/email-notifications", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(newSettings),
      });
      if (res.ok) {
        toast.success("Preferences saved");
      } else {
        throw new Error("Failed to save");
      }
    } catch (e) {
      toast.error("Couldn't save that one");
      setEmailSettings((prev) => ({ ...prev, [key]: !value }));
    } finally {
      setSavingEmail(false);
    }
  };

  const sendTestEmail = async () => {
    setSendingTest(true);
    try {
      const res = await fetch(API + "/settings/test-email", {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        toast.success("Test email sent. Check your inbox.");
      } else {
        const data = await res.json();
        toast.error(data.detail || "Failed to send test email");
      }
    } catch (e) {
      toast.error("Failed to send test email");
    } finally {
      setSendingTest(false);
    }
  };

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await fetch(`${API}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
      toast.success("Signed out");
      navigate("/");
    } catch (error) {
      toast.error("Failed to sign out");
    } finally {
      setLoggingOut(false);
    }
  };

  // The user's join date would ideally come from user.created_at but the auth
  // payload doesn't always include it — omit silently rather than show a default.
  const joinLine = user?.email ? `Signed in as ${user.email}` : "Signed in.";

  return (
    <Layout user={user}>
      <div className="max-w-[680px] mx-auto px-6 md:px-10 py-14 md:py-20" data-testid="settings-page">

        {/* Head */}
        <div className="mb-16">
          <p className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-4">
            Settings
          </p>
          <h1 className="font-serif text-[36px] leading-[1.05] tracking-[-0.02em] font-medium text-foreground">
            Preferences
          </h1>
          <p className="text-[13.5px] text-muted-foreground mt-2">{joinLine}</p>
        </div>

        {/* ─── You ─── */}
        <Section title="You" desc="Who the coach is talking to.">
          <Row
            title="Display name"
            desc="Appears in games and the coach's notes."
          >
            <span className="text-[13px] text-foreground tabular-nums">
              {user?.name || "—"}
            </span>
          </Row>
          <Row title="Email" desc="Used for sign-in and reminders." last>
            <span className="text-[13px] text-muted-foreground">
              {user?.email || "—"}
            </span>
          </Row>
        </Section>

        {/* ─── Game imports ─── */}
        <Section title="Game imports" desc="Where your games come from.">
          <Row
            title="Chess.com"
            desc={
              user?.chess_com_username ? (
                <span className="text-emerald-500/80">
                  Connected as{" "}
                  <span className="font-medium text-foreground/80">
                    {user.chess_com_username}
                  </span>
                </span>
              ) : (
                "Not connected."
              )
            }
          >
            <span className="text-[12px] text-muted-foreground tabular-nums">
              {user?.chess_com_username ? "linked" : "—"}
            </span>
          </Row>
          <Row
            title="Lichess"
            desc={
              user?.lichess_username ? (
                <span className="text-emerald-500/80">
                  Connected as{" "}
                  <span className="font-medium text-foreground/80">
                    {user.lichess_username}
                  </span>
                </span>
              ) : (
                "Not connected."
              )
            }
            last
          >
            <span className="text-[12px] text-muted-foreground tabular-nums">
              {user?.lichess_username ? "linked" : "—"}
            </span>
          </Row>
        </Section>

        {/* ─── The coach ─── */}
        <Section title="The coach" desc="How we reach you about your chess.">
          {loadingEmail ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              <Row
                title="Game-analyzed emails"
                desc="A note when we finish analyzing a new game."
              >
                <Switch
                  checked={emailSettings.game_analyzed}
                  onCheckedChange={(v) => updateEmailSetting("game_analyzed", v)}
                  disabled={savingEmail}
                  data-testid="email-game-analyzed-switch"
                />
              </Row>
              <Row
                title="Weekly summary"
                desc="One email a week — what you practiced, what's fading."
              >
                <Switch
                  checked={emailSettings.weekly_summary}
                  onCheckedChange={(v) => updateEmailSetting("weekly_summary", v)}
                  disabled={savingEmail}
                  data-testid="email-weekly-summary-switch"
                />
              </Row>
              <Row
                title="Pattern alerts"
                desc="Tell me when I'm repeating a mistake across games."
                last
              >
                <Switch
                  checked={emailSettings.weakness_alert}
                  onCheckedChange={(v) => updateEmailSetting("weakness_alert", v)}
                  disabled={savingEmail}
                  data-testid="email-weakness-alert-switch"
                />
              </Row>
            </>
          )}
        </Section>

        {/* ─── Appearance ─── */}
        <Section title="Appearance" desc="How the app looks to you.">
          <Row
            title="Dark mode"
            desc="Easier on the eyes at night and during long sessions."
            last
          >
            <Switch
              checked={theme === "dark"}
              onCheckedChange={toggleTheme}
              data-testid="theme-switch"
            />
          </Row>
        </Section>

        {/* ─── Account ─── subtle inline links, never a destructive card */}
        <section className="mt-20 pt-10 border-t border-border/60">
          <h2 className="font-serif text-[18px] text-muted-foreground font-medium mb-1">
            Account
          </h2>
          <p className="text-[12.5px] text-muted-foreground/70 mb-7">
            Rarely needed.
          </p>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-[12.5px]">
            <button
              onClick={sendTestEmail}
              disabled={sendingTest}
              className="text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50 inline-flex items-center gap-1.5"
              data-testid="send-test-email-btn"
            >
              {sendingTest ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Send className="w-3 h-3" />
              )}
              Send test email
            </button>
            <span className="text-border">·</span>
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className="text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
              data-testid="logout-button"
            >
              {loggingOut ? "Signing out…" : "Sign out"}
            </button>
          </div>
        </section>
      </div>
    </Layout>
  );
};

export default Settings;
