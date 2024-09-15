// components/Navbar.tsx
import Link from "next/link";

export function Navbar() {
  return (
    <header className="bg-white shadow">
      <nav className="container mx-auto px-4 py-3 flex justify-between items-center">
        <Link href="/" className="text-2xl font-bold text-gray-800">
          GenAI Showcase
        </Link>
        <div>
          <Link href="/about" className="text-gray-600 hover:text-gray-800">
            About
          </Link>
        </div>
      </nav>
    </header>
  );
}
