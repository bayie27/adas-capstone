import cv2
from ultralytics import YOLO
import config  # Executes OS configurations automatically
from camera import CameraStream
from manager import AccidentManager

def run_multi_camera_inference():
    print("Initializing ADAS Edge Inference Server...")

    # Load the optimized TensorRT Engine
    model = YOLO("ai_engine/best.engine")
    alert_manager = AccidentManager()

    # Initialize cameras with their exact Database IDs
    cameras = [
        # CameraStream("rtsp://localhost:8554/camera1", "jeep_motorcycle", camera_id=1),
        # CameraStream("rtsp://localhost:8554/camera2", "car_car", camera_id=2),
        CameraStream("ai_engine/sample_vids/jeep_motorcycle.mp4", "jeep_motorcycle", camera_id=1),
        CameraStream("ai_engine/sample_vids/car_car.mp4", "car_car", camera_id=2),
        # Add more cameras as your hardware allows!
    ]

    print("Streams loaded. Press 'q' in any video window to quit.")

    while True:
        frames_to_process = []
        active_cameras = []

        # Gather frames ONLY from cameras that are online and NOT paused
        for cam in cameras:
            if not cam.is_paused and cam.latest_frame is not None:
                frames_to_process.append(cam.latest_frame)
                active_cameras.append(cam)

        # GPU BATCHING
        if frames_to_process:
            results = model(frames_to_process, stream=False, device=0, verbose=False)

            for i, r in enumerate(results):
                current_cam = active_cameras[i]
                annotated_frame = r.plot()

                # Hand it to the manager to check for accidents and trigger webhooks
                alert_manager.process_detections(current_cam, r, annotated_frame)

                cv2.imshow(f"ADAS Stream: {current_cam.name}", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Manual exit triggered.")
            break

    # Clean up operations
    print("Shutting down worker threads...")
    for cam in cameras:
        cam.stop()
    cv2.destroyAllWindows()
    print("ADAS Edge Server safely powered down.")


if __name__ == "__main__":
    run_multi_camera_inference()
