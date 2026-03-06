import { Layout } from "@/components/layout/Layout";
import { PageMeta } from "@/components/seo/PageMeta";
import { motion } from "framer-motion";

export default function Legal() {
  return (
    <Layout>
      <PageMeta
        title="Mentions légales | ApexAI"
        description="Mentions légales et conditions d'utilisation ApexAI."
        path="/legal"
      />
      <div className="container mx-auto px-4 py-12 max-w-3xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="prose prose-invert prose-sm max-w-none"
        >
          <h1 className="text-3xl font-bold text-foreground mb-8">
            Mentions légales
          </h1>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-foreground mb-4">
              Éditeur
            </h2>
            <p className="text-muted-foreground">
              <strong className="text-foreground">Apex AI</strong>
              <br />
              France
              <br />
              Contact :{" "}
              <a
                href="mailto:contact@apexai.run"
                className="text-primary hover:underline"
              >
                contact@apexai.run
              </a>
            </p>
          </section>

          <section className="mb-8" id="hebergeur">
            <h2 className="text-xl font-semibold text-foreground mb-4">
              Hébergeur
            </h2>
            <p className="text-muted-foreground">
              <strong className="text-foreground">Vercel Inc.</strong>
              <br />
              340 S Lemon Ave #4133, Walnut, CA 91789, USA
              <br />
              <a
                href="https://vercel.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                vercel.com
              </a>
            </p>
          </section>

          <section className="mb-8" id="paiements">
            <h2 className="text-xl font-semibold text-foreground mb-4">
              Paiements
            </h2>
            <p className="text-muted-foreground">
              Les paiements sont traités par{" "}
              <strong className="text-foreground">Stripe</strong>, conforme PCI-DSS.
              <br />
              Aucune donnée bancaire n'est stockée sur nos serveurs.
              <br />
              <a
                href="https://stripe.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                stripe.com
              </a>
            </p>
          </section>

          <section className="mb-8" id="cgv">
            <span id="cgu" className="block -mt-20 pt-20" aria-hidden />
            <h2 className="text-xl font-semibold text-foreground mb-4">
              CGV / CGU
            </h2>
            <p className="text-muted-foreground">
              Conditions générales de vente (CGV) et conditions générales d'utilisation (CGU) disponibles sur demande à{" "}
              <a href="mailto:contact@apexai.run" className="text-primary hover:underline">
                contact@apexai.run
              </a>
              .
            </p>
            <p className="text-muted-foreground text-sm mt-2">
              Pour toute demande :{" "}
              <a href="mailto:contact@apexai.run?subject=Demande%20CGV-CGU" className="text-primary hover:underline">
                Demander les CGV/CGU par email
              </a>
            </p>
          </section>

          <section className="mb-8" id="cookies">
            <h2 className="text-xl font-semibold text-foreground mb-4">
              Cookies
            </h2>
            <p className="text-muted-foreground">
              Ce site utilise <strong className="text-foreground">Vercel Analytics</strong> pour mesurer l'audience.
              <br />
              Vous pouvez vous opposer (opt-out) via les paramètres de votre navigateur ou en nous contactant.
            </p>
          </section>

          <section className="mb-8" id="droit">
            <h2 className="text-xl font-semibold text-foreground mb-4">
              Droit applicable
            </h2>
            <p className="text-muted-foreground">
              Droit français. Tribunaux compétents : Paris.
            </p>
          </section>

          <section className="mb-8" id="privacy">
            <h2 className="text-xl font-semibold text-foreground mb-4">
              Confidentialité (RGPD 2026)
            </h2>
            <p className="text-muted-foreground">
              Conformément au RGPD, vous disposez d'un droit d'accès, de rectification, de suppression et de portabilité de vos données personnelles.
              <br />
              Contact :{" "}
              <a href="mailto:contact@apexai.run" className="text-primary hover:underline">
                contact@apexai.run
              </a>
            </p>
          </section>
        </motion.div>
      </div>
    </Layout>
  );
}
