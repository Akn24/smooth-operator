'use client';

import { useAuth } from '@/context/AuthContext';
import { Sparkles, LogOut, User } from 'lucide-react';
import Link from 'next/link';

export default function Header() {
  const { user, signOut, isDemoMode } = useAuth();

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link href="/" className="flex items-center gap-2">
            <div className="p-2 bg-gradient-to-r from-purple-600 to-blue-600 rounded-lg">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900">Smooth Operator</span>
            {isDemoMode && (
              <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded-full">
                Demo Mode
              </span>
            )}
          </Link>

          <nav className="flex items-center gap-4">
            <Link
              href="/connect"
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Connections
            </Link>

            {user && (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <User className="w-4 h-4" />
                  <span>{user.email}</span>
                </div>

                <button
                  onClick={() => signOut()}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  {isDemoMode ? 'Exit Demo' : 'Sign Out'}
                </button>
              </div>
            )}
          </nav>
        </div>
      </div>
    </header>
  );
}
