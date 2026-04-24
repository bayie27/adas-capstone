import os

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

import cv2
from ultralytics import YOLO


def run_local_inference():
    print("Initializing ADAS...")

    model = YOLO("AI engine/best.pt")

    # video_path = "AI engine/sample_vids/car_car.mp4"
    video_path = "AI engine/sample_vids/jeep_motorcycle.mp4"
    cap = cv2.VideoCapture(video_path)

    # cap = cv2.VideoCapture("rtsp://localhost:8554/camera1")

    if not cap.isOpened():
        print("Video playback finished or stream dropped")
        return

    print("Video loaded successfully. Press 'q' in the video window to quit.")

    while True:
        success, frame = cap.read()

        if not success:
            print("Video playback finished or frame dropped.")
            break

        results = model(frame, stream=True)
        # results = model(frame, stream=True, device=0)

        for r in results:
            annotated_frame = r.plot()

            cv2.imshow("ADAS AI Detection Stream", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Manual exit triggered.")
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Inference pipeline shut down safely.")


if __name__ == "__main__":
    run_local_inference()
