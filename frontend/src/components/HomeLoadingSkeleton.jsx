/**
 * HomeLoadingSkeleton - what /home shows while it is thinking.
 *
 * Mohit 2026-09-17: "no loader shows up here, a very very sexy loader should
 * show up please."
 *
 * It was a 24px spinner alone in 60vh of empty page, which reads as a broken
 * page rather than a loading one - and /home waits on two requests, so it is
 * on screen long enough to matter.
 *
 * This mirrors the real layout instead: the same cg-hero eyebrow / title /
 * lede and the same cg-panel that CurriculumHome renders, at the same widths.
 * Nothing jumps when the content arrives, because the shapes were already
 * where the content lands.
 *
 * The stagger is the whole trick. One uniform pulse looks like a dead page
 * blinking; offsetting each row by 90ms makes it read as a wave moving down
 * the page, which is what makes a skeleton feel alive. motion-reduce turns it
 * off for anyone who has asked the OS for less animation.
 */
import { Skeleton } from "@/components/ui/skeleton";

// A row that joins the wave. Delay is inline because Tailwind has no
// arbitrary animation-delay utility we can rely on across versions.
function Line({ className, delay = 0 }) {
  return (
    <Skeleton
      className={`motion-reduce:animate-none ${className}`}
      style={{ animationDelay: `${delay}ms` }}
    />
  );
}

export default function HomeLoadingSkeleton() {
  return (
    <div
      className="cg-page max-w-[960px]"
      role="status"
      aria-busy="true"
      aria-live="polite"
      data-testid="home-loading-skeleton"
    >
      {/* Screen readers get words; everyone else gets the shapes. */}
      <span className="sr-only">Loading your coaching home…</span>

      <header className="cg-hero mb-6">
        <Line className="h-3 w-52 rounded-full" delay={0} />
        <Line className="mt-4 h-8 w-[78%] max-w-[560px] rounded-lg" delay={90} />
        <Line className="mt-3 h-8 w-[52%] max-w-[380px] rounded-lg" delay={180} />
        <Line className="mt-5 h-4 w-[88%] max-w-[640px] rounded-full" delay={270} />
        <Line className="mt-2 h-4 w-[64%] max-w-[460px] rounded-full" delay={360} />
      </header>

      <div className="cg-panel p-5 sm:p-7">
        <Line className="h-4 w-40 rounded-full" delay={450} />
        <Line className="mt-4 h-5 w-[82%] rounded-full" delay={540} />
        <Line className="mt-2 h-5 w-[58%] rounded-full" delay={630} />

        {/* The board preview the real card carries. Square, so the panel
            does not resize under the user when the game loads in. */}
        <div className="mt-6 flex flex-wrap items-start gap-5">
          <Line className="h-[168px] w-[168px] shrink-0 rounded-xl" delay={720} />
          <div className="min-w-[180px] flex-1 space-y-3 pt-1">
            <Line className="h-4 w-[70%] rounded-full" delay={810} />
            <Line className="h-4 w-[48%] rounded-full" delay={900} />
            <Line className="h-4 w-[60%] rounded-full" delay={990} />
          </div>
        </div>

        <Line className="mt-7 h-11 w-44 rounded-full" delay={1080} />
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="cg-panel p-4">
            <Line className="h-3 w-24 rounded-full" delay={1170 + i * 90} />
            <Line className="mt-3 h-6 w-16 rounded-md" delay={1215 + i * 90} />
          </div>
        ))}
      </div>
    </div>
  );
}
