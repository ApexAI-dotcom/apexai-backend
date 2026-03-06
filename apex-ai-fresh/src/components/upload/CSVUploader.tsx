import React, { useState, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate, Link } from "react-router-dom";
import {
  Upload,
  FileSpreadsheet,
  CheckCircle,
  Loader2,
  X,
  AlertCircle,
  Download,
  ExternalLink,
  TrendingUp,
  Target,
  Zap,
  Clock,
  Save,
  Database,
  Wifi,
  WifiOff,
  Brain,
  BarChart3,
  Eye,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  uploadAndAnalyzeCSV,
  parseLaps,
  checkBackendConnection,
  API_BASE_URL,
  getDisplayScore,
  type AnalysisResult,
  type ApiError,
  type LapInfo,
} from "@/lib/api";
import { saveAnalysis, getAnalysesCount } from "@/lib/storage";
import { useAuth } from "@/hooks/useAuth";
import { toast } from "@/hooks/use-toast";
import { ToastAction } from "@/components/ui/toast";

// ─── Types ───────────────────────────────────────────────────────────────────

interface CSVUploaderProps {
  onUploadComplete?: (data: AnalysisResult) => void;
}

function formatLapTime(seconds: number): string {
  if (seconds <= 0 || !Number.isFinite(seconds)) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  const ms = Math.round((s % 1) * 1000);
  const sec = Math.floor(s);
  if (m > 0) return `${m}:${sec.toString().padStart(2, "0")}.${ms.toString().padStart(3, "0")}`;
  return `${sec}.${ms.toString().padStart(3, "0")}s`;
}

// Étapes de progression affichées pendant l'analyse
const ANALYSIS_STEPS = [
  { icon: Wifi,      message: "Connexion au serveur…",              duration: 1200 },
  { icon: Upload,    message: "Téléchargement du fichier CSV…",     duration: 1500 },
  { icon: Brain,     message: "L'IA analyse vos apices…",           duration: 3000 },
  { icon: BarChart3, message: "Calcul du score de performance…",    duration: 2000 },
  { icon: Target,    message: "Génération des graphiques…",         duration: 1500 },
];

// ─── Composant ────────────────────────────────────────────────────────────────

export const CSVUploader = ({ onUploadComplete }: CSVUploaderProps) => {
  const navigate = useNavigate();
  const { user, session, isAuthenticated, canUploadFree, guestUsed, guestUpload, consumeGuestSlot } = useAuth();
  const canUpload = isAuthenticated || canUploadFree;
  const storageUserId = user?.id ?? undefined;

  // États upload
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  // Tours détectés (parse-laps) : null = pas encore chargé ou erreur
  const [laps, setLaps] = useState<LapInfo[] | null>(null);
  const [lapsLoading, setLapsLoading] = useState(false);
  const [selectedLapNumbers, setSelectedLapNumbers] = useState<number[]>([]);
  const [trackCondition, setTrackCondition] = useState<"dry" | "damp" | "wet" | "rain">("dry");
  const [trackTemperature, setTrackTemperature] = useState<number | "">("");

  // États analyse
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [analysisStepIndex, setAnalysisStepIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [showLimitReachedModal, setShowLimitReachedModal] = useState(false);

  // Résultats
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [savedAnalysisId, setSavedAnalysisId] = useState<string | null>(null);
  const [analysesCount, setAnalysesCount] = useState<number>(0);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
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

  // ─── Chargement initial du compteur ──────────────────────────────────────

  useEffect(() => {
    getAnalysesCount(storageUserId).then(setAnalysesCount).catch(() => {});
  }, [storageUserId]);

  // ─── Détection des tours (parse-laps) à la sélection du fichier ───────────
  useEffect(() => {
    if (!file) {
      setLaps(null);
      setSelectedLapNumbers([]);
      setLapsLoading(false);
      return;
    }
    let cancelled = false;
    setLapsLoading(true);
    setLaps(null);
    parseLaps(file)
      .then((res) => {
        if (cancelled) return;
        setLaps(res.laps);
        const defaultSelected = (res.laps || []).filter((l) => !l.is_outlier).map((l) => l.lap_number);
        setSelectedLapNumbers(defaultSelected);
      })
      .catch(() => {
        if (!cancelled) setLaps(null);
      })
      .finally(() => {
        if (!cancelled) setLapsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [file]);

  // ─── Progression simulée pendant l'analyse ───────────────────────────────

  useEffect(() => {
    if (!isAnalyzing) {
      setAnalysisStepIndex(0);
      return;
    }

    let stepIdx = 0;
    const advance = () => {
      if (stepIdx < ANALYSIS_STEPS.length - 1) {
        stepIdx++;
        setAnalysisStepIndex(stepIdx);
        setTimeout(advance, ANALYSIS_STEPS[stepIdx].duration);
      }
    };

    const firstTimer = setTimeout(advance, ANALYSIS_STEPS[0].duration);
    return () => clearTimeout(firstTimer);
  }, [isAnalyzing]);

  // ─── Drag & drop ──────────────────────────────────────────────────────────

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile?.name.endsWith(".csv")) {
      setFile(droppedFile);
      setError(null);
    } else if (droppedFile) {
      setError("Format invalide — seuls les fichiers .csv sont acceptés.");
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile?.name.endsWith(".csv")) {
      setFile(selectedFile);
      setError(null);
    } else if (selectedFile) {
      setError("Format invalide — seuls les fichiers .csv sont acceptés.");
    }
    // Reset l'input pour permettre de re-sélectionner le même fichier
    e.target.value = "";
  }, []);

  // ─── Reset complet ────────────────────────────────────────────────────────

  const handleReset = () => {
    setFile(null);
    setLaps(null);
    setSelectedLapNumbers([]);
    setIsComplete(false);
    setIsAnalyzing(false);
    setError(null);
    setResult(null);
    setSavedAnalysisId(null);
    setSaveSuccess(null);
    setAnalysisStepIndex(0);
    getAnalysesCount(storageUserId).then(setAnalysesCount).catch(() => {});
  };

  // ─── Sauvegarde manuelle (si l'auto-save a échoué) ───────────────────────

  const handleSaveAnalysis = async () => {
    if (!result || savedAnalysisId) return; // déjà sauvegardé

    try {
      const analysisId = await saveAnalysis(result, storageUserId);
      setSavedAnalysisId(analysisId);
      setSaveSuccess(`Analyse sauvegardée (ID : ${analysisId})`);
      const count = await getAnalysesCount(storageUserId);
      setAnalysesCount(count);
      setTimeout(() => setSaveSuccess(null), 5000);
    } catch (err) {
      setError(
        `Erreur lors de la sauvegarde : ${err instanceof Error ? err.message : "Erreur inconnue"}`
      );
    }
  };

  // ─── Navigation Dashboard ────────────────────────────────────────────────

  const handleViewInDashboard = () => {
    const id = savedAnalysisId ?? result?.analysis_id;
    if (id) navigate(`/dashboard?analysisId=${id}`);
  };

  // ─── Download JSON ────────────────────────────────────────────────────────

  const handleDownloadResults = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `apex-ai-analysis-${result.analysis_id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // ─── Analyse principale ───────────────────────────────────────────────────

  const handleAnalyze = async () => {
    if (!file) return;

    // Gestion accès
    if (!canUpload) {
      if (guestUsed) {
        toast({
          title: "Connexion requise",
          description: "Connectez-vous pour effectuer d'autres analyses.",
          action: (
            <ToastAction altText="Se connecter" onClick={() => navigate("/login")}>
              Se connecter
            </ToastAction>
          ),
        });
      } else {
        toast({
          title: "1 analyse gratuite disponible",
          description: "Cliquez sur Essayer pour analyser sans compte.",
          action: (
            <ToastAction altText="Essayer" onClick={guestUpload}>
              Essayer
            </ToastAction>
          ),
        });
      }
      return;
    }

    setIsAnalyzing(true);
    setError(null);
    setSaveSuccess(null);

    try {
      // Vérification connexion backend
      const isConnected = await checkBackendConnection();
      if (!isConnected) {
        throw {
          success: false,
          error: "backend_unavailable",
          message: `Serveur inaccessible (${API_BASE_URL}). Vérifiez votre connexion ou réessayez dans quelques instants.`,
        } as ApiError;
      }

      // Upload + analyse
      const lapFilter =
        selectedLapNumbers.length > 0 && laps?.length ? selectedLapNumbers : undefined;
      const tempNum =
        trackTemperature === "" || trackTemperature == null
          ? undefined
          : Number(trackTemperature);
      const analysisResult = await uploadAndAnalyzeCSV(file, {
        lapFilter: lapFilter ?? undefined,
        track_condition: trackCondition,
        track_temperature: tempNum ?? undefined,
        accessToken: session?.access_token ?? undefined,
      });

      // Auto-save (clé storage = user courant ou guest)
      let analysisId: string | null = null;
      try {
        analysisId = await saveAnalysis(analysisResult, storageUserId);
        setSavedAnalysisId(analysisId);
        setSaveSuccess(`Analyse sauvegardée automatiquement.`);
        setTimeout(() => setSaveSuccess(null), 5000);
        const count = await getAnalysesCount(storageUserId);
        setAnalysesCount(count);
      } catch (saveErr) {
        console.warn("Auto-save failed:", saveErr);
        // Non bloquant — le bouton "Sauvegarder" restera disponible
      }

      if (!isAuthenticated && canUploadFree) consumeGuestSlot();

      setResult(analysisResult);
      setIsAnalyzing(false);
      setIsComplete(true);

      onUploadComplete?.(analysisResult);
    } catch (err) {
      setIsAnalyzing(false);
      const apiError = err as ApiError;
      if (apiError?.error === "limit_reached") {
        setError(null);
        setShowLimitReachedModal(true);
      } else {
        setError(
          apiError?.message ?? "Une erreur inattendue s'est produite. Réessayez dans quelques instants."
        );
      }
    }
  };

  // ─── Helpers UI ──────────────────────────────────────────────────────────

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

  const currentStep = ANALYSIS_STEPS[analysisStepIndex];
  const StepIcon = currentStep?.icon ?? Loader2;

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-8"
    >
      {/* Compteur analyses sauvegardées (masqué si non connecté) */}
      {isAuthenticated && analysesCount > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 flex items-center justify-center gap-2 text-sm text-muted-foreground"
        >
          <Database className="w-4 h-4" />
          <span>
            {analysesCount} analyse{analysesCount > 1 ? "s" : ""} sauvegardée
            {analysesCount > 1 ? "s" : ""}
          </span>
        </motion.div>
      )}

      {/* Alerte sauvegarde réussie */}
      <AnimatePresence>
        {saveSuccess && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mb-6"
          >
            <Alert className="bg-green-500/10 border-green-500/50">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <AlertTitle className="text-green-200">Sauvegarde réussie</AlertTitle>
              <AlertDescription className="text-green-300">{saveSuccess}</AlertDescription>
            </Alert>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Modal limite Rookie atteinte */}
      <Dialog open={showLimitReachedModal} onOpenChange={setShowLimitReachedModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Limite atteinte</DialogTitle>
            <DialogDescription>
              Passez à Racer pour des analyses illimitées.
            </DialogDescription>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Vous avez utilisé vos 3 analyses du mois. Passez au plan Racer pour analyser sans limite.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowLimitReachedModal(false)}>
              Fermer
            </Button>
            <Button asChild>
              <Link to="/pricing">Voir les offres Racer</Link>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Alerte erreur */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mb-6"
          >
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Erreur</AlertTitle>
              <AlertDescription className="flex flex-col gap-2">
                <span>{error}</span>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-fit border-destructive/50 text-destructive hover:bg-destructive/10"
                  onClick={() => setError(null)}
                >
                  Fermer
                </Button>
              </AlertDescription>
            </Alert>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Contenu principal ── */}
      <AnimatePresence mode="wait">

        {/* État : Résultats affichés */}
        {isComplete && result ? (
          <motion.div
            key="complete"
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            className="space-y-6"
          >
            {/* Header succès */}
            <div className="text-center py-6">
              <div className="w-20 h-20 rounded-full gradient-success flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-10 h-10 text-success-foreground" />
              </div>
              <h3 className="text-2xl font-display font-bold text-foreground mb-2">
                Analyse terminée !
              </h3>
              <p className="text-muted-foreground mb-4">
                Votre session a été analysée avec succès.
              </p>
              {result.session_conditions && (
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-sm text-muted-foreground mb-6">
                  <span>
                    {result.session_conditions.track_condition === "dry" && "☀️"}
                    {result.session_conditions.track_condition === "damp" && "🌦️"}
                    {result.session_conditions.track_condition === "wet" && "💧"}
                    {result.session_conditions.track_condition === "rain" && "🌧️"}
                  </span>
                  <span>
                    Conditions :{" "}
                    {result.session_conditions.track_condition === "dry" && "Sec"}
                    {result.session_conditions.track_condition === "damp" && "Humide"}
                    {result.session_conditions.track_condition === "wet" && "Mouillée"}
                    {result.session_conditions.track_condition === "rain" && "Pluie"}
                    {result.session_conditions.track_temperature != null &&
                    Number.isFinite(result.session_conditions.track_temperature)
                      ? ` — ${result.session_conditions.track_temperature}°C`
                      : ""}
                  </span>
                </div>
              )}
              {!result.session_conditions && <div className="mb-6" />}
              <div className="flex flex-col sm:flex-row justify-center gap-3 flex-wrap">
                <Button variant="heroOutline" onClick={handleReset}>
                  Nouvelle analyse
                </Button>
                <Button variant="hero" onClick={handleDownloadResults}>
                  <Download className="w-4 h-4 mr-2" />
                  Télécharger JSON
                </Button>
                {(savedAnalysisId || result?.analysis_id) && (
                  <Button variant="heroOutline" onClick={handleViewInDashboard}>
                    <ExternalLink className="w-4 h-4 mr-2" />
                    Voir dans le Dashboard
                  </Button>
                )}
                {/* Bouton sauvegarde manuelle si auto-save a échoué */}
                {!savedAnalysisId && (
                  <Button variant="outline" onClick={handleSaveAnalysis}>
                    <Save className="w-4 h-4 mr-2" />
                    Sauvegarder
                  </Button>
                )}
              </div>
            </div>

            {/* Score de performance */}
            <Card className="glass-card border-primary/20">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-primary" />
                    Score de Performance
                  </span>
                  <Badge className={getGradeColor(result.performance_score.grade)}>
                    {result.performance_score.grade}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center mb-6">
                  <div className="text-6xl font-display font-bold bg-gradient-to-r from-primary to-pink-500 text-transparent bg-clip-text mb-2">
                    {Math.round(getDisplayScore(result.performance_score))}/100
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Centile : {result.performance_score.percentile ?? "—"}%
                  </p>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: "Précision Apex", value: result.performance_score.breakdown.apex_precision, max: 30 },
                    { label: "Régularité",     value: result.performance_score.breakdown.trajectory_consistency, max: 25 },
                    { label: "Vitesse Apex",   value: result.performance_score.breakdown.apex_speed, max: 25 },
                    { label: "Temps Secteurs", value: result.performance_score.breakdown.sector_times, max: 20 },
                  ].map(({ label, value, max }) => (
                    <div key={label} className="text-center p-3 rounded-lg bg-secondary/50">
                      <div className="text-xs text-muted-foreground mb-1">{label}</div>
                      <div className="text-lg font-bold text-foreground">
                        {Math.round(value)}/{max}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Stats rapides */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card className="glass-card">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2 mb-2">
                    <Target className="w-4 h-4 text-primary" />
                    <div className="text-xs text-muted-foreground">Virages détectés</div>
                  </div>
                  <div className="text-2xl font-bold text-foreground">{result.corners_detected}</div>
                </CardContent>
              </Card>
              {(result.statistics.laps_analyzed ?? 1) <= 1 ? (
                <Card className="glass-card">
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 mb-2">
                      <Clock className="w-4 h-4 text-primary" />
                      <div className="text-xs text-muted-foreground">Temps du tour</div>
                    </div>
                    <div className="text-2xl font-bold text-foreground">{result.lap_time.toFixed(2)}s</div>
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
                      {(result.best_lap_time ?? result.lap_time).toFixed(2)}s
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
                  <div className="text-2xl font-bold text-foreground">{result.statistics.data_points}</div>
                </CardContent>
              </Card>
              <Card className="glass-card">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2 mb-2">
                    <Clock className="w-4 h-4 text-primary" />
                    <div className="text-xs text-muted-foreground">Temps traitement</div>
                  </div>
                  <div className="text-2xl font-bold text-foreground">{result.statistics.processing_time_seconds.toFixed(1)}s</div>
                </CardContent>
              </Card>
            </div>

            {/* Conseils de coaching */}
            {result.coaching_advice?.length > 0 && (
              <Card className="glass-card border-primary/20">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Zap className="w-5 h-5 text-primary" />
                    Conseils de Coaching (Top {result.coaching_advice.length})
                  </CardTitle>
                  <CardDescription>
                    Conseils prioritaires pour améliorer votre performance
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {result.coaching_advice.map((advice, index) => (
                      <div key={index} className="p-4 rounded-lg bg-secondary/50 border border-white/5">
                        <div className="flex items-start justify-between mb-2 flex-wrap gap-2">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge variant="outline" className="text-xs">Priorité {advice.priority}</Badge>
                            <Badge variant="outline" className="text-xs capitalize">{advice.category}</Badge>
                            {advice.corner && (
                              <Badge variant="outline" className="text-xs">Virage {advice.corner}</Badge>
                            )}
                          </div>
                          {advice.impact_seconds > 0 && (
                            <span className="text-xs text-muted-foreground">
                              Gain potentiel : {advice.impact_seconds.toFixed(2)}s
                            </span>
                          )}
                        </div>
                        <p className="font-semibold text-foreground mb-1">{advice.message}</p>
                        <p className="text-sm text-muted-foreground">{advice.explanation}</p>
                        <div className="mt-2">
                          <Badge variant="secondary" className="text-xs">
                            Difficulté : {advice.difficulty}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Analyse des virages */}
            {result.corner_analysis?.length > 0 && (
              <Card className="glass-card border-primary/20">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Target className="w-5 h-5 text-primary" />
                    Analyse des Virages
                  </CardTitle>
                  <CardDescription>
                    {result.statistics?.laps_analyzed === 1
                      ? "Performance sur ce tour"
                      : `Valeurs moyennées sur les ${result.statistics?.laps_analyzed ?? 0} tours sélectionnés`}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-white/5">
                          <th className="px-4 py-2 text-left text-muted-foreground w-8"></th>
                          {["Virage","Type","Vit. Réelle","Vit. Optimale","G Latéral","Tps Perdu","Score","Grade"].map((h) => (
                            <th key={h} className="px-4 py-2 text-left text-muted-foreground">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.corner_analysis.slice(0, 10).map((corner, index) => {
                          const cornerTypeLabel = corner.corner_type === "right" ? "Droite" : corner.corner_type === "left" ? "Gauche" : corner.corner_type;
                          const hasPerLap = (corner.per_lap_data?.length ?? 0) > 1 && (result.statistics?.laps_analyzed ?? 0) > 1;
                          const showWarning = corner.time_lost > 0.05;
                          return (
                            <React.Fragment key={index}>
                              <tr className="border-b border-white/5 hover:bg-white/5">
                                <td className="px-4 py-2 w-8">
                                  {hasPerLap && (
                                    <button
                                      type="button"
                                      onClick={() => setExpandedCorner(expandedCorner === corner.corner_id ? null : corner.corner_id)}
                                      className="text-muted-foreground hover:text-foreground"
                                    >
                                      {expandedCorner === corner.corner_id ? "▼" : "▶"}
                                    </button>
                                  )}
                                </td>
                                <td className="px-4 py-2 font-medium">{corner.label ?? `#${corner.corner_number}`}</td>
                                <td className="px-4 py-2">{cornerTypeLabel}</td>
                                <td className="px-4 py-2">{corner.apex_speed_real.toFixed(1)} km/h</td>
                                <td className="px-4 py-2">{corner.apex_speed_optimal.toFixed(1)} km/h</td>
                                <td className="px-4 py-2">{corner.lateral_g_max.toFixed(2)}G</td>
                                <td className="px-4 py-2">{corner.time_lost.toFixed(3)}s</td>
                                <td className="px-4 py-2">
                                  {showWarning && <span className="text-orange-500 mr-1" title="Temps perdu &gt; 0.05s">⚠️</span>}
                                  {Math.round(corner.score)}/100
                                </td>
                                <td className="px-4 py-2">
                                  <Badge className={getGradeColor(corner.grade)}>{corner.grade}</Badge>
                                </td>
                              </tr>
                              {hasPerLap && expandedCorner === corner.corner_id && corner.per_lap_data && (
                                <tr className="border-b border-white/5 bg-white/5">
                                  <td colSpan={9} className="px-4 py-2">
                                    <div className="text-xs text-muted-foreground mb-1">Détail par tour</div>
                                    <table className="w-full text-xs">
                                      <thead>
                                        <tr><th className="text-left py-0.5">Tour</th><th className="text-left py-0.5">Vit. Apex</th><th className="text-left py-0.5">G Lat</th><th className="text-left py-0.5">Tps Perdu</th></tr>
                                      </thead>
                                      <tbody>
                                        {corner.per_lap_data.map((lap, i) => (
                                          <tr key={i}>
                                            <td className="py-0.5">{lap.lap}</td>
                                            <td className="py-0.5">{(lap.apex_speed_kmh ?? 0).toFixed(1)} km/h</td>
                                            <td className="py-0.5">{(lap.max_lateral_g ?? 0).toFixed(2)}G</td>
                                            <td className="py-0.5">{(lap.time_lost ?? 0).toFixed(3)}s</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Graphiques */}
            {result.plots && Object.keys(result.plots).length > 0 && (
              <Card className="glass-card border-primary/20">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="w-5 h-5 text-primary" />
                    Graphiques Générés
                  </CardTitle>
                  <CardDescription>Visualisations de votre performance</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Object.entries(result.plots).map(([plotName, plotUrl]) => {
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
                            <span className="text-sm font-medium text-foreground">{displayName}</span>
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
          </motion.div>

        ) : isAnalyzing ? (
          /* ── État : Analyse en cours ── */
          <motion.div
            key="analyzing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="text-center py-12"
          >
            {/* Spinner double ring */}
            <div className="relative w-24 h-24 mx-auto mb-8">
              <div className="absolute inset-0 rounded-full border-4 border-muted" />
              <motion.div
                className="absolute inset-0 rounded-full border-4 border-primary border-t-transparent"
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              />
              <div className="absolute inset-0 flex items-center justify-center">
                <StepIcon className="w-8 h-8 text-primary" />
              </div>
            </div>

            <h3 className="text-xl font-display font-bold text-foreground mb-2">
              Analyse en cours…
            </h3>
            <p className="text-muted-foreground mb-4">Notre IA analyse vos données de course</p>

            {/* Message d'étape animé */}
            <AnimatePresence mode="wait">
              <motion.p
                key={analysisStepIndex}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.3 }}
                className="text-sm text-primary font-medium"
              >
                {currentStep?.message}
              </motion.p>
            </AnimatePresence>

            {/* Barre de progression */}
            <div className="mt-6 max-w-xs mx-auto">
              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-primary rounded-full"
                  initial={{ width: "5%" }}
                  animate={{ width: `${((analysisStepIndex + 1) / ANALYSIS_STEPS.length) * 100}%` }}
                  transition={{ duration: 0.6, ease: "easeOut" }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-2 text-right">
                {Math.round(((analysisStepIndex + 1) / ANALYSIS_STEPS.length) * 100)}%
              </p>
            </div>
          </motion.div>

        ) : (
          /* ── État : Upload ── */
          <motion.div
            key="upload"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`relative border-2 border-dashed rounded-xl p-12 text-center transition-all duration-300 ${
                isDragging
                  ? "border-primary bg-primary/5 scale-[1.01]"
                  : file
                    ? "border-green-500/60 bg-green-500/5"
                    : "border-border hover:bg-slate-800/50 hover:border-orange-400"
              }`}
            >
              <input
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />

              {file ? (
                <div className="flex flex-col items-center">
                  <div className="w-16 h-16 rounded-xl gradient-success flex items-center justify-center mb-4">
                    <FileSpreadsheet className="w-8 h-8 text-success-foreground" />
                  </div>
                  <p className="text-lg font-medium text-foreground mb-1">{file.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {(file.size / 1024).toFixed(1)} KB
                  </p>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleReset();
                    }}
                    className="absolute top-4 right-4 p-2 rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                    aria-label="Supprimer le fichier"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center">
                  <div className="w-16 h-16 rounded-xl bg-secondary flex items-center justify-center mb-4">
                    <Upload className="w-8 h-8 text-muted-foreground" />
                  </div>
                  <p className="text-lg font-medium text-foreground mb-1">
                    Glissez votre fichier CSV ici
                  </p>
                  <p className="text-sm text-muted-foreground mb-4">ou cliquez pour sélectionner</p>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {["MyChron5", "AiM", "RaceBox"].map((label) => (
                      <span key={label} className="px-2 py-1 rounded bg-secondary">{label}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Sélection des tours (si parse-laps a réussi) */}
            {file && (lapsLoading || laps) && (
              <Card className="mt-6 glass-card border-white/10 w-full max-w-2xl mx-auto">
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Clock className="w-5 h-5 text-[#ff6b35]" />
                    Tours à analyser
                  </CardTitle>
                  <CardDescription>
                    {lapsLoading
                      ? "Détection des tours en cours…"
                      : "Cochez les tours à inclure. Les tours stand/prépa (⚠️) sont décochés par défaut."}
                  </CardDescription>
                </CardHeader>
                {laps && laps.length > 0 && (
                  <CardContent className="pt-0">
                    <div className="overflow-x-auto rounded-lg border border-white/10">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-white/10 bg-white/5">
                            <th className="px-4 py-2 text-left text-muted-foreground w-12">Inclure</th>
                            <th className="px-4 py-2 text-left text-muted-foreground">N°</th>
                            <th className="px-4 py-2 text-left text-muted-foreground">Temps</th>
                            <th className="px-4 py-2 text-left text-muted-foreground">Points</th>
                            <th className="px-4 py-2 text-left text-muted-foreground">Statut</th>
                          </tr>
                        </thead>
                        <tbody>
                          {laps.map((lap) => {
                            const checked = selectedLapNumbers.includes(lap.lap_number);
                            return (
                              <tr
                                key={lap.lap_number}
                                className="border-b border-white/5 hover:bg-white/5 cursor-pointer"
                                onClick={() => {
                                  setSelectedLapNumbers((prev) =>
                                    prev.includes(lap.lap_number)
                                      ? prev.filter((n) => n !== lap.lap_number)
                                      : [...prev, lap.lap_number]
                                  );
                                }}
                              >
                                <td className="px-4 py-2" onClick={(e) => e.stopPropagation()}>
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() => {
                                      setSelectedLapNumbers((prev) =>
                                        prev.includes(lap.lap_number)
                                          ? prev.filter((n) => n !== lap.lap_number)
                                          : [...prev, lap.lap_number]
                                      );
                                    }}
                                    className="h-4 w-4 rounded border-white/20 text-[#ff6b35] focus:ring-[#ff6b35]"
                                  />
                                </td>
                                <td className="px-4 py-2 font-medium">{lap.lap_number}</td>
                                <td className="px-4 py-2 font-mono">{formatLapTime(lap.lap_time_seconds)}</td>
                                <td className="px-4 py-2 text-muted-foreground">{lap.points_count}</td>
                                <td className="px-4 py-2">
                                  {lap.is_outlier ? (
                                    <span className="text-amber-500" title="Tour stand / prépa">⚠️ outlier</span>
                                  ) : (
                                    <span className="text-green-500">✅ normal</span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    <div className="flex flex-wrap gap-2 mt-3">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="border-white/10 text-[#ff6b35] hover:bg-[#ff6b35]/10"
                        onClick={() => setSelectedLapNumbers(laps.map((l) => l.lap_number))}
                      >
                        Tout cocher
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="border-white/10"
                        onClick={() => setSelectedLapNumbers([])}
                      >
                        Tout décocher
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="border-white/10"
                        onClick={() =>
                          setSelectedLapNumbers(laps.filter((l) => !l.is_outlier).map((l) => l.lap_number))
                        }
                      >
                        Normaux seulement
                      </Button>
                    </div>
                  </CardContent>
                )}
                {laps && laps.length === 0 && !lapsLoading && (
                  <CardContent className="text-sm text-muted-foreground">
                    Aucun tour détecté — l'analyse portera sur l'ensemble du fichier.
                  </CardContent>
                )}
              </Card>
            )}

            {/* Conditions de piste */}
            {file && (
              <Card className="mt-6 glass-card border-white/10 w-full max-w-2xl mx-auto">
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg">Conditions de piste</CardTitle>
                  <CardDescription>
                    Sélectionne la condition et optionnellement la température
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-0 space-y-4">
                  <div className="flex flex-wrap gap-2">
                    {(
                      [
                        { value: "dry" as const, label: "Sec", icon: "☀️" },
                        { value: "damp" as const, label: "Humide", icon: "🌦️" },
                        { value: "wet" as const, label: "Mouillée", icon: "💧" },
                        { value: "rain" as const, label: "Pluie", icon: "🌧️" },
                      ] as const
                    ).map(({ value, label, icon }) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setTrackCondition(value)}
                        className={`px-4 py-2 rounded-full text-sm font-medium transition-all border-2 ${
                          trackCondition === value
                            ? "bg-[#ff6b35] text-white border-[#ff6b35]"
                            : "border-white/10 bg-white/5 text-muted-foreground hover:bg-white/10"
                        }`}
                      >
                        {icon} {label}
                      </button>
                    ))}
                  </div>
                  <div>
                    <label className="text-sm text-muted-foreground block mb-1">
                      Température piste (°C)
                    </label>
                    <input
                      type="number"
                      placeholder="ex. 28"
                      value={trackTemperature === "" ? "" : trackTemperature}
                      onChange={(e) => {
                        const v = e.target.value;
                        setTrackTemperature(v === "" ? "" : parseFloat(v) || 0);
                      }}
                      className="w-full max-w-[120px] p-2 rounded-lg bg-secondary/50 border border-white/10 text-foreground placeholder:text-muted-foreground"
                    />
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Bouton analyser + avertissement accès */}
            {file && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 flex flex-col items-center gap-4"
              >
                {!canUpload && !isAuthenticated && (
                  <Alert className="bg-primary/10 border-primary/30 w-full max-w-md">
                    <AlertCircle className="h-4 w-4 text-primary" />
                    <AlertTitle>
                      {guestUsed ? "Connexion requise" : "1 analyse gratuite"}
                    </AlertTitle>
                    <AlertDescription className="flex items-center gap-2 flex-wrap">
                      {guestUsed ? (
                        <>
                          Connectez-vous pour continuer.
                          <Button variant="outline" size="sm" onClick={() => navigate("/login")}>
                            Se connecter
                          </Button>
                        </>
                      ) : (
                        <>
                          Testez sans compte — cliquez Essayer puis Analyser.
                          <Button variant="outline" size="sm" onClick={guestUpload}>
                            Essayer
                          </Button>
                        </>
                      )}
                    </AlertDescription>
                  </Alert>
                )}

                <Button
                  variant="hero"
                  size="lg"
                  onClick={handleAnalyze}
                  disabled={isAnalyzing}
                  className="min-w-[200px]"
                >
                  {isAnalyzing ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Analyse en cours…
                    </>
                  ) : (
                    "Analyser le fichier"
                  )}
                </Button>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

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
    </motion.div>
  );
};
