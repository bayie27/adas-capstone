# adas-capstone

if nvidia gpu:
    uv pip uninstall torch torchvision
    uv pip install {pytorch cuda}
then:
    uv run --no-sync '.\AI engine\main.py' 


broadcast video file to MediaMTX (force tcp):
    ffmpeg -re -stream_loop -1 -i "AI engine\sample_vids\jeep_motorcycle.mp4" -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/camera1