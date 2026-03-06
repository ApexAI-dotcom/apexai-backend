import { useEffect } from "react";

const BASE_URL = "https://apexai.racing";
const DEFAULT_OG_IMAGE = `${BASE_URL}/og-image.svg`;

function setMetaContent(
  doc: Document,
  type: "name" | "property",
  key: string,
  value: string
) {
  const selector = `meta[${type}="${key}"]`;
  let el = doc.querySelector(selector) as HTMLMetaElement | null;
  if (!el) {
    el = doc.createElement("meta");
    el.setAttribute(type, key);
    doc.head.appendChild(el);
  }
  el.setAttribute("content", value);
}

interface PageMetaProps {
  title: string;
  description: string;
  ogTitle?: string;
  ogDescription?: string;
  ogImage?: string;
  path?: string;
}

/**
 * Met à jour title + meta description + og (pour partage social) côté client.
 * Chaque page appelle <PageMeta ... /> en entête.
 */
export function PageMeta({
  title,
  description,
  ogTitle,
  ogDescription,
  ogImage = DEFAULT_OG_IMAGE,
  path,
}: PageMetaProps) {
  useEffect(() => {
    document.title = title;
    setMetaContent(document, "name", "description", description);
    setMetaContent(document, "property", "og:title", ogTitle ?? title);
    setMetaContent(document, "property", "og:description", ogDescription ?? description);
    setMetaContent(document, "property", "og:image", ogImage);
    setMetaContent(
      document,
      "property",
      "og:url",
      path ? `${BASE_URL}${path}` : `${BASE_URL}${window.location.pathname}`
    );
    setMetaContent(document, "name", "twitter:title", ogTitle ?? title);
    setMetaContent(document, "name", "twitter:description", ogDescription ?? description);
  }, [title, description, ogTitle, ogDescription, ogImage, path]);

  return null;
}
