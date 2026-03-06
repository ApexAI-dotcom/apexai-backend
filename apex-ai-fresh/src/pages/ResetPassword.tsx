import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { supabase } from '@/lib/supabase'
import { Layout } from '@/components/layout/Layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Helmet } from 'react-helmet-async'
import { Loader2, AlertCircle, CheckCircle2, Eye, EyeOff } from 'lucide-react'

export default function ResetPassword() {
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [sessionReady, setSessionReady] = useState(false)

  useEffect(() => {
    // 1. Enregistrer le listener EN PREMIER, avant tout
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'PASSWORD_RECOVERY' || (event === 'SIGNED_IN' && session)) {
        setSessionReady(true)
      }
    })

    // 2. Ensuite vérifier si session déjà présente (cas refresh de page)
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) setSessionReady(true)
    })

    // 3. Timeout fallback
    const timeout = setTimeout(() => {
      setSessionReady((prev) => {
        if (!prev) setError('Lien invalide ou expiré. Demande un nouveau lien depuis la page de connexion.')
        return prev
      })
    }, 5000)

    return () => {
      subscription.unsubscribe()
      clearTimeout(timeout)
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (password.length < 8) {
      setError('Le mot de passe doit contenir au moins 8 caractères.')
      return
    }
    if (password !== confirmPassword) {
      setError('Les mots de passe ne correspondent pas.')
      return
    }

    setLoading(true)
    const { error } = await supabase.auth.updateUser({ password })
    setLoading(false)

    if (error) {
      setError('Erreur lors de la modification. Réessaie ou demande un nouveau lien.')
    } else {
      setSuccess(true)
      setTimeout(() => navigate('/dashboard'), 3000)
    }
  }

  return (
    <Layout>
      <Helmet>
        <meta name="robots" content="noindex, nofollow" />
      </Helmet>
      <div className="container mx-auto px-4 py-8 flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md"
        >
          <Card className="glass-card border-white/10">
            <CardHeader className="text-center">
              <CardTitle className="font-display text-2xl font-bold text-foreground">
                Nouveau mot de passe
              </CardTitle>
              <CardDescription className="text-muted-foreground">
                Choisis un nouveau mot de passe pour ton compte APEX AI
              </CardDescription>
            </CardHeader>
            <CardContent>
              {success ? (
                <div className="text-center py-6">
                  <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-4" />
                  <p className="text-foreground font-medium mb-2">Mot de passe modifié !</p>
                  <p className="text-muted-foreground text-sm">
                    Redirection vers ton tableau de bord...
                  </p>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                  {error && (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>
                        {error}{' '}
                        {error.includes('expiré') && (
                          <a href="/login" className="underline text-primary">
                            Retour à la connexion
                          </a>
                        )}
                      </AlertDescription>
                    </Alert>
                  )}

                  <div className="flex flex-col gap-2">
                    <Label htmlFor="password" className="text-foreground text-sm font-medium">
                      Nouveau mot de passe
                    </Label>
                    <div className="relative">
                      <Input
                        id="password"
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="Minimum 8 caractères"
                        className="bg-secondary/50 border-white/10 text-foreground placeholder:text-muted-foreground pr-10"
                        required
                        disabled={!sessionReady || !!error}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  <div className="flex flex-col gap-2">
                    <Label htmlFor="confirmPassword" className="text-foreground text-sm font-medium">
                      Confirmer le mot de passe
                    </Label>
                    <Input
                      id="confirmPassword"
                      type={showPassword ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Répète ton mot de passe"
                      className="bg-secondary/50 border-white/10 text-foreground placeholder:text-muted-foreground"
                      required
                      disabled={!sessionReady || !!error}
                    />
                  </div>

                  <Button
                    type="submit"
                    variant="hero"
                    className="w-full mt-2"
                    disabled={loading || !sessionReady || !!error}
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        Modification...
                      </>
                    ) : !sessionReady && !error ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        Vérification du lien...
                      </>
                    ) : (
                      'Enregistrer le nouveau mot de passe'
                    )}
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </Layout>
  )
}
