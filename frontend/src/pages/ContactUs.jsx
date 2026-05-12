/**
 * Contact Us — Razorpay compliance.
 *
 * Operator: Maheshwari Innovative IT Services LLP (GSTIN 09ABXFM7842G1ZH)
 * Address:  Tulsi Residency, Goverdhan, Mathura, UP – 281502
 * Email:    mohitm@miiscollp.com
 */

import { useNavigate } from "react-router-dom";
import { ChevronLeft, Mail, MapPin, Clock } from "lucide-react";

export default function ContactUs() {
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

        <h1 className="text-3xl font-heading mb-2">Contact Us</h1>
        <p className="text-sm text-gray-500 mb-10">
          We respond to most enquiries within 1 business day.
        </p>

        <div className="space-y-6 text-sm leading-relaxed">
          <div className="rounded-lg border border-white/10 p-6 space-y-5">
            <div className="flex items-start gap-3">
              <Mail className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-gray-100 font-medium">Email</p>
                <a
                  href="mailto:mohitm@miiscollp.com"
                  className="text-blue-400 hover:underline"
                >
                  mohitm@miiscollp.com
                </a>
                <p className="text-xs text-gray-500 mt-1">
                  For general questions, billing, refunds, and feedback.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <MapPin className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-gray-100 font-medium">Registered address</p>
                <p className="text-gray-400">
                  Maheshwari Innovative IT Services LLP<br />
                  Tulsi Residency, Goverdhan<br />
                  Mathura, Uttar Pradesh – 281502<br />
                  India
                </p>
                <p className="text-xs text-gray-500 mt-2">
                  GSTIN: 09ABXFM7842G1ZH
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Clock className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-gray-100 font-medium">Support hours</p>
                <p className="text-gray-400">
                  Monday – Friday, 10:00 – 18:00 IST
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Emails received outside business hours are answered the next
                  working day.
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-white/10 p-6">
            <h2 className="text-gray-100 font-medium mb-3">Common topics</h2>
            <ul className="space-y-2 text-gray-400">
              <li>
                Billing or refunds —{" "}
                <a href="/refund" className="text-blue-400 hover:underline">
                  see Refund Policy
                </a>
              </li>
              <li>
                Privacy or data requests —{" "}
                <a href="/privacy" className="text-blue-400 hover:underline">
                  see Privacy Policy
                </a>
              </li>
              <li>
                Terms of service —{" "}
                <a href="/terms" className="text-blue-400 hover:underline">
                  see Terms of Service
                </a>
              </li>
              <li>
                Pricing —{" "}
                <a href="/pricing" className="text-blue-400 hover:underline">
                  see Pricing
                </a>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
