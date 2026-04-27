import cv2

# Replace this with your specific MediaMTX RTSP URL
rtsp_url = "rtsp://localhost:8554/channel1"

# Initialize the video capture object
cap = cv2.VideoCapture(rtsp_url)

# Verify the connection was successful
if not cap.isOpened():
    print(f"Error: Could not connect to {rtsp_url}")
    exit()

print("Stream connected. Press 'q' to close the window.")

while True:
    # Read the next frame from the stream
    ret, frame = cap.read()

    # If ret is False, the frame wasn't grabbed (stream dropped or ended)
    if not ret:
        print("Stream ended or connection lost.")
        break

    # Display the frame in a window
    cv2.imshow("MediaMTX RTSP Stream", frame)

    # Wait 1ms for a key event; exit if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Clean up resources
cap.release()
cv2.destroyAllWindows()