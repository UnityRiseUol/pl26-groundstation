import serial
import time
import os
import sys

# --- Configuration (Match your main script) ---
if sys.platform.startswith("win"):
    SERIAL_PORT = "COM3"
else:
    SERIAL_PORT = "/dev/ttyAMA0"

BAUD_RATE = 115200
OUTPUT_FILE = "quaternion_calibration.txt"

def get_latest_packet(ser):
    """Reads the latest valid packet from the buffer."""
    line = None
    while ser.in_waiting:
        try:
            line = ser.readline().decode("ascii", errors="ignore").strip()
        except:
            continue
    return line

def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        print(f"Connected to {SERIAL_PORT}")
    except Exception as e:
        print(f"Could not open serial port: {e}")
        return

    # Poses to capture
    poses = [
        "LEVEL (Nose pointing North, upright)",
        "NOSE UP (Vertical)",
        "90 DEGREE ROLL (Right side down)",
        "PITCH DOWN 90 (Nose to ground)"
    ]

    with open(OUTPUT_FILE, "a") as f:
        f.write(f"\n--- Calibration Session: {time.ctime()} ---\n")
        
        for pose in poses:
            input(f"\n[ACTION] Place rocket in: {pose}\nPress ENTER when steady...")
            
            # Clear buffer and wait for a fresh packet
            ser.reset_input_buffer()
            time.sleep(0.1) 
            
            packet_str = get_latest_packet(ser)
            
            if packet_str and "," in packet_str:
                v = packet_str.split(",")
                if len(v) >= 9:
                    # Extract r, i, j, k (indices 5, 6, 7, 8 based on your original code)
                    qr, qi, qj, qk = v[5], v[6], v[7], v[8]
                    data_line = f"Pose: {pose} | Quat: [{qr}, {qi}, {qj}, {qk}]"
                    
                    print(f"Captured: {data_line}")
                    f.write(data_line + "\n")
                else:
                    print("Error: Received malformed packet.")
            else:
                print("Error: No data received. Check sensor/connection.")

    print(f"\nCalibration finished. Data saved to {OUTPUT_FILE}")
    ser.close()

if __name__ == "__main__":
    main()