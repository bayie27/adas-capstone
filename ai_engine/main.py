import os

# Force OpenCV to use TCP for RTSP streams to prevent packet loss
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

import cv2
import threading
import time
from ultralytics import YOLO


class CameraStream:
    """A threaded camera reader with Auto-Reconnect capabilities."""

    def __init__(self, url, name):
        self.url = url
        self.name = name
        self.latest_frame = None
        self.running = True
        self.cap = None  # We will initialize this inside the thread instead

        # Start the background thread immediately
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def _update(self):
        """This function runs infinitely in the background."""
        while self.running:
            # 1. THE RECONNECT LOOP: If there is no connection, keep trying to build one
            if self.cap is None or not self.cap.isOpened():
                print(f"[SYSTEM] {self.name} is offline. Attempting connection...")
                self.cap = cv2.VideoCapture(self.url)

                if not self.cap.isOpened():
                    time.sleep(2)  # Network delay, wait 2 seconds before trying again
                    continue  # Skip the rest of the loop and try again

            # 2. THE READ LOOP: If connected, grab the frame
            success, frame = self.cap.read()

            if success:
                # Overwrite the old frame with the newest one
                self.latest_frame = frame
            else:
                # 3. THE DROP DETECTOR: If reading fails, the stream died!
                print(f"[SYSTEM] Stream dropped on {self.name}! Releasing socket...")
                self.cap.release()
                self.cap = None  # This forces Step 1 to trigger on the next loop
                time.sleep(1)

            # Tiny sleep to prevent this thread from maxing out a CPU core
            time.sleep(0.01)

    def stop(self):
        """Safely shuts down the thread and connection."""
        self.running = False
        self.thread.join()
        if self.cap:
            self.cap.release()


def run_multi_camera_inference():
    print("Initializing ADAS Multi-Stream AI...")
    model = YOLO("ai_engine/best.engine")

    # 1. Initialize our threaded cameras
    cameras = [
        CameraStream("rtsp://localhost:8554/camera1", "Main Intersection"),
        CameraStream("rtsp://localhost:8554/camera2", "Southbound Lane"),
        # You can keep adding cameras here as your hardware allows
    ]

    print("Streams loaded. Press 'q' in any video window to quit.")

    while True:
        frames_to_process = []
        camera_names = []

        # 2. Gather the absolute newest frame from every camera
        for cam in cameras:
            if cam.latest_frame is not None:
                frames_to_process.append(cam.latest_frame)
                camera_names.append(cam.name)

        # 3. GPU BATCHING: Send all frames to YOLO simultaneously
        if frames_to_process:
            # By passing a list of frames, YOLO processes them in parallel on the GPU!
            results = model(frames_to_process, stream=False, device=0)

            # 4. Draw the boxes and display the windows
            for i, r in enumerate(results):
                annotated_frame = r.plot()
                # Dynamically create a window for each camera name
                cv2.imshow(f"ADAS Stream: {camera_names[i]}", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Manual exit triggered.")
            break

    # Clean up operations
    for cam in cameras:
        cam.stop()
    cv2.destroyAllWindows()
    print("Multi-stream pipeline shut down safely.")


if __name__ == "__main__":
    run_multi_camera_inference()
