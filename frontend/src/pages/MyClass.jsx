/**
 * Where a signed-in academy child lands: his own classes (/class/:token).
 * The child signs in with the username his coach set; GET /academy/me says
 * which class page is his.
 */
import { useEffect, useState } from "react";

import { API } from "@/App";

export default function MyClass() {
  const [error, setError] = useState(false);
  useEffect(() => {
    fetch(`${API}/academy/me`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => window.location.replace(d.class_url))
      .catch(() => setError(true));
  }, []);
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6 text-center">
      <p className="max-w-sm text-body text-muted-foreground">
        {error ? "Your coach has not set up your classes yet. Ask your coach." : "Opening your classes…"}
      </p>
    </div>
  );
}
