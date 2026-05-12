/**
 * Refund & Cancellation Policy — Razorpay-required.
 *
 * Stance: all sales are final. No discretionary refunds for change of
 * mind, cancellation mid-period, or unused subscription time. The
 * mandatory-by-law exceptions (duplicate charges, unauthorised
 * payments, processor errors, service non-delivery) are preserved
 * because Indian consumer protection law preserves those rights
 * regardless of merchant policy.
 */

import { useNavigate } from "react-router-dom";
import { ChevronLeft } from "lucide-react";

export default function RefundPolicy() {
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

        <h1 className="text-3xl font-heading mb-2">Refund &amp; Cancellation Policy</h1>
        <p className="text-sm text-gray-500 mb-10">Last updated: 12 May 2026</p>

        <div className="space-y-8 text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">1. Overview</h2>
            <p>
              This Refund &amp; Cancellation Policy describes how subscriptions
              to ChessGuru, operated by Maheshwari Innovative IT Services LLP
              (GSTIN 09ABXFM7842G1ZH), can be cancelled and the limited
              circumstances under which refunds may be issued. It applies to
              all paid plans on{" "}
              <a href="https://chessguru.ai" className="text-blue-400 hover:underline">chessguru.ai</a>.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">2. All sales are final</h2>
            <p className="mb-3">
              ChessGuru is a digital subscription service. Access to coaching
              features, analysis, and content is granted immediately upon
              successful payment. Because the service is delivered digitally
              and consumed from the moment of activation, all payments are
              non-refundable.
            </p>
            <p>
              We do not offer refunds for:
            </p>
            <ul className="list-disc list-inside space-y-2 mt-3">
              <li>Change of mind after a successful purchase.</li>
              <li>Cancellation in the middle of a billing period (monthly or annual).</li>
              <li>Unused time on a subscription after cancellation.</li>
              <li>Partial-month or partial-year periods on either tier.</li>
              <li>Dissatisfaction with the coaching results or analysis output.</li>
              <li>Decisions to stop using the service.</li>
            </ul>
            <p className="mt-3">
              You are encouraged to use the free tier and review our{" "}
              <a href="/pricing" className="text-blue-400 hover:underline">Pricing</a>
              {" "}page before subscribing to a paid plan, so you can confirm
              the Service meets your needs.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">3. Cancellation</h2>
            <p className="mb-3">
              You can cancel your subscription at any time:
            </p>
            <ul className="list-disc list-inside space-y-2">
              <li>Through your account Settings on the website, or</li>
              <li>
                By emailing us at{" "}
                <a href="mailto:mohitm@miiscollp.com" className="text-blue-400 hover:underline">
                  mohitm@miiscollp.com
                </a>{" "}with the subject line "Cancellation Request" and your
                registered email.
              </li>
            </ul>
            <p className="mt-3">
              On cancellation, you continue to have access to your paid plan
              features until the end of the current billing period. No
              recurring charge will be made for the next period. Cancellation
              does NOT generate a refund for the current period.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">4. Exceptions — when a refund is issued</h2>
            <p className="mb-3">
              The following situations are NOT discretionary; we will refund
              affected charges because Indian consumer protection law and
              Razorpay merchant rules require it:
            </p>
            <ul className="list-disc list-inside space-y-2">
              <li>
                <strong className="text-gray-100">Duplicate charges:</strong>{" "}
                if you are charged twice for the same billing period, the
                duplicate charge is refunded in full.
              </li>
              <li>
                <strong className="text-gray-100">Unauthorised charges:</strong>{" "}
                if you can demonstrate a charge was made without your
                authorisation (e.g., your payment method was used by someone
                else without consent), contact us and we will investigate and
                refund as appropriate.
              </li>
              <li>
                <strong className="text-gray-100">Payment processor errors:</strong>{" "}
                if Razorpay or your bank applies a charge that did not result
                in service activation on your ChessGuru account, the charge
                is refunded.
              </li>
              <li>
                <strong className="text-gray-100">Service not delivered:</strong>{" "}
                if your subscription does not activate within 24 hours of a
                successful payment because of an issue on our side, you may
                request a full refund.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">5. How to request a refund under section 4</h2>
            <p className="mb-3">
              Email{" "}
              <a href="mailto:mohitm@miiscollp.com" className="text-blue-400 hover:underline">
                mohitm@miiscollp.com
              </a>{" "}with:
            </p>
            <ul className="list-disc list-inside space-y-2">
              <li>Your registered email address.</li>
              <li>Date and amount of the charge.</li>
              <li>Razorpay payment ID or order ID (visible in your invoice email).</li>
              <li>The exception you are claiming under (duplicate, unauthorised, processor error, non-delivery).</li>
              <li>Any supporting evidence (screenshots, bank statements).</li>
            </ul>
            <p className="mt-3">
              We respond within 3 business days. Approved refunds are
              processed within 7 business days through the original payment
              method via Razorpay. Bank credit timing depends on your card
              issuer (typically 5–10 working days).
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">6. Failed-payment handling</h2>
            <p>
              If a recurring charge fails, we retry up to 3 times over the
              following 7 days. If all retries fail, your subscription is
              downgraded to the free tier. Your paid-tier data remains
              available for 30 days, after which it may be archived.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">7. Disputes</h2>
            <p>
              If a refund decision is disputed, email us at{" "}
              <a href="mailto:mohitm@miiscollp.com" className="text-blue-400 hover:underline">
                mohitm@miiscollp.com
              </a>{" "}and we will review your case within 7 business days. If
              we cannot reach a resolution, you may refer the matter to
              Razorpay's dispute process or applicable consumer protection
              authorities.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">8. Contact</h2>
            <p>
              For any refund or cancellation questions, contact us at{" "}
              <a href="mailto:mohitm@miiscollp.com" className="text-blue-400 hover:underline">
                mohitm@miiscollp.com
              </a>{" "}or through our{" "}
              <a href="/contact" className="text-blue-400 hover:underline">Contact page</a>.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
