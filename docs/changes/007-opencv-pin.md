# 007 — Pin OpenCV < 5: face detection was dead on the rebuilt VM (R-01 fix)
Date: 2026-09-29 · Commit: see `git log --grep "fix(R-01)"` · Files: worker/requirements.txt

## What changed
- `opencv-python-headless>=4.10,<5` (resolved to 4.14.0).

## Why
The rebuilt image resolved `>=4.10` to OpenCV 5.0.0, which removed `cv2.dnn.readNetFromCaffe`. Every corner probe
logged "Corner face detection failed … has no attribute 'readNetFromCaffe'" and every render since the rebuild used
the no-face fallback box (the half-black facecam pane seen in the R-22 end-to-end run).

## Decisions & trade-offs
- Pin instead of porting the res10 SSD to ONNX: smallest change, same model as the old VM.

## Gotchas for future changes
- Moving to OpenCV 5 requires converting the face detector (e.g. YuNet ONNX via `cv2.FaceDetectorYN`).
- "No face detected; using … fallback" on a video that clearly has a webcam = check this first.

## Verification
- In the worker: `cv2.__version__` 4.14.0, Caffe net loads; the R-04 test job's face is detected
  (`cx=165, cy=914, h=111` on a 1920x1080 source with a bottom-left webcam).
