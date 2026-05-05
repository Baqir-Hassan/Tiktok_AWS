import modal
import os

# Define the Modal app
app = modal.App("saas-worker")

# Mount the project directory
project_mount = modal.Mount.from_local_dir(".", remote_path="/root/project")

# Define the image with dependencies
image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .apt_install("ffmpeg")  # Install FFmpeg
    .run_commands(
        "apt-get update && apt-get install -y libsndfile1",  # For audio processing
    )
)

# Secrets for API keys, etc.
secrets = [
    modal.Secret.from_name("worker-secrets"),  # To be created with env vars
]

# Placeholder for job processing function
@app.function(
    image=image, 
    secrets=secrets, 
    mounts=[project_mount],
    timeout=1800  # 30 minutes timeout for video processing
)
def process_job(job_data: dict):
    # Add project to path
    import sys
    sys.path.insert(0, "/root/project")
    
    # Import and run pipeline
    from modal_worker.pipeline import run_job_pipeline
    return run_job_pipeline(job_data)

# For local testing
if __name__ == "__main__":
    with app.run():
        result = process_job.remote({"id": 1, "subreddit": "test"})
        print(result)