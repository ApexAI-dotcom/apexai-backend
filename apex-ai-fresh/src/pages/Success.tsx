import { useSearchParams, Link } from "react-router-dom";
import { motion } from "framer-motion";
import { CheckCircle2, ArrowRight, Sparkles } from "lucide-react";
import { Layout } from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";

export default function Success() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id");

  return (
    <Layout>
      <div className="min-h-screen flex items-center justify-center py-20">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-2xl mx-auto px-4 text-center"
        >
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
            className="w-24 h-24 mx-auto mb-6 rounded-full bg-green-500/20 flex items-center justify-center"
          >
            <CheckCircle2 className="w-12 h-12 text-green-500" />
          </motion.div>

          <h1 className="font-display text-4xl md:text-5xl font-bold text-foreground mb-4 flex items-center justify-center gap-3 flex-wrap">
            <Sparkles className="w-10 h-10 text-primary shrink-0" aria-hidden />
            Paiement Réussi !
          </h1>

          <p className="text-xl text-muted-foreground mb-2">
            Votre abonnement <span className="text-primary font-semibold">ApexAI Pro</span> est maintenant actif
          </p>

          {sessionId && (
            <p className="text-sm text-muted-foreground mb-8">
              ID de session : <code className="bg-muted px-2 py-1 rounded text-xs">{sessionId}</code>
            </p>
          )}

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <Link to="/dashboard">
              <Button variant="hero" size="xl">
                Accéder au tableau de bord Pro
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </Link>
            <Link to="/upload">
              <Button variant="outline" size="lg">
                Analyser un fichier
              </Button>
            </Link>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="mt-12 p-6 glass-card rounded-xl"
          >
            <h3 className="font-semibold text-foreground mb-2">Ce qui vous attend maintenant :</h3>
            <ul className="text-left text-muted-foreground space-y-2 max-w-md mx-auto">
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                <span>Analyses illimitées de fichiers CSV MyChron</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                <span>Accès aux fonctionnalités avancées de coaching IA</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                <span>Support prioritaire et mises à jour en avant-première</span>
              </li>
            </ul>
          </motion.div>
        </motion.div>
      </div>
    </Layout>
  );
}
