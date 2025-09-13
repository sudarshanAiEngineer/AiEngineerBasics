import os
import openai
import requests
import subprocess
import json
from pathlib import Path

# ==============================
# 1. SETUP
# ==============================
openai.api_key = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
STABLE_DIFFUSION_API = "https://api.stability.ai/v1/generation/stable-diffusion-v1-5/text-to-image"

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# ==============================
# 2. BREAK SCRIPT INTO SCENES
# ==============================
def split_into_scenes(script_text):
    prompt = f"""
    Split this script into 3 short scene descriptions for an animation.
    Return as JSON list of strings.
    Script: {script_text}
    """
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    try:
        scenes = json.loads(resp.choices[0].message.content.strip())
    except:
        scenes = [script_text]  # fallback
    return scenes

# ==============================
# 3. GENERATE IMAGE (Stable Diffusion API placeholder)
# ==============================
def generate_image(scene_text, scene_id):
    headers = {"Authorization": f"Bearer {os.getenv('STABILITY_API_KEY')}"}
    payload = {
        "text_prompts": [{"text": scene_text}],
        "cfg_scale": 7,
        "clip_guidance_preset": "FAST_BLUE",
        "height": 512,
        "width": 512,
        "samples": 1,
        "steps": 30
    }
    response = requests.post(STABLE_DIFFUSION_API, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"Image gen failed: {response.text}")
    
    data = response.json()
    image_bytes = bytes(data["artifacts"][0]["base64"], "utf-8")
    image_path = OUTPUT_DIR / f"scene_{scene_id}.png"
    with open(image_path, "wb") as f:
        f.write(image_bytes)
    return image_path

# ==============================
# 4. GENERATE VOICE (ElevenLabs TTS)
# ==============================
def generate_audio(scene_text, scene_id):
    url = "https://api.elevenlabs.io/v1/text-to-speech/<VOICE_ID>"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": scene_text,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.7}
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"Audio gen failed: {response.text}")
    
    audio_path = OUTPUT_DIR / f"scene_{scene_id}.mp3"
    with open(audio_path, "wb") as f:
        f.write(response.content)
    return audio_path

# ==============================
# 5. STITCH VIDEO (ffmpeg)
# ==============================
def make_video(image_path, audio_path, scene_id):
    video_path = OUTPUT_DIR / f"scene_{scene_id}.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest", str(video_path)
    ]
    subprocess.run(cmd, check=True)
    return video_path

# ==============================
# 6. PIPELINE ORCHESTRATOR
# ==============================
def run_pipeline(script_text):
    print("Splitting into scenes...")
    scenes = split_into_scenes(script_text)

    final_videos = []
    for i, scene in enumerate(scenes, start=1):
        print(f"Processing scene {i}: {scene}")
        img = generate_image(scene, i)
        audio = generate_audio(scene, i)
        vid = make_video(img, audio, i)
        final_videos.append(vid)

    # Merge all scene videos
    list_file = OUTPUT_DIR / "scenes.txt"
    with open(list_file, "w") as f:
        for vid in final_videos:
            f.write(f"file '{vid.absolute()}'\n")

    final_path = OUTPUT_DIR / "final_output.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(final_path)],
        check=True
    )
    print(f"Final video created: {final_path}")
    return final_path

# ==============================
# 7. RUN DEMO
# ==============================
if __name__ == "__main__":
    script_input = """
    A young boy walks into a magical forest. 
    Suddenly, glowing butterflies surround him. 
    He smiles as the trees light up like lanterns.
    """
    run_pipeline(script_input)
