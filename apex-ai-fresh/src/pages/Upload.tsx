import { motion } from "framer-motion";
import { Helmet } from "react-helmet-async";
import { Layout } from "@/components/layout/Layout";
import { CSVUploader } from "@/components/upload/CSVUploader";
import { PageMeta } from "@/components/seo/PageMeta";
import { FileSpreadsheet, CheckCircle, Shield, Zap, BarChart3, TrendingUp, Car, FolderOpen } from "lucide-react";

const supportedFormats = [
  { name: "MyChron5", icon: BarChart3 },
  { name: "AiM", icon: TrendingUp },
  { name: "RaceBox", icon: Car },
  { name: "CSV standard", icon: FolderOpen },
];

const features = [
  {
    icon: Zap,
    title: "Analyse en 3 secondes",
    description: "Notre IA traite vos données instantanément",
  },
  {
    icon: Shield,
    title: "Données sécurisées",
    description: "Vos fichiers sont chiffrés et privés",
  },
  {
    icon: CheckCircle,
    title: "Précision 94%",
    description: "Détection précise de chaque apex",
  },
];

export default function Upload() {
  return (
    <Layout>
      <Helmet>
        <meta name="robots" content="noindex, nofollow" />
      </Helmet>
      <PageMeta
        title="Upload CSV MyChron5 → Analyse IA Immédiate | ApexAI"
        description="Upload MyChron5, AiM RaceBox → IA analyse apices, freinage. Score + coaching 30s."
        ogTitle="Analyse CSV MyChron5 → IA ApexAI"
        path="/upload"
      />
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <h1 className="font-display text-4xl md:text-5xl font-bold text-foreground mb-4">
            Analysez votre <span className="text-gradient-primary">session</span>
          </h1>
          <p className="text-muted-foreground max-w-xl mx-auto">
            Importez votre fichier CSV depuis votre data logger et obtenez une analyse complète en
            quelques secondes.
          </p>
        </motion.div>

        {/* Uploader */}
        <div className="max-w-3xl mx-auto mb-12">
          <CSVUploader />
        </div>

        {/* Supported Formats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="max-w-3xl mx-auto mb-12"
        >
          <h3 className="text-center text-sm font-medium text-muted-foreground mb-4">
            Formats supportés
          </h3>
          <div className="flex flex-wrap justify-center gap-4">
            {supportedFormats.map((format) => {
              const Icon = format.icon;
              return (
                <div
                  key={format.name}
                  className="flex items-center gap-2 px-4 py-2 rounded-full bg-secondary/50 border border-white/5"
                >
                  <Icon className="w-5 h-5 text-primary" />
                  <span className="text-sm text-foreground">{format.name}</span>
                </div>
              );
            })}
          </div>
        </motion.div>

        {/* Features */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto"
        >
          {features.map((feature, index) => (
            <div key={feature.title} className="glass-card p-6 text-center">
              <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                <feature.icon className="w-6 h-6 text-primary" />
              </div>
              <h4 className="font-semibold text-foreground mb-2">{feature.title}</h4>
              <p className="text-sm text-muted-foreground">{feature.description}</p>
            </div>
          ))}
        </motion.div>

        {/* Sample Data Preview */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mt-16 max-w-4xl mx-auto"
        >
          <h3 className="font-display font-semibold text-lg text-foreground mb-4 text-center">
            Exemple de données analysées
          </h3>
          <div className="glass-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="px-4 py-3 text-left text-muted-foreground font-medium">
                      Horodatage
                    </th>
                    <th className="px-4 py-3 text-left text-muted-foreground font-medium">
                      Lat. GPS
                    </th>
                    <th className="px-4 py-3 text-left text-muted-foreground font-medium">
                      Long. GPS
                    </th>
                    <th className="px-4 py-3 text-left text-muted-foreground font-medium">
                      Vitesse
                    </th>
                    <th className="px-4 py-3 text-left text-muted-foreground font-medium">
                      Accélération G
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["00:12.345", "46.2041", "6.1434", "72 km/h", "1.2G"],
                    ["00:12.450", "46.2042", "6.1436", "68 km/h", "1.8G"],
                    ["00:12.555", "46.2044", "6.1439", "65 km/h", "2.1G"],
                    ["00:12.660", "46.2047", "6.1442", "70 km/h", "1.5G"],
                    ["00:12.765", "46.2050", "6.1445", "78 km/h", "0.8G"],
                  ].map((row, index) => (
                    <tr
                      key={index}
                      className="border-b border-white/5 last:border-0 hover:bg-white/2"
                    >
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex} className="px-4 py-3 text-foreground">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      </div>
    </Layout>
  );
}
