'use client';

import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from 'react';
import { supabase, AuthUser } from '@/lib/supabase';
import { api } from '@/lib/api';

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  isDemoMode: boolean;
  enterDemoMode: () => void;
  exitDemoMode: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [isDemoMode, setIsDemoMode] = useState(false);

  useEffect(() => {
    // Check for existing session
    const checkSession = async () => {
      try {
        // Check if in demo mode from localStorage
        const demoMode = localStorage.getItem('proactivepa_demo_mode');
        if (demoMode === 'true') {
          setIsDemoMode(true);
          setUser({ id: 'demo-user', email: 'demo@example.com' });
          api.setUserId('demo-user');
          setLoading(false);
          return;
        }

        const { data: { session } } = await supabase.auth.getSession();
        if (session?.user) {
          const authUser: AuthUser = {
            id: session.user.id,
            email: session.user.email || '',
          };
          setUser(authUser);
          api.setUserId(authUser.id);
        }
      } catch (error) {
        console.error('Error checking session:', error);
      } finally {
        setLoading(false);
      }
    };

    checkSession();

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (session?.user) {
          const authUser: AuthUser = {
            id: session.user.id,
            email: session.user.email || '',
          };
          setUser(authUser);
          api.setUserId(authUser.id);
        } else if (!isDemoMode) {
          setUser(null);
          api.setUserId(null);
        }
      }
    );

    return () => {
      subscription.unsubscribe();
    };
  }, [isDemoMode]);

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw error;
  };

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({
      email,
      password,
    });
    if (error) throw error;
  };

  const signOut = async () => {
    if (isDemoMode) {
      exitDemoMode();
      return;
    }
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
    setUser(null);
    api.setUserId(null);
  };

  const enterDemoMode = () => {
    localStorage.setItem('proactivepa_demo_mode', 'true');
    setIsDemoMode(true);
    setUser({ id: 'demo-user', email: 'demo@example.com' });
    api.setUserId('demo-user');
  };

  const exitDemoMode = () => {
    localStorage.removeItem('proactivepa_demo_mode');
    setIsDemoMode(false);
    setUser(null);
    api.setUserId(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        signIn,
        signUp,
        signOut,
        isDemoMode,
        enterDemoMode,
        exitDemoMode,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
