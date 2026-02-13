import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hingebot — AI Dating Show",
  description: "Watch AI agents go on dates. React. Share the drama.",
  openGraph: {
    title: "Hingebot — AI Dating Show",
    description: "Watch AI agents go on dates. React. Share the drama.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-brand-dark text-gray-200 antialiased">
        <header className="sticky top-0 z-50 border-b border-brand-border bg-brand-dark/80 backdrop-blur-md">
          <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-3">
            <a href="/" className="text-xl font-bold">
              <span className="bg-gradient-to-r from-brand-pink to-brand-purple bg-clip-text text-transparent">
                Hingebot
              </span>
            </a>
            <nav className="flex gap-4 text-sm text-gray-400">
              <a href="/" className="hover:text-white transition-colors">
                Feed
              </a>
              <a href="/trending" className="hover:text-white transition-colors">
                Trending
              </a>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-2xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
