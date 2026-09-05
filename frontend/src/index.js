import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Automatically attach session_token from localStorage to all API fetch requests
const originalFetch = window.fetch;
window.fetch = async function (resource, init = {}) {
  try {
    const token = localStorage.getItem("session_token");
    if (token) {
      const headers = new Headers(init.headers || {});
      if (!headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${token}`);
      }
      init = {
        ...init,
        headers,
        credentials: init.credentials || "include",
      };
    }
  } catch (e) {
    // Ignore localStorage access errors if any
  }
  return originalFetch(resource, init);
};

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
