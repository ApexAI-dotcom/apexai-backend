import { ReactNode } from "react";

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-950 via-slate-900 to-purple-950">
      {children}
    </div>
  );
}
