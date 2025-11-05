import os
import json

import yt_dlp # for audio extraction
import ffmpeg
from pydub import AudioSegment

import requests # for image extraction
from PIL import Image
from io import BytesIO

from colorthief import ColorThief #For image colour extraction
import matplotlib.pyplot as plt

#-----------------------creating job folders
#'''
job_id = 1
job_folder = f"jobs/job_{job_id:03}"
os.makedirs(job_folder, exist_ok=True)
print("created", job_folder)
#'''
#-----------------------
mp3URL = str(input("Enter Audio URL"))
#------------------------------------------- EXTRACTING AUDIO
#'''
ydl_opts = {
    'format': 'mp3/bestaudio/best',
    'outtmpl': os.path.join(job_folder, 'audio_source.%(ext)s'),
    'postprocessors': [{  # Extract audio using ffmpeg
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
    }]
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download(mp3URL)
#'''
#---------------------------------------- TRIMMING AUDIO
#'''
def mmss_to_millisecondsaudio(time_str):
    m, s = map(int, time_str.split(':'))
    return ((m * 60) + s) * 1000
 
# Load audio file
audio_import = f'jobs/job_{job_id:03}/audio_source.mp3'
song = AudioSegment.from_file(audio_import, format="mp3")

# Take input from user
start_time = input("Enter start time (MM:SS): ")
end_time = input("Enter end time (MM:SS): ")
 
# Convert to milliseconds
start_ms = mmss_to_millisecondsaudio(start_time)
end_ms = mmss_to_millisecondsaudio(end_time)

# Slice the audio
clip = song[start_ms:end_ms]
 
# Export new audio clip
export_path = os.path.join(job_folder, "audio_trimmed.wav")
clip.export(export_path, format="wav")
print("New Audio file is created and saved")

#'''
#----------------------------------------
imgurl = str(input("Enter Image URL"))
#---------------------------------------- DOWNLOADING PNG
#'''
image_save_path = f'jobs/job_{job_id:03}/cover.png'
response = requests.get(imgurl)
print(response)
if response.status_code == 200:
    img = Image.open(BytesIO(response.content))
    img.save(image_save_path)
else:
    print("BAD IMAGE LINK")
#'''
#--------------------------------------- EXTRACTING COLORS FROM PNG
#'''
image_import_path = f'jobs/job_{job_id:03}/cover.png'
text_export_path = f'jobs/job_{job_id:03}/4dominantcolours.txt'

extractionimg = ColorThief(image_import_path) # setup image for extraction

palette = extractionimg.get_palette(color_count=4) # getting the 4 most dominant colours

with open(text_export_path, 'w'): # removes previous 4 colours
    pass

for r,g,b in palette: 
    hexvalue = '#' + format(r,'02x') + format(g,'02x') + format(b,'02x')# convert rgb values into hex
    with open(text_export_path, 'a') as file: # append values into output file
        file.write(hexvalue + '\n')
#'''
#-------------------------------------- Taking in lyrics
#'''
initial_list = []
final_list = []

lyric_export_path = f'jobs/job_{job_id:03}/lyrics.txt'

with open(lyric_export_path, 'w'): # removes previous lyrics
    pass

def MMSS_Seconds(time_str):# converting from MMSS format to seconds for AE marker compatibility
    m, s = map(float, time_str.split(':'))
    return m * 60 + s

print("Enter lyrics in the format 'MM:SS lyric' ")
print("When your finished typing lyrics type finish")
print("If you mess up lyric input then type reset")

while True:
    line = input(" >>Enter>> ").strip()

    if line.lower() == 'finish':#self explanatory
        break

    if line.lower() == 'reset':
        initial_list.clear()
        print("List has been reset")
        continue

    try:   
        time_str,lyric_text = line.split(" ",1)#split the line ONCE into two sections, the time (before the space) and the lyrics (after)
    except ValueError:
        print("not the correct format")
        continue
   
    t= MMSS_Seconds(time_str) #assigning a variable to time input from user
    initial_list.append({'t':t, 'cur': lyric_text}) # appending this final structure to the list


for i, lyric in enumerate(initial_list):
    prev=initial_list[i-1]["cur"] if i>0 else ""
    curr = lyric["cur"]
    next1= initial_list[i+1]["cur"] if i+1 < len(initial_list) else ""
    next2= initial_list[i+2]["cur"] if i+2 < len(initial_list) else ""

    final_list.append({
        "t": lyric["t"] ,
        "lyric_prev": prev,
        "lyric_current": curr,
        "lyric_next1": next1,
        "lyric_next2": next2 ,
    })

with open(lyric_export_path, 'a') as file: # append values into output file
        json.dump(final_list, file, indent=4)
for i,l in enumerate(final_list,start=1):
    print(f"{l}")
#'''


#-------------------------GENERATING JSON FILE FROM ALL DATA----------------------------------------