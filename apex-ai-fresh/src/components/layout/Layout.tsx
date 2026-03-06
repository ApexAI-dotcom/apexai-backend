import { ReactNode } from "react";
import { Navbar } from "./Navbar";
import { MobileNav } from "./MobileNav";
import { LegalFooter } from "@/components/legal/LegalFooter";

interface LayoutProps {
  children: ReactNode;
}

export const Layout = ({ children }: LayoutProps) => {
  return (
    <div className="min-h-screen min-h-[100dvh] bg-background overflow-x-hidden flex flex-col">
      <Navbar />
      <main className="pt-16 pb-24 md:pb-0 flex-1">{children}</main>
      <LegalFooter />
      <MobileNav />
    </div>
  );
};
