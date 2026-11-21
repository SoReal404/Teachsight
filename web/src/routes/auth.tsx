import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/auth")({
  head: () => ({ meta: [{ title: "Teachsight — reset password" }, { name: "description", content: "Reset your Teachsight account password." }, { property: "og:title", content: "Teachsight — reset password" }, { property: "og:description", content: "Securely reset your Teachsight password." }, { property: "og:type", content: "website" }, { name: "twitter:card", content: "summary" }] }),
  component: PasswordReset,
});
function PasswordReset() {
  const [password, setPassword] = useState(""); const [message, setMessage] = useState("");
  return <main className="mx-auto max-w-md space-y-4 p-8"><h1>Reset password</h1><input aria-label="New password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /><Button onClick={async () => { const { error } = await supabase.auth.updateUser({ password }); setMessage(error ? error.message : "Password updated."); }}>Save password</Button><p role="status">{message}</p><a href="/">Back to Teachsight</a></main>;
}