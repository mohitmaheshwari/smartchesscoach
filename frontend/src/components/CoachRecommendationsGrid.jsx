/**
 * CoachRecommendationsGrid
 *
 * Shows:
 * 1. Coach's top recommendation (data-backed)
 * 2. All available training plans as choosable boxes
 * 3. Wires acceptance to start training
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, TrendingUp, Target, Zap } from "lucide-react";
import { API } from "@/App";

export default function CoachRecommendationsGrid() {
  const navigate = useNavigate();
  const [recommendations, setRecommendations] = useState(null);
  const [activePlans, setActivePlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [accepting, setAccepting] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch recommendations with accuracy data
        const recRes = await fetch(
          `${API}/coaching/recommendations-with-accuracy`,
          { credentials: "include" }
        );
        if (!recRes.ok) throw new Error("Failed to fetch recommendations");
        const recData = await recRes.json();
        setRecommendations(recData.recommendations || []);

        // Fetch active plans to show which are already started
        const presRes = await fetch(
          `${API}/coaching/current-prescriptions`,
          { credentials: "include" }
        );
        if (presRes.ok) {
          const presData = await presRes.json();
          const active = (presData.prescriptions || [])
            .filter(p => p.status === "active")
            .map(p => p.plan_id);
          setActivePlans(active);
        }
      } catch (err) {
        console.error("Error fetching data:", err);
        setError("Failed to load training plans");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
      </div>
    );
  }

  if (error || !recommendations || recommendations.length === 0) {
    return (
      <div className="p-6 rounded-lg bg-amber-50 border border-amber-200">
        <p className="text-amber-900">{error || "No recommendations available"}</p>
      </div>
    );
  }

  const topRecommendation = recommendations[0];
  const otherPlans = recommendations.slice(1);

  const handleStartPlan = async (planId, planName, prescriptionId) => {
    setAccepting(planId);
    try {
      // Activate the prescription
      if (!prescriptionId) {
        throw new Error("No prescription ID found for this plan");
      }

      const acceptRes = await fetch(
        `${API}/coaching/accept-prescription`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            prescription_id: prescriptionId,
            plan_id: planId,
            start_immediately: true
          })
        }
      );

      if (!acceptRes.ok) {
        const errData = await acceptRes.json();
        throw new Error(errData.detail || "Failed to activate prescription");
      }

      // Navigate to training page
      navigate(`/training/prescribed?plan=${planId}`);
    } catch (err) {
      console.error("Error starting plan:", err);
      setError(`Failed to start plan: ${err.message}`);
    } finally {
      setAccepting(null);
    }
  };

  return (
    <div className="space-y-8">
      {/* ─── COACH'S TOP RECOMMENDATION ─── */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-blue-600" />
          <h2 className="text-[14px] font-semibold uppercase tracking-wide text-gray-700">
            Coach's Top Recommendation
          </h2>
        </div>

        <div className="bg-gradient-to-br from-blue-50 to-blue-100/50 border-2 border-blue-300 rounded-lg p-6 space-y-4">
          <div className="space-y-2">
            <h3 className="text-[18px] font-semibold text-blue-900">
              {topRecommendation.plan_name}
            </h3>
            <p className="text-[13px] text-blue-700">
              Focus: <span className="font-medium">{topRecommendation.gap.replace(/_/g, " ")}</span>
            </p>
          </div>

          {/* Evidence */}
          <div className="grid grid-cols-3 gap-4 py-4 border-t border-b border-blue-200">
            <div>
              <p className="text-[11px] font-semibold text-blue-600 uppercase">Mistakes Found</p>
              <p className="text-[16px] font-bold text-blue-900">{topRecommendation.mistake_count}</p>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-blue-600 uppercase">Confidence</p>
              <p className="text-[16px] font-bold text-blue-900">{topRecommendation.confidence_pct}%</p>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-blue-600 uppercase">Recent</p>
              <p className="text-[16px] font-bold text-blue-900">
                {topRecommendation.last_mistake_days_ago ? `${topRecommendation.last_mistake_days_ago}d ago` : "Today"}
              </p>
            </div>
          </div>

          {/* Rating Improvement */}
          <div className="bg-white rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-600" />
              <p className="text-[12px] font-semibold text-gray-700">ESTIMATED RATING GAIN</p>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="text-center">
                <p className="text-[11px] text-gray-600">Conservative (70%)</p>
                <p className="text-[18px] font-bold text-gray-900">
                  +{topRecommendation.rating_improvement.conservative.elo_gain}
                </p>
              </div>
              <div className="text-center border-l border-r border-gray-200">
                <p className="text-[11px] text-gray-600 font-medium">Realistic (85%)</p>
                <p className="text-[18px] font-bold text-emerald-600">
                  +{topRecommendation.rating_improvement.realistic.elo_gain}
                </p>
              </div>
              <div className="text-center">
                <p className="text-[11px] text-gray-600">Optimistic (95%)</p>
                <p className="text-[18px] font-bold text-gray-900">
                  +{topRecommendation.rating_improvement.optimistic.elo_gain}
                </p>
              </div>
            </div>
          </div>

          {/* CTA */}
          <button
            onClick={() => handleStartPlan(topRecommendation.plan_id, topRecommendation.plan_name, topRecommendation.prescription_id)}
            disabled={accepting === topRecommendation.plan_id || !topRecommendation.prescription_id}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {accepting === topRecommendation.plan_id ? "Starting..." : "Start This Training Plan"}
          </button>
        </div>
      </div>

      {/* ─── ALL AVAILABLE PLANS ─── */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-amber-600" />
          <h2 className="text-[14px] font-semibold uppercase tracking-wide text-gray-700">
            Or Choose Another Plan
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {otherPlans.map((plan) => {
            const isActive = activePlans.includes(plan.plan_id);
            return (
              <div
                key={plan.plan_id}
                className={`p-5 rounded-lg border-2 transition-all ${
                  isActive
                    ? "border-emerald-300 bg-emerald-50"
                    : "border-gray-200 bg-white hover:border-gray-300"
                }`}
              >
                <div className="space-y-3">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <h3 className="font-semibold text-gray-900">{plan.plan_name}</h3>
                      {isActive && (
                        <span className="text-[10px] px-2 py-1 bg-emerald-200 text-emerald-800 rounded font-semibold">
                          ACTIVE
                        </span>
                      )}
                    </div>
                    <p className="text-[12px] text-gray-600">
                      {plan.mistake_count} mistakes · {plan.confidence_pct}% confidence
                    </p>
                  </div>

                  {/* Elo Gain */}
                  <div className="py-3 bg-gray-50 rounded px-3">
                    <p className="text-[11px] font-semibold text-gray-600 mb-1">Estimated Gain</p>
                    <p className="text-[16px] font-bold text-gray-900">
                      +{plan.rating_improvement.realistic.elo_gain} elo
                    </p>
                    <p className="text-[10px] text-gray-500 mt-1">
                      (Realistic: 85% improvement)
                    </p>
                  </div>

                  {/* Button */}
                  <button
                    onClick={() => handleStartPlan(plan.plan_id, plan.plan_name, plan.prescription_id)}
                    disabled={accepting === plan.plan_id || isActive || !plan.prescription_id}
                    className={`w-full py-2 rounded font-medium text-[13px] transition-colors ${
                      isActive
                        ? "bg-emerald-100 text-emerald-700 cursor-default"
                        : "bg-gray-100 hover:bg-gray-200 text-gray-900"
                    }`}
                  >
                    {accepting === plan.plan_id
                      ? "Starting..."
                      : isActive
                      ? "Already Training"
                      : "Start This Plan"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
