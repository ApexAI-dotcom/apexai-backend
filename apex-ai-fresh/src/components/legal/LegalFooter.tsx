import { Link } from "react-router-dom";

export const LegalFooter = () => (
  <footer className="border-t border-white/5 bg-card/30 py-6 pb-24 md:pb-6 mt-auto">
    <div className="container mx-auto px-4">
      <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
        <div>
          <strong className="text-foreground">Apex AI</strong>
          <span className="mx-1">•</span>
          <span>France</span>
        </div>
        <nav className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2">
          <Link
            to="/legal"
            className="hover:text-foreground hover:underline font-medium transition-colors"
          >
            Mentions légales
          </Link>
          <span className="text-muted-foreground/60" aria-hidden>·</span>
          <Link
            to="/legal#cgv"
            className="hover:text-foreground hover:underline transition-colors"
          >
            CGV
          </Link>
          <span className="text-muted-foreground/60" aria-hidden>·</span>
          <Link
            to="/legal#cgu"
            className="hover:text-foreground hover:underline transition-colors"
          >
            CGU
          </Link>
          <span className="text-muted-foreground/60" aria-hidden>·</span>
          <a
            href="mailto:contact@apexai.run"
            className="hover:text-foreground hover:underline transition-colors"
            rel="noopener noreferrer"
          >
            Contact
          </a>
        </nav>
      </div>
    </div>
  </footer>
);
