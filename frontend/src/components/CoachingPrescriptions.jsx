import React, { useState, useEffect } from 'react'
import PrescriptionCard from './PrescriptionCard'
import NextRecommendation from './NextRecommendation'

export default function CoachingPrescriptions() {
  const [currentPrescriptions, setCurrentPrescriptions] = useState([])
  const [nextRecommendation, setNextRecommendation] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchPrescriptions = async () => {
      try {
        setLoading(true)
        const token = localStorage.getItem('authToken')
        const headers = token ? { Authorization: `Bearer ${token}` } : {}

        const [current, next] = await Promise.all([
          fetch(
            `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'}/api/coaching/current-prescriptions`,
            { headers }
          ).then(r => r.json()),
          fetch(
            `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'}/api/coaching/next-prescription`,
            { headers }
          ).then(r => r.json())
        ])

        setCurrentPrescriptions(current.prescriptions || [])
        setNextRecommendation(next.recommendation || null)
      } catch (err) {
        setError(err.message)
        console.error('Failed to load prescriptions:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchPrescriptions()
  }, [])

  if (loading) {
    return <div className="p-4">Loading training plans...</div>
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
        <p className="text-red-700">Failed to load coaching plans: {error}</p>
      </div>
    )
  }

  const primaryPlan = currentPrescriptions.find(p => p.priority_order === 1)
  const secondaryPlans = currentPrescriptions.filter(p => p.priority_order > 1)

  return (
    <div className="space-y-6 p-4">
      {primaryPlan ? (
        <div>
          <h2 className="text-lg font-semibold mb-3">Coach Recommendation</h2>
          <PrescriptionCard prescription={primaryPlan} isPrimary={true} />
        </div>
      ) : nextRecommendation ? (
        <div>
          <h2 className="text-lg font-semibold mb-3">Coach Recommendation</h2>
          <NextRecommendation recommendation={nextRecommendation} />
        </div>
      ) : (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-blue-700">No active training plans. Keep playing and improving!</p>
        </div>
      )}

      {secondaryPlans.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Also Training On</h2>
          <div className="space-y-3">
            {secondaryPlans.map(plan => (
              <PrescriptionCard
                key={plan.prescription_id}
                prescription={plan}
                isPrimary={false}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
