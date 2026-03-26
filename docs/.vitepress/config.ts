import { defineConfig } from "vitepress";

export default defineConfig({
  title: "DocFlow",
  description: "Automatisierte Dokumentenverarbeitung fuer macOS",
  lang: "de-DE",
  base: "/docs/",
  outDir: "../docs-dist",

  head: [["link", { rel: "icon", type: "image/svg+xml", href: "/docs/logo.svg" }]],

  themeConfig: {
    logo: "/logo.svg",
    siteTitle: "DocFlow",

    nav: [
      { text: "Startseite", link: "/" },
      { text: "Anleitung", link: "/guide/" },
      { text: "Architektur", link: "/architecture/" },
      { text: "API", link: "/api/" },
      { text: "App", link: "http://localhost:8765/" },
    ],

    sidebar: {
      "/guide/": [
        {
          text: "Erste Schritte",
          items: [
            { text: "Ueberblick", link: "/guide/" },
            { text: "Installation", link: "/guide/installation" },
            { text: "Konfiguration", link: "/guide/configuration" },
          ],
        },
        {
          text: "Nutzung",
          items: [
            { text: "Anwendungsflow", link: "/guide/flow" },
            { text: "Dashboard", link: "/guide/dashboard" },
            { text: "Dokumente", link: "/guide/documents" },
            { text: "E-Mail-Eingang", link: "/guide/email" },
          ],
        },
      ],
      "/architecture/": [
        {
          text: "Architektur",
          items: [
            { text: "Ueberblick", link: "/architecture/" },
            { text: "Backend", link: "/architecture/backend" },
            { text: "Frontend", link: "/architecture/frontend" },
            { text: "Pipeline", link: "/architecture/pipeline" },
            { text: "Erweiterbarkeit", link: "/architecture/extending" },
          ],
        },
      ],
      "/api/": [
        {
          text: "API Referenz",
          items: [
            { text: "Endpunkte", link: "/api/" },
            { text: "Runs", link: "/api/runs" },
            { text: "Dokumente", link: "/api/documents" },
            { text: "Einstellungen", link: "/api/settings" },
          ],
        },
      ],
    },

    search: {
      provider: "local",
    },

    socialLinks: [
      { icon: "github", link: "https://github.com/" },
    ],

    footer: {
      message: "DocFlow — Dokumentenverarbeitung fuer macOS",
    },

    outline: {
      level: [2, 3],
      label: "Auf dieser Seite",
    },

    lastUpdated: {
      text: "Zuletzt aktualisiert",
    },

    docFooter: {
      prev: "Vorherige Seite",
      next: "Naechste Seite",
    },
  },
});
