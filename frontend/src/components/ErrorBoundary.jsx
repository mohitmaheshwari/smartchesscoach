import React from "react";

/**
 * A render crash used to blank the whole page.
 *
 * Mohit 2026-10-10, on /admin/detector-review: "page loads up a list and then
 * goes here" -- a screenshot of an empty dark window. The API was fine; every
 * endpoint returned 200 and the payload had no nulls and no missing keys. One
 * component threw while rendering, React unmounted the tree, and because the
 * app had NO error boundary anywhere the result was a blank page with the
 * reason only in a console neither of us was looking at.
 *
 * This does not fix the crash. It makes the page say what the crash was, and
 * on which card, so the next one takes a minute instead of an afternoon.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    this.setState({ info });
    // Keep the console copy: the boundary shows the message, the console
    // keeps the full component stack.
    console.error("[ErrorBoundary]", this.props.where || "", error, info);
  }

  render() {
    const { error, info } = this.state;
    if (!error) return this.props.children;
    const stack = String(info?.componentStack || "").trim().split("\n")[0];
    return (
      <div className="m-4 rounded border border-rose-400/60 bg-rose-50 p-4 text-sm dark:bg-rose-950/30">
        <p className="font-semibold text-rose-800 dark:text-rose-200">
          This part of the page failed to render.
        </p>
        <p className="mt-1 text-rose-900/90 dark:text-rose-100/90">
          {String(error?.message || error)}
        </p>
        {this.props.where && (
          <p className="mt-1 text-xs text-rose-900/70 dark:text-rose-100/70">
            where: {this.props.where}
          </p>
        )}
        {stack && (
          <p className="mt-1 font-mono text-xs text-rose-900/70 dark:text-rose-100/70">
            {stack}
          </p>
        )}
        <button
          type="button"
          onClick={() => this.setState({ error: null, info: null })}
          className="mt-3 rounded border border-rose-400 px-2 py-1 text-xs"
        >
          Try rendering again
        </button>
      </div>
    );
  }
}
