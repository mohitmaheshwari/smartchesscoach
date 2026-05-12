/**
 * Refund & Cancellation Policy — MANDATORY for Razorpay compliance.
 *
 * Placeholders to fill before publishing:
 *   [LEGAL_NAME]          — proprietor or company name
 *   [REFUND_WINDOW_DAYS]  — default 7 (Razorpay-typical)
 *
 * Drafted for a subscription SaaS product with monthly and annual
 * billing through Razorpay. NOT a substitute for review by counsel.
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
              to ChessGuru, operated by [LEGAL_NAME], can be cancelled and
              when refunds are issued. It applies to all paid plans on{" "}
              <a href="https://chessguru.ai" className="text-blue-400 hover:underline">chessguru.ai</a>.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">2. Cancellation</h2>
            <p className="mb-3">You can cancel your subscription at any time:</p>
            <ul className="list-disc list-inside space-y-2">
              <li>Through your account Settings on the website, or</li>
              <li>By emailing us at{" "}
                <a href="mailto:bhutramohit@gmail.com" className="text-blue-400 hover:underline">
                  bhutramohit@gmail.com
                </a>{" "}with the subject line "Cancellation Request" and your registered email.
              </li>
            </ul>
            <p className="mt-3">
              After cancellation, you will continue to have access to your paid
              plan features until the end of your current billing period.
              Recurring charges will stop from the next billing cycle.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">3. Refund eligibility</h2>
            <p className="mb-3">
              We offer refunds under the following conditions:
            </p>
            <ul className="list-disc list-inside space-y-2">
              <li>
                <strong className="text-gray-100">First-time subscribers:</strong>{" "}
                a full refund is available within [REFUND_WINDOW_DAYS] days of
                your first paid subscription, provided you have not used the
                Pro features extensively (more than 25 analysed games or 10
                Play-with-Coach sessions).
              </li>
              <li>
                <strong className="text-gray-100">Service failure:</strong> if
                the Service is unavailable for more than 72 consecutive hours
                due to our fault, you may request a pro-rated refund for the
                downtime.
              </li>
              <li>
                <strong className="text-gray-100">Duplicate charges:</strong>{" "}
                if you are charged twice for the same billing period, the
                duplicate charge will be refunded in full.
              </li>
              <li>
                <strong className="text-gray-100">Unauthorised charges:</strong>{" "}
                if you can demonstrate a charge was made without your authorisation, contact us and we will investigate and refund as
                appropriate.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">4. Non-refundable cases</h2>
            <ul className="list-disc list-inside space-y-2">
              <li>
                Renewals of an existing subscription after the initial
                [REFUND_WINDOW_DAYS]-day window has passed.
              </li>
              <li>
                Annual plans after extensive use (defined as &gt;25 analysed
                games or &gt;10 Play-with-Coach sessions).
              </li>
              <li>
                Partial-month refunds when the user has used the Service
                during the billing period.
              </li>
              <li>
                Refund requests made more than 90 days after the original
                charge.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">5. How to request a refund</h2>
            <p className="mb-3">Email{" "}
              <a href="mailto:bhutramohit@gmail.com" className="text-blue-400 hover:underline">
                bhutramohit@gmail.com
              </a>{" "}with:
            </p>
            <ul className="list-disc list-inside space-y-2">
              <li>Your registered email address.</li>
              <li>Date and amount of the charge.</li>
              <li>Razorpay payment ID or order ID (visible in your invoice email).</li>
              <li>Reason for the refund request.</li>
            </ul>
            <p className="mt-3">
              We will respond within 3 business days. Approved refunds are
              processed within 7 business days through the original payment
              method via Razorpay. Bank credit timing depends on your
              card-issuing bank (typically 5–10 working days).
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">6. Failed-payment handling</h2>
            <p>
              If a recurring charge fails, we will retry up to 3 times over
              the following 7 days. If all retries fail, your subscription
              will be downgraded to the free tier, and your paid-tier data
              will remain available for 30 days, after which it may be
              archived.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">7. Disputes</h2>
            <p>
              If a refund decision is disputed, please email us at{" "}
              <a href="mailto:bhutramohit@gmail.com" className="text-blue-400 hover:underline">
                bhutramohit@gmail.com
              </a>{" "}and we will review your case within 7 business days. If
              we cannot reach a resolution, refer to Razorpay's dispute
              process or applicable consumer protection regulations.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">8. Contact</h2>
            <p>
              For any refund or cancellation questions, contact us at{" "}
              <a href="mailto:bhutramohit@gmail.com" className="text-blue-400 hover:underline">
                bhutramohit@gmail.com
              </a>{" "}or through our{" "}
              <a href="/contact" className="text-blue-400 hover:underline">Contact page</a>.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
