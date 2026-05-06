import modal
import subprocess

app = modal.App('test-font')
image = (
    modal.Image.from_registry('nvidia/cuda:12.1.1-devel-ubuntu22.04', add_python='3.11')
    .apt_install('fontconfig')
    .add_local_dir('fonts', '/usr/share/fonts/truetype/custom', copy=True)
    .run_commands('fc-cache -f -v')
)

@app.function(image=image)
def test():
    print(subprocess.check_output(['fc-match', 'Luckiest Guy']).decode('utf-8'))

@app.local_entrypoint()
def main():
    test.remote()
