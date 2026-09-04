import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Automatically attach session_token from localStorage to all API fetch requests
const originalFetch = window.fetch;
window.fetch = async function (resource, init = {}) {
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
  return originalFetch(resource, init);
};

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

