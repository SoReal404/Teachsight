import { createFileRoute } from "@tanstack/react-router";
import { lazy, Suspense, useEffect, useState } from "react";

// The app talks to the engine on the user's PC and uses browser storage, so it renders only in the browser.
const App = lazy(() => import("@/teachsight/App"));

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Teachsight — train picture AI on your PC" },
      { name: "description", content: "Teachsight walks you through adding pictures, training, testing and improving an image classifier on your own computer." },
      { property: "og:title", content: "Teachsight — train picture AI on your PC" },
      { property: "og:description", content: "Add pictures, train, test and improve an image classifier step by step." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  if (!ready) return <div className="app" />;
  return (
    <Suspense fallback={<div className="app" />}>
      <App />
    </Suspense>
  );
}
