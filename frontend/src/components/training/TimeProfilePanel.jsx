/**
 * Where your clock goes.
 *
 * A clock focus has no puzzle pool, so /training/pattern/time_collapse used to
 * render "No puzzle available" next to a coach heading. This shows the thing
 * that is actually true instead: sums over the clock stamps the player's own
 * games already carry. Every figure comes from the server; nothing is
 * estimated here. See docs/time_management_practice_scope.md.
 */
import { useEffect, useState } from "react";
import { ArrowLeft, Clock, Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";

const mmss = (seconds) => {
  const s = Math.max(0, Math.round(Number(seconds) || 0));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rest = s % 60;
  return rest ? `${m}m ${rest}s` : `${m}m`;
};

function Figure({ value, label, note }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/65 p-4">
      <div className="font-heading text-[26px] leading-none text-foreground">{value}</div>
      <div className="mt-2 text-[12.5px] font-medium text-foreground/80">{label}</div>
      {note && <div className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">{note}</div>}
    </div>
  );
}

export default function TimeProfilePanel({ focusLabel = "your clock" }) {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [state, setState] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/training/time-profile`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled) return;
        setProfile(data);
        setState(data ? "ready" : "error");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const back = () => {
    if (window.history.state?.idx > 0) navigate(-1);
    else navigate("/home");
  };

  return (
    <div
      className="experience-page experience-training-page min-h-screen bg-background text-foreground"
      data-testid="time-profile-panel"
    >
      <div className="cg-page cg-page--wide">
        <button
          type="button"
          onClick={back}
          className="mb-8 inline-flex items-center gap-1.5 text-[11.5px] text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-3 w-3" strokeWidth={1.75} />
          Back
        </button>

        <div className="cg-hero mb-8">
          <p className="cg-eyebrow">Today with your coach</p>
          <h1 className="cg-title">Let&rsquo;s look at your clock.</h1>
          <p className="cg-lede">
            There is nothing to solve here. Losing on time is not a puzzle you
            can practise &mdash; so first, here is what your own games say about
            where your time goes.
          </p>
        </div>

        {state === "loading" && (
          <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Reading your clocks&hellip;
          </div>
        )}

        {state === "error" && (
          <p className="text-[13px] text-muted-foreground">
            I couldn&rsquo;t read your clocks just now. Nothing is wrong with your
            games &mdash; try again in a moment.
          </p>
        )}

        {state === "ready" && profile && !profile.eligible && (
          <div className="cg-panel p-5 sm:p-7">
            <p className="text-[13.5px] leading-relaxed text-muted-foreground">
              I don&rsquo;t have enough games with clock data yet to say anything
              useful about your time
              {typeof profile.games_needed === "number"
                ? ` — I need about ${profile.games_needed} and have ${profile.games_with_clock_data || 0}.`
                : "."}{" "}
              Play a few more and this will fill in on its own.
            </p>
          </div>
        )}

        {state === "ready" && profile && profile.eligible && (
          <>
            <div className="cg-panel mb-8 p-5 sm:p-7">
              <div className="mb-5 flex items-start gap-3">
                <Clock className="mt-0.5 h-4 w-4 shrink-0 text-violet-600" />
                <p className="max-w-[640px] text-[13.5px] leading-relaxed text-foreground/80">
                  Across your last {profile.games_with_clock_data} games with clock
                  data, {profile.timeout_losses} ended with your flag falling
                  &mdash; {profile.timeout_loss_rate_pct}% of them. The figures
                  below come from
                  {profile.sample === "timeout_losses"
                    ? ` those ${profile.sample_size} games,`
                    : ` all ${profile.sample_size} of them,`}{" "}
                  so this is your own clock, not an average player&rsquo;s.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Figure
                  value={`${profile.pct_clock_by_move_10}%`}
                  label="of your clock is gone by move 10"
                />
                <Figure
                  value={`${profile.pct_clock_by_move_20}%`}
                  label="of your clock is gone by move 20"
                />
                <Figure
                  value={profile.long_thinks_per_game}
                  label="moves per game over a minute"
                  note="This is the number that matters. You are not slow — one or two decisions per game run long."
                />
                <Figure
                  value={mmss(profile.worst_think_seconds)}
                  label="your longest single think"
                  note={`Average of your longest: ${mmss(profile.avg_longest_think_seconds)}.`}
                />
              </div>
            </div>

            {Array.isArray(profile.burn_moments) && profile.burn_moments.length > 0 && (
              <div className="cg-panel p-5 sm:p-7">
                <p className="cg-eyebrow mb-2">The moments that ate the clock</p>
                <p className="mb-5 max-w-[640px] text-[13px] leading-relaxed text-muted-foreground">
                  One decision per game is usually the whole story. These are the
                  exact moves &mdash; open one and see what you were weighing up.
                </p>
                <div className="space-y-2">
                  {profile.burn_moments.map((moment) => (
                    <button
                      key={`${moment.game_id}-${moment.move_number}`}
                      type="button"
                      onClick={() => navigate(`/game/${moment.game_id}`)}
                      className="flex w-full items-center justify-between gap-4 rounded-xl border border-border/70 bg-background/65 px-4 py-3 text-left transition hover:border-violet-500/40"
                    >
                      <span className="text-[13px] text-foreground">
                        Move {moment.move_number}
                        {moment.lost_on_time && (
                          <span className="ml-2 text-[11.5px] text-amber-700 dark:text-amber-300/80">
                            lost on time
                          </span>
                        )}
                      </span>
                      <span className="font-heading text-[15px] tabular-nums text-foreground">
                        {mmss(moment.seconds)}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
