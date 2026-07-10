import React, { useState } from 'react'

export default function PrescriptionCard({ prescription, isPrimary }) {
  const [accepting, setAccepting] = useState(false)
  const [alternativeOpen, setAlternativeOpen] = useState(false)

  const handleAccept = async () => {
    try {
      setAccepting(true)
      const token = localStorage.getItem('authToken')
      const response = await fetch(
        `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'}/api/coaching/accept-prescription`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token && { Authorization: `Bearer ${token}` })
          },
          body: JSON.stringify({
            prescription_id: prescription.prescription_id
          })
        }
      )
      if (response.ok) {
        window.location.reload()
      }
    } catch (err) {
      console.error('Failed to accept prescription:', err)
    } finally {
      setAccepting(false)
    }
  }

  const getProgressColor = (pct) => {
    if (pct < 25) return 'bg-red-500'
    if (pct < 50) return 'bg-yellow-500'
    if (pct < 75) return 'bg-blue-500'
    return 'bg-green-500'
  }

  return (
    <div className={`border rounded-lg p-4 ${isPrimary ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-white'}`}>
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="font-semibold text-lg">{prescription.plan_name}</h3>
          <p className="text-gray-600 text-sm">{prescription.issue_detected}</p>
        </div>
        <span className={`px-2 py-1 text-xs font-semibold rounded ${
          prescription.status === 'active' ? 'bg-green-100 text-green-800' :
          prescription.status === 'completed' ? 'bg-blue-100 text-blue-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {prescription.status}
        </span>
      </div>

      <p className="text-sm text-gray-700 mb-4">{prescription.reasoning}</p>

      <div className="mb-4">
        <div className="flex justify-between text-sm mb-1">
          <span className="font-medium">Progress</span>
          <span className="text-gray-600">{Math.round(prescription.improvement_pct)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all ${getProgressColor(prescription.improvement_pct)}`}
            style={{ width: `${Math.min(prescription.improvement_pct, 100)}%` }}
          ></div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
        <div>
          <p className="text-gray-600">Before</p>
          <p className="font-semibold">{prescription.baseline_metric?.toFixed(2) || 'N/A'}</p>
        </div>
        <div>
          <p className="text-gray-600">Now</p>
          <p className="font-semibold">{prescription.current_metric?.toFixed(2) || 'N/A'}</p>
        </div>
      </div>

      {prescription.status === 'pending' && isPrimary && (
        <div className="flex gap-2">
          <button
            onClick={handleAccept}
            disabled={accepting}
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {accepting ? 'Starting...' : 'Start Training Plan'}
          </button>
          <button
            onClick={() => setAlternativeOpen(!alternativeOpen)}
            className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50"
          >
            Choose Different
          </button>
        </div>
      )}

      {prescription.status === 'active' && (
        <button className="w-full px-4 py-2 bg-blue-100 text-blue-700 rounded-lg font-medium hover:bg-blue-200">
          Continue Training Plan
        </button>
      )}
    </div>
  )
}
