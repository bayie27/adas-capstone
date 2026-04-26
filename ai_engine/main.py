import cv2
from ultralytics import YOLO
from accident import AccidentManager
from config import CONFIDENCE_THRESHOLD
from sync import start_sync_thread

def run_multi_camera_inference():
    print("Initializing ADAS Edge Inference Server...")

    # Load the optimized TensorRT Engine
    model = YOLO("ai_engine/best.engine")
    alert_manager = AccidentManager()

    # Change cameras from a list to a dictionary for dynamic lookup by ID
    cameras = {}

    # Start the background sync thread (polls every 3 seconds)
    start_sync_thread(cameras)

    print("Waiting for backend sync... Press 'q' in any video window to quit.")

    while True:
        frames_to_process = []
        active_cameras = []

        # Gather frames ONLY from cameras that are online and NOT paused
        for cam in list(cameras.values()):
            if not cam.is_paused:
                frame = cam.read()
                if frame is not None:
                    frames_to_process.append(frame)
                    active_cameras.append(cam)

        # GPU BATCHING
        if frames_to_process:
            results = model(frames_to_process, stream=False, device=0, verbose=False, conf=CONFIDENCE_THRESHOLD)

            for i, r in enumerate(results):
                current_cam = active_cameras[i]
                annotated_frame = r.plot()

                # Hand it to the manager to check for accidents and trigger webhooks
                alert_manager.process_detections(current_cam, r, annotated_frame)

                cv2.imshow(f"ADAS Stream - Camera {current_cam.camera_id} (Ch. {current_cam.channel_id})", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Manual exit triggered.")
            break

    # Clean up operations
    print("Shutting down worker threads...")
    for cam in list(cameras.values()):
        cam.stop()
    cv2.destroyAllWindows()
    print("ADAS Edge Server safely powered down.")


if __name__ == "__main__":
    run_multi_camera_inference()
