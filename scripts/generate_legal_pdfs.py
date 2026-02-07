#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Génère CGV et CGU PDF pour Apex AI."""

import os
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    print("Install: pip install reportlab")
    raise

OUTPUT_DIR = Path(__file__).parent.parent / "apex-ai-fresh" / "public" / "docs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Localisation France
SOCIETE = "Apex AI SARL"
VILLE = "Paris"
ADRESSE = "France (SIRET en cours)"
DROIT = f"France - Tribunaux de {VILLE}"


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="LegalTitle", parent=s["Title"], fontSize=18, spaceAfter=12))
    s.add(ParagraphStyle(name="LegalHeading", parent=s["Heading2"], fontSize=14, spaceAfter=8))
    s.add(ParagraphStyle(name="LegalBody", parent=s["Normal"], fontSize=10, spaceAfter=6))
    return s


def build_cgv(path: Path):
    """CGV Apex AI - Conditions Générales de Vente."""
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=2*cm, leftMargin=2*cm)
    styles = _styles()
    story = []

    story.append(Paragraph("CONDITIONS GÉNÉRALES DE VENTE", styles["LegalTitle"]))
    story.append(Paragraph(f"{SOCIETE}, {VILLE} France &ndash; 2026", styles["LegalBody"]))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("<b>Article 1 &ndash; Objet</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        "Les présentes conditions régissent les ventes d'abonnements et de services proposés par Apex AI SAS "
        f"(ci-après « le Prestataire »), {ADRESSE}, pour le produit Apex AI Race Coach, "
        "application SaaS d'analyse de données karting.",
        styles["LegalBody"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("<b>Article 2 &ndash; Produits et tarifs</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        "• Abonnement mensuel : 29,99 € HT/mois<br/>"
        "• Packs NFC : 19 € HT l'unité<br/>"
        "Les prix sont indiqués en euros HT. TVA applicable selon la législation.",
        styles["LegalBody"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("<b>Article 3 &ndash; Paiement</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        "Les paiements sont traités par Stripe, conforme PCI-DSS. Aucune donnée bancaire n'est stockée "
        "sur nos serveurs. Le client autorise les prélèvements récurrents pour les abonnements.",
        styles["LegalBody"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("<b>Article 4 &ndash; Résiliation</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        "Résiliation en 1 clic depuis le tableau de bord ou le portail client Stripe. L'accès reste actif "
        "jusqu'à la fin de la période payée. Aucun frais de résiliation.",
        styles["LegalBody"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("<b>Article 5 &ndash; Remboursement</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        "Délai de rétractation de 14 jours à compter de la souscription, conformément à la directive "
        "consommateurs. Demande par email à contact@apexai.run.",
        styles["LegalBody"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("<b>Article 6 &ndash; Données personnelles (RGPD)</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        "Conformément au RGPD 2026, les données personnelles font l'objet d'un traitement strict. "
        f"Responsable du traitement : {SOCIETE}. Droits : accès, rectification, effacement, portabilité, "
        "opposition. Contact : contact@apexai.run.",
        styles["LegalBody"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("<b>Article 7 &ndash; Contact</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        f"{SOCIETE}, {VILLE} France<br/>"
        f"{ADRESSE}<br/>"
        "Email : contact@apexai.run",
        styles["LegalBody"]))

    doc.build(story)
    print(f"CGV généré : {path}")


def build_cgu(path: Path):
    """CGU Apex AI - Conditions Générales d'Utilisation."""
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=2*cm, leftMargin=2*cm)
    styles = _styles()
    story = []

    story.append(Paragraph("CONDITIONS GÉNÉRALES D'UTILISATION", styles["LegalTitle"]))
    story.append(Paragraph(f"{SOCIETE}, {VILLE} France &ndash; 2026", styles["LegalBody"]))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("<b>Article 1 &ndash; Objet</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        "Les présentes CGU régissent l'utilisation du service Apex AI Race Coach, application SaaS "
        "d'analyse de données GPS pour le karting.",
        styles["LegalBody"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("<b>Article 2 &ndash; Usage des données</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        "Le service traite des données personnelles incluant des coordonnées GPS. Ces données sont "
        "utilisées uniquement pour fournir l'analyse et ne sont pas partagées avec des tiers, sauf "
        "obligation légale.",
        styles["LegalBody"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("<b>Article 3 &ndash; Interdictions</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        "Il est strictement interdit de : reverse engineering, décompilation, modification du code, "
        "utilisation abusive des API, extraction de données à des fins commerciales non autorisées.",
        styles["LegalBody"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("<b>Article 4 &ndash; Responsabilité limitée</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        f"{SOCIETE} ne saurait être tenue responsable des dommages indirects, pertes de données ou "
        "décisions prises sur la base des analyses. La responsabilité est limitée au montant des "
        "sommes effectivement versées sur les 12 derniers mois.",
        styles["LegalBody"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("<b>Article 5 &ndash; Mises à jour</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        "Le service est mis à jour automatiquement. Les utilisateurs sont informés des changements "
        "majeurs par email ou notification in-app. La poursuite de l'utilisation vaut acceptation.",
        styles["LegalBody"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("<b>Article 6 &ndash; Droit applicable</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        "Le droit italien est applicable. En cas de litige, les tribunaux de Genova seront seuls compétents.",
        styles["LegalBody"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("<b>Article 7 &ndash; Contact</b>", styles["LegalHeading"]))
    story.append(Paragraph(
        f"{SOCIETE}, {VILLE} France<br/>"
        f"{ADRESSE}<br/>"
        "Email : contact@apexai.run",
        styles["LegalBody"]))

    doc.build(story)
    print(f"CGU généré : {path}")


if __name__ == "__main__":
    build_cgv(OUTPUT_DIR / "cgv.pdf")
    build_cgu(OUTPUT_DIR / "cgu.pdf")
    print("OK - PDFs créés dans public/docs/")
