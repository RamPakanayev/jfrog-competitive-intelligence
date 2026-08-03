import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CitationChips, ImpactBadge } from "./ui";

describe("CitationChips", () => {
  const articles = {
    "7": { id: 7, title: "Snyk pricing", url: "https://x/7", published_at: "2026-08-02T00:00:00Z", source_name: "Blog" },
  };
  it("renders links only for resolvable ids", () => {
    render(<CitationChips ids={[7, 999]} articles={articles} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://x/7");
    expect(link.textContent).toContain("[7]");
    expect(link.textContent).toContain("2026-08-02");   // timestamped citation
    expect(screen.queryByText("[999]")).toBeNull();     // hallucinated id renders nothing
  });
});

describe("ImpactBadge", () => {
  it("colors high impact red-ish and shows value", () => {
    render(<ImpactBadge value={5} />);
    expect(screen.getByText("impact 5").className).toContain("red");
  });
});
