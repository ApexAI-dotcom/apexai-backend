import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Zap, LogOut, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useAuth } from "@/hooks/useAuth";
import { SubscriptionBadge } from "@/components/SubscriptionBadge";
import { ADMIN_EMAIL } from "@/constants";

const navItems = [
  { name: "Accueil", path: "/" },
  { name: "Tableau de bord", path: "/dashboard" },
  { name: "Télécharger", path: "/upload" },
  { name: "Tarifs", path: "/pricing" },
];

export const Navbar = () => {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user, signOut, loading } = useAuth();

  const handleSignOut = async () => {
    const { error } = await signOut();
    if (!error) {
      navigate("/");
    }
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass-card border-b border-white/5">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo → accueil */}
          <Link to="/" replace className="flex items-center gap-2 group transition-opacity hover:opacity-90 cursor-pointer no-underline">
            <div className="w-10 h-10 rounded-lg gradient-primary flex items-center justify-center shadow-lg shadow-primary/30 group-hover:scale-110 group-hover:shadow-orange-500/50 transition-transform duration-200 cursor-pointer">
              <Zap className="w-5 h-5 text-primary-foreground" />
            </div>
            <span className="font-display font-bold text-xl text-foreground group-hover:text-primary/90 transition-colors">
              APEX<span className="text-primary">AI</span>
            </span>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-8">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`text-sm font-medium transition-all ${
                  location.pathname === item.path
                    ? "text-primary"
                    : "text-muted-foreground hover:text-orange-400 hover:underline underline-offset-4"
                }`}
              >
                {item.name}
              </Link>
            ))}
          </div>

          {/* Desktop CTA */}
          <div className="hidden md:flex items-center gap-3">
            {loading ? (
              <div className="w-8 h-8 animate-pulse bg-secondary rounded" />
            ) : isAuthenticated ? (
              <>
                {user?.email === ADMIN_EMAIL && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-600 text-white border border-red-500 shadow-sm">
                    Admin
                  </span>
                )}
                <SubscriptionBadge />
                <Link to="/profile">
                  <Button variant="ghost" size="sm" className="gap-2">
                    {(user?.user_metadata?.avatar_url as string) ? (
                      <Avatar className="w-6 h-6 rounded-lg">
                        <AvatarImage src={user.user_metadata.avatar_url as string} alt="" className="object-cover" />
                        <AvatarFallback className="rounded-lg text-xs">
                          {(user?.user_metadata?.full_name || user?.email || "U").toString().slice(0, 2).toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                    ) : (
                      <User className="w-4 h-4" />
                    )}
                    {user?.user_metadata?.full_name || user?.email?.split("@")[0] || "Profil"}
                  </Button>
                </Link>
                <Link to="/upload">
                  <Button variant="hero" size="sm">
                    Analyser CSV
                  </Button>
                </Link>
                <Button variant="ghost" size="sm" onClick={handleSignOut} className="gap-2">
                  <LogOut className="w-4 h-4" />
                  Déconnexion
                </Button>
              </>
            ) : (
              <>
                <Link to="/login">
                  <Button variant="ghost" size="sm">
                    Connexion
                  </Button>
                </Link>
                <Link to="/login">
                  <Button variant="hero" size="sm">
                    Inscription
                  </Button>
                </Link>
              </>
            )}
          </div>

          {/* Mobile Menu Button */}
          <button onClick={() => setIsOpen(!isOpen)} className="md:hidden p-2 text-foreground">
            {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden glass-card border-t border-white/5"
          >
            <div className="container mx-auto px-4 py-4 flex flex-col gap-4">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setIsOpen(false)}
                  className={`text-sm font-medium py-2 rounded-lg transition-all hover:bg-slate-800 hover:scale-[1.02] ${
                    location.pathname === item.path ? "text-primary" : "text-muted-foreground"
                  }`}
                >
                  {item.name}
                </Link>
              ))}
              <div className="flex flex-col gap-2 pt-4 border-t border-white/5">
                {loading ? (
                  <div className="w-full h-10 animate-pulse bg-secondary rounded" />
                ) : isAuthenticated ? (
                  <>
                    {user?.email === ADMIN_EMAIL && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-600 text-white border border-red-500 shadow-sm w-fit">
                        Admin
                      </span>
                    )}
                    <div className="w-fit">
                      <SubscriptionBadge />
                    </div>
                    <Link to="/profile" onClick={() => setIsOpen(false)}>
                      <Button variant="ghost" className="w-full gap-2">
                        <User className="w-4 h-4" />
                        {user?.user_metadata?.full_name || user?.email?.split("@")[0] || "Mon Profil"}
                      </Button>
                    </Link>
                    <Link to="/upload" onClick={() => setIsOpen(false)}>
                      <Button variant="hero" className="w-full">
                        Analyser CSV
                      </Button>
                    </Link>
                    <Button
                      variant="ghost"
                      className="w-full gap-2"
                      onClick={() => {
                        setIsOpen(false);
                        handleSignOut();
                      }}
                    >
                      <LogOut className="w-4 h-4" />
                      Déconnexion
                    </Button>
                  </>
                ) : (
                  <>
                    <Link to="/login" onClick={() => setIsOpen(false)}>
                      <Button variant="ghost" className="w-full">
                        Connexion
                      </Button>
                    </Link>
                    <Link to="/login" onClick={() => setIsOpen(false)}>
                      <Button variant="hero" className="w-full">
                        Inscription
                      </Button>
                    </Link>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
};
