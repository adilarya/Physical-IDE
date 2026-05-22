import { useRef, useState, useEffect, useCallback } from 'react';

// 1x1 transparent PNG - fallback "frame" so the mock loop never stalls when the
// camera is denied/unavailable. Mock mode ignores image content anyway.
const PLACEHOLDER_FRAME =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

/**
 * useWebcam(enabled)
 *  - opens getUserMedia when `enabled` flips true
 *  - returns videoRef to attach to a <video>, plus captureFrame()
 *  - on failure, still reports ready=true so the agent loop keeps working
 */
export function useWebcam(enabled) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!enabled) return;
    let stream = null;
    let cancelled = false;

    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 1280, height: 720, facingMode: 'environment' },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
          setReady(true);
        }
      } catch (e) {
        // Demo resilience: don't block the loop on a missing camera.
        console.warn('[useWebcam] camera unavailable:', e);
        setError(e?.message || 'camera unavailable');
        setReady(true);
      }
    })();

    return () => {
      cancelled = true;
      if (stream) stream.getTracks().forEach((t) => t.stop());
    };
  }, [enabled]);

  /** Grab the current video frame as a JPEG data URI (or a placeholder). */
  const captureFrame = useCallback(() => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return PLACEHOLDER_FRAME;

    let canvas = canvasRef.current;
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvasRef.current = canvas;
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    // 0.6 quality keeps the upstream WebSocket frame small.
    return canvas.toDataURL('image/jpeg', 0.6);
  }, []);

  return { videoRef, ready, error, captureFrame };
}
