import React from "react";

/**
 * Per-route SEO component using React 19's native metadata hoisting.
 *
 * React 19 lifts <title>, <meta>, <link> rendered anywhere in the
 * component tree to the document <head> automatically. No external
 * library (react-helmet-async) needed.
 *
 * Usage in a page:
 *   <SEO
 *     title="Italian Game — White Opening Guide"
 *     description="Full guide to playing the Italian Game as White..."
 *     canonical="https://chessguru.ai/learn/openings/italian-game"
 *     ogImage="https://chessguru.ai/og-image.png"
 *     jsonLd={[<Course schema>, <FAQPage schema>]}
 *     breadcrumbs={[{ name: "Home", url: "/" }, { name: "Openings", url: "/learn/openings" }, ...]}
 *   />
 *
 * Defaults are baked into index.html so when this component is absent
 * the route still has Landing-targeted meta. Per-route SEO OVERRIDES
 * the static baseline. React 19 doesn't deduplicate, so we render
 * exactly the tags we want — index.html keeps providing only what
 * we don't override (icons, manifest, fonts).
 *
 * For SoftwareApplication / Organization JSON-LD that should appear
 * site-wide, use index.html. For per-page Course / FAQPage / Article
 * / BreadcrumbList, pass via jsonLd here.
 */
export const SEO = ({
  title,
  description,
  canonical,
  ogImage = "https://chessguru.ai/og-image.png",
  ogType = "website",
  jsonLd = [],
  breadcrumbs = [],
  noindex = false,
}) => {
  const fullTitle = title?.endsWith("ChessGuru") ? title : `${title} | ChessGuru`;

  // Auto-generate BreadcrumbList JSON-LD if breadcrumbs provided.
  // Helps Google show the breadcrumb trail in search results AND
  // gives AI engines a clean hierarchy to follow when citing.
  const breadcrumbSchema =
    breadcrumbs.length > 0
      ? {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          itemListElement: breadcrumbs.map((b, i) => ({
            "@type": "ListItem",
            position: i + 1,
            name: b.name,
            item: b.url.startsWith("http") ? b.url : `https://chessguru.ai${b.url}`,
          })),
        }
      : null;

  const allSchemas = breadcrumbSchema ? [breadcrumbSchema, ...jsonLd] : jsonLd;

  return (
    <>
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      {noindex && <meta name="robots" content="noindex, nofollow" />}

      {canonical && <link rel="canonical" href={canonical} />}

      {/* Open Graph — social share preview */}
      <meta property="og:type" content={ogType} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      {canonical && <meta property="og:url" content={canonical} />}
      <meta property="og:image" content={ogImage} />
      <meta property="og:site_name" content="ChessGuru" />

      {/* Twitter / X — same content, separate namespace */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={ogImage} />

      {/* JSON-LD structured data — Google rich results + AI citation */}
      {allSchemas.map((schema, i) => (
        <script
          key={`jsonld-${i}`}
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
        />
      ))}
    </>
  );
};

export default SEO;
