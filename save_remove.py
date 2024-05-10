import os
import time
import cv2

def safe_remove(file_path, retries=3, delay=2):
    """Safely remove a file with retries."""
    for i in range(retries):
        try:
            os.remove(file_path)
            print(f"Removed: {file_path}")
            return True
        except PermissionError as e:
            print(f"Retrying ({i+1}/{retries})... Error: {e}")
            time.sleep(delay)
    print(f"Failed to remove: {file_path}")
    return False

# Example usage
safe_remove("some_file.jpg")