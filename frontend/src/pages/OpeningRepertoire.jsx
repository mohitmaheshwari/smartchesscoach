import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  BookOpen,
  ChevronRight,
  Crown,
  Loader2,
  Sparkles,
  Swords,
  Target,
  X,
} from "lucide-react";
import Layout from "@/components/Layout";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { API } from "@/App";

function OpeningCard({ opening, onClick }) {
  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -3 }}
      onClick={onClick}
      className="cg-panel group w-full p-5 text-left"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-heading text-base font-semibold text-foreground">{opening.name}</h3>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            I’ve seen this opening in your games. Let’s make the plan behind it easier to recognise.
          </p>
        </div>
        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1" />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {opening.in_library && (
          <span className="rounded-full bg-[#B7F34A]/20 px-2.5 py-1 text-[10px] font-bold text-emerald-900 dark:text-[#DFFFA7]">
            Lesson ready
          </span>
        )}
        {opening.traps_learned?.length > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-[#FF8066]/10 px-2.5 py-1 text-[10px] font-semibold text-[#B94D37] dark:text-[#FF9B86]">
            <Target className="h-3 w-3" /> You’ve met a trap here
          </span>
        )}
      </div>
    </motion.button>
  );
}

function RecommendedCard({ opening, onClick }) {
  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -3 }}
      onClick={onClick}
      className="experience-focus-card group w-full rounded-2xl border p-5 text-left"
    >
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-[#B7F34A]/20 p-2">
          <Sparkles className="h-4 w-4 text-emerald-800 dark:text-[#B7F34A]" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="font-heading text-base font-semibold">{opening.name}</h3>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{opening.description}</p>
          {opening.reason && (
            <p className="mt-3 text-xs font-medium leading-relaxed text-emerald-800 dark:text-emerald-200">
              {opening.reason}
            </p>
          )}
        </div>
        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1" />
      </div>
    </motion.button>
  );
}

export default function OpeningRepertoire({ user }) {
  const navigate = useNavigate();
  const [repertoire, setRepertoire] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("white");
  const [showAllOpenings, setShowAllOpenings] = useState(false);
  const [allOpenings, setAllOpenings] = useState([]);

  useEffect(() => {
    const fetchRepertoire = async () => {
      try {
        const res = await fetch(`${API}/openings/repertoire`, { credentials: "include" });
        if (res.ok) setRepertoire(await res.json());

        const libraryResponse = await fetch(`${API}/openings/library`, { credentials: "include" });
        if (libraryResponse.ok) {
          const data = await libraryResponse.json();
          setAllOpenings(data.openings || []);
        }
      } catch (error) {
        console.error("Error fetching repertoire:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchRepertoire();
  }, []);

  const openLesson = (opening) => {
    const key = opening.library_key || opening.key;
    if (key) navigate(`/openings/${key}`);
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="grid min-h-[60vh] place-items-center">
          <Loader2 className="h-7 w-7 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }

  const sections = {
    white: {
      recommendations: repertoire?.recommended_white || [],
      played: repertoire?.white_repertoire || [],
      empty: "Play naturally as White. I’ll build this part of your repertoire from the positions you reach.",
    },
    black: {
      recommendations: repertoire?.recommended_black || [],
      played: repertoire?.black_repertoire || [],
      empty: "Play naturally as Black. I’ll build this part of your repertoire from the positions you reach.",
    },
  };
  const current = sections[activeTab];

  return (
    <Layout user={user}>
      <main className="experience-page experience-learning-page experience-repertoire-page cg-page" data-testid="opening-repertoire-page">
        <header className="cg-hero">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-[#B7F34A]/20 p-2.5">
              <BookOpen className="h-5 w-5 text-emerald-800 dark:text-[#B7F34A]" />
            </div>
            <p className="cg-eyebrow">Openings with your coach</p>
          </div>
          <h1 className="cg-title">Build openings you understand.</h1>
          <p className="cg-lede">
            We’ll learn the plans behind the positions you actually reach—not memorise a tree of moves you may never play.
          </p>
        </header>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-8">
          <TabsList className="mb-8 grid w-full max-w-md grid-cols-2 rounded-2xl bg-muted/60 p-1.5">
            <TabsTrigger value="white" className="gap-2 rounded-xl">
              <Crown className="h-4 w-4" /> As White
            </TabsTrigger>
            <TabsTrigger value="black" className="gap-2 rounded-xl">
              <Swords className="h-4 w-4" /> As Black
            </TabsTrigger>
          </TabsList>

          {["white", "black"].map((color) => (
            <TabsContent key={color} value={color} className="space-y-10">
              {current.recommendations.length > 0 && (
                <section>
                  <p className="cg-eyebrow mb-4">What I’d teach next</p>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {current.recommendations.map((opening, index) => (
                      <RecommendedCard key={opening.key || index} opening={opening} onClick={() => openLesson(opening)} />
                    ))}
                  </div>
                </section>
              )}

              <section>
                <h2 className="font-heading text-2xl font-semibold tracking-tight">Openings I’ve seen in your games</h2>
                <p className="mt-2 text-sm text-muted-foreground">Choose one and we’ll work on the idea that matters most.</p>
                {current.played.length > 0 ? (
                  <div className="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {current.played.map((opening, index) => (
                      <OpeningCard key={opening.key || index} opening={opening} onClick={() => openLesson(opening)} />
                    ))}
                  </div>
                ) : (
                  <div className="cg-coach-card mt-5 text-sm leading-relaxed text-muted-foreground">{current.empty}</div>
                )}
              </section>
            </TabsContent>
          ))}
        </Tabs>

        <button type="button" className="cg-secondary-action mt-10 w-full" onClick={() => setShowAllOpenings(true)}>
          <BookOpen className="h-4 w-4" /> Explore every opening lesson
        </button>

        {showAllOpenings && (
          <div className="fixed inset-0 z-50 grid place-items-center bg-[#071411]/70 p-4 backdrop-blur-sm">
            <section className="cg-panel max-h-[82vh] w-full max-w-3xl overflow-hidden">
              <header className="flex items-center justify-between border-b border-border p-5">
                <div>
                  <p className="cg-eyebrow mb-1">Explore</p>
                  <h2 className="font-heading text-xl font-semibold">Opening lessons</h2>
                </div>
                <button type="button" onClick={() => setShowAllOpenings(false)} className="rounded-full p-2 hover:bg-muted" aria-label="Close opening lessons">
                  <X className="h-4 w-4" />
                </button>
              </header>
              <div className="max-h-[65vh] overflow-y-auto p-5">
                <div className="grid gap-3 md:grid-cols-2">
                  {allOpenings.map((opening) => (
                    <button
                      key={opening.key}
                      type="button"
                      className="group rounded-2xl border border-border bg-card/60 p-4 text-left transition-all hover:-translate-y-0.5 hover:border-emerald-700/25"
                      onClick={() => {
                        navigate(`/openings/${opening.key}`);
                        setShowAllOpenings(false);
                      }}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <h3 className="font-medium">{opening.name}</h3>
                          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                            Learn the plan, the danger, and the positions to aim for.
                          </p>
                        </div>
                        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1" />
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </section>
          </div>
        )}
      </main>
    </Layout>
  );
}
