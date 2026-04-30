import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ChevronRight, Loader2 } from "lucide-react";
import { API } from "@/App";
import SEO from "@/components/seo/SEO";

/**
 * Public openings index — /learn/openings
 *
 * Hub page that lists every opening guide. Indexable, no auth.
 * Doubles as the landing target for "chess opening guide" searches
 * AND as the parent for breadcrumb hierarchy on the per-opening pages.
 */
const OpeningsIndex = () => {
  const [openings, setOpenings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/public/openings`);
        if (res.ok) {
          const data = await res.json();
          if (!cancelled) setOpenings(data.openings || []);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Group by color for clearer hierarchy
  const whiteOpenings = openings.filter((o) => o.color === "white");
  const blackOpenings = openings.filter((o) => o.color === "black");
  const otherOpenings = openings.filter((o) => o.color !== "white" && o.color !== "black");

  // Schema: ItemList of opening Course entries — Google indexes this
  // as a list of related courses; AI engines extract the full set
  // when users ask "what chess openings should I learn"
  const itemListSchema =
    openings.length > 0
      ? {
          "@context": "https://schema.org",
          "@type": "ItemList",
          itemListElement: openings.map((o, i) => ({
            "@type": "ListItem",
            position: i + 1,
            url: `https://chessguru.ai/learn/openings/${o.slug}`,
            name: o.name,
          })),
        }
      : null;

  return (
    <div className="min-h-screen bg-[#06060B] text-white">
      <SEO
        title="Chess Opening Guides for 600–1500 Rated Players"
        description="Free, in-depth guides to popular chess openings. Setup order, golden rules, traps, middlegame plans, and endgame tips for the Italian Game, Sicilian, French, Caro-Kann, Queen's Gambit, Ruy Lopez, and more."
        canonical="https://chessguru.ai/learn/openings"
        breadcrumbs={[
          { name: "Home", url: "/" },
          { name: "Opening Guides", url: "/learn/openings" },
        ]}
        jsonLd={itemListSchema ? [itemListSchema] : []}
      />

      <header className="border-b border-white/[0.04] sticky top-0 z-50 bg-[#06060B]/95 backdrop-blur">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <img src="/chessguru-logo.svg" alt="" className="w-5 h-5" />
            <span className="font-heading font-semibold">ChessGuru</span>
          </Link>
          <Link to="/" className="text-sm text-gray-400 hover:text-white transition-colors">
            Home
          </Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-12 space-y-10">
        <nav className="flex items-center gap-2 text-xs text-gray-500" aria-label="Breadcrumb">
          <Link to="/" className="hover:text-white transition-colors">Home</Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-white">Opening Guides</span>
        </nav>

        <div>
          <p className="text-xs tracking-[0.25em] uppercase font-mono text-amber-400 mb-3">
            Opening Guides
          </p>
          <h1 className="text-4xl sm:text-5xl font-heading font-bold tracking-[-0.03em] leading-tight mb-4">
            Chess opening guides
          </h1>
          <p className="text-lg text-gray-400 leading-relaxed max-w-2xl">
            Setup order, golden rules, traps, middlegame plans, and endgame tips —
            built for players rated 600–1500. Pick an opening to get the full guide.
          </p>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-amber-400" />
          </div>
        ) : (
          <>
            {whiteOpenings.length > 0 && (
              <OpeningSection title="As White" openings={whiteOpenings} />
            )}
            {blackOpenings.length > 0 && (
              <OpeningSection title="As Black" openings={blackOpenings} />
            )}
            {otherOpenings.length > 0 && (
              <OpeningSection title="Other" openings={otherOpenings} />
            )}
          </>
        )}

        {/* CTA — funnel to signup */}
        <section className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-6 text-center mt-12">
          <h2 className="text-xl font-heading font-bold mb-2">
            Practice these openings with an AI coach
          </h2>
          <p className="text-sm text-gray-400 mb-4 max-w-md mx-auto">
            Reading an opening guide is one thing. Playing it against an adaptive AI coach who watches every move is how it sticks.
          </p>
          <Link
            to="/"
            className="px-6 py-3 rounded-lg bg-amber-500 text-black font-semibold hover:bg-amber-400 transition-colors inline-flex items-center gap-2"
          >
            Try ChessGuru free <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
      </main>

      <footer className="py-8 border-t border-white/[0.04] mt-12">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <p className="text-xs text-gray-600">
            <Link to="/" className="hover:text-white transition-colors">
              ChessGuru home
            </Link>
          </p>
        </div>
      </footer>
    </div>
  );
};

const OpeningSection = ({ title, openings }) => (
  <section>
    <h2 className="text-xl font-heading font-bold text-gray-300 mb-4">{title}</h2>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {openings.map((o) => (
        <Link
          key={o.slug}
          to={`/learn/openings/${o.slug}`}
          className="group p-4 rounded-lg border border-white/[0.06] bg-white/[0.02] hover:border-amber-500/20 hover:bg-amber-500/[0.03] transition-all"
        >
          <div className="flex items-start justify-between gap-3 mb-1">
            <h3 className="font-heading font-semibold text-white group-hover:text-amber-300 transition-colors">
              {o.name}
            </h3>
            {o.difficulty && (
              <span className="text-[10px] uppercase tracking-wide text-gray-500 mt-1">
                {o.difficulty}
              </span>
            )}
          </div>
          {o.summary && (
            <p className="text-xs text-gray-400 leading-relaxed line-clamp-2">
              {o.summary}
            </p>
          )}
          {o.trap_count > 0 && (
            <p className="text-[10px] text-amber-400/80 mt-2">
              {o.trap_count} trap{o.trap_count === 1 ? "" : "s"}
            </p>
          )}
        </Link>
      ))}
    </div>
  </section>
);

export default OpeningsIndex;
