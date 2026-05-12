/**
 * Privacy Policy — Razorpay compliance + general data law.
 *
 * Operator: Maheshwari Innovative IT Services LLP
 * Address:  Tulsi Residency, Goverdhan, Mathura, UP – 285102
 *
 * Covers account info, imported chess games (PGN), engine-analysis
 * metadata, and billing information via Razorpay. India / DPDPA-aware
 * framing. NOT a substitute for review by counsel.
 */

import { useNavigate } from "react-router-dom";
import { ChevronLeft } from "lucide-react";

export default function PrivacyPolicy() {
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

        <h1 className="text-3xl font-heading mb-2">Privacy Policy</h1>
        <p className="text-sm text-gray-500 mb-10">Last updated: 12 May 2026</p>

        <div className="space-y-8 text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">1. Introduction</h2>
            <p>
              This Privacy Policy explains how Maheshwari Innovative IT Services LLP ("we", "us")
              collects, uses, and protects your personal information when you
              use ChessGuru ("Service"). By using the Service, you consent to
              the practices described here.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">2. Information we collect</h2>
            <p className="mb-3">We collect the following types of information:</p>
            <ul className="list-disc list-inside space-y-2">
              <li>
                <strong className="text-gray-100">Account data:</strong> name,
                email address, password (hashed), profile preferences.
              </li>
              <li>
                <strong className="text-gray-100">Chess data:</strong> games
                you import from Chess.com or Lichess (PGNs), analysis results,
                training history, coach memory, and pattern statistics derived
                from your play.
              </li>
              <li>
                <strong className="text-gray-100">Usage data:</strong> pages
                visited, features used, in-app events, IP address, browser
                user agent, device type.
              </li>
              <li>
                <strong className="text-gray-100">Payment data:</strong> when
                you subscribe, our payment processor Razorpay collects card,
                UPI, or wallet details directly. We receive transaction
                metadata (amount, status, order ID) but do NOT store your
                payment instrument.
              </li>
              <li>
                <strong className="text-gray-100">Authentication tokens:</strong>{" "}
                if you sign in via Google or Lichess OAuth, we store an
                identifier from those providers.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">3. How we use your information</h2>
            <ul className="list-disc list-inside space-y-2">
              <li>To provide the coaching Service — analyse your games, generate captions, build training plans.</li>
              <li>To process subscriptions and billing.</li>
              <li>To improve the Service, including detection of common mistake patterns at an aggregate level.</li>
              <li>To communicate with you about your account, security, and product updates.</li>
              <li>To meet legal obligations (tax records, fraud prevention).</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">4. Sharing your information</h2>
            <p className="mb-3">We do NOT sell your personal information. We share it only with:</p>
            <ul className="list-disc list-inside space-y-2">
              <li>
                <strong className="text-gray-100">Service providers:</strong>{" "}
                Razorpay (payments), cloud hosting (MongoDB, hosting provider),
                Stockfish (engine analysis runs on our servers — no third-party
                transmission of your games).
              </li>
              <li>
                <strong className="text-gray-100">External chess platforms:</strong>{" "}
                Chess.com and Lichess only when you authorise game import.
              </li>
              <li>
                <strong className="text-gray-100">Law enforcement:</strong> when
                required by valid legal process.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">5. Data retention</h2>
            <p>
              We retain your account and chess data for as long as your account
              is active. If you delete your account, we delete personal data
              within 30 days, except where retention is required for legal
              purposes (tax records: 8 years for India compliance).
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">6. Cookies and tracking</h2>
            <p>
              We use essential cookies for authentication (session cookies) and
              functional cookies to remember your preferences. We do NOT use
              third-party advertising or cross-site tracking cookies. You can
              clear cookies from your browser at any time; doing so will log
              you out.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">7. Security</h2>
            <p>
              We use industry-standard measures to protect your data:
              encrypted connections (HTTPS), hashed passwords, restricted
              database access, and regular security reviews. No system is
              perfectly secure; we cannot guarantee absolute security but
              will notify affected users of any breach as required by law.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">8. Your rights</h2>
            <p className="mb-3">You have the right to:</p>
            <ul className="list-disc list-inside space-y-2">
              <li>Access the personal information we hold about you.</li>
              <li>Correct inaccurate information.</li>
              <li>Delete your account and associated data.</li>
              <li>Export your data in a portable format.</li>
              <li>Withdraw consent for optional data processing.</li>
            </ul>
            <p className="mt-3">
              To exercise any of these rights, email us at{" "}
              <a href="mailto:bhutramohit@gmail.com" className="text-blue-400 hover:underline">
                bhutramohit@gmail.com
              </a>.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">9. Children's privacy</h2>
            <p>
              The Service is not directed at children under 13. We do not
              knowingly collect data from children under 13. If you believe
              we have inadvertently collected such data, contact us and we
              will delete it.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">10. International data transfer</h2>
            <p>
              Our servers may be located outside India. By using the Service,
              you consent to your data being processed in the countries where
              our service providers operate. We ensure adequate safeguards are
              in place for international transfers.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">11. Changes to this policy</h2>
            <p>
              We may update this Privacy Policy from time to time. We will
              update the "Last updated" date and notify you of material
              changes by email or in-app banner.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-heading text-gray-100 mb-3">12. Grievance officer</h2>
            <p>
              In accordance with Indian IT Rules, the Grievance Officer for
              ChessGuru is:
            </p>
            <p className="mt-3 ml-4">
              Name: Maheshwari Innovative IT Services LLP<br />
              Email:{" "}
              <a href="mailto:bhutramohit@gmail.com" className="text-blue-400 hover:underline">
                bhutramohit@gmail.com
              </a>
              <br />
              We respond to grievances within 15 days.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
