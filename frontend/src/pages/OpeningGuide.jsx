import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, ChevronRight, Loader2, Target, AlertTriangle, BookOpen, Trophy } from "lucide-react";
import { API } from "@/App";
import SEO from "@/components/seo/SEO";

/**
 * Public opening guide page — /learn/openings/:slug
 *
 * Indexable, no auth, no PII. Renders curriculum content for one
 * opening with full SEO metadata + Schema.org Course / FAQPage /
 * BreadcrumbList markup so Google rich results and AI engines
 * (ChatGPT, Claude, Perplexity) can extract clean facts.
 *
 * Content source: GET /api/public/openings/:slug — backed by
 * backend/data/opening_curriculum.json. The auth-gated lesson flow
 * uses the same curriculum but renders interactive content; this
 * page renders read-only marketing content with a CTA to sign up.
 */
const OpeningGuide = () => {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [opening, setOpening] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API}/public/openings/${slug}`);
        if (!res.ok) {
          if (res.status === 404) {
            setError("not-found");
          } else {
            setError("server");
          }
          return;
        }
        const data = await res.json();
        if (!cancelled) setOpening(data);
      } catch (e) {
        if (!cancelled) setError("network");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#06060B] text-white flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-amber-400" />
      </div>
    );
  }

  if (error === "not-found") {
    return (
      <div className="min-h-screen bg-[#06060B] text-white">
        <SEO
          title="Opening not found"
          description="That opening guide doesn't exist. Browse the full list of opening guides on ChessGuru."
          canonical={`https://chessguru.ai/learn/openings/${slug}`}
          noindex={true}
        />
        <div className="max-w-2xl mx-auto px-6 py-24 text-center">
          <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto mb-4" />
          <h1 className="text-3xl font-heading font-bold mb-3">Opening not found</h1>
          <p className="text-gray-400 mb-6">
            We don't have a guide for "{slug}" yet. Browse the full list to find one.
          </p>
          <Link
            to="/learn/openings"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-amber-500 text-black font-semibold hover:bg-amber-400 transition-colors"
          >
            Browse openings <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    );
  }

  if (error || !opening) {
    return (
      <div className="min-h-screen bg-[#06060B] text-white flex items-center justify-center">
        <p className="text-gray-400">Couldn't load this guide. Try again in a moment.</p>
      </div>
    );
  }

  return <OpeningGuideContent opening={opening} slug={slug} navigate={navigate} />;
};

const OpeningGuideContent = ({ opening, slug, navigate }) => {
  const {
    name,
    color,
    summary,
    difficulty,
    setup_order = [],
    golden_rules = [],
    traps = [],
    middlegame_plans = {},
    endgame_tips = [],
  } = opening;

  // Display name handles "vs Sicilian Defense" framing when this is
  // a defensive guide for the opposite color.
  const displayName = color === "white" ? name : color === "black" ? `${name} (Black)` : name;

  const canonical = `https://chessguru.ai/learn/openings/${slug}`;
  const colorLabel = color === "white" ? "white" : color === "black" ? "black" : "either color";

  // ─── SEO copy ─────────────────────────────────────────────────
  // Title: keyword-led, opening name first, then function. Under 60 chars.
  const seoTitle = `${displayName} — Chess Opening Guide for ${colorLabel}`;
  // Description: 150–160 chars. Names the opening, the rating range,
  // what the guide covers. AI-citation friendly: clean, factual.
  const seoDescription =
    `${summary} Full guide: setup order, golden rules, traps, middlegame plans, and endgame tips. Built for players rated 600–1500.`;

  // ─── FAQ for this opening ─────────────────────────────────────
  // Templated from curriculum data — same shape per opening so
  // FAQPage schema stays consistent. AI engines cite Q&A pairs
  // verbatim; clean structure matters more than clever wording.
  const faqs = [
    {
      q: `What is the ${name}?`,
      a: summary,
    },
    {
      q: `Is the ${name} good for beginners?`,
      a:
        difficulty === "beginner"
          ? `Yes. The ${name} is one of the most beginner-friendly openings — the setup is straightforward and the ideas are clear.`
          : difficulty === "intermediate"
          ? `The ${name} is solid for intermediate players. The setup is approachable but the middlegame requires a real plan.`
          : `The ${name} is best for players who already know basic opening principles. The plans are subtle.`,
    },
    {
      q: `What's the setup order for the ${name}?`,
      a: `The standard setup is ${setup_order.join(", ")}. Play these in order — the goal is fast development before any attacking idea.`,
    },
    {
      q: `What are the main traps in the ${name}?`,
      a:
        traps.length > 0
          ? `The ${name} has ${traps.length} well-known traps. The most common ones catch opponents who play too aggressively or skip development.`
          : `The ${name} doesn't rely on opening traps — it's a positional opening that wins with sound play.`,
    },
    {
      q: `Can I practice the ${name} with the ChessGuru AI coach?`,
      a: `Yes. Sign up free, pick the ${name} from your repertoire, and play training games against an adaptive AI coach that watches your moves and explains why each one works or doesn't.`,
    },
  ];

  // ─── Schema.org JSON-LD ───────────────────────────────────────
  // Course: Google rich result + AI extraction. ItemListElement gives
  // a clean breakdown of what the guide teaches.
  const courseSchema = {
    "@context": "https://schema.org",
    "@type": "Course",
    name: `${displayName} — Chess Opening Guide`,
    description: summary,
    url: canonical,
    provider: {
      "@type": "Organization",
      name: "ChessGuru",
      url: "https://chessguru.ai/",
    },
    educationalLevel: difficulty,
    audience: {
      "@type": "EducationalAudience",
      educationalRole: "chess player rated 600–1500",
    },
    teaches: golden_rules,
    hasCourseInstance: {
      "@type": "CourseInstance",
      courseMode: "online",
      courseWorkload: "PT30M",
    },
  };

  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };

  return (
    <div className="min-h-screen bg-[#06060B] text-white">
      <SEO
        title={seoTitle}
        description={seoDescription}
        canonical={canonical}
        ogType="article"
        breadcrumbs={[
          { name: "Home", url: "/" },
          { name: "Opening Guides", url: "/learn/openings" },
          { name: displayName, url: `/learn/openings/${slug}` },
        ]}
        jsonLd={[courseSchema, faqSchema]}
      />

      {/* Header bar — minimal, brand consistent */}
      <header className="border-b border-white/[0.04] sticky top-0 z-50 bg-[#06060B]/95 backdrop-blur">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <img src="/chessguru-logo.svg" alt="" className="w-5 h-5" />
            <span className="font-heading font-semibold">ChessGuru</span>
          </Link>
          <Link
            to="/"
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            Home
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12 space-y-12">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-xs text-gray-500" aria-label="Breadcrumb">
          <Link to="/" className="hover:text-white transition-colors">Home</Link>
          <ChevronRight className="w-3 h-3" />
          <Link to="/learn/openings" className="hover:text-white transition-colors">Openings</Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-white">{displayName}</span>
        </nav>

        {/* H1 + summary — the SEO meat */}
        <div>
          <p className="text-xs tracking-[0.25em] uppercase font-mono text-amber-400 mb-3">
            {colorLabel === "white" ? "White Opening" : colorLabel === "black" ? "Black Defense" : "Opening Guide"}
            {difficulty && ` · ${difficulty}`}
          </p>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-4xl sm:text-5xl font-heading font-bold tracking-[-0.03em] leading-tight mb-4"
          >
            {displayName}
          </motion.h1>
          <p className="text-lg text-gray-400 leading-relaxed">{summary}</p>
        </div>

        {/* Setup order — high-signal section, named moves */}
        {setup_order.length > 0 && (
          <section>
            <h2 className="text-2xl font-heading font-bold mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-amber-400" />
              Setup order
            </h2>
            <p className="text-sm text-gray-400 mb-4">
              Play these moves in order. The goal: fast development, no early commitments.
            </p>
            <div className="flex flex-wrap gap-2">
              {setup_order.map((move, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.06]"
                >
                  <span className="text-xs font-mono text-gray-500">{i + 1}.</span>
                  <span className="font-mono font-semibold text-amber-400">{move}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Golden rules */}
        {golden_rules.length > 0 && (
          <section>
            <h2 className="text-2xl font-heading font-bold mb-4 flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-amber-400" />
              Golden rules
            </h2>
            <ul className="space-y-3">
              {golden_rules.map((rule, i) => (
                <li
                  key={i}
                  className="p-4 rounded-lg bg-white/[0.02] border border-white/[0.06]"
                >
                  <p className="text-sm text-gray-300 leading-relaxed">
                    <span className="text-amber-400 font-mono mr-2">{i + 1}.</span>
                    {rule}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Traps */}
        {traps.length > 0 && (
          <section>
            <h2 className="text-2xl font-heading font-bold mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-400" />
              Traps in the {name}
            </h2>
            <p className="text-sm text-gray-400 mb-4">
              Lines opponents fall into. The setup looks innocuous; the punishment is decisive.
            </p>
            <div className="space-y-3">
              {traps.map((trap, i) => (
                <div
                  key={i}
                  className="p-4 rounded-lg bg-white/[0.02] border border-amber-500/15"
                >
                  <h3 className="font-heading font-semibold text-amber-400 mb-1">
                    {trap.name || `Trap ${i + 1}`}
                  </h3>
                  {trap.description && (
                    <p className="text-sm text-gray-400">{trap.description}</p>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Middlegame plans */}
        {Object.keys(middlegame_plans).length > 0 && (
          <section>
            <h2 className="text-2xl font-heading font-bold mb-4 flex items-center gap-2">
              <Trophy className="w-5 h-5 text-amber-400" />
              Middlegame plans
            </h2>
            <div className="space-y-4">
              {middlegame_plans.when_ahead && (
                <PlanCard label="When you're ahead" plan={middlegame_plans.when_ahead} />
              )}
              {middlegame_plans.when_equal && (
                <PlanCard label="When the position is equal" plan={middlegame_plans.when_equal} />
              )}
              {middlegame_plans.when_behind && (
                <PlanCard label="When you're behind" plan={middlegame_plans.when_behind} />
              )}
            </div>
          </section>
        )}

        {/* Endgame tips */}
        {endgame_tips.length > 0 && (
          <section>
            <h2 className="text-2xl font-heading font-bold mb-4">Endgame tips</h2>
            <ul className="space-y-2">
              {endgame_tips.map((tip, i) => (
                <li key={i} className="text-sm text-gray-300 leading-relaxed flex items-start gap-2">
                  <span className="text-amber-400 mt-1">•</span>
                  <span>{tip}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* CTA — sign-up driver */}
        <section className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-6 text-center">
          <h2 className="text-xl font-heading font-bold mb-2">
            Practice the {name} with an AI coach
          </h2>
          <p className="text-sm text-gray-400 mb-4 max-w-md mx-auto">
            ChessGuru's AI coach watches every move, names the patterns you're missing, and trains you on positions from your own games.
          </p>
          <button
            onClick={() => navigate("/")}
            className="px-6 py-3 rounded-lg bg-amber-500 text-black font-semibold hover:bg-amber-400 transition-colors inline-flex items-center gap-2"
          >
            Try ChessGuru free <ArrowRight className="w-4 h-4" />
          </button>
        </section>

        {/* FAQ */}
        <section id="faq">
          <h2 className="text-2xl font-heading font-bold mb-4">
            Common questions about the {name}
          </h2>
          <div className="space-y-3">
            {faqs.map((item, i) => (
              <details
                key={i}
                className="group rounded-lg border border-white/[0.06] bg-white/[0.02]"
              >
                <summary className="cursor-pointer p-4 list-none flex items-start justify-between gap-4">
                  <h3 className="text-base font-heading font-semibold">{item.q}</h3>
                  <ChevronRight className="w-4 h-4 text-amber-400/60 mt-1 flex-shrink-0 transition-transform group-open:rotate-90" />
                </summary>
                <div className="px-4 pb-4 -mt-1">
                  <p className="text-sm text-gray-400 leading-relaxed">{item.a}</p>
                </div>
              </details>
            ))}
          </div>
        </section>
      </main>

      <footer className="py-8 border-t border-white/[0.04] mt-12">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <p className="text-xs text-gray-600">
            <Link to="/learn/openings" className="hover:text-white transition-colors">
              Browse all opening guides
            </Link>
            {" · "}
            <Link to="/" className="hover:text-white transition-colors">
              ChessGuru home
            </Link>
          </p>
        </div>
      </footer>
    </div>
  );
};

const PlanCard = ({ label, plan }) => (
  <div className="p-4 rounded-lg bg-white/[0.02] border border-white/[0.06]">
    <p className="text-xs tracking-wide uppercase text-gray-500 mb-2">{label}</p>
    <p className="text-sm text-gray-300 mb-3 font-medium">{plan.plan}</p>
    {plan.ideas && plan.ideas.length > 0 && (
      <ul className="space-y-1">
        {plan.ideas.map((idea, i) => (
          <li key={i} className="text-xs text-gray-400 flex items-start gap-2">
            <span className="text-amber-400 mt-0.5">·</span>
            <span>{idea}</span>
          </li>
        ))}
      </ul>
    )}
  </div>
);

export default OpeningGuide;
