import win32com.client

# try:
#     # Create PTGui Application COM Object
#     ptgui = win32com.client.Dispatch("PTGui.Application")
#     print("PTGui Pro COM automation initialized successfully!")
# except Exception as e:
#     print(f"Error initializing PTGui COM object: {e}")

import subprocess

# Define the paths
ptgui_executable = r"C:\Program Files\PTGui\PTGui.exe"
project_file = r"C:\path\to\project.pts"
panorama_output = r"C:\path\to\stitched_panorama.jpg"

# Create the PTGui project file if not available
# Align and stitch via PTGui CLI
command = [
    ptgui_executable,
    "-project", project_file,
    "-align", "-stitch"
]

result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if result.returncode == 0:
    print(f"Panorama created successfully: {panorama_output}")
else:
    print(f"Error creating panorama: {result.stderr.decode()}")
