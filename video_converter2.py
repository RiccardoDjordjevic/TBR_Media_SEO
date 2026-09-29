import os
import subprocess

# Define input and output folders
input_folder = "/Users/riccardodjordjevic/Downloads/TBR/to_convert_video"
output_folder = os.path.join(input_folder, "converted")

# Create output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)

# Loop through files in the input folder
for filename in os.listdir(input_folder):
    if filename.lower().endswith(".mov"):
        input_path = os.path.join(input_folder, filename)
        output_filename = os.path.splitext(filename)[0] + ".mp4"
        output_path = os.path.join(output_folder, output_filename)

        # FFmpeg command to preserve color and metadata
        command = [
            "ffmpeg",
            "-y",  # overwrite output files
            "-i", input_path,
            "-c:v", "libx264",  # encode video with h.264
            "-preset", "slow",
            "-crf", "18",  # high quality
            "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-colorspace", "bt709",
            "-c:a", "aac",  # re-encode audio
            "-b:a", "192k",
            output_path
        ]

        print(f"Converting: {filename} → {output_filename}")
        subprocess.run(command, check=True)

print("All MOV files have been converted to MP4 without color changes.")
