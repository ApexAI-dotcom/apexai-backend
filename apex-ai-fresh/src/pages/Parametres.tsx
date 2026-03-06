import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Settings, Save, Sun, Moon, User, ImagePlus, Loader2 } from "lucide-react";
import { Helmet } from "react-helmet-async";
import { Layout } from "@/components/layout/Layout";
import { PageMeta } from "@/components/seo/PageMeta";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useAuth } from "@/hooks/useAuth";
import { supabase } from "@/lib/supabase";

const STORAGE_KEY = "apexai_settings";

interface ApexSettings {
  nomPilote: string;
  unites: "kmh" | "mph";
  theme: "dark" | "light";
  notifications: boolean;
}

const defaultSettings: ApexSettings = {
  nomPilote: "",
  unites: "kmh",
  theme: "dark",
  notifications: true,
};

function applyTheme(theme: "dark" | "light") {
  const html = document.documentElement;
  if (theme === "light") {
    html.classList.add("light");
  } else {
    html.classList.remove("light");
  }
}

export default function Parametres() {
  const { user } = useAuth();
  const [settings, setSettings] = useState<ApexSettings>(defaultSettings);
  const [displayName, setDisplayName] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Charger le profil depuis la table profiles (full_name, avatar_url)
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      const { data, error } = await supabase
        .from("profiles")
        .select("*")
        .eq("id", user.id)
        .single();
      if (cancelled) return;
      if (!error && data) {
        if (data.full_name != null) setDisplayName(String(data.full_name));
        if (data.avatar_url != null) setAvatarUrl(String(data.avatar_url));
      } else {
        // Fallback user_metadata si pas encore de ligne profiles
        const name =
          (user.user_metadata?.full_name as string) ||
          user.email?.split("@")[0] ||
          "";
        const avatar = (user.user_metadata?.avatar_url as string) || "";
        setDisplayName(name);
        setAvatarUrl(avatar);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.id]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved) as Partial<ApexSettings & { circuitFavori?: string }>;
        const { circuitFavori: _removed, ...rest } = parsed;
        const next = { ...defaultSettings, ...rest };
        setSettings(next);
        applyTheme(next.theme);
      } else {
        applyTheme("dark");
      }
    } catch {
      applyTheme("dark");
    }
  }, []);

  const saveSettings = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    applyTheme(settings.theme);
    (window as unknown as { apexaiUnits?: string }).apexaiUnits = settings.unites;
    toast.success("Paramètres appliqués !");
  };

  const saveProfile = async () => {
    if (!user) return;
    setSavingProfile(true);
    const full_name = displayName.trim() || null;
    const avatar_url = avatarUrl.trim() || null;
    try {
      const { error: profileError } = await supabase
        .from("profiles")
        .update({
          full_name,
          avatar_url,
          updated_at: new Date().toISOString(),
        })
        .eq("id", user.id);
      if (profileError) throw profileError;
      // Garder auth user_metadata en sync pour l'affichage ailleurs
      const { error: authError } = await supabase.auth.updateUser({
        data: { full_name, avatar_url },
      });
      if (authError) throw authError;
      const nomPilote = full_name || settings.nomPilote;
      if (nomPilote) {
        const next = { ...settings, nomPilote };
        setSettings(next);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      }
      toast.success("Profil mis à jour.");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erreur lors de la mise à jour.";
      toast.error(msg);
    } finally {
      setSavingProfile(false);
    }
  };

  const handleAvatarFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !user) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Choisissez une image (JPG, PNG, WebP).");
      return;
    }
    setUploadingAvatar(true);
    try {
      const ext = file.name.split(".").pop() || "jpg";
      const path = `${user.id}.${ext}`;
      const { error: uploadError } = await supabase.storage
        .from("avatars")
        .upload(path, file, { upsert: true, contentType: file.type });
      if (uploadError) {
        const baseUrl = import.meta.env.VITE_SUPABASE_URL?.replace(/\/$/, "") || "";
        toast.info("Stockage non configuré : utilisez une URL d'avatar ci-dessous.");
        setUploadingAvatar(false);
        return;
      }
      const { data: urlData } = supabase.storage.from("avatars").getPublicUrl(path);
      setAvatarUrl(urlData.publicUrl);
      toast.success("Photo téléversée.");
    } catch {
      toast.error("Échec du téléversement.");
    } finally {
      setUploadingAvatar(false);
      e.target.value = "";
    }
  };

  return (
    <Layout>
      <Helmet>
        <meta name="robots" content="noindex, nofollow" />
      </Helmet>
      <PageMeta
        title="Paramètres | ApexAI"
        description="Personnalise ton expérience ApexAI"
        path="/parametres"
      />
      <div className="container mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-2xl mx-auto space-y-8"
        >
          <div className="flex items-center gap-4">
            <Settings className="w-8 h-8 text-primary" />
            <h1 className="font-display text-3xl font-bold text-foreground">
              Paramètres
            </h1>
          </div>

          {/* Profil : photo + pseudo (Supabase) */}
          {user && (
            <div className="glass-card p-6 rounded-xl space-y-6">
              <div className="flex items-center gap-3">
                <User className="w-6 h-6 text-primary" />
                <Label className="text-lg font-semibold">Profil (compte connecté)</Label>
              </div>
              <div className="flex flex-col sm:flex-row gap-6">
                <div className="flex flex-col items-center gap-3">
                  <Avatar className="w-24 h-24 rounded-2xl border-2 border-primary/20">
                    {avatarUrl ? (
                      <AvatarImage src={avatarUrl} alt="Avatar" className="object-cover" />
                    ) : null}
                    <AvatarFallback className="rounded-2xl gradient-primary text-2xl text-primary-foreground">
                      {(displayName || user.email || "U").slice(0, 2).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleAvatarFile}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadingAvatar}
                    className="gap-2"
                  >
                    {uploadingAvatar ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ImagePlus className="w-4 h-4" />
                    )}
                    {uploadingAvatar ? "Téléversement…" : "Changer la photo"}
                  </Button>
                </div>
                <div className="flex-1 space-y-4">
                  <div>
                    <Label className="text-sm font-medium text-muted-foreground">Pseudo / Nom d'affichage</Label>
                    <Input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder={user.email?.split("@")[0] || "moreauy58"}
                      className="mt-2 w-full p-4 border-2 rounded-xl focus-visible:ring-4 focus-visible:ring-primary/20"
                    />
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-muted-foreground">Ou URL de la photo de profil</Label>
                    <Input
                      type="url"
                      value={avatarUrl}
                      onChange={(e) => setAvatarUrl(e.target.value)}
                      placeholder="https://..."
                      className="mt-2 w-full p-4 border-2 rounded-xl focus-visible:ring-4 focus-visible:ring-primary/20"
                    />
                  </div>
                  <Button
                    onClick={saveProfile}
                    disabled={savingProfile}
                    className="gap-2"
                  >
                    {savingProfile ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    Enregistrer le profil
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Nom Pilote (local, pour "Bonjour X" sur Dashboard/Profil) */}
          <div className="glass-card p-6 rounded-xl">
            <Label className="text-lg font-semibold mb-4 block">
              Nom du pilote
            </Label>
            <Input
              type="text"
              value={settings.nomPilote}
              onChange={(e) =>
                setSettings({ ...settings, nomPilote: e.target.value })
              }
              placeholder="Yann Moreau"
              className="w-full p-4 border-2 rounded-xl focus-visible:ring-4 focus-visible:ring-primary/20"
            />
          </div>

          {/* Unités + Thème */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Unités */}
            <div className="glass-card p-6 rounded-xl">
              <Label className="text-lg font-semibold mb-6 block">
                Unités vitesse
              </Label>
              <div className="space-y-3">
                <label className="flex items-center p-3 rounded-lg hover:bg-secondary/50 cursor-pointer">
                  <input
                    type="radio"
                    name="unites"
                    value="kmh"
                    checked={settings.unites === "kmh"}
                    onChange={(e) =>
                      setSettings({ ...settings, unites: e.target.value as "kmh" })
                    }
                    className="mr-3 w-5 h-5 text-primary"
                  />
                  <span className="text-sm">km/h</span>
                </label>
                <label className="flex items-center p-3 rounded-lg hover:bg-secondary/50 cursor-pointer">
                  <input
                    type="radio"
                    name="unites"
                    value="mph"
                    checked={settings.unites === "mph"}
                    onChange={(e) =>
                      setSettings({ ...settings, unites: e.target.value as "mph" })
                    }
                    className="mr-3 w-5 h-5 text-primary"
                  />
                  <span className="text-sm">mph</span>
                </label>
              </div>
            </div>

            {/* Thème - Fonctionnel */}
            <div className="glass-card p-6 rounded-xl">
              <Label className="text-lg font-semibold mb-6 block">Thème</Label>
              <div className="space-y-3">
                <button
                  type="button"
                  onClick={() => setSettings({ ...settings, theme: "light" })}
                  className={`flex items-center p-3 w-full rounded-lg hover:bg-secondary/50 transition-all border-2 ${
                    settings.theme === "light"
                      ? "border-primary ring-2 ring-primary/20 bg-primary/5"
                      : "border-transparent"
                  }`}
                >
                  <Sun className="w-5 h-5 mr-3 text-yellow-500" />
                  <span className="text-sm font-medium">Clair</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSettings({ ...settings, theme: "dark" })}
                  className={`flex items-center p-3 w-full rounded-lg hover:bg-secondary/50 transition-all border-2 ${
                    settings.theme === "dark"
                      ? "border-primary ring-2 ring-primary/20 bg-primary/5"
                      : "border-transparent"
                  }`}
                >
                  <Moon className="w-5 h-5 mr-3 text-muted-foreground" />
                  <span className="text-sm font-medium">Sombre</span>
                </button>
              </div>
            </div>
          </div>

          {/* Notifications */}
          <div className="glass-card p-6 rounded-xl">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.notifications}
                onChange={(e) =>
                  setSettings({ ...settings, notifications: e.target.checked })
                }
                className="h-4 w-4 rounded border-input text-primary"
              />
              <span className="text-sm font-medium">
                Notifications analyses terminées
              </span>
            </label>
          </div>

          <Button
            onClick={saveSettings}
            className="w-full gradient-primary text-primary-foreground py-6 text-lg font-bold shadow-xl hover:shadow-2xl hover:-translate-y-0.5 transition-all duration-300 flex items-center justify-center gap-3"
          >
            <Save className="w-5 h-5" />
            Sauvegarder & Appliquer
          </Button>
        </motion.div>
      </div>
    </Layout>
  );
}
