import { describe, expect, it } from "vitest";
import { extractJob, isJobPage } from "@/lib/extraction";

// ---------------------------------------------------------------------------
// Extraction is a pure function over a `Document`, so every case builds a
// jsdom document via DOMParser (no network, no chrome runtime).
// ---------------------------------------------------------------------------

function doc(html: string): Document {
  return new DOMParser().parseFromString(html, "text/html");
}

function jsonLdScript(payload: unknown): string {
  return `<script type="application/ld+json">${JSON.stringify(payload)}</script>`;
}

describe("Tier 1: JSON-LD JobPosting", () => {
  it("extracts a LinkedIn-style JobPosting with structured confidence", () => {
    const d = doc(`
      <html><head>
        <link rel="canonical" href="https://www.linkedin.com/jobs/view/123" />
        ${jsonLdScript({
          "@context": "https://schema.org/",
          "@type": "JobPosting",
          title: "Senior Backend Engineer",
          description: "<p>Build <strong>distributed</strong> systems in Go.</p>",
          hiringOrganization: { "@type": "Organization", name: "Acme Corp" },
          jobLocation: {
            "@type": "Place",
            address: { "@type": "PostalAddress", addressLocality: "Remote", addressRegion: "CA" },
          },
          baseSalary: {
            "@type": "MonetaryAmount",
            currency: "USD",
            value: { "@type": "QuantitativeValue", minValue: 150000, maxValue: 180000, unitText: "YEAR" },
          },
        })}
      </head><body></body></html>
    `);

    const job = extractJob(d);
    expect(job.confidence).toBe("structured");
    expect(job.title).toBe("Senior Backend Engineer");
    expect(job.company).toBe("Acme Corp");
    // HTML must be stripped to plain text.
    expect(job.description).toBe("Build distributed systems in Go.");
    expect(job.description).not.toContain("<");
    expect(job.location).toBe("Remote, CA");
    expect(job.salary).toContain("150000");
    expect(job.salary).toContain("180000");
    expect(job.url).toBe("https://www.linkedin.com/jobs/view/123");
    expect(job.source).toBe("www.linkedin.com");
  });

  it("finds a JobPosting nested inside an @graph array", () => {
    const d = doc(`
      <html><head>
        ${jsonLdScript({
          "@context": "https://schema.org/",
          "@graph": [
            { "@type": "WebSite", name: "Greenhouse" },
            {
              "@type": "JobPosting",
              title: "Product Manager",
              description: "Own the roadmap.",
              hiringOrganization: { name: "Boards Inc" },
            },
          ],
        })}
      </head><body></body></html>
    `);

    const job = extractJob(d);
    expect(job.confidence).toBe("structured");
    expect(job.title).toBe("Product Manager");
    expect(job.company).toBe("Boards Inc");
    expect(job.description).toBe("Own the roadmap.");
  });

  it("handles a hiringOrganization given as a bare string", () => {
    const d = doc(
      `<html><head>${jsonLdScript({
        "@type": "JobPosting",
        title: "Data Scientist",
        description: "Models.",
        hiringOrganization: "Stringly Co",
      })}</head><body></body></html>`,
    );
    const job = extractJob(d);
    expect(job.company).toBe("Stringly Co");
    expect(job.confidence).toBe("structured");
  });

  it("recognizes an @type array that includes JobPosting", () => {
    const d = doc(
      `<html><head>${jsonLdScript({
        "@type": ["JobPosting", "Thing"],
        title: "SRE",
        description: "Keep it up.",
        hiringOrganization: { name: "Uptime LLC" },
      })}</head><body></body></html>`,
    );
    const job = extractJob(d);
    expect(job.title).toBe("SRE");
    expect(job.company).toBe("Uptime LLC");
  });
});

describe("Tier 2: OpenGraph / meta fallback", () => {
  it("extracts title + company from OG tags when no JSON-LD is present", () => {
    const d = doc(`
      <html><head>
        <meta property="og:title" content="Staff Frontend Engineer" />
        <meta property="og:description" content="React and TypeScript all day." />
        <meta property="og:site_name" content="Lever" />
        <meta property="og:url" content="https://jobs.lever.co/acme/xyz" />
      </head><body></body></html>
    `);

    const job = extractJob(d);
    expect(job.confidence).toBe("structured");
    expect(job.title).toBe("Staff Frontend Engineer");
    expect(job.company).toBe("Lever");
    expect(job.description).toBe("React and TypeScript all day.");
    expect(job.url).toBe("https://jobs.lever.co/acme/xyz");
    expect(job.source).toBe("jobs.lever.co");
  });

  it("degrades to raw when OG has a title but no derivable company", () => {
    const d = doc(`
      <html><head>
        <meta property="og:title" content="Some Job" />
      </head><body>Full posting body text about the role.</body></html>
    `);

    const job = extractJob(d);
    expect(job.confidence).toBe("raw");
    // Raw tier fills description with page text for the backend LLM fallback.
    expect(job.description).toContain("Full posting body text");
  });
});

describe("Tier 3: raw-text fallback", () => {
  it("returns raw confidence with body text when nothing structured exists", () => {
    const d = doc(`
      <html><head><title>Careers</title></head>
      <body><main>We are hiring a Widget Designer. Apply within.</main></body></html>
    `);

    const job = extractJob(d);
    expect(job.confidence).toBe("raw");
    expect(job.title).toBe("");
    expect(job.company).toBe("");
    expect(job.description).toContain("Widget Designer");
  });

  it("caps raw description length", () => {
    const big = "x".repeat(50000);
    const d = doc(`<html><body>${big}</body></html>`);
    const job = extractJob(d);
    expect(job.confidence).toBe("raw");
    expect(job.description.length).toBeLessThanOrEqual(30000);
  });
});

describe("defensive parsing", () => {
  it("does not throw on malformed JSON-LD and falls through to a lower tier", () => {
    const d = doc(`
      <html><head>
        <script type="application/ld+json">{ this is not valid json ]</script>
        <meta property="og:title" content="Resilient Role" />
        <meta property="og:site_name" content="Ashby" />
      </head><body>fallback body</body></html>
    `);

    expect(() => extractJob(d)).not.toThrow();
    const job = extractJob(d);
    // Malformed JSON-LD ignored → OG tier wins.
    expect(job.title).toBe("Resilient Role");
    expect(job.company).toBe("Ashby");
    expect(job.confidence).toBe("structured");
  });

  it("ignores a JSON-LD block that is valid JSON but not a JobPosting", () => {
    const d = doc(
      `<html><head>${jsonLdScript({ "@type": "BreadcrumbList", itemListElement: [] })}</head>` +
        `<body>raw only body</body></html>`,
    );
    const job = extractJob(d);
    expect(job.confidence).toBe("raw");
    expect(job.description).toContain("raw only body");
  });
});

describe("isJobPage", () => {
  it("is true when a JSON-LD JobPosting is present", () => {
    const d = doc(
      `<html><head>${jsonLdScript({ "@type": "JobPosting", title: "X", hiringOrganization: { name: "Y" } })}</head><body></body></html>`,
    );
    expect(isJobPage(d)).toBe(true);
  });

  it("is false on a page with no JobPosting signal", () => {
    const d = doc(`<html><body>just a blog</body></html>`);
    expect(isJobPage(d)).toBe(false);
  });
});
