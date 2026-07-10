import React, { useState } from 'react'

export default function NextRecommendation({ recommendation }) {
  const [accepting, setAccepting] = useState(false)

  const handleAccept = async () => {
    try {
      setAccepting(true)
      const token = localStorage.getItem('authToken')
      await fetch(
        `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'}/api/coaching/accept-prescription`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token && { Authorization: `Bearer ${token}` })
          },
          body: JSON.stringify({
            plan_id: recommendation.recommended_plan_id
          })
        }
      )
      window.location.reload()
    } catch (err) {
      console.error('Failed to accept recommendation:', err)
    } finally {
      setAccepting(false)
    }
  }

  const getSeverityColor = (severity) => {
    const colors = {
      'high': 'text-red-600 bg-red-50',
      'medium': 'text-yellow-600 bg-yellow-50',
      'low': 'text-green-600 bg-green-50'
    }
    return colors[severity] || 'text-gray-600 bg-gray-50'
  }

  return (
    <div className="border border-blue-300 bg-blue-50 rounded-lg p-6">
      <div className="mb-4">
        <h3 className="text-xl font-bold text-gray-800 mb-2">{recommendation.plan_name}</h3>
        <p className="text-gray-600 mb-4">{recommendation.description}</p>
      </div>

      <div className="bg-white rounded-lg p-4 mb-4 border border-blue-100">
        <h4 className="font-semibold mb-2">Why this training plan?</h4>
        <p className="text-gray-700 text-sm mb-3">{recommendation.reasoning}</p>

        <div className="grid grid-cols-3 gap-3 text-sm">
          <div>
            <span className="text-gray-600">Occurrences</span>
            <p className="font-semibold text-lg">{recommendation.occurrence_count}</p>
          </div>
          <div>
            <span className="text-gray-600">Trend</span>
            <p className={`font-semibold ${recommendation.trend === 'improving' ? 'text-green-600' : 'text-red-600'}`}>
              {recommendation.trend}
            </p>
          </div>
          <div>
            <span className="text-gray-600">Severity</span>
            <span className={`inline-block px-2 py-1 rounded text-xs font-semibold mt-1 ${getSeverityColor(recommendation.issue_severity)}`}>
              {recommendation.issue_severity}
            </span>
          </div>
        </div>
      </div>

      {recommendation.alternatives && recommendation.alternatives.length > 0 && (
        <div className="mb-4">
          <p className="text-sm text-gray-600 mb-2">Other options:</p>
          <div className="space-y-2">
            {recommendation.alternatives.map((alt, i) => (
              <div key={i} className="text-sm bg-white p-2 rounded border border-gray-200">
                <p className="font-medium">{alt.name}</p>
                <p className="text-gray-600 text-xs">{alt.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={handleAccept}
          disabled={accepting}
          className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
        >
          {accepting ? 'Starting...' : 'Start Training Plan'}
        </button>
        <button className="flex-1 px-4 py-3 border border-gray-300 text-gray-700 rounded-lg font-semibold hover:bg-gray-50">
          I'd rather learn something else
        </button>
      </div>
    </div>
  )
}
