import os
import subprocess
import sys
import json
import requests
from os.path import exists
from craiyon import Craiyon
from moviepy.editor import *
from moviepy.video.tools.subtitles import SubtitlesClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from PIL import Image
import random

def get_sec(time_str):
    m, s = time_str.split(':') 
    return round(int(m) * 60 + float(s), 2)


def create_directory(spotifyid):
	if not os.path.exists("songs/"):
		os.makedirs("songs/")
	if not os.path.exists(f"songs/{spotifyid}"):
		os.mkdir(f"songs/{spotifyid}")


def download_song(spotifyid, spotifyurl):
	max_runs = 3
	run_count = 0

	if not exists(f"{spotifyid}.mp3"):
		while run_count < max_runs:
			try:
				subprocess.run(["spotdl", "--output", "{track-id}", "--format", "mp3", "--download", f"{spotifyurl}"])
			except subprocess.CalledProcessError as e:
				print(e)
				run_count += 1
				continue
			else:
				if not exists(f"{spotifyid}.mp3"):
					run_count += 1
					continue
				else:
					break
		if run_count == max_runs:
			print("Error: Song download failed.")
			sys.exit(1)


def download_lyrics(spotifyid, lyricsurl):
	if not exists(f"{spotifyid}.json"):
		lyrics = requests.get(lyricsurl)
		lyricsjson = lyrics.json()
		with open(f"{spotifyid}.json", "w") as f:
			json.dump(lyricsjson, f)
	else:
		with open(f"{spotifyid}.json", "r") as f:
			lyricsjson = json.load(f)

	if lyricsjson["error"] == True:
		print("Error: Lyrics not found.")
		sys.exit(1)

	return lyricsjson


def generate_backing(spotifyid):
	max_runs = 3
	run_count = 0

	if not exists(f"{spotifyid}.mp4"):
		while run_count < max_runs:
			try:
				subprocess.run(["xvfb-run", "avp", "-c", "0", "classic", "layout=top", "color=255,255,255", "-i", f"{spotifyid}.mp3", "-o", f"{spotifyid}.mp4", "--no-preview"])
			except subprocess.CalledProcessError as e:
				print(e)
				run_count += 1
				continue
			else:
				break
		if run_count == max_runs:
			print("Error: Video generation failed.")
			sys.exit(1)


def generate_images(lyricsjson):
	mappings = {}
	if exists("mappings.json"):
		with open("mappings.json", "r") as f:
			mappings = json.load(f)

	i = 0
	for line in lyricsjson["lines"]:
		if line["words"] == "" or line["words"] in mappings:
			continue
		result = generator.generate(line["words"])
		result.save_images(f"images/{i}")
		# iterate through each saved image and open
		for root, dirs, files in os.walk("images", topdown = False):
			for name in files:
				if name.endswith('.png'):
					filename = os.path.join(root, name)
					im = Image.open(f"{filename}")
					im.save(f"{filename}", "PNG")
		print("Generated images for: ", line["words"])
		mappings[line["words"]] = i
		i += 1

	with open("mappings.json", "w") as outfile:
		json.dump(mappings, outfile)

	return mappings


def generate_video(spotifyid, lyricsjson, mappings):
	video = VideoFileClip(f"{spotifyid}.mp4")

	generator = lambda txt: TextClip(txt, font='Liberation-Sans', fontsize=48, color='white')

	subconvert = []
	images = []
	length = len(lyricsjson["lines"])
	for i in range(length):
		line = lyricsjson["lines"][i]
		if line["words"] == "":
			continue
		start = get_sec(line["timeTag"])
		if i == length - 1:
			end = video.duration
		else:
			end = get_sec(lyricsjson["lines"][i + 1]["timeTag"])
		duration = end - start
		subtitle = ((start, end), line["words"])
		folder = mappings[line["words"]]
		image = ImageClip(f"images/{folder}/image-{random.randint(1, 9)}.png").resize(height=512).set_start(start).set_duration(duration).set_pos(("center", 104)).margin(mar=5, color=(255, 255, 255))
		subconvert.append(subtitle)
		images.append(image)

	subs = SubtitlesClip(subconvert, generator).set_pos(("center", 644))

	result = CompositeVideoClip([video, subs] + images)

	result.write_videofile("output.mp4", fps=video.fps, temp_audiofile="temp-audio.m4a", remove_temp=True, codec="libx264", audio_codec="aac")


generator = Craiyon()

lyricsbase = "https://spotify-lyric-api.herokuapp.com/?trackid="
spotifybase = "https://open.spotify.com/track/"
spotifyid = sys.argv[1]
spotifyurl = spotifybase + spotifyid
lyricsurl = lyricsbase + spotifyid + "&format=lrc"

home = os.getcwd()
create_directory(spotifyid)
os.chdir(f"songs/{spotifyid}")

print("Searching for song...")
download_song(spotifyid, spotifyurl)

print("Searching for lyrics...")
lyricsjson = download_lyrics(spotifyid, lyricsurl)

print("Generating backing video...")
generate_backing(spotifyid)

print("Generating images...")
mappings = generate_images(lyricsjson)

print("Generating video...")
generate_video(spotifyid, lyricsjson, mappings)

os.chdir(home)