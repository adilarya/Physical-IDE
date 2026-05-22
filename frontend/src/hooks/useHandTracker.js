import { useEffect, useRef, useState } from 'react';
import { HandLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';

// MediaPipe assets served from CDN - no local model files to manage.
const WASM_URL =
  'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm';
const MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';

// How long hands must stay OUT of frame before we declare the area "clear".
const CLEAR_DEBOUNCE_MS = 500;

/**
 * useHandTracker(videoRef, enabled, onHandClear)
 *  - runs MediaPipe HandLandmarker on the video feed
 *  - exposes handsInFrame: boolean
 *  - fires onHandClear() ONCE, ~500ms after hands fully leave the frame
 *    (re-arms only when hands return, so one fire per departure)
 */
export function useHandTracker(videoRef, enabled, onHandClear) {
  const [handsInFrame, setHandsInFrame] = useState(false);
  const [trackerReady, setTrackerReady] = useState(false);

  // keep the latest callback without re-running the effect
  const cbRef = useRef(onHandClear);
  cbRef.current = onHandClear;

  useEffect(() => {
    if (!enabled) return;

    let landmarker = null;
    let raf = 0;
    let cancelled = false;
    let clearTimer = null;
    let armed = false; // becomes true once hands have been seen at least once
    let lastInFrame = false;
    let lastVideoTime = -1;

    (async () => {
      try {
        const vision = await FilesetResolver.forVisionTasks(WASM_URL);
        landmarker = await HandLandmarker.createFromOptions(vision, {
          baseOptions: { modelAssetPath: MODEL_URL, delegate: 'GPU' },
          runningMode: 'VIDEO',
          numHands: 2,
        });
        if (cancelled) {
          landmarker.close();
          return;
        }
        setTrackerReady(true);
        loop();
      } catch (e) {
        // If MediaPipe fails to init, the FORCE CAPTURE button is the fallback.
        console.warn('[useHandTracker] init failed - use Force Capture instead', e);
      }
    })();

    function loop() {
      if (cancelled) return;
      const video = videoRef.current;

      if (video && video.videoWidth && video.currentTime !== lastVideoTime) {
        lastVideoTime = video.currentTime;

        let inFrame = false;
        try {
          const res = landmarker.detectForVideo(video, performance.now());
          inFrame = !!(res && res.landmarks && res.landmarks.length > 0);
        } catch {
          /* swallow per-frame detection errors */
        }

        if (inFrame !== lastInFrame) {
          lastInFrame = inFrame;
          setHandsInFrame(inFrame);

          if (inFrame) {
            // hands returned - cancel any pending clear, re-arm
            armed = true;
            if (clearTimer) {
              clearTimeout(clearTimer);
              clearTimer = null;
            }
          } else if (armed) {
            // hands just left - debounce, then fire once
            clearTimer = setTimeout(() => {
              clearTimer = null;
              armed = false; // disarm until hands return
              if (cbRef.current) cbRef.current();
            }, CLEAR_DEBOUNCE_MS);
          }
        }
      }
      raf = requestAnimationFrame(loop);
    }

    return () => {
      cancelled = true;
      if (raf) cancelAnimationFrame(raf);
      if (clearTimer) clearTimeout(clearTimer);
      if (landmarker) landmarker.close();
    };
  }, [enabled, videoRef]);

  return { handsInFrame, trackerReady };
}
