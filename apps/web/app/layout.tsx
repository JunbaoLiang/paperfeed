import type { Metadata, Viewport } from "next";
import { Newsreader, IBM_Plex_Mono } from "next/font/google";
import NavBar from "@/components/NavBar";
import "./globals.css";

const newsreader = Newsreader({
  subsets: ["latin"],
  style: ["normal", "italic"],
  variable: "--font-newsreader",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "PaperFeed · 每日 arXiv 推荐",
  description: "单用户 arXiv 论文推荐系统 — 端到端 ML 生命周期演示",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${newsreader.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <NavBar />
        <main className="flex-1 w-full">{children}</main>
        <footer className="mt-16 border-t border-line">
          <div className="mx-auto max-w-5xl px-4 py-6 flex items-center justify-between text-xs text-ink-faint">
            <span className="font-data">PaperFeed · single-user arXiv recsys</span>
            <span className="font-data">ingest → embed → rank → learn</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
