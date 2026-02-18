#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Email Templates (HTML)
Templates pour emails Brevo : Bienvenue, Reset, Trial fin, Pro activé
"""

WELCOME_HTML = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Bienvenue Apex AI</title></head>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;">
  <h1 style="color:#10b981;">Bienvenue sur APEX AI !</h1>
  <p>Votre compte <strong>Apex AI {tier}</strong> est activé.</p>
  <p>Connectez-vous pour analyser vos sessions et améliorer vos temps au circuit.</p>
  <a href="{dashboard_url}" style="display:inline-block;background:#10b981;color:white;padding:12px 24px;text-decoration:none;border-radius:8px;">Accéder au tableau de bord</a>
  <p style="color:#6b7280;font-size:12px;margin-top:40px;">© APEX AI - no-reply@apexai.run</p>
</body>
</html>
"""

RESET_HTML = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Réinitialiser mot de passe</title></head>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;">
  <h1 style="color:#10b981;">Réinitialiser votre mot de passe</h1>
  <p>Cliquez sur le lien ci-dessous pour définir un nouveau mot de passe :</p>
  <p><a href="{reset_url}">Réinitialiser mot de passe Apex AI</a></p>
  <p style="color:#6b7280;font-size:12px;">Ce lien expire dans 1 heure.</p>
  <p style="color:#6b7280;font-size:12px;margin-top:40px;">© APEX AI - no-reply@apexai.run</p>
</body>
</html>
"""

PRO_ACTIVATED_HTML = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Pro activé</title></head>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;">
  <h1 style="color:#10b981;">Apex AI Pro activé !</h1>
  <p>Votre abonnement <strong>Pro</strong> est maintenant actif.</p>
  <p>Analyses illimitées, coaching avancé, export PDF — profitez-en !</p>
  <a href="{dashboard_url}" style="display:inline-block;background:#10b981;color:white;padding:12px 24px;text-decoration:none;border-radius:8px;">Accéder au tableau de bord</a>
  <p style="color:#6b7280;font-size:12px;margin-top:40px;">© APEX AI - no-reply@apexai.run</p>
</body>
</html>
"""

TRIAL_ENDING_HTML = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Passez Pro</title></head>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;">
  <h1 style="color:#f59e0b;">Votre essai se termine bientôt</h1>
  <p>Passez Pro pour continuer à analyser vos sessions sans interruption.</p>
  <a href="{pricing_url}" style="display:inline-block;background:#10b981;color:white;padding:12px 24px;text-decoration:none;border-radius:8px;">Passez Pro</a>
  <p style="color:#6b7280;font-size:12px;margin-top:40px;">© APEX AI - no-reply@apexai.run</p>
</body>
</html>
"""
