import requests

API_BASE = "http://149.36.1.179:5004"
API_KEY = "YourSecretApiKeyForCaptionService123"  # لو فيه حماية برأس API Key

def test_health():
    print("🔍 Testing /health")
    r = requests.get(f"{API_BASE}/health")
    print("✅ Response:", r.text)

def test_gpu_status():
    print("🔍 Testing /gpu-status")
    r = requests.get(f"{API_BASE}/gpu-status")
    print("✅ Response:", r.text)

def test_system_stats():
    print("🔍 Testing /system-stats")
    r = requests.get(f"{API_BASE}/system-stats")
    print("✅ Response:", r.json())

def process_direct():
    print("🔍 Testing /process_direct (send video)")
    file_path = "/home/ubuntu/video-caption/sample2.mp4"  # تأكد إن الملف ده موجود
    try:
        with open(file_path, "rb") as f:
            files = {"video_file": f}  # ✅ التعديل هنا
            headers = {"x-api-key": API_KEY}
            r = requests.post(f"{API_BASE}/process_direct", files=files, headers=headers)
            print("✅ Status Code:", r.status_code)
            content_type = r.headers.get("Content-Type", "")
            print("✅ Content-Type:", content_type)
            if "video" in content_type:
                with open("result3.mp4", "wb") as out:
                    out.write(r.content)
                print("📥 Video saved as result.mp4")
            else:
                print("⚠️ Response is not a video. Response content:", r.text)
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")

if __name__ == "__main__":
    print("🎯 Starting API tests...\n")
    test_health()
    print()
    test_gpu_status()
    print()
    test_system_stats()
    print()
    process_direct()
