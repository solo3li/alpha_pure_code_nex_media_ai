import requests
import json
import os
import sys

class LahajatiTTS:
    def __init__(self, api_key):
        """
        Initialize the Lahajati TTS client.
        
        Args:
            api_key (str): Your Lahajati AI API Key.
        """
        self.api_key = api_key
        self.base_url = "https://lahajati.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json" 
        }

    def get_voices(self, page=1, per_page=100):
        """
        Fetches the list of available voices (Absolute Control).
        GET /voices-absolute-control
        """
        endpoint = f"{self.base_url}/voices-absolute-control"
        params = {"page": page, "per_page": per_page}
        return self._get_paginated_data(endpoint, params, "voices")

    def get_performance_styles(self, page=1, per_page=100):
        """
        Retrieves a list of available performance styles.
        GET /performance-absolute-control
        """
        endpoint = f"{self.base_url}/performance-absolute-control"
        params = {"page": page, "per_page": per_page}
        return self._get_paginated_data(endpoint, params, "performance styles")

    def get_dialects(self, page=1, per_page=100):
        """
        Retrieves a list of available dialects.
        GET /dialect-absolute-control
        """
        endpoint = f"{self.base_url}/dialect-absolute-control"
        params = {"page": page, "per_page": per_page}
        return self._get_paginated_data(endpoint, params, "dialects")

    def _get_paginated_data(self, endpoint, params, label):
        """Helper to handle GET requests for lists."""
        try:
            print(f"Fetching {label} from API...")
            response = requests.get(endpoint, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {label}: {e}")
            if 'response' in locals() and response.text:
                print(f"Server response: {response.text}")
            return []

    def generate_speech(self, text, voice_id, output_filename="output.mp3", 
                        mode="1", custom_prompt=None, performance_id=None, 
                        dialect_id=None, temperature=None):
        """
        Generates speech from text (POST /text-to-speech-absolute-control).
        
        Args:
            mode (str): "0" for Structured (uses perf/dialect IDs), "1" for Custom Prompt.
            temperature (float): 0.1 - 2.0 (Optional).
        """
        endpoint = f"{self.base_url}/text-to-speech-absolute-control"
        
        payload = {
            "text": text,
            "id_voice": voice_id,
            "input_mode": mode
        }

        # Add optional temperature
        if temperature is not None:
            payload["temperature"] = float(temperature)

        if mode == "1":
            # Custom Mode
            if not custom_prompt:
                custom_prompt = "Speak clearly and naturally."
            payload["custom_prompt_text"] = custom_prompt
            print(f"   > Mode: Custom | Prompt: '{custom_prompt}'")
        else:
            # Structured Mode
            if performance_id: payload["performance_id"] = performance_id
            if dialect_id: payload["dialect_id"] = dialect_id
            print(f"   > Mode: Structured | Perf ID: {performance_id} | Dialect ID: {dialect_id}")

        return self._send_audio_request(endpoint, payload, output_filename)

    def convert_speech_to_speech(self, audio_filepath, voice_id, output_filename="converted.mp3",
                                 stability=50, similarity_boost=95, style=0):
        """
        Converts an audio file to speech with another voice.
        POST /speech-to-speech-absolute-control
        """
        endpoint = f"{self.base_url}/speech-to-speech-absolute-control"
        
        if not os.path.exists(audio_filepath):
            print(f"   ❌ Error: Input file '{audio_filepath}' not found.")
            return False

        # Prepare Multipart Data
        try:
            with open(audio_filepath, 'rb') as f:
                files = {
                    'audio_file': (os.path.basename(audio_filepath), f, 'audio/mpeg') 
                    # Note: MIME type might need adjustment based on actual file input (wav/mp3)
                }
                
                # Non-file parameters go into 'data' for multipart requests
                data = {
                    "id_voice": voice_id,
                    "stability": stability,
                    "similarity_boost": similarity_boost,
                    "style": style
                }

                # Headers for multipart must NOT have Content-Type set manually (requests handles it)
                upload_headers = self.headers.copy()
                upload_headers.pop("Content-Type", None)

                print(f"   > Uploading '{audio_filepath}' for Speech-to-Speech conversion...")
                response = requests.post(endpoint, headers=upload_headers, files=files, data=data)
                
                return self._handle_audio_response(response, output_filename)

        except Exception as e:
            print(f"   ❌ Error preparing/sending file: {e}")
            return False

    def chat_completions(self, message, custom_prompt_message=None, temperature=1.0):
        """
        Generates intelligent responses using Arabic LLM.
        POST /chat/completions
        """
        endpoint = f"{self.base_url}/chat/completions"
        
        payload = {
            "message": message,
            "temperature": temperature
        }
        if custom_prompt_message:
            payload["custom_prompt_message"] = custom_prompt_message

        try:
            print(f"   > Sending Chat request...")
            response = requests.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result.get("message", "No message returned.")
            
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Chat Error: {e}")
            if 'response' in locals() and response.text:
                print(f"   Response: {response.text}")
            return None

    def _send_audio_request(self, endpoint, json_payload, output_filename):
        """Internal helper for JSON-based audio generation requests."""
        try:
            # Ensure Accept header specifically asks for audio here if needed, 
            # though usually endpoint dictates response.
            req_headers = self.headers.copy()
            req_headers["Accept"] = "audio/mpeg"

            response = requests.post(endpoint, headers=req_headers, json=json_payload)
            return self._handle_audio_response(response, output_filename)

        except requests.exceptions.RequestException as e:
            print(f"   Connection error: {e}")
            return False

    def _handle_audio_response(self, response, output_filename):
        """Internal helper to save audio or print errors."""
        if response.status_code == 200:
            with open(output_filename, 'wb') as f:
                f.write(response.content)
            print(f"   ✅ Success! Audio saved to: {output_filename}")
            return True
        else:
            print(f"   ❌ Failed. Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

# --- Main Execution Block ---
if __name__ == "__main__":
    print("--- Lahajati AI Complete Tool ---")
    
    api_key = "sk_eyJpdiI6Im5oRyt3Y1lXWmJGalhENU5ieGtjRmc9PSIsInZhbHVlIjoiVnRZWFB6TE5uS2s4eDQxWWUvYXQxWFFIblVVamsybm42ekU3KzF5dUNnSU9ONkJ2NDYwc3gwM1BMUCtBb3lLQSIsIm1hYyI6ImNjM2ZiNjIzMmIzOTQ4ZmZhYmEzMGE1YTU0NjI1YjFiNGNhMThhMjQyNjYwYTFkOTE1NDc4NWEyNDE5MGM3NjUiLCJ0YWciOiIifQ=="

    if not api_key:
        api_key = input("Enter your Lahajati API Key: ").strip()

    if not api_key:
        print("API Key is required.")
        sys.exit(1)

    client = LahajatiTTS(api_key)

    # Cache lists to avoid spamming API
    cached_voices = []
    
    def ensure_voices_loaded():
        if not cached_voices:
            print("\n--- Loading Voices ---")
            voices = client.get_voices()
            cached_voices.extend(voices)
            print(f"Loaded {len(cached_voices)} voices.")
            
            print("-" * 85)
            print(f"{'ID (Copy this)':<35} | {'Name':<30} | {'Gender'}")
            print("-" * 85)
            for v in cached_voices[:1000]:
                v_id = v.get('id_voice', v.get('id'))
                v_name = v.get('display_name', v.get('voice_name', v.get('name', 'Unknown')))
                v_gender = v.get('gender', 'N/A')
                if v_id: print(f"{v_id:<35} | {v_name:<30} | {v_gender}")
            if len(cached_voices) > 1000: print("... (more available)")
        return cached_voices

    while True:
        print("\n" + "="*40)
        print("       LAHAJATI MAIN MENU")
        print("="*40)
        print("1. Text-to-Speech (Custom Mode 1)")
        print("2. Text-to-Speech (Structured Mode 0)")
        print("3. Speech-to-Speech (Convert Audio)")
        print("4. Chat with Arabic LLM")
        print("5. List Voices")
        print("6. List Performance Styles & Dialects")
        print("7. Exit")
        
        try:
            choice = input("\nEnter choice (1-7): ").strip()
        except KeyboardInterrupt:
            break
        
        if choice == "7":
            print("Goodbye!")
            break

        # --- Option 1: TTS Custom ---
        elif choice == "1":
            ensure_voices_loaded()
            v_id = input("Paste Voice ID: ").strip()
            if not v_id and cached_voices: v_id = cached_voices[0].get('id_voice', cached_voices[0].get('id'))
            
            text = input("Enter text: ").strip()
            prompt = input("Custom Prompt (default: 'Speak naturally'): ").strip()
            temp = input("Temperature (0.1-2.0, default None): ").strip()
            temp = float(temp) if temp else None
            
            client.generate_speech(text, v_id, "tts_custom.mp3", mode="1", custom_prompt=prompt, temperature=temp)

        # --- Option 2: TTS Structured ---
        elif choice == "2":
            ensure_voices_loaded()
            v_id = input("Paste Voice ID: ").strip()
            
            # Fetch styles/dialects on demand
            styles = client.get_performance_styles()
            dialects = client.get_dialects()
            
            # DEBUG: Print first item to see keys if they are missing
            if styles:
                print(f"[DEBUG] Style Keys: {list(styles[0].keys())}")
            if dialects:
                print(f"[DEBUG] Dialect Keys: {list(dialects[0].keys())}")

            print("\n--- Available Styles ---")
            for s in styles[:1000]: 
                # Try all likely name keys
                s_name = s.get('display_name', s.get('performance_name', s.get('name_en', s.get('name', 'Unknown'))))
                print(f"ID: {s.get('id', s.get('performance_id'))} | Name: {s_name}")
            
            print("\n--- Available Dialects ---")
            for d in dialects[:1000]: 
                 # Try all likely name keys
                d_name = d.get('display_name', d.get('dialect_name', d.get('name_en', d.get('name', 'Unknown'))))
                print(f"ID: {d.get('id', d.get('dialect_id'))} | Name: {d_name}")
            
            p_id = input("\nEnter Performance ID: ").strip()
            d_id = input("Enter Dialect ID: ").strip()
            text = input("Enter text: ").strip()
            
            client.generate_speech(text, v_id, "tts_structured.mp3", mode="0", performance_id=p_id, dialect_id=d_id)

        # --- Option 3: Speech to Speech ---
        elif choice == "3":
            ensure_voices_loaded()
            v_id = input("Paste Target Voice ID: ").strip()
            input_file = input("Path to source audio file (e.g., input.mp3): ").strip()
            
            client.convert_speech_to_speech(input_file, v_id, "s2s_output.mp3")

        # --- Option 4: LLM Chat ---
        elif choice == "4":
            msg = input("Enter message for AI: ").strip()
            sys_prompt = input("Custom System Prompt (optional): ").strip()
            response = client.chat_completions(msg, custom_prompt_message=sys_prompt if sys_prompt else None)
            print(f"\n🤖 AI Response:\n{response}")

        # --- Option 5: List Voices ---
        elif choice == "5":
            ensure_voices_loaded() # Logic already inside prints list

        # --- Option 6: List Meta Data ---
        elif choice == "6":
            styles = client.get_performance_styles()
            print(f"\nFound {len(styles)} Styles. First 5 Raw Data:")
            for s in styles[:5]: print(s)
            
            dialects = client.get_dialects()
            print(f"\nFound {len(dialects)} Dialects. First 5 Raw Data:")
            for d in dialects[:5]: print(d)