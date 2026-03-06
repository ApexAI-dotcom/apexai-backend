import { useState, useEffect, useCallback, Fragment } from "react";
import { createPortal } from "react-dom";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  TrendingUp,
  TrendingDown,
  Target,
  Clock,
  Trash2,
  Eye,
  Compare,
  BarChart3,
  Zap,
  AlertCircle,
  X,
  ArrowLeft,
  ArrowRight,
  FileDown,
  CheckCircle2,
  ExternalLink,
  Save,
  Database,
  RefreshCw,
  Download,
} from "lucide-react";
import { Layout } from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getAllAnalyses,
  getAnalysisById,
  deleteAnalysis,
  clearAllAnalyses,
  type AnalysisSummary,
} from "@/lib/storage";
import { getDisplayScore, type AnalysisResult, type CornerAnalysis, type CoachingAdvice } from "@/lib/api";
import { useSubscriptionLegacy } from "@/hooks/useSubscriptionLegacy";
import { useAuth } from "@/hooks/useAuth";
import { PageMeta } from "@/components/seo/PageMeta";
import { Helmet } from "react-helmet-async";
import { ADMIN_EMAIL } from "@/constants";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { toast } from "sonner";

export default function Dashboard() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const analysisIdParam = searchParams.get("analysisId");
  const { subscription, limits, isPro } = useSubscriptionLegacy();
  const { user } = useAuth();
  const isAdmin = user?.email === ADMIN_EMAIL;

  // States
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [selectedAnalysis, setSelectedAnalysis] = useState<AnalysisResult | null>(null);
  const [compareAnalysis1, setCompareAnalysis1] = useState<string>("");
  const [compareAnalysis2, setCompareAnalysis2] = useState<string>("");
  const [compareResult1, setCompareResult1] = useState<AnalysisResult | null>(null);
  const [compareResult2, setCompareResult2] = useState<AnalysisResult | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [analysisToDelete, setAnalysisToDelete] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalImage, setModalImage] = useState<string | null>(null);
  const [modalTitle, setModalTitle] = useState<string>("");
  const [expandedCorner, setExpandedCorner] = useState<number | null>(null);

  // Fermeture modal par ESC
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setModalImage(null);
    };
    if (modalImage) {
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [modalImage]);

  // Calculer les analyses du mois actuel
  const getCurrentMonthAnalyses = () => {
    const now = new Date();
    const currentMonth = now.getMonth();
    const currentYear = now.getFullYear();

    return analyses.filter((analysis) => {
      const analysisDate = new Date(analysis.date);
      return (
        analysisDate.getMonth() === currentMonth &&
        analysisDate.getFullYear() === currentYear
      );
    });
  };

  const currentMonthAnalyses = getCurrentMonthAnalyses();
  const analysesRemaining =
    limits.maxAnalysesPerMonth === Infinity
      ? Infinity
      : Math.max(0, limits.maxAnalysesPerMonth - currentMonthAnalyses.length);
  const hasReachedLimit = !isPro && currentMonthAnalyses.length >= limits.maxAnalysesPerMonth;

  // Load analyses on mount and when user changes (login/logout → clé storage différente)
  const loadAnalyses = useCallback(async () => {
    try {
      setLoading(true);
      const allAnalyses = await getAllAnalyses(user?.id ?? undefined);
      setAnalyses(allAnalyses);
    } catch (err) {
      setError("Erreur lors du chargement des analyses");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    loadAnalyses();
  }, [loadAnalyses]);

  // Load specific analysis from query param (recharger si user change)
  useEffect(() => {
    if (analysisIdParam) {
      loadAnalysis(analysisIdParam);
    }
  }, [analysisIdParam, user?.id]);

  const loadAnalysis = async (id: string) => {
    try {
      const analysis = await getAnalysisById(id, user?.id ?? undefined);
      if (analysis) {
        setSelectedAnalysis(analysis);
      } else {
        setError(`Analyse ${id} non trouvée`);
      }
    } catch (err) {
      setError(`Erreur lors du chargement de l'analyse ${id}`);
      console.error(err);
    }
  };

  const handleViewAnalysis = async (id: string) => {
    await loadAnalysis(id);
    setSearchParams({ analysisId: id });
  };

  const handleDeleteClick = (id: string) => {
    setAnalysisToDelete(id);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!analysisToDelete) return;

    try {
      const success = await deleteAnalysis(analysisToDelete, user?.id ?? undefined);
      if (success) {
        // Reload analyses
        await loadAnalyses();

        // Clear selected if deleted
        if (selectedAnalysis?.analysis_id === analysisToDelete) {
          setSelectedAnalysis(null);
          setSearchParams({});
        }

        // Clear compare if deleted
        if (compareAnalysis1 === analysisToDelete) {
          setCompareAnalysis1("");
          setCompareResult1(null);
        }
        if (compareAnalysis2 === analysisToDelete) {
          setCompareAnalysis2("");
          setCompareResult2(null);
        }
      }
    } catch (err) {
      setError("Erreur lors de la suppression");
      console.error(err);
    } finally {
      setDeleteDialogOpen(false);
      setAnalysisToDelete(null);
    }
  };

  const handleCompareLoad = async () => {
    if (!compareAnalysis1 || !compareAnalysis2) return;

    const uid = user?.id ?? undefined;
    try {
      const [result1, result2] = await Promise.all([
        getAnalysisById(compareAnalysis1, uid),
        getAnalysisById(compareAnalysis2, uid),
      ]);

      setCompareResult1(result1);
      setCompareResult2(result2);
    } catch (err) {
      setError("Erreur lors du chargement de la comparaison");
      console.error(err);
    }
  };

  useEffect(() => {
    if (compareAnalysis1 && compareAnalysis2) {
      handleCompareLoad();
    }
  }, [compareAnalysis1, compareAnalysis2]);

  // Statistics
  const statistics = {
    total: analyses.length,
    averageScore:
      analyses.length > 0
        ? Math.round(analyses.reduce((sum, a) => sum + a.score, 0) / analyses.length)
        : 0,
    bestScore: analyses.length > 0 ? Math.max(...analyses.map((a) => a.score)) : 0,
    bestAnalysis:
      analyses.length > 0
        ? analyses.reduce((best, a) => (a.score > best.score ? a : best), analyses[0])
        : null,
  };

  const getGradeColor = (grade: string) => {
    switch (grade.toUpperCase()) {
      case "A+":
      case "A":
        return "bg-green-500/20 text-green-200 border-green-500/50";
      case "B":
        return "bg-blue-500/20 text-blue-200 border-blue-500/50";
      case "C":
        return "bg-yellow-500/20 text-yellow-200 border-yellow-500/50";
      case "D":
        return "bg-red-500/20 text-red-200 border-red-500/50";
      default:
        return "bg-gray-500/20 text-gray-200 border-gray-500/50";
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("fr-FR", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Actions admin (fonctionnelles)
  const handleAdminClearCache = async () => {
    try {
      const count = await clearAllAnalyses(user?.id ?? undefined);
      await loadAnalyses();
      setSelectedAnalysis(null);
      setCompareResult1(null);
      setCompareResult2(null);
      setCompareAnalysis1("");
      setCompareAnalysis2("");
      toast.success(`Cache vidé : ${count} analyse(s) supprimée(s).`);
    } catch (e) {
      console.error(e);
      toast.error("Erreur lors du vidage du cache.");
    }
  };

  const handleAdminResetTestUsers = () => {
    try {
      localStorage.removeItem("apex_guest_mode");
      localStorage.removeItem("apex_guest_used");
      toast.success("Flags guest / test réinitialisés.");
    } catch {
      toast.error("Erreur réinitialisation.");
    }
  };

  const handleAdminExportStats = () => {
    try {
      const payload = {
        exportedAt: new Date().toISOString(),
        totalAnalyses: analyses.length,
        analyses: analyses.map((a) => ({
          id: a.id,
          date: a.date,
          score: a.score,
          grade: a.grade,
          corner_count: a.corner_count,
          lap_time: a.lap_time,
        })),
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `apex-admin-stats-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Stats exportées en JSON.");
    } catch (e) {
      console.error(e);
      toast.error("Erreur export.");
    }
  };

  const exportDashboardPDFUltra = async (analyses: AnalysisSummary[]) => {
    console.log("[PDF] Dashboard export start", analyses);
    try {
      const doc = new jsPDF("p", "mm", "a4");

      // HEADER ROUGE APEX
      doc.setFillColor(239, 68, 68);
      doc.rect(0, 0, 210, 45, "F");
      doc.setTextColor(255, 255, 255);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(28);
      doc.text("APEX AI", 20, 25);
      doc.setFontSize(18);
      doc.text("TABLEAU DE BORD COMPLET", 20, 35);

      let yPos = 55;

      // STATS GLOBALES
      doc.setFontSize(14);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(0, 0, 0);
      doc.text("STATISTIQUES GLOBALES", 20, yPos);
      yPos += 10;

      const totalAnalyses = analyses.length;
      const avgScore = (analyses.reduce((a, b) => a + b.score, 0) / totalAnalyses).toFixed(1);
      const bestScore = Math.max(...analyses.map((a) => a.score));
      const bestAnalysis = analyses.find((a) => a.score === bestScore);
      const bestDate = bestAnalysis?.date ? new Date(bestAnalysis.date).toISOString().split("T")[0] : "N/A";

      doc.setFontSize(12);
      doc.setFont("helvetica", "normal");
      doc.text(`Total analyses: ${totalAnalyses}`, 20, yPos);
      yPos += 7;
      doc.text(`Score moyen: ${avgScore}/100`, 20, yPos);
      yPos += 7;
      doc.text(`Meilleur score: ${bestScore}/100 (${bestDate})`, 20, yPos);
      yPos += 15;

      // TABLEAU HISTORIQUE COMPLET
      doc.setFontSize(14);
      doc.setFont("helvetica", "bold");
      doc.text("HISTORIQUE DETAILLE", 20, yPos);
      yPos += 10;

      const tableData = analyses.map((a) => [
        new Date(a.date).toLocaleDateString("fr-FR"),
        `${a.score}/100`,
        a.grade,
        String(a.corner_count),
        `${a.lap_time.toFixed(1)}s`,
        "N/A", // percentile pas disponible dans AnalysisSummary
        "N/A", // precision_score pas disponible
        "N/A", // data_points pas disponible
      ]);

      autoTable(doc, {
        startY: yPos,
        head: [["Date", "Score", "Grade", "Virages", "Temps", "Centile", "Precision", "Donnees"]],
        body: tableData,
        theme: "grid",
        styles: { fontSize: 10, cellPadding: 3 },
        headStyles: { fillColor: [239, 68, 68], textColor: 255, fontStyle: "bold" },
        columnStyles: {
          0: { halign: "left" },
          1: { halign: "center" },
          5: { halign: "right" },
          7: { halign: "right" },
        },
        margin: { left: 15, right: 15 },
        rowPageBreak: "avoid",
      });

      yPos = (doc as any).lastAutoTable?.finalY ? (doc as any).lastAutoTable.finalY + 20 : yPos + 50;

      // TOP 3 MEILLEURES ANALYSES
      if (yPos > 250) {
        doc.addPage();
        doc.setFillColor(239, 68, 68);
        doc.rect(0, 0, 210, 45, "F");
        doc.setTextColor(255, 255, 255);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(28);
        doc.text("APEX AI", 20, 25);
        doc.setFontSize(18);
        doc.text("TABLEAU DE BORD COMPLET", 20, 35);
        yPos = 50;
      }

      doc.setFontSize(14);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(0, 0, 0);
      doc.text("TOP 3 MEILLEURES SESSIONS", 20, yPos);
      yPos += 10;

      const top3 = [...analyses]
        .sort((a, b) => b.score - a.score)
        .slice(0, 3)
        .map(
          (a, i) =>
            `${i + 1}. ${new Date(a.date).toISOString().split("T")[0]} - Score ${a.score}/100 (Grade ${a.grade}) - ${a.corner_count} virages`
        );

      doc.setFontSize(11);
      doc.setFont("helvetica", "normal");
      top3.forEach((line) => {
        doc.text(line, 20, yPos);
        yPos += 8;
      });

      // FOOTER TOUTES PAGES
      const pageCount = doc.internal.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.setFillColor(30, 58, 138);
        doc.rect(0, doc.internal.pageSize.height - 30, 210, 30, "F");
        doc.setTextColor(255, 255, 255);
        doc.setFontSize(10);
        doc.setFont("helvetica", "normal");
        doc.text("Apex AI - contact@apexai.run - www.apexai.run", 20, doc.internal.pageSize.height - 15);
        doc.text(`Page ${i}/${pageCount}`, 180, doc.internal.pageSize.height - 15, { align: "right" });
      }

      doc.save(`Apex-Dashboard-${new Date().toISOString().split("T")[0]}.pdf`);
      console.log("[PDF] Dashboard export success");
    } catch (error) {
      console.error("PDF DASHBOARD ULTRA ERROR:", error);
      alert("Erreur PDF: " + (error instanceof Error ? error.message : String(error)));
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="container mx-auto px-4 py-8">
          <div className="flex items-center justify-center min-h-[400px]">
            <div className="text-center">
              <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-muted-foreground">Chargement des analyses...</p>
            </div>
          </div>
        </div>
      </Layout>
    );
  }

  if (analyses.length === 0) {
    return (
      <Layout>
        <div className="container mx-auto px-4 py-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-2xl mx-auto text-center py-16"
          >
            <div className="w-24 h-24 rounded-full bg-secondary flex items-center justify-center mx-auto mb-6">
              <BarChart3 className="w-12 h-12 text-muted-foreground" />
            </div>
            <h2 className="text-3xl font-display font-bold text-foreground mb-4">
              Aucune analyse sauvegardée
            </h2>
            <p className="text-muted-foreground mb-8">
              Vous n'avez pas encore d'analyses sauvegardées. Téléversez un fichier CSV pour
              commencer.
            </p>
            <Button variant="hero" size="lg" onClick={() => navigate("/upload")}>
              Aller au téléchargement
            </Button>
          </motion.div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <Helmet>
        <meta name="robots" content="noindex, nofollow" />
      </Helmet>
      <PageMeta
        title="Tableau de bord | ApexAI"
        description="Historique de vos analyses, comparaison de sessions et export PDF."
        path="/dashboard"
      />
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="font-display text-4xl md:text-5xl font-bold text-foreground mb-2">
                Tableau de bord
              </h1>
              <p className="text-muted-foreground">Gérez et comparez vos analyses de performance</p>
            </div>
            <div className="flex gap-3">
              {analyses.length > 0 && (
                <Button
                  className="gradient-primary text-primary-foreground font-semibold shadow-lg shadow-primary/30 hover:shadow-xl hover:shadow-primary/40 hover:scale-105 active:scale-100"
                  onClick={() => exportDashboardPDFUltra(analyses)}
                >
                  <FileDown className="w-4 h-4 mr-2" />
                  Rapport Complet PDF
                </Button>
              )}
              <Button
                variant="heroOutline"
                onClick={() => navigate("/upload")}
                disabled={hasReachedLimit}
              >
                Nouvelle analyse
              </Button>
            </div>
          </div>

          {/* Limit Warning for Free Plan */}
          {!isPro && (
            <Alert className="mb-6 border-primary/30 bg-primary/5">
              <AlertCircle className="h-4 w-4 text-primary" />
              <AlertTitle>Plan Gratuit</AlertTitle>
              <AlertDescription className="flex items-center justify-between">
                <span>
                  {hasReachedLimit
                    ? "Vous avez atteint la limite de 3 analyses ce mois-ci."
                    : `${analysesRemaining} analyse${analysesRemaining > 1 ? "s" : ""} restante${analysesRemaining > 1 ? "s" : ""} ce mois-ci.`}
                </span>
                <Button
                  variant="hero"
                  size="sm"
                  onClick={() => navigate("/pricing")}
                  className="ml-4"
                >
                  Passer à PRO
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {/* Statistics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
            <Card className="glass-card">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 mb-2">
                  <BarChart3 className="w-4 h-4 text-primary" />
                  <div className="text-xs text-muted-foreground">Analyses totales</div>
                </div>
                <div className="text-2xl font-bold text-foreground">{statistics.total}</div>
                {!isPro && (
                  <div className="text-xs text-muted-foreground mt-1">
                    {currentMonthAnalyses.length}/{limits.maxAnalysesPerMonth} ce mois
                  </div>
                )}
              </CardContent>
            </Card>
            <Card className="glass-card">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="w-4 h-4 text-primary" />
                  <div className="text-xs text-muted-foreground">Score moyen</div>
                </div>
                <div className="text-2xl font-bold text-foreground">
                  {statistics.averageScore}/100
                </div>
              </CardContent>
            </Card>
            <Card className="glass-card">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 mb-2">
                  <Target className="w-4 h-4 text-primary" />
                  <div className="text-xs text-muted-foreground">Meilleur score</div>
                </div>
                <div className="text-2xl font-bold text-foreground">{statistics.bestScore}/100</div>
              </CardContent>
            </Card>
            <Card className="glass-card">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="w-4 h-4 text-primary" />
                  <div className="text-xs text-muted-foreground">Tendance</div>
                </div>
                <div className="text-2xl font-bold text-foreground flex justify-center">
                  {analyses.length >= 2 ? (
                    analyses[0].score >= analyses[1].score ? (
                      <TrendingUp className="w-6 h-6 text-green-500" />
                    ) : (
                      <TrendingDown className="w-6 h-6 text-destructive" />
                    )
                  ) : (
                    "—"
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </motion.div>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Erreur</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Tabs */}
        <Tabs defaultValue="list" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="list">Liste</TabsTrigger>
            <TabsTrigger value="compare">Comparer</TabsTrigger>
            {selectedAnalysis && <TabsTrigger value="details">Détails</TabsTrigger>}
          </TabsList>

          {/* List Tab */}
          <TabsContent value="list" className="space-y-4">
            <Card className="glass-card">
              <CardHeader>
                <CardTitle>Toutes les analyses</CardTitle>
                <CardDescription>
                  {analyses.length} analyse{analyses.length > 1 ? "s" : ""} sauvegardée
                  {analyses.length > 1 ? "s" : ""}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Score</TableHead>
                        <TableHead>Grade</TableHead>
                        <TableHead>Virages</TableHead>
                        <TableHead>Temps tour</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {analyses.map((analysis) => (
                        <TableRow
                          key={analysis.id}
                          className="cursor-pointer hover:bg-white/5"
                          onClick={() => handleViewAnalysis(analysis.id)}
                        >
                          <TableCell className="font-medium">{formatDate(analysis.date)}</TableCell>
                          <TableCell>
                            <span className="font-bold">{analysis.score}/100</span>
                          </TableCell>
                          <TableCell>
                            <Badge className={getGradeColor(analysis.grade)}>
                              {analysis.grade}
                            </Badge>
                          </TableCell>
                          <TableCell>{analysis.corner_count}</TableCell>
                          <TableCell>{analysis.lap_time.toFixed(2)}s</TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-2">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleViewAnalysis(analysis.id);
                                }}
                              >
                                <Eye className="w-4 h-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteClick(analysis.id);
                                }}
                              >
                                <Trash2 className="w-4 h-4 text-destructive" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Compare Tab */}
          <TabsContent value="compare" className="space-y-4">
            <Card className="glass-card">
              <CardHeader>
                <CardTitle>Comparer deux analyses</CardTitle>
                <CardDescription>
                  Sélectionnez deux analyses pour les comparer côte à côte
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium mb-2 block">Analyse 1</label>
                    <Select value={compareAnalysis1} onValueChange={setCompareAnalysis1}>
                      <SelectTrigger>
                        <SelectValue placeholder="Sélectionner une analyse" />
                      </SelectTrigger>
                      <SelectContent>
                        {analyses.map((analysis) => (
                          <SelectItem key={analysis.id} value={analysis.id}>
                            {formatDate(analysis.date)} - {analysis.score}/100 ({analysis.grade})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-2 block">Analyse 2</label>
                    <Select value={compareAnalysis2} onValueChange={setCompareAnalysis2}>
                      <SelectTrigger>
                        <SelectValue placeholder="Sélectionner une analyse" />
                      </SelectTrigger>
                      <SelectContent>
                        {analyses
                          .filter((a) => a.id !== compareAnalysis1)
                          .map((analysis) => (
                            <SelectItem key={analysis.id} value={analysis.id}>
                              {formatDate(analysis.date)} - {analysis.score}/100 ({analysis.grade})
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {compareResult1 && compareResult2 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                    {/* Analysis 1 */}
                    <Card className="glass-card">
                      <CardHeader>
                        <CardTitle className="flex items-center justify-between">
                          <span>Analyse 1</span>
                          <Badge className={getGradeColor(compareResult1.performance_score.grade)}>
                            {compareResult1.performance_score.grade}
                          </Badge>
                        </CardTitle>
                        <CardDescription>
                          {formatDate(new Date(compareResult1.timestamp).toISOString())}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="text-center">
                          <div className="text-4xl font-bold text-foreground mb-2">
                            {Math.round(getDisplayScore(compareResult1.performance_score))}/100
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {compareResult1.corners_detected} virages •{" "}
                            {compareResult1.lap_time.toFixed(2)}s
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Analysis 2 */}
                    <Card className="glass-card">
                      <CardHeader>
                        <CardTitle className="flex items-center justify-between">
                          <span>Analyse 2</span>
                          <Badge className={getGradeColor(compareResult2.performance_score.grade)}>
                            {compareResult2.performance_score.grade}
                          </Badge>
                        </CardTitle>
                        <CardDescription>
                          {formatDate(new Date(compareResult2.timestamp).toISOString())}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="text-center">
                          <div className="text-4xl font-bold text-foreground mb-2">
                            {Math.round(getDisplayScore(compareResult2.performance_score))}/100
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {compareResult2.corners_detected} virages •{" "}
                            {compareResult2.lap_time.toFixed(2)}s
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Comparison */}
                    <Card className="glass-card md:col-span-2">
                      <CardHeader>
                        <CardTitle>Comparaison</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div className="text-center p-4 rounded-lg bg-secondary/50">
                            <div className="text-xs text-muted-foreground mb-1">
                              Différence score
                            </div>
                            <div
                              className={`text-2xl font-bold ${
                                getDisplayScore(compareResult2.performance_score) >
                                getDisplayScore(compareResult1.performance_score)
                                  ? "text-green-400"
                                  : getDisplayScore(compareResult2.performance_score) <
                                      getDisplayScore(compareResult1.performance_score)
                                    ? "text-red-400"
                                    : "text-foreground"
                              }`}
                            >
                              {getDisplayScore(compareResult2.performance_score) >
                              getDisplayScore(compareResult1.performance_score)
                                ? "+"
                                : ""}
                              {(
                                getDisplayScore(compareResult2.performance_score) -
                                getDisplayScore(compareResult1.performance_score)
                              ).toFixed(1)}
                            </div>
                          </div>
                          <div className="text-center p-4 rounded-lg bg-secondary/50">
                            <div className="text-xs text-muted-foreground mb-1">
                              Différence temps
                            </div>
                            <div
                              className={`text-2xl font-bold ${
                                compareResult2.lap_time < compareResult1.lap_time
                                  ? "text-green-400"
                                  : compareResult2.lap_time > compareResult1.lap_time
                                    ? "text-red-400"
                                    : "text-foreground"
                              }`}
                            >
                              {compareResult2.lap_time < compareResult1.lap_time ? "-" : "+"}
                              {Math.abs(compareResult2.lap_time - compareResult1.lap_time).toFixed(
                                2
                              )}
                              s
                            </div>
                          </div>
                          <div className="text-center p-4 rounded-lg bg-secondary/50">
                            <div className="text-xs text-muted-foreground mb-1">
                              Différence virages
                            </div>
                            <div className="text-2xl font-bold text-foreground">
                              {compareResult2.corners_detected - compareResult1.corners_detected}
                            </div>
                          </div>
                          <div className="text-center p-4 rounded-lg bg-secondary/50">
                            <div className="text-xs text-muted-foreground mb-1">Amélioration</div>
                            <div className="text-2xl font-bold text-foreground flex justify-center">
                              {getDisplayScore(compareResult2.performance_score) >
                              getDisplayScore(compareResult1.performance_score) ? (
                                <CheckCircle2 className="w-6 h-6 text-green-500" />
                              ) : getDisplayScore(compareResult2.performance_score) <
                                  getDisplayScore(compareResult1.performance_score) ? (
                                <X className="w-6 h-6 text-destructive" />
                              ) : (
                                <ArrowRight className="w-6 h-6 text-muted-foreground" />
                              )}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Details Tab */}
          {selectedAnalysis && (
            <TabsContent value="details" className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setSelectedAnalysis(null);
                    setSearchParams({});
                  }}
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Retour à la liste
                </Button>
                <div className="flex gap-2">
                  <Button
                    variant="destructive"
                    onClick={() => handleDeleteClick(selectedAnalysis.analysis_id)}
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Supprimer
                  </Button>
                </div>
              </div>

              {/* Score Card */}
              <Card className="glass-card border-primary/20">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <TrendingUp className="w-5 h-5 text-primary" />
                      Score de Performance
                    </span>
                    <Badge className={getGradeColor(selectedAnalysis.performance_score.grade)}>
                      {selectedAnalysis.performance_score.grade}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-center mb-6">
                    <div className="text-6xl font-display font-bold bg-gradient-to-r from-primary to-pink-500 text-transparent bg-clip-text mb-2">
                      {Math.round(getDisplayScore(selectedAnalysis.performance_score))}/100
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Percentile: {selectedAnalysis.performance_score.percentile || "N/A"}%
                    </p>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center p-3 rounded-lg bg-secondary/50">
                      <div className="text-xs text-muted-foreground mb-1">Précision Apex</div>
                      <div className="text-lg font-bold text-foreground">
                        {Math.round(selectedAnalysis.performance_score.breakdown.apex_precision)}/30
                      </div>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-secondary/50">
                      <div className="text-xs text-muted-foreground mb-1">Régularité</div>
                      <div className="text-lg font-bold text-foreground">
                        {Math.round(
                          selectedAnalysis.performance_score.breakdown.trajectory_consistency
                        )}
                        /25
                      </div>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-secondary/50">
                      <div className="text-xs text-muted-foreground mb-1">Vitesse Apex</div>
                      <div className="text-lg font-bold text-foreground">
                        {Math.round(selectedAnalysis.performance_score.breakdown.apex_speed)}/25
                      </div>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-secondary/50">
                      <div className="text-xs text-muted-foreground mb-1">Temps Secteurs</div>
                      <div className="text-lg font-bold text-foreground">
                        {Math.round(selectedAnalysis.performance_score.breakdown.sector_times)}/20
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Statistics */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="glass-card">
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 mb-2">
                      <Target className="w-4 h-4 text-primary" />
                      <div className="text-xs text-muted-foreground">Virages détectés</div>
                    </div>
                    <div className="text-2xl font-bold text-foreground">
                      {selectedAnalysis.corners_detected}
                    </div>
                  </CardContent>
                </Card>
                {(selectedAnalysis.statistics.laps_analyzed ?? 1) <= 1 ? (
                  <Card className="glass-card">
                    <CardContent className="pt-6">
                      <div className="flex items-center gap-2 mb-2">
                        <Clock className="w-4 h-4 text-primary" />
                        <div className="text-xs text-muted-foreground">Temps du tour</div>
                      </div>
                      <div className="text-2xl font-bold text-foreground">
                        {selectedAnalysis.lap_time.toFixed(2)}s
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <Card className="glass-card border-green-500/30">
                    <CardContent className="pt-6">
                      <div className="flex items-center gap-2 mb-2">
                        <Clock className="w-4 h-4 text-green-500" />
                        <div className="text-xs text-muted-foreground">Meilleur tour</div>
                      </div>
                      <div className="text-2xl font-bold text-green-500">
                        {(selectedAnalysis.best_lap_time ?? selectedAnalysis.lap_time).toFixed(2)}s
                      </div>
                    </CardContent>
                  </Card>
                )}
                <Card className="glass-card">
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 mb-2">
                      <Zap className="w-4 h-4 text-primary" />
                      <div className="text-xs text-muted-foreground">Points de données</div>
                    </div>
                    <div className="text-2xl font-bold text-foreground">
                      {selectedAnalysis.statistics.data_points}
                    </div>
                  </CardContent>
                </Card>
                <Card className="glass-card">
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 mb-2">
                      <Clock className="w-4 h-4 text-primary" />
                      <div className="text-xs text-muted-foreground">Temps traitement</div>
                    </div>
                    <div className="text-2xl font-bold text-foreground">
                      {selectedAnalysis.statistics.processing_time_seconds.toFixed(1)}s
                    </div>
                  </CardContent>
                </Card>
              </div>


              {/* Coaching Advice */}
              {selectedAnalysis.coaching_advice && selectedAnalysis.coaching_advice.length > 0 && (
                <Card className="glass-card border-primary/20">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Zap className="w-5 h-5 text-primary" />
                      Conseils de Coaching
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {selectedAnalysis.coaching_advice.map((advice, index) => (
                        <div
                          key={index}
                          className="p-4 rounded-lg bg-secondary/50 border border-white/5"
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="text-xs">
                                Priorité {advice.priority}
                              </Badge>
                              <Badge variant="outline" className="text-xs capitalize">
                                {advice.category}
                              </Badge>
                              {advice.corner && (
                                <Badge variant="outline" className="text-xs">
                                  Virage {advice.corner}
                                </Badge>
                              )}
                            </div>
                            {advice.impact_seconds > 0 && (
                              <span className="text-xs text-muted-foreground">
                                Gain potentiel: {advice.impact_seconds.toFixed(2)}s
                              </span>
                            )}
                          </div>
                          <p className="font-semibold text-foreground mb-1">{advice.message}</p>
                          <p className="text-sm text-muted-foreground">{advice.explanation}</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Corner Analysis */}
              {selectedAnalysis.corner_analysis && selectedAnalysis.corner_analysis.length > 0 && (
                <Card className="glass-card border-primary/20">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Target className="w-5 h-5 text-primary" />
                      Analyse des Virages
                    </CardTitle>
                    <CardDescription>
                      {selectedAnalysis.statistics?.laps_analyzed === 1
                        ? "Performance sur ce tour"
                        : `Valeurs moyennées sur les ${selectedAnalysis.statistics?.laps_analyzed ?? 0} tours sélectionnés`}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead></TableHead>
                            <TableHead>Virage</TableHead>
                            <TableHead>Type</TableHead>
                            <TableHead>Vitesse Réelle</TableHead>
                            <TableHead>Vitesse Optimale</TableHead>
                            <TableHead>G Latéral</TableHead>
                            <TableHead>Temps Perdu</TableHead>
                            <TableHead>Score</TableHead>
                            <TableHead>Grade</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {selectedAnalysis.corner_analysis.map((corner, index) => {
                            const cornerTypeLabel = corner.corner_type === "right" ? "Droite" : corner.corner_type === "left" ? "Gauche" : corner.corner_type;
                            const hasPerLap = (corner.per_lap_data?.length ?? 0) > 1 && (selectedAnalysis.statistics?.laps_analyzed ?? 0) > 1;
                            const showWarning = corner.time_lost > 0.05;
                            return (
                              <Fragment key={index}>
                                <TableRow>
                                  <TableCell className="w-8">
                                    {hasPerLap && (
                                      <button
                                        type="button"
                                        onClick={() => setExpandedCorner(expandedCorner === corner.corner_id ? null : corner.corner_id)}
                                        className="text-muted-foreground hover:text-foreground"
                                      >
                                        {expandedCorner === corner.corner_id ? "▼" : "▶"}
                                      </button>
                                    )}
                                  </TableCell>
                                  <TableCell className="font-medium">{corner.label ?? `#${corner.corner_number}`}</TableCell>
                                  <TableCell>{cornerTypeLabel}</TableCell>
                                  <TableCell>{corner.apex_speed_real.toFixed(1)} km/h</TableCell>
                                  <TableCell>{corner.apex_speed_optimal.toFixed(1)} km/h</TableCell>
                                  <TableCell>{corner.lateral_g_max.toFixed(2)}G</TableCell>
                                  <TableCell>{corner.time_lost.toFixed(3)}s</TableCell>
                                  <TableCell>
                                    {showWarning && <span className="text-orange-500 mr-1" title="Temps perdu &gt; 0.05s">⚠️</span>}
                                    {Math.round(corner.score)}/100
                                  </TableCell>
                                  <TableCell>
                                    <Badge className={getGradeColor(corner.grade)}>
                                      {corner.grade}
                                    </Badge>
                                  </TableCell>
                                </TableRow>
                                {hasPerLap && expandedCorner === corner.corner_id && corner.per_lap_data && (
                                  <TableRow>
                                    <TableCell colSpan={9} className="bg-muted/30 p-4">
                                      <div className="text-xs font-medium text-muted-foreground mb-2">Détail par tour</div>
                                      <table className="w-full text-sm">
                                        <thead>
                                          <tr className="border-b border-white/5">
                                            <th className="text-left py-1">Tour</th>
                                            <th className="text-left py-1">Vit. Apex</th>
                                            <th className="text-left py-1">G Lat</th>
                                            <th className="text-left py-1">Tps Perdu</th>
                                          </tr>
                                        </thead>
                                        <tbody>
                                          {corner.per_lap_data.map((lap, i) => (
                                            <tr key={i}>
                                              <td className="py-1">{lap.lap}</td>
                                              <td className="py-1">{(lap.apex_speed_kmh ?? 0).toFixed(1)} km/h</td>
                                              <td className="py-1">{(lap.max_lateral_g ?? 0).toFixed(2)}G</td>
                                              <td className="py-1">{(lap.time_lost ?? 0).toFixed(3)}s</td>
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    </TableCell>
                                  </TableRow>
                                )}
                              </Fragment>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Plots */}
              {selectedAnalysis.plots && Object.keys(selectedAnalysis.plots).length > 0 && (
                <Card className="glass-card border-primary/20">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <FileDown className="w-5 h-5 text-primary" />
                      Graphiques Générés
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {Object.entries(selectedAnalysis.plots).map(([plotName, plotUrl]) => {
                        if (!plotUrl) return null;
                        const displayName = plotName
                          .replace(/_/g, " ")
                          .replace(/\b\w/g, (l) => l.toUpperCase());
                        return (
                          <div
                            key={plotName}
                            onClick={() => {
                              setModalImage(plotUrl);
                              setModalTitle(displayName);
                            }}
                            className="p-4 rounded-lg bg-secondary/50 border border-white/5 hover:border-primary/50 transition-colors group cursor-pointer hover:opacity-80"
                          >
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-sm font-medium text-foreground">
                                {displayName}
                              </span>
                              <Eye className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                            </div>
                            <img
                              src={plotUrl}
                              alt={displayName}
                              className="w-full h-32 object-cover rounded border border-white/5"
                              onError={(e) => {
                                (e.target as HTMLImageElement).style.display = "none";
                              }}
                            />
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          )}
        </Tabs>

        {/* Panel Admin - moreauy58@gmail.com uniquement */}
        {isAdmin && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-8 p-6 bg-gradient-to-r from-red-600 to-red-700 rounded-2xl border border-red-500/30 shadow-xl"
          >
            <h2 className="text-2xl font-bold text-white mb-6">Panel Admin</h2>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
              <div className="bg-white/10 rounded-xl p-6 text-center border border-white/20">
                <div className="text-3xl font-bold text-white">{analyses.length}</div>
                <div className="text-white/90 text-sm">Analyses totales</div>
              </div>
              <div className="bg-white/10 rounded-xl p-6 text-center border border-white/20" title="Backend requis">
                <div className="text-3xl font-bold text-white">—</div>
                <div className="text-white/90 text-sm">Utilisateurs actifs</div>
              </div>
              <div className="bg-white/10 rounded-xl p-6 text-center border border-white/20" title="Backend requis">
                <div className="text-3xl font-bold text-white">—</div>
                <div className="text-white/90 text-sm">CA généré</div>
              </div>
            </div>

            <div className="grid md:grid-cols-3 gap-4">
              <Button
                type="button"
                onClick={handleAdminClearCache}
                className="p-4 h-auto flex items-center justify-center gap-3 bg-white/15 border border-white/30 text-white hover:bg-white/25"
              >
                <RefreshCw className="w-5 h-5" />
                Vider cache IA
              </Button>
              <Button
                type="button"
                onClick={handleAdminResetTestUsers}
                className="p-4 h-auto flex items-center justify-center gap-3 bg-white/15 border border-white/30 text-white hover:bg-white/25"
              >
                <Trash2 className="w-5 h-5" />
                Reset users test
              </Button>
              <Button
                type="button"
                onClick={handleAdminExportStats}
                className="p-4 h-auto flex items-center justify-center gap-3 bg-white/15 border border-white/30 text-white hover:bg-white/25"
              >
                <Download className="w-5 h-5" />
                Exporter stats
              </Button>
            </div>
          </motion.div>
        )}

        {/* Delete Confirmation Dialog */}
        <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Supprimer l'analyse</DialogTitle>
              <DialogDescription>
                Êtes-vous sûr de vouloir supprimer cette analyse ? Cette action est irréversible.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
                Annuler
              </Button>
              <Button variant="destructive" onClick={handleDeleteConfirm}>
                Supprimer
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Modal lightbox pour graphiques */}
        {modalImage && createPortal(
          <div
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              zIndex: 99999,
              backgroundColor: 'rgba(0, 0, 0, 0.88)',
              backdropFilter: 'blur(6px)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onClick={() => setModalImage(null)}
          >
            <div
              style={{
                position: 'relative',
                maxWidth: '95vw',
                maxHeight: '92vh',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '12px',
                padding: '16px',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Barre titre + bouton fermer */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                width: '100%',
                minWidth: '300px',
              }}>
                <p style={{
                  color: '#e2e8f0',
                  fontWeight: 600,
                  fontSize: '15px',
                  margin: 0,
                  flex: 1,
                }}>
                  {modalTitle}
                </p>
                <button
                  style={{
                    background: '#374151',
                    border: 'none',
                    color: 'white',
                    borderRadius: '50%',
                    width: '32px',
                    height: '32px',
                    cursor: 'pointer',
                    fontSize: '18px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginLeft: '12px',
                    flexShrink: 0,
                  }}
                  onClick={() => setModalImage(null)}
                >
                  ✕
                </button>
              </div>
              {/* Image */}
              <img
                src={modalImage}
                alt={modalTitle}
                style={{
                  maxWidth: '100%',
                  maxHeight: '80vh',
                  objectFit: 'contain',
                  borderRadius: '8px',
                  boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
                }}
                onClick={(e) => e.stopPropagation()}
              />
              <p style={{ color: '#64748b', fontSize: '11px', margin: 0 }}>
                Cliquer en dehors pour fermer · ESC pour fermer
              </p>
            </div>
          </div>,
          document.body
        )}
      </div>
    </Layout>
  );
}
