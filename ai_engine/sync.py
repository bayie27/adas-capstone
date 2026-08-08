import threading
import time

import requests
from camera import CameraStream
from config import INTERNAL_API_KEY, SYNC_URL


def camera_sync_job(local_cameras_dict):
    """Runs infinitely in the background to sync the AI Engine with the FastAPI Backend."""
    headers = {"x-api-key": INTERNAL_API_KEY}

    print(f"[SYNC] Background thread successfully started. Targeting {SYNC_URL}")
    while True:
        try:
            print("[SYNC] Polling backend for active cameras...")
            # 1. Fetch the absolute truth from the backend (pre-filtered for active cameras)
            response = requests.get(SYNC_URL, headers=headers, timeout=5)
            print(f"[SYNC] Backend responded with status code: {response.status_code}")

            if response.status_code == 200:
                db_cameras_list = response.json()

                # Track which cameras should be actively running right now
                valid_camera_ids = set()

                for db_cam in db_cameras_list:
                    cid = db_cam["camera_id"]

                    # Only ingest if the camera is enabled (turned on by operator)
                    if db_cam.get("is_enabled"):
                        valid_camera_ids.add(cid)

                        # A. Start new streams that aren't in our dictionary yet
                        if cid not in local_cameras_dict:
                            print(
                                f"[SYNC] New camera detected! Starting Channel {db_cam['channel_id']}..."
                            )
                            local_cameras_dict[cid] = CameraStream(
                                channel_id=db_cam["channel_id"], camera_id=cid
                            )

                        # B. Sync the Digital Blindfold (Pause/Resume state)
                        else:
                            local_cam = local_cameras_dict[cid]
                            if (
                                db_cam.get("ai_status") == "Paused"
                                and not local_cam.is_paused
                            ):
                                local_cam.pause()
                            elif (
                                db_cam.get("ai_status") == "Active"
                                and local_cam.is_paused
                            ):
                                local_cam.resume()

                # 2. Shutdown and remove cameras that were disabled or deleted
                for cid in list(local_cameras_dict.keys()):
                    if cid not in valid_camera_ids:
                        print(
                            f"[SYNC] Camera {cid} removed/disabled. Shutting down stream..."
                        )
                        local_cameras_dict[cid].stop()
                        del local_cameras_dict[cid]
            else:
                print(
                    f"[SYNC] Backend returned status {response.status_code}: {response.text}"
                )

        except Exception as e:
            print(f"[SYNC] Failed to sync with backend: {e}")

        # Sleep for 3 seconds before polling again
        time.sleep(3)


def start_sync_thread(local_cameras_dict):
    """Starts the sync job in a daemon thread so it dies when the main program exits."""
    thread = threading.Thread(
        target=camera_sync_job, args=(local_cameras_dict,), daemon=True
    )
    thread.start()
    return thread
