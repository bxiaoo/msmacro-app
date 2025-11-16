import { useState, useEffect } from 'react'
import { Download, AlertCircle, CheckCircle, XCircle, Pipette } from 'lucide-react'
import { saveCalibrationSample, getCVStatus } from '../api'
import { Button } from './ui/button'
import { CalibrationGallery } from './cv/CalibrationGallery'
import { CalibrationWizard } from './cv/CalibrationWizard'

export default function EventsPanel() {
  // Sample save state
  const [sampleCount, setSampleCount] = useState(0)
  const [savingSample, setSavingSample] = useState(false)
  const [sampleMessage, setSampleMessage] = useState(null)
  const [refreshGallery, setRefreshGallery] = useState(0)

  // Calibration wizard state
  const [showCalibration, setShowCalibration] = useState(false)
  const [calibrationType, setCalibrationType] = useState('player')

  // CV status for checking if frame is available
  const [hasFrame, setHasFrame] = useState(false)

  // Check CV status periodically to enable/disable sample save
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const status = await getCVStatus()
        setHasFrame(status?.has_frame || false)
      } catch (err) {
        setHasFrame(false)
      }
    }

    checkStatus()
    const interval = setInterval(checkStatus, 2000)
    return () => clearInterval(interval)
  }, [])

  const handleSaveCalibrationSample = async () => {
    setSavingSample(true)
    setSampleMessage(null)

    try {
      const result = await saveCalibrationSample()

      if (result.success) {
        setSampleCount(prev => prev + 1)
        setRefreshGallery(prev => prev + 1) // Trigger gallery refresh
        setSampleMessage({
          type: 'success',
          text: `Sample ${result.filename} saved! (${result.resolution[0]}×${result.resolution[1]})`
        })

        // Clear success message after 3 seconds
        setTimeout(() => setSampleMessage(null), 3000)
      } else {
        // Detailed error handling with troubleshooting
        console.error('Sample save failed:', result)

        let errorText = result.message || 'Failed to save sample'

        // Add action hints if available
        if (result.details?.action) {
          errorText += `\n\n${result.details.action}`
        }

        setSampleMessage({
          type: 'error',
          text: errorText,
          error: result.error, // Error code for debugging
          details: result.details
        })

        // Don't auto-dismiss errors
      }
    } catch (err) {
      console.error('Failed to save calibration sample:', err)
      setSampleMessage({
        type: 'error',
        text: `Network error: ${err.message}\n\nCheck that the daemon is running and accessible.`
      })
    } finally {
      setSavingSample(false)
    }
  }

  const handleCalibrationComplete = (result) => {
    console.log('Calibration complete:', result)
    setShowCalibration(false)
    // Optionally show a success message
  }

  return (
    <div className="bg-white p-4 relative rounded-tl-[8px] rounded-tr-[8px] w-full max-h-[95vh] flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Pipette size={20} className="text-indigo-600" />
          <h3 className="font-['Roboto:Bold',_sans-serif] font-bold text-[16px] text-gray-900">
            CV Debug Panel
          </h3>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          Calibration tools and sample management
        </p>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-6">
        {/* Calibration Section */}
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
          <h3 className="font-semibold text-indigo-900 mb-2 flex items-center gap-2">
            <Pipette size={16} />
            Color Calibration
          </h3>
          <p className="text-sm text-indigo-800 mb-3">
            Click to calibrate HSV color ranges for accurate detection with real YUYV frames.
          </p>
          <div className="flex gap-3">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setCalibrationType('player')
                setShowCalibration(true)
              }}
            >
              Player
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setCalibrationType('other_player')
                setShowCalibration(true)
              }}
            >
              Other player
            </Button>
          </div>
        </div>

        {/* Sample Save Section */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Calibration Samples</h3>
            <div className="flex items-center gap-3">
              {sampleCount > 0 && (
                <span className="text-sm text-gray-600 bg-blue-50 px-3 py-1 rounded-full">
                  Samples: {sampleCount}
                </span>
              )}
              <Button
                onClick={handleSaveCalibrationSample}
                disabled={savingSample || !hasFrame}
                className="flex items-center gap-2"
                size="sm"
              >
                <Download size={16} />
                {savingSample ? 'Saving...' : 'Save Sample'}
              </Button>
            </div>
          </div>

          {/* Sample save message */}
          {sampleMessage && (
            <div className={`p-4 rounded-lg text-sm ${
              sampleMessage.type === 'success'
                ? 'bg-green-50 text-green-800 border border-green-200'
                : 'bg-red-50 text-red-800 border border-red-200'
            }`}>
              <div className="flex items-start gap-2">
                {sampleMessage.type === 'error' && (
                  <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
                )}
                {sampleMessage.type === 'success' && (
                  <CheckCircle size={16} className="flex-shrink-0 mt-0.5" />
                )}
                <div className="flex-1">
                  <div className="font-medium mb-1">
                    {sampleMessage.type === 'success' ? 'Success!' : 'Failed to save sample'}
                  </div>
                  <div className="whitespace-pre-line">
                    {sampleMessage.text}
                  </div>
                  {sampleMessage.error && (
                    <div className="mt-2 text-xs opacity-75 font-mono">
                      Error code: {sampleMessage.error}
                    </div>
                  )}
                </div>
                {sampleMessage.type === 'error' && (
                  <button
                    onClick={() => setSampleMessage(null)}
                    className="flex-shrink-0 text-red-600 hover:text-red-800"
                  >
                    <XCircle size={16} />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Calibration Gallery */}
          <CalibrationGallery refreshTrigger={refreshGallery} />
        </div>
      </div>

      {/* Calibration Wizard Modal */}
      {showCalibration && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
            <CalibrationWizard
              colorType={calibrationType}
              onComplete={handleCalibrationComplete}
              onCancel={() => setShowCalibration(false)}
            />
          </div>
        </div>
      )}
    </div>
  )
}
