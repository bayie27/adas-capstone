# adas-capstone

if nvidia gpu:
    uv pip uninstall torch torchvision
    uv pip install {pytorch cuda}
then:
    uv run --no-sync 


broadcast video file to MediaMTX (force tcp):
    ffmpeg -re -stream_loop -1 -i "ai_engine\sample_vids\jeep_motorcycle.mp4" -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/camera1
    ffmpeg -re -stream_loop -1 -i "ai_engine\sample_vids\car_car.mp4" -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/camera2