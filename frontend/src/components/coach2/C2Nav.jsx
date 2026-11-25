/**
 * The /coach2 preview's rail and mobile bar. One NAV list, two pages —
 * the settings preview must not carry its own copy of the destinations.
 *
 * Labelled, never icon-only: an unlabelled rail is the single thing that
 * makes a chess app read as an engine tool rather than a coach.
 */
import React from "react";
import {
  Home,
  BookOpen,
  Target,
  TrendingUp,
  Play,
  Settings as SettingsIcon,
} from "lucide-react";

export const NAV = [
  { label: "Home", Icon: Home, href: "/home" },
  { label: "Learn", Icon: BookOpen, href: "/lab" },
  { label: "Train", Icon: Target, href: "/training/prescribed" },
  { label: "Progress", Icon: TrendingUp, href: "/progress" },
  { label: "Play", Icon: Play, href: "/coach2" },
];

const ACTIVE_STYLE = {
  background: "rgb(var(--cg-accent-rgb) / 0.18)",
  color: "var(--c2-green)",
};

export function C2Rail({ active }) {
  return (
    <nav
      aria-label="Main"
      className="hidden w-[92px] shrink-0 flex-col gap-1 border-r border-border bg-card px-2 py-5 md:flex"
    >
      {NAV.map(({ label, Icon, href }) => {
        const on = label === active;
        return (
          <a
            key={label}
            href={href}
            aria-current={on ? "page" : undefined}
            className={`flex flex-col items-center gap-1.5 rounded-card px-1 py-2.5 text-meta font-semibold no-underline ${
              on ? "" : "text-muted-foreground"
            }`}
            style={on ? ACTIVE_STYLE : undefined}
          >
            <Icon className="h-5 w-5" aria-hidden="true" />
            <span>{label}</span>
          </a>
        );
      })}
      <a
        href="/coach2/settings"
        aria-current={active === "Settings" ? "page" : undefined}
        className={`mt-auto flex flex-col items-center gap-1.5 rounded-card px-1 py-2.5 text-meta font-semibold no-underline ${
          active === "Settings" ? "" : "text-muted-foreground"
        }`}
        style={active === "Settings" ? ACTIVE_STYLE : undefined}
      >
        <SettingsIcon className="h-5 w-5" aria-hidden="true" />
        <span>Settings</span>
      </a>
    </nav>
  );
}

export function C2MobileBar({ active }) {
  return (
    <nav
      aria-label="Main"
      /* z-40: without it the chessground pieces paint THROUGH the bar —
         chessground gives its pieces a stacking context, and a fixed
         element with no z-index does not beat it. Stays under the
         dialog overlay, which is z-50. */
      className="fixed bottom-0 left-0 right-0 z-40 grid h-16 border-t border-border bg-card md:hidden"
      /* grid-auto-flow column so a 5th item cannot wrap onto a second line */
      style={{ gridAutoFlow: "column", gridAutoColumns: "minmax(0, 1fr)" }}
    >
      {NAV.map(({ label, Icon, href }) => {
        const on = label === active;
        return (
          <a
            key={label}
            href={href}
            aria-current={on ? "page" : undefined}
            className={`flex flex-col items-center justify-center gap-1 text-meta font-semibold no-underline ${
              on ? "" : "text-muted-foreground"
            }`}
            style={on ? { color: "var(--c2-green)" } : undefined}
          >
            <Icon className="h-5 w-5" aria-hidden="true" />
            <span>{label}</span>
          </a>
        );
      })}
    </nav>
  );
}
