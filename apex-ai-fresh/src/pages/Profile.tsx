import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import { useUser, useAuth } from "@/hooks/useAuth";
import { useSubscriptionLegacy } from "@/hooks/useSubscriptionLegacy";
import { useSubscription } from "@/hooks/useSubscription";
import { SubscriptionBadge } from "@/components/SubscriptionBadge";
import { createPortalSession } from "@/lib/api";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import {
  User,
  Mail,
  Calendar,
  Trophy,
  TrendingUp,
  Settings,
  ChevronRight,
  CreditCard,
  Loader2,
  LogOut,
  ExternalLink,
  Zap,
  Target,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { PageMeta } from "@/components/seo/PageMeta";
import { Helmet } from "react-helmet-async";
import { getAllAnalyses, type AnalysisSummary } from "@/lib/storage";
import { ADMIN_EMAIL } from "@/constants";

const achievements = [
  { icon: Trophy, title: "Pro Apex", description: "10 analyses complétées" },
  { icon: Zap, title: "Démon de la vitesse", description: "Score > 80 atteint" },
  { icon: Target, title: "Précision", description: "5 apex parfaits consécutifs" },
];

export default function Profile() {
  const { user, loading } = useUser();
  const { signOut } = useAuth();
  const { subscription, isPro, isActive } = useSubscriptionLegacy();
  const {
    tier,
    status,
    billingPeriod,
    subscriptionEndDate,
    isLoading: subscriptionLoading,
  } = useSubscription();
  const hasActivePaidSubscription = (tier === "racer" || tier === "team") && status === "active";
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<AnalysisSummary[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [stats, setStats] = useState({
    totalSessions: 0,
    averageScore: 0,
    totalLaps: 0,
  });
  const [error, setError] = useState<string | null>(null);
  const [loadingPortal, setLoadingPortal] = useState(false);

  // Charger les sessions depuis le storage local
  useEffect(() => {
    const loadSessions = async () => {
      if (!user) return;

      try {
        setLoadingSessions(true);
        setError(null);
        const analyses = await getAllAnalyses(user.id);
        setSessions(analyses.slice(0, 10)); // Limiter à 10 dernières sessions

        // Calculer les statistiques
        if (analyses.length > 0) {
          const totalScore = analyses.reduce((sum, a) => sum + a.score, 0);
          const avgScore = Math.round(totalScore / analyses.length);
          const totalLaps = analyses.reduce((sum, a) => sum + a.corner_count, 0);

          setStats({
            totalSessions: analyses.length,
            averageScore: avgScore,
            totalLaps,
          });
        } else {
          setStats({
            totalSessions: 0,
            averageScore: 0,
            totalLaps: 0,
          });
        }
      } catch (err) {
        console.error("Error loading sessions:", err);
        setError("Erreur lors du chargement des sessions");
      } finally {
        setLoadingSessions(false);
      }
    };

    if (!loading && user) {
      loadSessions();
    }
  }, [user, loading]);

  const handleLogout = async () => {
    try {
      const { error } = await signOut();
      if (error) {
        setError("Erreur lors de la déconnexion");
      } else {
        navigate("/");
      }
    } catch (err) {
      console.error("Logout error:", err);
      setError("Erreur lors de la déconnexion");
    }
  };

  const handleCustomerPortal = async () => {
    if (!user?.id) {
      setError("Session invalide");
      return;
    }
    try {
      setLoadingPortal(true);
      setError(null);
      const { portal_url } = await createPortalSession(user.id);
      if (portal_url) window.location.href = portal_url;
    } catch (err) {
      console.error("Customer portal error:", err);
      setError(
        err instanceof Error ? err.message : "Erreur lors de l'ouverture du portail client"
      );
    } finally {
      setLoadingPortal(false);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
            <p className="text-muted-foreground">Chargement du profil...</p>
          </div>
        </div>
      </Layout>
    );
  }

  if (!user) {
    return (
      <Layout>
        <div className="container mx-auto px-4 py-8">
          <Alert variant="destructive">
            <AlertDescription>Vous devez être connecté pour voir votre profil.</AlertDescription>
          </Alert>
        </div>
      </Layout>
    );
  }

  const displayName = user.user_metadata?.full_name || user.email?.split("@")[0] || "Utilisateur";
  const avatarUrl = user.user_metadata?.avatar_url as string | undefined;

  const getInitials = () => {
    if (user.user_metadata?.full_name) {
      return (user.user_metadata.full_name as string)
        .split(" ")
        .map((n: string) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2);
    }
    if (user.email) {
      return user.email
        .split("@")[0]
        .slice(0, 2)
        .toUpperCase();
    }
    return "U";
  };

  // Formater la date de création
  const getMemberSince = () => {
    if (user.created_at) {
      try {
        return format(new Date(user.created_at), "d MMM yyyy", { locale: fr });
      } catch {
        return format(new Date(user.created_at), "MMM yyyy");
      }
    }
    return "Récemment";
  };

  // Date complète pour l'affichage
  const getFullCreationDate = () => {
    if (user.created_at) {
      try {
        return format(new Date(user.created_at), "EEEE d MMMM yyyy", { locale: fr });
      } catch {
        return format(new Date(user.created_at), "d MMMM yyyy");
      }
    }
    return "Date inconnue";
  };

  // Utiliser le hook useSubscription pour le statut

  return (
    <Layout>
      <Helmet>
        <meta name="robots" content="noindex, nofollow" />
      </Helmet>
      <PageMeta
        title="Mon profil | ApexAI"
        description="Statistiques, historique des sessions et gestion de l'abonnement."
        path="/profile"
      />
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-8 mb-8"
        >
          <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
            {/* Avatar */}
            <Avatar className="w-20 h-20 rounded-2xl border-2 border-primary/20">
              {avatarUrl ? (
                <AvatarImage src={avatarUrl} alt={displayName} className="object-cover" />
              ) : null}
              <AvatarFallback className="rounded-2xl gradient-primary text-3xl font-bold text-primary-foreground">
                {getInitials()}
              </AvatarFallback>
            </Avatar>

            {/* Info */}
            <div className="flex-1">
              {(() => {
                try {
                  const userSettings = JSON.parse(
                    localStorage.getItem("apexai_settings") || "{}"
                  ) as { nomPilote?: string };
                  const bonjourName = userSettings.nomPilote?.trim() || (user.user_metadata?.full_name as string) || user.email?.split("@")[0];
                  if (bonjourName) {
                    return (
                      <p className="text-lg font-medium text-primary mb-1">
                        Bonjour {bonjourName} !
                      </p>
                    );
                  }
                } catch {
                  // ignore
                }
                return null;
              })()}
              <h1 className="font-display text-2xl font-bold text-foreground mb-2">
                {displayName}
              </h1>
              <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                {user.email === ADMIN_EMAIL && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-600 text-white border border-red-500 shadow-sm">
                    Admin
                  </span>
                )}
                <span className="flex items-center gap-1">
                  <Mail className="w-4 h-4" />
                  {user.email || "Email non disponible"}
                </span>
                <span className="flex items-center gap-1" title={getFullCreationDate()}>
                  <Calendar className="w-4 h-4" />
                  Membre depuis {getMemberSince()}
                </span>
                {isPro && <span className="apex-badge-pro">PRO</span>}
                {!isPro && (
                  <span className="px-2 py-1 rounded-full text-xs bg-secondary/50 text-muted-foreground">
                    Gratuit
                  </span>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-wrap gap-3">
              <Button variant="outline" size="sm" asChild>
                <Link to="/parametres" className="inline-flex items-center justify-center gap-2">
                  <Settings className="w-4 h-4 mr-2" />
                  Paramètres
                </Link>
              </Button>
              {hasActivePaidSubscription && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCustomerPortal}
                  disabled={loadingPortal}
                  className="gap-2"
                >
                  {loadingPortal ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <ExternalLink className="w-4 h-4" />
                      Gérer l'abonnement
                    </>
                  )}
                </Button>
              )}
              {!isPro && (
                <Button
                  variant="hero"
                  size="sm"
                  onClick={() => navigate("/pricing")}
                  className="gap-2"
                >
                  <CreditCard className="w-4 h-4" />
                  Passer à PRO
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={handleLogout} className="gap-2">
                <LogOut className="w-4 h-4" />
                Déconnexion
              </Button>
            </div>
          </div>
        </motion.div>

        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Stats Sidebar */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            className="lg:col-span-4 space-y-6"
          >
            {/* Stats Overview */}
            <div className="glass-card p-6">
              <h3 className="font-display font-semibold text-lg text-foreground mb-4">
                Statistiques
              </h3>
              <div className="space-y-4">
                {[
                  {
                    label: "Sessions analysées",
                    value: loadingSessions ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      stats.totalSessions.toString()
                    ),
                    icon: Trophy,
                  },
                  {
                    label: "Score moyen",
                    value: loadingSessions ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : stats.totalSessions > 0 ? (
                      `${stats.averageScore}/100`
                    ) : (
                      "—"
                    ),
                    icon: TrendingUp,
                  },
                  {
                    label: "Tours analysés",
                    value: loadingSessions ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      stats.totalLaps.toString()
                    ),
                    icon: TrendingUp,
                  },
                ].map((stat) => (
                  <div
                    key={stat.label}
                    className="flex items-center justify-between p-3 rounded-xl bg-secondary/30"
                  >
                    <div className="flex items-center gap-3">
                      <stat.icon className="w-5 h-5 text-primary" />
                      <span className="text-sm text-muted-foreground">{stat.label}</span>
                    </div>
                    <span className="font-semibold text-foreground flex items-center gap-2">
                      {stat.value}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Abonnement */}
            <div className="glass-card p-6">
              <h3 className="font-display font-semibold text-lg text-foreground mb-4">
                Abonnement
              </h3>
              {subscriptionLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Chargement…</span>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <SubscriptionBadge />
                  </div>
                  {billingPeriod && (
                    <p className="text-sm text-muted-foreground">
                      Facturation{" "}
                      {billingPeriod === "annual" ? "annuelle" : "mensuelle"}
                    </p>
                  )}
                  {subscriptionEndDate && (
                    <p className="text-sm text-muted-foreground">
                      Prochain renouvellement :{" "}
                      {format(new Date(subscriptionEndDate), "d MMMM yyyy", { locale: fr })}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Changez de plan, mettez à jour vos moyens de paiement ou annulez
                    depuis le portail Stripe.
                  </p>
                  <div className="flex flex-col gap-2">
                    {tier === "rookie" ? (
                      <Button variant="hero" size="sm" asChild className="w-full gap-2">
                        <Link to="/pricing">
                          <Zap className="w-4 h-4" />
                          Passer à Racer
                        </Link>
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full gap-2"
                        onClick={async () => {
                          if (!user?.id) return;
                          try {
                            setLoadingPortal(true);
                            setError(null);
                            const { portal_url } = await createPortalSession(user.id);
                            if (portal_url) window.location.href = portal_url;
                          } catch (err) {
                            setError(
                              err instanceof Error ? err.message : "Erreur lors de l'ouverture du portail"
                            );
                          } finally {
                            setLoadingPortal(false);
                          }
                        }}
                        disabled={loadingPortal}
                      >
                        {loadingPortal ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <ExternalLink className="w-4 h-4" />
                        )}
                        Gérer mon abonnement
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Achievements */}
            <div className="glass-card p-6">
              <h3 className="font-display font-semibold text-lg text-foreground mb-4">
                Badges obtenus
              </h3>
              <div className="space-y-3">
                {achievements.map((achievement, index) => (
                  <motion.div
                    key={achievement.title}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 + index * 0.1 }}
                    className="flex items-center gap-3 p-3 rounded-xl bg-secondary/30"
                  >
                    <achievement.icon className="w-6 h-6 text-primary" />
                    <div>
                      <div className="font-medium text-foreground text-sm">{achievement.title}</div>
                      <div className="text-xs text-muted-foreground">{achievement.description}</div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* Evolution Chart */}
            <div className="glass-card p-6">
              <h3 className="font-display font-semibold text-lg text-foreground mb-4">
                Évolution du score
              </h3>
              {loadingSessions || sessions.length === 0 ? (
                <div className="h-40 flex items-center justify-center text-muted-foreground text-sm">
                  {loadingSessions ? (
                    <Loader2 className="w-6 h-6 animate-spin text-primary" />
                  ) : (
                    "Aucune donnée disponible"
                  )}
                </div>
              ) : (
                <>
                  <div className="h-40 flex items-end justify-between gap-2">
                    {sessions
                      .slice(0, 8)
                      .reverse()
                      .map((session, index) => {
                        const height = Math.min(100, Math.max(10, (session.score / 100) * 100));
                        return (
                          <motion.div
                            key={session.id}
                            initial={{ height: 0 }}
                            animate={{ height: `${height}%` }}
                            transition={{ delay: 0.3 + index * 0.1, duration: 0.5 }}
                            className="flex-1 rounded-t-sm bg-gradient-to-t from-primary/50 to-primary"
                            title={`Score: ${session.score}/100`}
                          />
                        );
                      })}
                  </div>
                  <div className="flex justify-between mt-2 text-xs text-muted-foreground">
                    <span>Ancien</span>
                    <span>Récent</span>
                  </div>
                </>
              )}
            </div>
          </motion.div>

          {/* Sessions History */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="lg:col-span-8"
          >
            <div className="glass-card p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-display font-semibold text-lg text-foreground">
                  Historique des sessions
                </h3>
              </div>

              {/* Table */}
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/5">
                      <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                        Date
                      </th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                        Circuit
                      </th>
                      <th className="px-4 py-3 text-center text-sm font-medium text-muted-foreground">
                        Tours
                      </th>
                      <th className="px-4 py-3 text-center text-sm font-medium text-muted-foreground">
                        Score
                      </th>
                      <th className="px-4 py-3 text-center text-sm font-medium text-muted-foreground">
                        Gain
                      </th>
                      <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {loadingSessions ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-8 text-center">
                          <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-primary" />
                          <p className="text-sm text-muted-foreground">Chargement des sessions...</p>
                        </td>
                      </tr>
                    ) : sessions.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                          Aucune session analysée pour le moment
                        </td>
                      </tr>
                    ) : (
                      sessions.map((session, index) => (
                        <motion.tr
                          key={session.id}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: 0.3 + index * 0.05 }}
                          className="border-b border-white/5 last:border-0 hover:bg-white/2 transition-colors"
                        >
                          <td className="px-4 py-4 text-sm text-muted-foreground">
                            {format(new Date(session.date), "d MMM yyyy", { locale: fr })}
                          </td>
                          <td className="px-4 py-4 text-sm font-medium text-foreground">
                            {session.filename || "Session de course"}
                          </td>
                          <td className="px-4 py-4 text-sm text-center text-muted-foreground">
                            {session.corner_count}
                          </td>
                          <td className="px-4 py-4 text-center">
                            <span
                              className={`inline-flex items-center justify-center w-12 h-6 rounded-full text-xs font-bold ${
                                session.score >= 80
                                  ? "bg-success/20 text-success"
                                  : session.score >= 70
                                    ? "bg-primary/20 text-primary"
                                    : "bg-warning/20 text-warning"
                              }`}
                            >
                              {session.score}
                            </span>
                          </td>
                          <td className="px-4 py-4 text-sm text-center font-medium text-muted-foreground">
                            {session.grade}
                          </td>
                          <td className="px-4 py-4 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                // TODO: Naviguer vers la page de détail de l'analyse
                                console.log("View session:", session.id);
                              }}
                            >
                              Voir
                              <ChevronRight className="w-4 h-4" />
                            </Button>
                          </td>
                        </motion.tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </Layout>
  );
}
