import glob
import csv
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

print(f"CUDA available: {torch.cuda.is_available()}")
device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

model_id = "openai/whisper-large-v3-turbo"

model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id, torch_dtype=torch_dtype, low_cpu_mem_usage=True, use_safetensors=True
)
model.to(device)

processor = AutoProcessor.from_pretrained(model_id)

pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    max_new_tokens=128,
    chunk_length_s=30,
    batch_size=16,
    return_timestamps=True,
    torch_dtype=torch_dtype,
    device=device,
)

audio_files = glob.glob("audios/**/*.mp3", recursive=True)
results = pipe(audio_files)

with open("transcriptions.csv", "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["filepath", "korean_word"])
    for i, result in enumerate(results):
        writer.writerow([audio_files[i], result["korean_word"]])

print("Transcriptions saved to transcriptions.csv")