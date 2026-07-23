'use client';

import { useState } from 'react';
import { ImageUp, Loader2 } from 'lucide-react';
import { WidgetCard } from '../dashboard/widget-card';
import { detectImage, type VisionDetection } from '@/lib/services/vision';
import { detectionClassLabel } from './detection-severity';

/**
 * Real ultralytics YOLOv8n inference on whatever image is uploaded here --
 * a live demonstration of the "Use YOLO" requirement, separate from the
 * simulated-pipeline panels above which derive their classes from
 * iot-simulator's ground truth rather than a neural network.
 */
export function VisionImageTest() {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [cameraId, setCameraId] = useState('CAM-TEST');
  const [zoneId, setZoneId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [detections, setDetections] = useState<VisionDetection[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setDetections(null);
    setError(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(f ? URL.createObjectURL(f) : null);
  }

  async function handleRun() {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const result = await detectImage(file, cameraId, zoneId || undefined);
      setDetections(result.detections);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Detection failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <WidgetCard title="YOLO Image Test" icon={ImageUp} accent="cyan">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            aria-label="Camera ID"
            value={cameraId}
            onChange={(e) => setCameraId(e.target.value)}
            placeholder="Camera ID"
            className="w-28 rounded-md border border-border bg-muted/20 px-2 py-1 text-xs text-foreground"
          />
          <input
            type="text"
            aria-label="Zone ID (optional)"
            value={zoneId}
            onChange={(e) => setZoneId(e.target.value)}
            placeholder="Zone ID (optional)"
            className="w-36 rounded-md border border-border bg-muted/20 px-2 py-1 text-xs text-foreground"
          />
          <input
            type="file"
            aria-label="Upload image for YOLO detection"
            accept="image/*"
            onChange={handleFileChange}
            className="flex-1 text-xs text-muted-foreground file:mr-2 file:rounded-md file:border-0 file:bg-aegis-indigo file:px-2 file:py-1 file:text-xs file:text-white"
          />
          <button
            onClick={handleRun}
            disabled={!file || loading}
            className="flex items-center gap-1.5 rounded-md bg-aegis-cyan px-3 py-1.5 text-xs font-medium text-background disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading && <Loader2 className="h-3 w-3 animate-spin" />}
            Run YOLO Detection
          </button>
        </div>

        {error && <p className="text-xs text-severity-high">{error}</p>}

        {previewUrl && (
          // Width constraint lives on this container, not the <img> -- an inline-block
          // parent can't shrink-wrap to a child with a percentage width (classic CSS
          // sizing conflict), which left the % bounding boxes below positioned against
          // an oversized invisible container instead of the image's actual rendered box.
          <div className="relative w-full max-w-xl overflow-hidden rounded-md border border-border">
            {/* eslint-disable-next-line @next/next/no-img-element -- dynamic user-uploaded blob URL, not a static asset */}
            <img src={previewUrl} alt="Uploaded frame" className="block h-auto w-full" />
            {detections?.map((d, i) => (
              <div
                key={i}
                className="absolute border-2 border-aegis-cyan"
                style={{
                  left: `${d.bounding_box.x * 100}%`,
                  top: `${d.bounding_box.y * 100}%`,
                  width: `${d.bounding_box.width * 100}%`,
                  height: `${d.bounding_box.height * 100}%`,
                }}
              >
                <span className="absolute -top-5 left-0 whitespace-nowrap rounded bg-aegis-cyan px-1 text-[10px] font-medium text-background">
                  {detectionClassLabel(d.detection_class)} {Math.round(d.confidence * 100)}%
                </span>
              </div>
            ))}
          </div>
        )}

        {detections && detections.length === 0 && (
          <p className="text-xs text-muted-foreground-subtle">
            No detections above threshold. YOLOv8n only recognizes Worker (mapped from COCO&apos;s &quot;person&quot; class) in this deployment.
          </p>
        )}
      </div>
    </WidgetCard>
  );
}
