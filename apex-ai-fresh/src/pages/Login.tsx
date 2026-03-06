import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuth } from '@/hooks/useAuth'
import { Helmet } from 'react-helmet-async'
import { Layout } from '@/components/layout/Layout'
import { PageMeta } from '@/components/seo/PageMeta'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'

type View = 'sign_in' | 'forgot_password'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, loading: authLoading, signInEmail, signUpEmail, resetPasswordForEmail } = useAuth()
  const [view, setView] = useState<View>('sign_in')
  const [isSignUp, setIsSignUp] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [submitLoading, setSubmitLoading] = useState(false)

  useEffect(() => {
    if (!authLoading && user) {
      const from = (location.state as { from?: Location })?.from?.pathname || '/dashboard'
      navigate(from, { replace: true })
    }
  }, [user, authLoading, navigate, location])

  if (authLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
            <p className="text-muted-foreground">Chargement...</p>
          </div>
        </div>
      </Layout>
    )
  }

  if (user) {
    return null
  }

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    setSubmitLoading(true)
    const { error } = isSignUp
      ? await signUpEmail(email, password)
      : await signInEmail(email, password)
    setSubmitLoading(false)
    if (error) {
      setError(error.message)
      return
    }
    const from = (location.state as { from?: Location })?.from?.pathname || '/dashboard'
    navigate(from, { replace: true })
  }

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    if (!email.trim()) {
      setError('Indique ton adresse email.')
      return
    }
    setSubmitLoading(true)
    const { error } = await resetPasswordForEmail(email.trim())
    setSubmitLoading(false)
    if (error) {
      setError(error.message)
      return
    }
    setSuccess('Un lien de réinitialisation a été envoyé à ton adresse email.')
  }

  return (
    <Layout>
      <Helmet>
        <meta name="robots" content="noindex, nofollow" />
      </Helmet>
      <PageMeta
        title="Connexion | ApexAI"
        description="Connectez-vous pour accéder à votre tableau de bord et vos analyses."
        path="/login"
      />
      <div className="container mx-auto px-4 py-8 flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md"
        >
          <Card className="glass-card border-white/10">
            <CardHeader className="text-center">
              <CardTitle className="font-display text-2xl font-bold text-foreground">
                {view === 'sign_in' ? 'Connexion' : 'Mot de passe oublié'}
              </CardTitle>
              <CardDescription className="text-muted-foreground">
                {view === 'sign_in'
                  ? 'Connectez-vous à votre compte APEX AI'
                  : 'Indique ton email pour recevoir un lien de réinitialisation.'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {(error || success) && (
                <Alert
                  variant={error ? 'destructive' : 'default'}
                  className={`mb-4 ${success ? 'bg-green-500/10 border-green-500/50' : ''}`}
                >
                  {error ? (
                    <AlertCircle className="h-4 w-4" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  )}
                  <AlertDescription className={success ? 'text-green-200' : ''}>
                    {error || success}
                  </AlertDescription>
                </Alert>
              )}

              {view === 'sign_in' ? (
                <form onSubmit={handleSignIn} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="email" className="text-foreground text-sm font-medium">
                      Adresse email
                    </Label>
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="Votre adresse email"
                      className="bg-secondary/50 border-white/10 text-foreground placeholder:text-muted-foreground"
                      required
                      disabled={submitLoading}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="password" className="text-foreground text-sm font-medium">
                      Mot de passe
                    </Label>
                    <Input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Votre mot de passe"
                      className="bg-secondary/50 border-white/10 text-foreground placeholder:text-muted-foreground"
                      required={!isSignUp}
                      disabled={submitLoading}
                    />
                  </div>
                  <Button
                    type="submit"
                    variant="default"
                    className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                    disabled={submitLoading}
                  >
                    {submitLoading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        {isSignUp ? 'Inscription…' : 'Connexion…'}
                      </>
                    ) : isSignUp ? (
                      "S'inscrire"
                    ) : (
                      'Se connecter'
                    )}
                  </Button>
                  <div className="flex flex-col gap-2 pt-2 text-center text-sm">
                    <button
                      type="button"
                      onClick={() => { setView('forgot_password'); setError(null); setSuccess(null); }}
                      className="text-primary hover:underline"
                    >
                      Mot de passe oublié ?
                    </button>
                    <button
                      type="button"
                      onClick={() => { setIsSignUp(!isSignUp); setError(null); setSuccess(null); }}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      {isSignUp ? 'Déjà un compte ? Se connecter' : "Pas encore de compte ? S'inscrire"}
                    </button>
                  </div>
                </form>
              ) : (
                <form onSubmit={handleForgotPassword} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="forgot-email" className="text-foreground text-sm font-medium">
                      Adresse email
                    </Label>
                    <Input
                      id="forgot-email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="Votre adresse email"
                      className="bg-secondary/50 border-white/10 text-foreground placeholder:text-muted-foreground"
                      required
                      disabled={submitLoading}
                    />
                  </div>
                  <Button
                    type="submit"
                    variant="default"
                    className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                    disabled={submitLoading}
                  >
                    {submitLoading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        Envoi…
                      </>
                    ) : (
                      'Envoyer le lien de réinitialisation'
                    )}
                  </Button>
                  <div className="pt-2 text-center text-sm">
                    <button
                      type="button"
                      onClick={() => { setView('sign_in'); setError(null); setSuccess(null); }}
                      className="text-primary hover:underline"
                    >
                      Retour à la connexion
                    </button>
                  </div>
                </form>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </Layout>
  )
}
