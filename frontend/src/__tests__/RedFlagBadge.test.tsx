/**
 * Tests for RedFlagBadge component (#73).
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RedFlagBadge } from "@/components/RedFlagBadge";
import type { RedFlag } from "@/api/types";

const flags: RedFlag[] = [
  {
    flag_type: "stale_posting",
    severity: "warning",
    description: "Posting is 120 days old",
  },
  {
    flag_type: "staffing_agency",
    severity: "caution",
    description: "Role via staffing agency",
  },
];

describe("RedFlagBadge", () => {
  describe("compact mode", () => {
    it("renders nothing when flags is null", () => {
      const { container } = render(<RedFlagBadge flags={null} />);
      expect(container.firstChild).toBeNull();
    });

    it("renders nothing when flags is empty", () => {
      const { container } = render(<RedFlagBadge flags={[]} />);
      expect(container.firstChild).toBeNull();
    });

    it("renders a count pill with warning background for worst severity", () => {
      render(<RedFlagBadge flags={flags} testId="rb" />);
      const badge = screen.getByTestId("rb");
      // Worst severity is "warning" -> orange pill.
      expect(badge.className).toContain("bg-orange-100");
      expect(badge.textContent).toContain("2");
    });

    it("picks dealbreaker as worst severity over everything else", () => {
      const worstCase: RedFlag[] = [
        ...flags,
        {
          flag_type: "blacklisted_company",
          severity: "dealbreaker",
          description: "Known bad actor",
        },
      ];
      render(<RedFlagBadge flags={worstCase} testId="rb" />);
      const badge = screen.getByTestId("rb");
      expect(badge.className).toContain("bg-red-100");
      expect(badge.textContent).toContain("3");
    });

    it("uses gray pill when only info flags are present", () => {
      const infoOnly: RedFlag[] = [
        {
          flag_type: "vague_responsibilities",
          severity: "info",
          description: "Short description",
        },
      ];
      render(<RedFlagBadge flags={infoOnly} testId="rb" />);
      const badge = screen.getByTestId("rb");
      expect(badge.className).toContain("bg-gray-100");
    });
  });

  describe("expanded mode", () => {
    it("renders a list row per flag with description", () => {
      render(<RedFlagBadge flags={flags} mode="expanded" testId="list" />);
      const list = screen.getByTestId("list");
      expect(list.tagName).toBe("UL");
      expect(list.children).toHaveLength(2);
      expect(list.textContent).toContain("Posting is 120 days old");
      expect(list.textContent).toContain("Role via staffing agency");
      expect(list.textContent).toContain("Warning");
      expect(list.textContent).toContain("Caution");
    });

    it("renders nothing when flags is null in expanded mode", () => {
      const { container } = render(
        <RedFlagBadge flags={null} mode="expanded" />,
      );
      expect(container.firstChild).toBeNull();
    });
  });
});
