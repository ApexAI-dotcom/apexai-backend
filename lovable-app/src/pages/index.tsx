import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Zap,
  Target,
  Timer,
  TrendingUp,
  Users,
  Star,
} from "lucide-react";
import { Layout } from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";

const stats = [
  { value: "12,847", label: "Tours analysés", icon: Target },
  { value: "+7.2s", label: "Gain moyen par session", icon: Timer },
  { value: "94%", label: "Précision apex", icon: TrendingUp },
];

const features = [
  {
    title: "Analyse IA des virages",
    description:
      "Notre algorithme identifie chaque apex et calcule votre trajectoire optimale.",
    icon: Target,
  },
  {
    title: "Score de performance",
    description:
      "Obtenez un score /100 détaillé avec des conseils personnalisés.",
    icon: Star,
  },
  {
    title: "Compatible MyChron5",
    description:
      "Import direct des données MyChron5, AiM, RaceBox et autres formats de télémétrie.",
    icon: Zap,
  },
];

const testimonials = [
  {
    name: "Lucas M.",
    role: "Pilote Rotax DD2",
    quote:
      "J'ai gagné 3 secondes en une session grâce aux conseils d'APEX AI.",
    avatar: "LM",
  },
  {
    name: "Marie D.",
    role: "Championne régionale",
    quote: "L'analyse des apex est incroyablement précise. Un game-changer.",
    avatar: "MD",
  },
];

export default function Index() {
  return (
    <Layout>
      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-b from-purple-950 via-slate-900 to-purple-950" />

        <div className="container mx-auto px-4 relative z-10 py-20">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="max-w-4xl mx-auto text-center"
          >
            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2 }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/10 border border-purple-500/20 mb-6"
            >
              <Zap className="w-4 h-4 text-purple-400" />
              <span className="text-sm font-medium text-purple-300">
                Propulsé par l'IA
              </span>
            </motion.div>

            {/* Title */}
            <h1 className="text-5xl md:text-7xl font-bold mb-6">
              <span className="text-white">APEX</span>
              <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">AI</span>
              <br />
              <span className="text-white text-3xl md:text-5xl">
                Ton Coach Virages IA
              </span>
            </h1>

            {/* Subtitle */}
            <p className="text-lg md:text-xl text-slate-400 mb-8 max-w-2xl mx-auto">
              Analyse ton fichier CSV <span className="text-purple-400 font-semibold">MyChron5</span> et obtiens un{" "}
              <span className="text-purple-400 font-semibold">Score /100</span> +{" "}
              <span className="text-green-400 font-semibold">7s gagnés</span> par
              session en moyenne.
            </p>

            {/* CTA */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="flex flex-col sm:flex-row items-center justify-center gap-4"
            >
              <Link to="/upload">
                <Button className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white h-12 px-8 text-lg">
                  Essai Gratuit - 3 Analyses
                  <ArrowRight className="w-5 h-5 ml-2" />
                </Button>
              </Link>
              <Link to="/upload">
                <Button variant="outline" className="border-purple-500/30 text-purple-300 hover:bg-purple-500/10 h-12 px-8">
                  Voir une démo
                </Button>
              </Link>
            </motion.div>

            {/* Social proof */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
              className="mt-12 flex items-center justify-center gap-2"
            >
              <div className="flex -space-x-2">
                {["LM", "MD", "JP", "AK"].map((initials, i) => (
                  <div
                    key={i}
                    className="w-8 h-8 rounded-full bg-purple-500/20 border-2 border-purple-500/30 flex items-center justify-center text-xs font-medium text-purple-300"
                  >
                    {initials}
                  </div>
                ))}
              </div>
              <span className="text-sm text-slate-400">
                Utilisé par <span className="text-white font-medium">127+ pilotes PRO</span>
              </span>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-20 border-t border-white/5 bg-slate-900/50">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {stats.map((stat, index) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="glass-card border-purple-500/20 p-8 text-center"
              >
                <stat.icon className="w-8 h-8 text-purple-400 mx-auto mb-4" />
                <div className="text-4xl font-bold text-white mb-2">
                  {stat.value}
                </div>
                <div className="text-slate-400">{stat.label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20">
        <div className="container mx-auto px-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl md:text-5xl font-bold text-white mb-4">
              Analyse <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">intelligente</span>
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              Notre IA analyse chaque virage pour vous donner des conseils précis
              et personnalisés.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="glass-card border-purple-500/20 p-8 hover:border-purple-500/40 transition-colors"
              >
                <div className="w-14 h-14 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 flex items-center justify-center mb-6">
                  <feature.icon className="w-7 h-7 text-white" />
                </div>
                <h3 className="text-xl font-bold text-white mb-3">
                  {feature.title}
                </h3>
                <p className="text-slate-400">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="py-20 border-t border-white/5 bg-slate-900/50">
        <div className="container mx-auto px-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl md:text-5xl font-bold text-white mb-4">
              Ce qu'en disent les <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">pilotes</span>
            </h2>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            {testimonials.map((testimonial, index) => (
              <motion.div
                key={testimonial.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="glass-card border-purple-500/20 p-8"
              >
                <div className="flex items-center gap-4 mb-4">
                  <div className="w-12 h-12 rounded-full bg-gradient-to-r from-purple-600 to-pink-600 flex items-center justify-center font-bold text-white">
                    {testimonial.avatar}
                  </div>
                  <div>
                    <div className="font-semibold text-white">
                      {testimonial.name}
                    </div>
                    <div className="text-sm text-slate-400">
                      {testimonial.role}
                    </div>
                  </div>
                </div>
                <p className="text-slate-400 italic">
                  "{testimonial.quote}"
                </p>
                <div className="flex gap-1 mt-4">
                  {[...Array(5)].map((_, i) => (
                    <Star
                      key={i}
                      className="w-4 h-4 text-yellow-400 fill-yellow-400"
                    />
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20">
        <div className="container mx-auto px-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="glass-card border-purple-500/20 p-12 text-center relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-purple-500/5 via-transparent to-purple-500/5" />
            <div className="relative z-10">
              <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
                Prêt à améliorer tes temps ?
              </h2>
              <p className="text-slate-400 mb-8 max-w-xl mx-auto">
                Rejoins les 127 pilotes qui utilisent déjà APEX AI pour dominer
                les circuits.
              </p>
              <Link to="/upload">
                <Button className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white h-12 px-8 text-lg">
                  Commencer maintenant
                  <ArrowRight className="w-5 h-5 ml-2" />
                </Button>
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 border-t border-white/5 bg-slate-900/50">
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-r from-purple-600 to-pink-600 flex items-center justify-center">
                <Zap className="w-4 h-4 text-white" />
              </div>
              <span className="font-bold text-white">
                APEX<span className="text-purple-400">AI</span>
              </span>
            </div>
            <div className="flex items-center gap-6 text-sm text-slate-400">
              <Link to="/upload" className="hover:text-white transition-colors">
                Tarifs
              </Link>
              <a href="#" className="hover:text-white transition-colors">
                Contact
              </a>
              <a href="#" className="hover:text-white transition-colors">
                Mentions légales
              </a>
            </div>
            <div className="text-sm text-slate-400">
              © 2024 APEX AI. Tous droits réservés.
            </div>
          </div>
        </div>
      </footer>
    </Layout>
  );
}
