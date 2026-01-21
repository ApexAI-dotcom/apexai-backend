import { useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, FileText, X, CheckCircle2, AlertCircle, Table } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "sonner";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface AnalysisResult {
  success: boolean;
  score: number;
  status: string;
  analyses: {
    CBV?: string;
    Chroma?: string;
    Trajectoire?: string;
    Vitesse?: string;
  };
  extract: string;
}

interface CSVPreview {
  headers: string[];
  rows: string[][];
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [csvPreview, setCsvPreview] = useState<CSVPreview | null>(null);

  const parseCSVPreview = useCallback((file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const lines = text.split('\n').slice(0, 11); // Premières 10 lignes + header
      
      if (lines.length > 0) {
        const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
        const rows = lines.slice(1, 11).map(line => 
          line.split(',').map(cell => cell.trim().replace(/"/g, ''))
        );
        
        setCsvPreview({ headers, rows });
      }
    };
    reader.readAsText(file);
  }, []);

  const handleFileSelect = useCallback((selectedFile: File) => {
    if (!selectedFile.name.endsWith('.csv')) {
      toast.error("Veuillez sélectionner un fichier CSV MyChron");
      return;
    }

    setFile(selectedFile);
    setError(null);
    setResult(null);
    parseCSVPreview(selectedFile);
  }, [parseCSVPreview]);

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);

      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) {
        handleFileSelect(droppedFile);
      }
    },
    [handleFileSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        handleFileSelect(selectedFile);
      }
    },
    [handleFileSelect]
  );

  const handleUpload = useCallback(async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_URL}/api/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({
          detail: `Erreur HTTP ${response.status}`,
        }));
        throw new Error(errorData.detail || "Erreur lors de l'upload");
      }

      const data = await response.json();
      setResult(data);
      toast.success("Analyse terminée avec succès !");
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Erreur inconnue";
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsUploading(false);
    }
  }, [file]);

  const handleRemoveFile = useCallback(() => {
    setFile(null);
    setCsvPreview(null);
    setResult(null);
    setError(null);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "excellente":
        return "bg-green-500/20 text-green-300 border-green-500/50";
      case "bonne":
        return "bg-blue-500/20 text-blue-300 border-blue-500/50";
      case "moyenne":
        return "bg-purple-500/20 text-purple-300 border-purple-500/50";
      default:
        return "bg-orange-500/20 text-orange-300 border-orange-500/50";
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-950 via-slate-900 to-purple-950 p-4 md:p-8">
      <div className="mx-auto max-w-4xl space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center space-y-2"
        >
          <h1 className="text-5xl md:text-6xl font-bold bg-gradient-to-r from-purple-400 via-pink-400 to-purple-400 bg-clip-text text-transparent">
            ApexAI
          </h1>
          <p className="text-slate-400 text-lg">
            Analyse de télémétrie karting avec IA
          </p>
        </motion.div>

        {/* Upload Zone */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="glass-card border-purple-500/20 backdrop-blur-xl bg-white/5">
            <CardContent className="p-6">
              {!file ? (
                <div
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  className={`
                    border-2 border-dashed rounded-xl p-12 text-center
                    transition-all duration-300 cursor-pointer
                    ${
                      isDragging
                        ? "border-purple-400 bg-purple-500/10 scale-105"
                        : "border-purple-500/30 hover:border-purple-500/50 bg-purple-500/5"
                    }
                  `}
                  onClick={() => document.getElementById("file-upload")?.click()}
                >
                  <input
                    type="file"
                    accept=".csv"
                    onChange={handleFileInput}
                    className="hidden"
                    id="file-upload"
                  />
                  <motion.div
                    animate={{
                      y: [0, -10, 0],
                    }}
                    transition={{
                      duration: 2,
                      repeat: Infinity,
                      ease: "easeInOut",
                    }}
                  >
                    <Upload className="w-16 h-16 md:w-20 md:h-20 text-purple-400/60 mx-auto mb-4" />
                  </motion.div>
                  <p className="text-white/80 text-lg font-medium mb-2">
                    Glissez-déposez votre fichier CSV MyChron ici
                  </p>
                  <p className="text-slate-400 text-sm">
                    ou cliquez pour sélectionner
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-lg bg-purple-500/20 flex items-center justify-center border-2 border-purple-500/30">
                      <FileText className="w-8 h-8 text-purple-400" />
                    </div>
                    <div className="flex-1">
                      <p className="text-white font-medium">{file.name}</p>
                      <p className="text-slate-400 text-sm">
                        {(file.size / 1024).toFixed(2)} KB
                      </p>
                    </div>
                    <button
                      onClick={handleRemoveFile}
                      className="w-8 h-8 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center text-white transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  {/* CSV Preview Table */}
                  {csvPreview && (
                    <div className="glass-card border-purple-500/20 p-4 rounded-lg max-h-64 overflow-auto">
                      <div className="flex items-center gap-2 mb-3">
                        <Table className="w-4 h-4 text-purple-400" />
                        <p className="text-sm text-purple-300 font-medium">Aperçu des données</p>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-purple-500/20">
                              {csvPreview.headers.slice(0, 6).map((header, i) => (
                                <th key={i} className="text-left p-2 text-purple-300 font-medium">
                                  {header.length > 10 ? header.substring(0, 10) + '...' : header}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {csvPreview.rows.slice(0, 5).map((row, i) => (
                              <tr key={i} className="border-b border-purple-500/10">
                                {row.slice(0, 6).map((cell, j) => (
                                  <td key={j} className="p-2 text-slate-300">
                                    {cell.length > 8 ? cell.substring(0, 8) + '...' : cell}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {!isUploading && (
                    <Button
                      onClick={handleUpload}
                      className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white h-12 text-lg"
                    >
                      <Upload className="mr-2 h-5 w-5" />
                      Analyser le CSV MyChron
                    </Button>
                  )}
                </div>
              )}

              {/* Loading */}
              {isUploading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center py-8 space-y-4"
                >
                  <Spinner size="lg" />
                  <p className="text-purple-300 text-lg">Analyse en cours...</p>
                </motion.div>
              )}

              {/* Error */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="flex items-center gap-3 p-4 bg-red-500/20 border border-red-500/50 rounded-lg mt-4"
                  >
                    <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                    <p className="text-red-200 text-sm">{error}</p>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Success */}
              <AnimatePresence>
                {result && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="flex items-center gap-3 p-4 bg-green-500/20 border border-green-500/50 rounded-lg mt-4"
                  >
                    <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />
                    <p className="text-green-200 text-sm">
                      Analyse terminée avec succès !
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>
            </CardContent>
          </Card>
        </motion.div>

        {/* Results Card */}
        <AnimatePresence>
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              transition={{ delay: 0.2 }}
            >
              <Card className="glass-card border-purple-500/20 backdrop-blur-xl bg-white/5">
                <CardContent className="p-8">
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <h2 className="text-2xl font-bold text-white mb-2">
                        Score de Performance
                      </h2>
                      <p className="text-slate-400">Analyse complète</p>
                    </div>
                    <div className="text-right">
                      <div className="text-6xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                        {result.score}%
                      </div>
                    </div>
                  </div>

                  {/* Status Badge */}
                  <div className="flex items-center gap-3 mb-6">
                    <span
                      className={`px-4 py-2 rounded-full border text-sm font-medium ${getStatusColor(
                        result.status
                      )}`}
                    >
                      {result.status.charAt(0).toUpperCase() +
                        result.status.slice(1)}
                    </span>
                    <span className="text-slate-400 text-sm">
                      Extraction: {result.extract}
                    </span>
                  </div>

                  {/* Analyses Cards */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {Object.entries(result.analyses).map(([key, value]) => (
                      <motion.div
                        key={key}
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: 0.3 }}
                        className="glass-card border-purple-500/20 p-4 rounded-lg bg-purple-500/10"
                      >
                        <p className="text-slate-400 text-xs mb-2">{key}</p>
                        <p className="text-white font-semibold text-lg">
                          {value}
                        </p>
                      </motion.div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
