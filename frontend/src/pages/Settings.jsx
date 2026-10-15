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
import { Loader2, Send, Sparkles, User, Database, Mail, Palette, Shield, LogOut } from "lucide-react";
import { resetAnalyticsContext } from "@/lib/analytics";
import { Capacitor } from "@capacitor/core";

// ─── Row: title + description on the left, control on the right ──────────────
function Row({ title, desc, children }) {
  return (
    <div className="grid grid-cols-[1fr_auto] gap-6 items-center py-4.5 first:pt-0 last:pb-0">
      <div className="min-w-0">
        <div className="text-sm font-semibold text-slate-100 dark:text-white tracking-tight">{title}</div>
        {desc && (
          <div className="text-xs text-slate-400 dark:text-slate-300 mt-0.5 leading-relaxed">
            {desc}
          </div>
        )}
      </div>
      <div className="shrink-0 flex items-center">{children}</div>
    </div>
  );
}

// ─── Section: studio card with icon, title, description, and rows ─────────────
function Section({ icon: Icon, title, desc, children }) {
  return (
    <section className="studio-card p-6 md:p-8 mb-6 border border-slate-700/60 dark:border-cyan-500/25 shadow-lg">
      <div className="flex items-center gap-2.5 mb-1.5">
        {Icon && (
          <div className="w-7 h-7 rounded-lg bg-cyan-950/80 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shrink-0">
            <Icon className="w-4 h-4" />
          </div>
        )}
        <h2 className="font-heading text-lg font-bold text-white tracking-tight">
          {title}
        </h2>
      </div>
      {desc && <p className="text-xs sm:text-sm text-slate-400 mb-6 leading-relaxed">{desc}</p>}
      <div className="divide-y divide-slate-700/50 dark:divide-cyan-500/15">{children}</div>
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
    const nativeToken = Capacitor.isNativePlatform()
      ? localStorage.getItem("session_token")
      : null;
    try {
      await fetch(`${API}/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: nativeToken ? { Authorization: `Bearer ${nativeToken}` } : {},
      });
      localStorage.removeItem("session_token");
      localStorage.removeItem("authToken");
      resetAnalyticsContext();
      toast.success("Signed out");
      navigate("/");
    } catch (error) {
      localStorage.removeItem("session_token");
      localStorage.removeItem("authToken");
      resetAnalyticsContext();
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
      <div className="max-w-[800px] mx-auto px-4 sm:px-6 md:px-8 py-8 md:py-12 relative z-10" data-testid="settings-page">

        {/* Head */}
        <div className="studio-card p-6 md:p-8 mb-8 border border-slate-700/60 dark:border-cyan-500/25 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/10 rounded-full blur-[80px] pointer-events-none" />
          <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 mb-2.5">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <span>Your space</span>
          </div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold text-white tracking-tight mb-2.5">
            Make the coaching feel right for you.
          </h1>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-sm text-slate-300">
            <p className="max-w-xl leading-relaxed">
              Choose how I reach you and how this room should feel.
            </p>
            <span className="font-mono text-xs text-cyan-300 bg-cyan-950/80 px-3 py-1 rounded-full border border-cyan-500/35 font-semibold shrink-0 shadow-sm">
              {joinLine}
            </span>
          </div>
        </div>

        {/* ─── You ─── */}
        <Section icon={User} title="You" desc="The person I’m getting to know through the board.">
          <Row
            title="Display name"
            desc="Appears in games and the coach's notes."
          >
            <span className="px-3 py-1 rounded-lg bg-slate-900/90 border border-slate-700/80 text-cyan-300 font-mono text-xs font-bold tracking-tight">
              {user?.name || "—"}
            </span>
          </Row>
          <Row title="Email" desc="Used for sign-in and reminders.">
            <span className="px-3 py-1 rounded-lg bg-slate-900/90 border border-slate-700/80 text-slate-200 font-mono text-xs font-medium">
              {user?.email || "—"}
            </span>
          </Row>
        </Section>

        {/* ─── Game imports ─── */}
        <Section icon={Database} title="Game imports" desc="Where your games come from.">
          <Row
            title="Chess.com"
            desc="Sync games played on Chess.com directly to your training history."
          >
            {user?.chess_com_username ? (
              <span className="px-3 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 font-mono text-xs font-semibold inline-flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Linked as {user.chess_com_username}
              </span>
            ) : (
              <span className="px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700/70 text-slate-400 font-mono text-xs font-medium">
                Not connected
              </span>
            )}
          </Row>
          <Row
            title="Lichess"
            desc="Sync games played on Lichess for analysis and mistake detection."
          >
            {user?.lichess_username ? (
              <span className="px-3 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 font-mono text-xs font-semibold inline-flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Linked as {user.lichess_username}
              </span>
            ) : (
              <span className="px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700/70 text-slate-400 font-mono text-xs font-medium">
                Not connected
              </span>
            )}
          </Row>
        </Section>

        {/* ─── The coach ─── */}
        <Section icon={Mail} title="The coach" desc="Choose when you want to hear from me away from the board.">
          {loadingEmail ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
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
                title="A weekly coaching note"
                desc="One calm note about what feels better and what we should revisit."
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
        <Section icon={Palette} title="Appearance" desc="How the app looks to you.">
          <Row
            title="Dark mode"
            desc="Black Studio theme — easier on the eyes at night and during long sessions."
          >
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs text-slate-400 uppercase tracking-wider font-semibold">
                {theme === "dark" ? "Black Studio" : "White Studio"}
              </span>
              <Switch
                checked={theme === "dark"}
                onCheckedChange={toggleTheme}
                data-testid="theme-switch"
              />
            </div>
          </Row>
        </Section>

        {/* ─── Account ─── */}
        <section className="studio-card p-6 md:p-8 mb-6 border border-slate-700/60 dark:border-cyan-500/25 shadow-lg">
          <div className="flex items-center gap-2.5 mb-1.5">
            <div className="w-7 h-7 rounded-lg bg-cyan-950/80 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shrink-0">
              <Shield className="w-4 h-4" />
            </div>
            <h2 className="font-heading text-lg font-bold text-white tracking-tight">
              Account
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mb-6 leading-relaxed">
            Testing utilities and session controls.
          </p>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button
              onClick={sendTestEmail}
              disabled={sendingTest}
              className="px-4 py-2.5 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-slate-700 hover:border-cyan-500/50 text-slate-200 hover:text-white transition-all text-xs font-semibold inline-flex items-center gap-2 cursor-pointer shadow-sm disabled:opacity-50"
              data-testid="send-test-email-btn"
            >
              {sendingTest ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
              ) : (
                <Send className="w-3.5 h-3.5 text-cyan-400" />
              )}
              Send test email
            </button>
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className="px-4 py-2.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 hover:text-rose-200 transition-all text-xs font-semibold inline-flex items-center gap-2 cursor-pointer shadow-sm disabled:opacity-50"
              data-testid="logout-button"
            >
              <LogOut className="w-3.5 h-3.5" />
              {loggingOut ? "Signing out…" : "Sign out"}
            </button>
          </div>
        </section>
      </div>
    </Layout>
  );
};

export default Settings;
