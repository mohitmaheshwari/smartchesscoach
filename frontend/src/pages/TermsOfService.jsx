/**
 * Terms of Service — Razorpay compliance.
 *
 * Operator:   Maheshwari Innovative IT Services LLP
 * GSTIN:      09ABXFM7842G1ZH
 * Address:    Tulsi Residency, Goverdhan, Mathura, UP – 281502
 * Jurisdiction for disputes: Mathura, Uttar Pradesh
 *
 * NOT a substitute for review by counsel.
 */

import { useNavigate } from "react-router-dom";
import { ChevronLeft } from "lucide-react";

export default function TermsOfService() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-black text-gray-200">
      <div className="max-w-3xl mx-auto px-6 py-12">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-300 mb-8"
        >
          <ChevronLeft className="w-4 h-4" /> Back
        </button>

        <h1 className="text-3xl font-heading mb-2">Terms of Service</h1>
        <p className="text-sm text-gray-500 mb-10">Last updated: 12 May 2026</p>

        <div className="space-y-8 text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">1. About these Terms</h2>
            <p>
              These Terms of Service ("Terms") govern your access to and use of
              ChessGuru, a chess coaching platform available at{" "}
              <a href="https://chessguru.ai" className="text-blue-400 hover:underline">chessguru.ai</a>
              {" "}("Service"), operated by Maheshwari Innovative IT Services LLP,
              a Limited Liability Partnership incorporated in India (GSTIN
              09ABXFM7842G1ZH), with its registered office at Tulsi Residency,
              Goverdhan, Mathura, Uttar Pradesh – 281502 ("we", "us", "our").
              By creating an account or using the Service, you agree to be bound
              by these Terms.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">2. Eligibility</h2>
            <p>
              You must be at least 13 years of age to use the Service. If you are
              under 18, you must use the Service under the supervision of a
              parent or legal guardian who agrees to these Terms on your behalf.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">3. Your account</h2>
            <ul className="list-disc list-inside space-y-2">
              <li>You are responsible for safeguarding your account credentials.</li>
              <li>You must provide accurate and current information when creating an account.</li>
              <li>You may not share your account with another person.</li>
              <li>We may suspend or terminate accounts that violate these Terms.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">4. Subscriptions and billing</h2>
            <p className="mb-3">
              ChessGuru offers a free tier and one or more paid subscription
              tiers ("Pro"). Subscriptions are billed in advance through our
              payment processor, Razorpay. By subscribing, you authorise
              recurring charges until you cancel.
            </p>
            <p>
              Subscription prices are displayed at{" "}
              <a href="/pricing" className="text-blue-400 hover:underline">chessguru.ai/pricing</a>
              {" "}and may change with prior notice. Existing subscribers will be
              notified by email at least 14 days before any price change takes
              effect.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">5. Cancellation and refunds</h2>
            <p>
              You may cancel your subscription at any time from your account
              settings or by contacting us. Refund eligibility is governed by
              our{" "}
              <a href="/refund" className="text-blue-400 hover:underline">Refund Policy</a>.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">6. Acceptable use</h2>
            <p className="mb-3">You agree NOT to use the Service to:</p>
            <ul className="list-disc list-inside space-y-2">
              <li>Violate any law or regulation.</li>
              <li>Reverse engineer, scrape, or attempt to extract source code, models, or training data.</li>
              <li>Resell, sublicense, or commercially exploit the Service without our written consent.</li>
              <li>Upload content that infringes the rights of others.</li>
              <li>Interfere with the Service's operation or other users' access.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">7. Intellectual property</h2>
            <p>
              The Service, including all software, content, designs, logos, and
              coaching content, is the property of Maheshwari Innovative IT Services LLP and is
              protected by intellectual property laws. We grant you a limited,
              non-exclusive, non-transferable licence to use the Service for
              personal, non-commercial chess study. You retain ownership of any
              game data you upload; you grant us a licence to process that data
              to provide the Service to you.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">8. Service availability</h2>
            <p>
              We aim to keep the Service available but do not guarantee
              uninterrupted access. We may modify, suspend, or discontinue
              features at any time, with notice for material changes when
              practicable.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">9. Disclaimers</h2>
            <p>
              The Service is provided "as is" and "as available." We make no
              warranties, express or implied, regarding fitness for a particular
              purpose, accuracy of analysis, or improvement in your chess
              rating. Chess coaching results vary by individual.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">10. Limitation of liability</h2>
            <p>
              To the maximum extent permitted by law, our total liability to you
              for any claim arising from the Service is limited to the amount
              you paid us in the 12 months preceding the claim. We are not
              liable for indirect, incidental, or consequential damages.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">11. Governing law and disputes</h2>
            <p>
              These Terms are governed by the laws of India. Any disputes
              arising out of or in connection with these Terms shall be subject
              to the exclusive jurisdiction of the courts at Mathura, Uttar
              Pradesh, India.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">12. Changes to these Terms</h2>
            <p>
              We may update these Terms from time to time. When we do, we will
              update the "Last updated" date at the top of this page. Continued
              use of the Service after a change constitutes acceptance of the
              updated Terms. For material changes, we will provide reasonable
              notice (e.g., email or in-app banner) before the changes take effect.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">13. Contact</h2>
            <p>
              For questions about these Terms, contact us at{" "}
              <a href="mailto:mohitm@miiscollp.com" className="text-blue-400 hover:underline">
                mohitm@miiscollp.com
              </a>
              {" "}or via our{" "}
              <a href="/contact" className="text-blue-400 hover:underline">Contact page</a>.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
