import { useState, useEffect } from 'react'
import { Download, Trash2, Package } from 'lucide-react'
import {
  listCalibrationSamples,
  getCalibrationSampleURL,
  downloadAllCalibrationSamples,
  deleteCalibrationSample
} from '../../api'
import { Button } from '../ui/button'

export function CalibrationGallery({ refreshTrigger }) {
  const [samples, setSamples] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [deletingFile, setDeletingFile] = useState(null)

  const loadSamples = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await listCalibrationSamples()
      setSamples(response.samples || [])
    } catch (err) {
      console.error('Failed to load samples:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSamples()
  }, [refreshTrigger])

  const handleDelete = async (filename) => {
    if (!confirm(`Delete ${filename}?`)) return

    try {
      setDeletingFile(filename)
      await deleteCalibrationSample(filename)
      await loadSamples() // Refresh list
    } catch (err) {
      alert(`Failed to delete: ${err.message}`)
    } finally {
      setDeletingFile(null)
    }
  }

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp * 1000).toLocaleString()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-4 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800 text-sm">
        Error loading samples: {error}
      </div>
    )
  }

  if (samples.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Package size={48} className="mx-auto mb-3 text-gray-300" />
        <p className="text-sm font-medium">No samples saved yet</p>
        <p className="text-xs mt-1">Click "Save Sample" to start collecting calibration data</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header with bulk actions */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">
          Calibration Samples ({samples.length})
        </h3>
        <Button
          onClick={downloadAllCalibrationSamples}
          className="flex items-center gap-2 text-sm"
        >
          <Download size={14} />
          Download All as ZIP
        </Button>
      </div>

      {/* Sample grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {samples.map((sample) => (
          <div
            key={sample.filename}
            className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow"
          >
            {/* Thumbnail */}
            <div className="relative bg-gray-100 aspect-[4/1]">
              <img
                src={getCalibrationSampleURL(sample.filename)}
                alt={sample.filename}
                className="w-full h-full object-cover"
                loading="lazy"
              />
            </div>

            {/* Info */}
            <div className="p-3 space-y-2">
              <div className="text-xs font-mono text-gray-600 truncate" title={sample.filename}>
                {sample.filename}
              </div>

              <div className="text-xs text-gray-500 space-y-1">
                {sample.metadata?.capture_info?.resolution && (
                  <div>{sample.metadata.capture_info.resolution[0]}×{sample.metadata.capture_info.resolution[1]}</div>
                )}
                <div>{formatFileSize(sample.size_bytes)}</div>
                <div className="truncate" title={formatTimestamp(sample.timestamp)}>
                  {formatTimestamp(sample.timestamp).split(',')[0]}
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-2">
                <a
                  href={getCalibrationSampleURL(sample.filename)}
                  download={sample.filename}
                  className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition-colors"
                >
                  <Download size={12} />
                  Download
                </a>
                <button
                  onClick={() => handleDelete(sample.filename)}
                  disabled={deletingFile === sample.filename}
                  className="flex items-center justify-center px-2 py-1 text-xs bg-red-50 text-red-700 rounded hover:bg-red-100 transition-colors disabled:opacity-50"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Help text */}
      <div className="text-xs text-gray-500 bg-blue-50 border border-blue-100 rounded p-3">
        <strong>💡 Tip:</strong> Collect 20-50 diverse samples (different positions, player counts, lighting) for best results.
        Download the ZIP and send to Claude for HSV range optimization analysis.
      </div>
    </div>
  )
}
