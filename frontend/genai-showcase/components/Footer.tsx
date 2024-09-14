// components/Footer.tsx
import Link from "next/link";

export function Footer() {
  return (
    <footer className="bg-white border-t">
      <div className="container mx-auto px-4 py-6 text-center text-sm text-gray-600">
        © {new Date().getFullYear()}{" "}
        <Link href="/" className="hover:text-gray-800">
          GenAI Chatbot Showcase
        </Link>
        . All rights reserved.
      </div>
    </footer>
  );
}
