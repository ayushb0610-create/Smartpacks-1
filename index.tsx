import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "SmartPack — Packaging Recommender" },
      {
        name: "description",
        content: "Compare food-packaging materials, barrier requirements, shelf life, and spoilage risk.",
      },
      { property: "og:title", content: "SmartPack — Packaging Recommender" },
      {
        property: "og:description",
        content: "Compare food-packaging materials, barrier requirements, shelf life, and spoilage risk.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <main className="smartpack-frame-shell">
      <iframe
        className="smartpack-frame"
        src="/smartpack.html?v=risk2"
        title="SmartPack packaging recommender"
      />
    </main>
  );
}
