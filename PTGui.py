import win32com.client
import glob
import os

# Initialize PTGui COM object
ptgui = win32com.client.Dispatch("PTGui.Application")

# Create a new PTGui project
project = ptgui.NewProject()
project.Filename = r"C:\path\to\project.pts"  # Replace with your actual path

# Directory containing the images
images_dir = r"C:\path\to\images"  # Replace with your actual path
image_files = glob.glob(os.path.join(images_dir, "*.jpg"))

# Add images to the PTGui project
for image_file in image_files:
    project.AddImage(image_file)

# Enable GPS alignment
project.Settings['align_using_gps'] = True

# Align and stitch the panorama
project.AlignImages()
project.StitchPanorama(r"C:\path\to\output_panorama.jpg")