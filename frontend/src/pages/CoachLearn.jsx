/**
 * Learn: homework and files (docs/coach_pages_scope.md, "Learn").
 *
 * His opening file built from his own games (habits that cost him, traps
 * against him and traps he can set), the habit he is training with the
 * moments it happened and a rule, positions to play from, and the library.
 * Everything comes from the player file; an empty block says so honestly or
 * is left out, and nothing links to an empty page.
 */
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { BookOpen, Crown, Swords, Target } from "lucide-react";

import Layout from "@/components/Layout";
import { useCoachFile } from "@/lib/coachFile";
import {
  HabitMoments,
  OpeningHabit,
  PlayPositions,
  TrapCard,
  WatchFor,
  allTraps,
} from "@/components/coachfile/CoachFileBlocks";

const LIBRARY = [
  { label: "Trap school", href: "/learn/traps", icon: Target },
  { label: "Openings", href: "/openings", icon: BookOpen },
  { label: "Tactics and traps", href: "/training", icon: Swords },
  { label: "Endgames", href: "/openings-overview?tab=endgames", icon: Crown },
  { label: "Pattern training", href: "/training/prescribed", icon: Target },
];

function Section({ eyebrow, title, children, testid }) {
  return (
    <section className="cg-panel rounded-panel p-6 md:p-8" data-testid={testid}>
      {eyebrow && <p className="cg-eyebrow">{eyebrow}</p>}
      <h2 className="mt-2 font-heading text-title text-foreground">
        {title}
      </h2>
      <div className="mt-6">{children}</div>
    </section>
  );
}

export default function CoachLearn({ user }) {
  const file = useCoachFile();
  const ready = file?.enabled && file.state === "ready";
  const notation = file?.notation !== false;
  const openings = ready ? file.openings || [] : [];
  const myTraps = ready ? allTraps(file) : [];
  const habit = ready ? file.habit : null;

  return (
    <Layout user={user}>
      <div className="experience-page cg-page" data-testid="coach-learn-page">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
          <header>
            <p className="cg-eyebrow">Learn</p>
            <h1 className="mt-2 font-heading text-display text-foreground">
              Your homework and your files
            </h1>
            <p className="mt-2 max-w-[620px] text-body text-muted-foreground">
              Built from your own games, and updated after every game you play.
            </p>
          </header>

          {file?.state === "building" && (
            <div className="cg-panel rounded-panel p-6 text-body text-muted-foreground" data-testid="coach-learn-building">
              Your coach is reading your games. This takes a moment the first time.
            </div>
          )}

          {ready && (
            <>
              <Section eyebrow="Built from your games" title="Your opening file" testid="coach-learn-openings">
                {openings.length === 0 && myTraps.length === 0 ? (
                  <p className="text-body text-muted-foreground">
                    No opening habit stands out in your games yet. It shows up once more of your games are read.
                  </p>
                ) : (
                  <div className="space-y-10">
                    {openings.map((h) => (
                      <OpeningHabit key={`${h.side}-${h.line}-${h.idea}`} habit={h} notation={notation} />
                    ))}
                    {myTraps.map((t) => (
                      <TrapCard key={`${t.key}-${t.headline}`} trap={t} notation={notation} />
                    ))}
                  </div>
                )}
              </Section>

              <Section eyebrow="The habit you're training" title={habit ? habit.label : "Nothing to train yet"} testid="coach-learn-habit">
                {habit ? (
                  <div className="space-y-6">
                    <WatchFor habit={habit} linkToLearn={false} />
                    <div>
                      <p className="text-body font-semibold text-foreground">Where it happened in your games</p>
                      <div className="mt-4">
                        <HabitMoments habit={habit} notation={notation} />
                      </div>
                    </div>
                    {habit.practice_key && (
                      <Link
                        to={`/training/pattern/${habit.practice_key}`}
                        className="cg-primary-action !min-h-10 !px-5 !py-2.5 text-note"
                        data-testid="coach-learn-practise"
                      >
                        <Target className="h-4 w-4" /> Practise it
                      </Link>
                    )}
                  </div>
                ) : (
                  <p className="text-body text-muted-foreground">
                    None of the problems your coach can check showed up in your recent games.
                  </p>
                )}
              </Section>

              {file.play_positions?.length > 0 && (
                <Section eyebrow="Play" title="Play from your own positions" testid="coach-learn-play">
                  <PlayPositions positions={file.play_positions} />
                </Section>
              )}
            </>
          )}

          <Section eyebrow="Library" title="Everything else" testid="coach-learn-library">
            <div className="grid gap-3 sm:grid-cols-2">
              {LIBRARY.map(({ label, href, icon: Icon }) => (
                <Link
                  key={href}
                  to={href}
                  className="flex items-center gap-3 rounded-card border border-border/70 p-4 text-body font-medium text-foreground hover:bg-muted/40"
                >
                  <Icon className="h-4 w-4 text-muted-foreground" /> {label}
                </Link>
              ))}
            </div>
          </Section>
        </motion.div>
      </div>
    </Layout>
  );
}
