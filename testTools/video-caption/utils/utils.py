ALLOWED_EXTENSIONS = {'mp4', 'mov', 'webm', 'mkv', 'avi'}
import shutil
import time
from deep_translator import GoogleTranslator # type: ignore
from pydub.utils import mediainfo # type: ignore
import logging
import cv2 
from moviepy.editor import VideoFileClip # type: ignore
from PIL import Image, ImageDraw, ImageFont # type: ignore
from pysrt import SubRipFile # type: ignore
import arabic_reshaper # type: ignore
from bidi.algorithm import get_display # type: ignore
import os
import numpy as np
import psutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FONT_FOLDER = os.getenv('FONT_FOLDER', '/app/fonts')

# Updated font paths with Arabic-supporting fonts first
font_paths_to_try = [
    # Arabic-supporting fonts (priority order)
    os.path.join(FONT_FOLDER, "NotoSansArabic-Regular.ttf"),
    os.path.join(FONT_FOLDER, "NotoSansArabic-Bold.ttf"),
    os.path.join(FONT_FOLDER, "Amiri-Regular.ttf"),
    os.path.join(FONT_FOLDER, "DejaVuSans.ttf"),
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    # Fallback fonts
    os.path.join(FONT_FOLDER, "Poppins-Bold.ttf"),
    "Poppins-Bold.ttf",
    os.path.join(FONT_FOLDER, "Arial.ttf"),
    "arial.ttf",
    "/System/Library/Fonts/Arial.ttf",  # macOS fallback
]

def find_best_font_for_text(text, font_size):
    """Find the best font that can render the given text"""
    has_arabic = any('\u0600' <= char <= '\u06FF' or '\u0750' <= char <= '\u077F' for char in text)
    
    for font_path in font_paths_to_try:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, font_size)
                
                # Test if font can render the text
                test_img = Image.new('RGB', (100, 50), 'white')
                test_draw = ImageDraw.Draw(test_img)
                
                # For Arabic text, prioritize Arabic fonts
                if has_arabic:
                    if any(arabic_indicator in font_path.lower() for arabic_indicator in 
                           ['arabic', 'noto', 'amiri', 'dejavu']):
                        logger.info(f"Selected Arabic-supporting font: {font_path}")
                        return font
                
                # Test rendering
                try:
                    if hasattr(test_draw, 'textbbox'):
                        test_draw.textbbox((0, 0), text[:10], font=font)
                    else:
                        test_draw.textsize(text[:10], font=font)
                    
                    logger.info(f"Selected font: {font_path}")
                    return font
                except Exception:
                    continue
                    
            except (IOError, OSError) as e:
                logger.debug(f"Could not load font {font_path}: {e}")
                continue
    
    # Fallback to default font
    logger.warning("No suitable TrueType font found, using default")
    try:
        return ImageFont.load_default()
    except:
        raise RuntimeError("Could not load any font")

def process_arabic_text(text):
    """Process Arabic text for proper display"""
    if not text or not text.strip():
        return ""
    
    try:
        # Check if text contains Arabic characters
        has_arabic = any('\u0600' <= char <= '\u06FF' or '\u0750' <= char <= '\u077F' for char in text)
        
        if has_arabic:
            # Reshape Arabic text for proper character connection
            reshaped_text = arabic_reshaper.reshape(text)
            # Apply bidirectional algorithm for proper text direction
            display_text = get_display(reshaped_text)
            logger.debug(f"Processed Arabic text: {text[:30]}... -> {display_text[:30]}...")
            return display_text
        else:
            return text
    except Exception as e:
        logger.error(f"Error processing Arabic text '{text[:30]}...': {e}")
        return text  # Return original text if processing fails

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_video_duration(file_path):
    try:
        info = mediainfo(file_path)
        return float(info['duration'])
    except Exception as e:
        logger.error(f"Pydub mediainfo error for {file_path}: {e}")
        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened(): return 0
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            cap.release()
            return duration
        except Exception as e_cv2:
            logger.error(f"OpenCV duration error for {file_path}: {e_cv2}")
            return 0

def extract_audio(video_path, audio_path, job_id_log_prefix=""):
    """Extract audio with optimized settings"""
    logger.info(f"{job_id_log_prefix} Extracting audio from {video_path} to {audio_path}")
    
    try:
        video = VideoFileClip(video_path)
        video.audio.write_audiofile(
            audio_path, 
            codec='pcm_s16le',
            ffmpeg_params=["-ar", "16000"],  # Whisper's preferred sample rate
            verbose=False,
            logger=None
        )
        video.close()
        logger.info(f"{job_id_log_prefix} Audio extracted successfully")
    except Exception as e:
        logger.error(f"{job_id_log_prefix} Audio extraction failed: {e}")
        raise

def translate_srt(original_srt_path, target_lang, translated_srt_path, job_id_log_prefix=""):
    """Translate SRT with error handling and batching"""
    if target_lang.lower() in ['en', 'english']:
        logger.info(f"{job_id_log_prefix} Target is English, skipping translation.")
        shutil.copyfile(original_srt_path, translated_srt_path)
        return
        
    logger.info(f"{job_id_log_prefix} Translating {original_srt_path} to {target_lang}")
    
    try:
        subs = SubRipFile.open(original_srt_path, encoding='utf-8')
        translator = GoogleTranslator(source='auto', target=target_lang)
        
        texts_to_translate = []
        for sub in subs:
            if sub.text.strip():
                texts_to_translate.append(sub.text)
        
        if texts_to_translate:
            try:
                batch_size = 10
                translated_texts = []
                
                for i in range(0, len(texts_to_translate), batch_size):
                    batch = texts_to_translate[i:i+batch_size]
                    batch_results = []
                    
                    for text in batch:
                        try:
                            translated = translator.translate(text)
                            batch_results.append(translated if translated else text)
                            time.sleep(0.1)  # Small delay to avoid rate limits
                        except Exception as e_trans:
                            logger.warning(f"{job_id_log_prefix} Translation failed for '{text[:30]}...': {e_trans}")
                            batch_results.append(text)
                    
                    translated_texts.extend(batch_results)
                
                text_idx = 0
                for sub in subs:
                    if sub.text.strip():
                        if text_idx < len(translated_texts):
                            sub.text = translated_texts[text_idx]
                            text_idx += 1
                
            except Exception as e:
                logger.error(f"{job_id_log_prefix} Batch translation failed: {e}")
                for sub in subs:
                    try:
                        if sub.text.strip():
                            translated = translator.translate(sub.text)
                            sub.text = translated if translated else sub.text
                    except Exception as e_trans:
                        logger.warning(f"{job_id_log_prefix} Individual translation failed for '{sub.text[:30]}...': {e_trans}")
        
        subs.save(translated_srt_path, encoding='utf-8')
        logger.info(f"{job_id_log_prefix} Translation complete.")
        
    except Exception as e:
        logger.error(f"{job_id_log_prefix} Translation error: {e}")
        shutil.copyfile(original_srt_path, translated_srt_path)

def get_text_dimensions(text, font):
    """Get text dimensions with compatibility for different Pillow versions"""
    try:
        # For newer Pillow versions (>= 8.0.0)
        if hasattr(ImageDraw.Draw(Image.new('RGB', (1, 1))), 'textbbox'):
            test_img = Image.new('RGB', (1, 1), 'white')
            draw = ImageDraw.Draw(test_img)
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]  # width, height
        else:
            # For older Pillow versions
            test_img = Image.new('RGB', (1, 1), 'white')
            draw = ImageDraw.Draw(test_img)
            return draw.textsize(text, font=font)
    except Exception as e:
        logger.error(f"Error getting text dimensions: {e}")
        return 100, 30  # Fallback dimensions

def add_captions_to_video(video_path, srt_path, output_path, font_opts, job_id_log_prefix=""):
    """Add captions to video with enhanced Arabic support"""
    try:
        logger.info(f"{job_id_log_prefix} Adding captions from {srt_path} to {video_path}")
        
        if not all(os.path.exists(f) for f in [video_path, srt_path]):
            raise FileNotFoundError("Input video or SRT file not found")
        
        video = VideoFileClip(video_path)
        subs = SubRipFile.open(srt_path, encoding='utf-8')
        
        font_name = font_opts.get('family', 'Arial.ttf')
        font_size = max(font_opts.get('size', 32), 16)  # Increased default size
        font_color = font_opts.get('color', '#FFFFFF')

        def text_overlay_func(get_frame, t):
            """Process each frame to add captions with proper Arabic handling"""
            try:
                frame_array = get_frame(t)
                img = Image.fromarray(frame_array)
                draw = ImageDraw.Draw(img)
                
                active_texts = []
                for sub in subs:
                    start = sub.start.ordinal / 1000.0
                    end = sub.end.ordinal / 1000.0
                    if start <= t <= end:
                        text = sub.text.strip()
                        if text:
                            # Process Arabic text properly
                            processed_text = process_arabic_text(text)
                            active_texts.append(processed_text)
                
                if not active_texts:
                    return np.array(img)
                
                full_caption = " ".join(active_texts)
                
                # Find best font for this text
                font = find_best_font_for_text(full_caption, font_size)
                
                # Text wrapping
                max_width = int(img.width * 0.9)
                lines = []
                words = full_caption.split()
                current_line = ""
                
                for word in words:
                    test_line = f"{current_line} {word}" if current_line else word
                    text_width = get_text_dimensions(test_line, font)[0]
                    
                    if text_width <= max_width:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                
                if current_line:
                    lines.append(current_line)
                
                # Calculate positioning
                line_height = get_text_dimensions("A", font)[1] + 8  # Add padding
                total_text_height = len(lines) * line_height
                margin = max(int(img.height * 0.08), 20)  # Adaptive margin
                base_y = img.height - total_text_height - margin
                
                # Styling
                stroke_width = max(2, font_size // 12)
                stroke_color = (0, 0, 0, 255)  # Black stroke
                
                # Parse color
                if font_color.startswith('#'):
                    color_hex = font_color.lstrip('#')
                    if len(color_hex) == 6:
                        text_color = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
                    else:
                        text_color = (255, 255, 255)  # Default white
                else:
                    # Handle named colors
                    color_map = {
                        'white': (255, 255, 255),
                        'black': (0, 0, 0),
                        'red': (255, 0, 0),
                        'green': (0, 255, 0),
                        'blue': (0, 0, 255),
                        'yellow': (255, 255, 0),
                        'cyan': (0, 255, 255),
                        'magenta': (255, 0, 255),
                    }
                    text_color = color_map.get(font_color.lower(), (255, 255, 255))
                
                # Draw text with outline
                for i, line in enumerate(lines):
                    if not line:
                        continue
                    
                    text_width = get_text_dimensions(line, font)[0]
                    x = (img.width - text_width) // 2
                    y = base_y + (i * line_height)
                    
                    # Draw stroke/outline
                    for dx in range(-stroke_width, stroke_width + 1):
                        for dy in range(-stroke_width, stroke_width + 1):
                            if dx != 0 or dy != 0:
                                draw.text((x + dx, y + dy), line, font=font, fill=stroke_color)
                    
                    # Draw main text
                    draw.text((x, y), line, font=font, fill=text_color)
                
                return np.array(img)
            
            except Exception as e:
                logger.error(f"{job_id_log_prefix} Error processing frame at {t}s: {str(e)}")
                return get_frame(t)
        
        logger.info(f"{job_id_log_prefix} Starting video processing...")
        captioned_clip = video.fl(text_overlay_func, apply_to=['video'])
        
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        thread_count = min(psutil.cpu_count(), 16)  # Don't use all cores
        
        captioned_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            threads=thread_count,
            preset='fast',  # Faster preset for GPU deployment
            ffmpeg_params=[
                "-crf", "20",  # Higher quality
                "-movflags", "+faststart",  # Web optimization
                "-pix_fmt", "yuv420p"  # Compatibility
            ],
            verbose=False,
            logger=None
        )
        
        logger.info(f"{job_id_log_prefix} Successfully created captioned video: {output_path}")
        
    except Exception as e:
        logger.error(f"{job_id_log_prefix} Error in add_captions_to_video: {str(e)}", exc_info=True)
        raise
    finally:
        # Ensure resources are cleaned up
        if 'video' in locals():
            video.close()
        if 'captioned_clip' in locals():
            captioned_clip.close()