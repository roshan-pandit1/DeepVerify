import cv2
import numpy as np
import os

os.makedirs("backend/ai_detection_pipeline/samples", exist_ok=True)
video_path = "backend/ai_detection_pipeline/samples/sample_video.mp4"

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(video_path, fourcc, 30.0, (320, 240))

for i in range(60):
    # Create synthetic frame with shifting sinusoidal pattern
    x = np.linspace(0, 5 * np.pi, 320)
    y = np.linspace(0, 5 * np.pi, 240)
    xx, yy = np.meshgrid(x, y)
    frame_grid = ((np.sin(xx + i*0.1) + np.cos(yy + i*0.1)) * 127 + 128).astype(np.uint8)
    frame_bgr = cv2.cvtColor(frame_grid, cv2.COLOR_GRAY2BGR)
    out.write(frame_bgr)

out.release()
print(f"Sample video generated: {video_path}")
