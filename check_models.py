
import os
import google.generativeai as genai

# Hardcoded key from app.py
API_KEY = "AIzaSyDa48eCwlAmnw0xrFXQZJaNzzH97I5MvPk"

genai.configure(api_key=API_KEY)

print("Listing available models:")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error listing models: {e}")
