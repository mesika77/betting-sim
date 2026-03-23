import type { Metadata } from "next";
import localFont from "next/font/local";
import Link from "next/link";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "Betting Sim Dashboard",
  description: "Track your simulated betting performance",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-gray-50 min-h-screen`}
      >
        <nav className="bg-white border-b border-gray-200 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              <Link
                href="/"
                className="text-lg font-bold text-blue-600 tracking-tight hover:text-blue-700 transition-colors"
              >
                Betting Sim
              </Link>
              <div className="flex items-center gap-6">
                <Link
                  href="/"
                  className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
                >
                  Overview
                </Link>
                <Link
                  href="/history"
                  className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
                >
                  History
                </Link>
                <Link
                  href="/analytics"
                  className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
                >
                  Analytics
                </Link>
              </div>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
