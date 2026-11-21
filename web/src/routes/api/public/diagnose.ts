import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/api/public/diagnose")({
  server: { handlers: { POST: async ({ request }) => {
    const { diagnoseTraining } = await import("@/lib/diagnostics.server");
    return diagnoseTraining(request);
  } } },
});