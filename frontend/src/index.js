import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Production polish (2026-06-08): silence debug logging in prod builds so the
// user's DevTools console is clean (the PWC flow logged ~30 [V2-DEBUG]/
// [CoachPlay] lines per move). console.error/warn stay for real diagnostics.
if (process.env.NODE_ENV === "production") {
  console.log = () => {};
  console.debug = () => {};
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
