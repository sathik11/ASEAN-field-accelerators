// layout.tsx
import "./globals.css";
import { Inter } from "next/font/google";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";

const inter = Inter({ subsets: ["latin"] });

export const metadata = {
  title: "GenAI Chatbot Showcase",
  description: "A showcase of various GenAI chatbots using Next.js App Router",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        className={`${inter.className} bg-gray-50 flex flex-col min-h-screen`}
      >
        <Navbar />
        <main className="container mx-auto px-4 py-6 flex-grow">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
