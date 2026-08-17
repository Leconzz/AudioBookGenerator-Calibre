import sys
import os
import shutil
import asyncio
import traceback
import time
import re
import unicodedata

# def main(epub_path, output_path, voice, engine, lang_code, vendor_path, book_id, output_format, audio_quality, notifications, abort, log):
#     """
#     Worker function for concurrent audiobook generation using asyncio.
#     """
#     if vendor_path not in sys.path:
#         sys.path.insert(0, vendor_path)

#     try:
#         log(f"Starting conversion for book ID: {book_id} (Quality: {audio_quality})")

#         # 1. Extract text
#         notifications.put((0.05, "Extracting text..."))
#         text = extract_content_robust(epub_path, log)
#         if not text:
#             return False, (book_id, output_format, "Could not extract text.")

#         text = clean_text_for_tts(text)
#         log(f"Cleaned text length: {len(text)} characters")
        
#         # 2. Prepare chunks (5000 chars per chunk)
#         chunk_size = 5000
#         text_chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
#         total_chunks = len(text_chunks)
#         log(f"Total chunks: {total_chunks}")

#         # 3. Concurrent generation using asyncio
#         async def run_concurrent_tts():
#             # Limit concurrency to avoid getting blocked (e.g., 3 concurrent requests)
#             semaphore = asyncio.Semaphore(3)
            
#             if os.path.exists(output_path):
#                 os.remove(output_path)

#             # We will store raw audio data in a list to keep them in order
#             audio_segments = [None] * total_chunks
#             completed = [0] # Use a list for mutable closure

#             async def fetch_chunk(index, chunk_text):
#                 async with semaphore:
#                     if abort.is_set(): return
                    
#                     try:
#                         data = b""
#                         if engine == 'Edge TTS':
#                             import edge_tts
#                             communicate = edge_tts.Communicate(chunk_text, voice)
#                             async for message in communicate.stream():
#                                 if message["type"] == "audio":
#                                     data += message["data"]
#                         elif engine == 'VibeVoice':
#                             # VibeVoice - Local model (must be installed system-wide), run in executor
#                             def run_vibevoice():
#                                 import tempfile
#                                 import os
#                                 import sys
#                                 import torch
                                
#                                 # VibeVoice must be installed system-wide (pip install vibevoice)
#                                 # Model must be downloaded to ~/vibevoice_model or specified path
#                                 model_path = os.path.expanduser("~/vibevoice_model")
#                                 if not os.path.exists(model_path):
#                                     raise Exception("VibeVoice model not found. Run: huggingface-cli download microsoft/VibeVoice-1.5B --local-dir ~/vibevoice_model")
                                
#                                 from transformers import AutoProcessor, AutoModelForCausalLM
#                                 processor = AutoProcessor.from_pretrained(model_path)
#                                 model = AutoModelForCausalLM.from_pretrained(
#                                     model_path,
#                                     torch_dtype=torch.float16,
#                                     device_map="auto"
#                                 )
                                
#                                 model.eval()
#                                 inputs = processor(text=chunk_text, return_tensors="pt")
#                                 inputs = {k: v.to(model.device) if torch.is_tensor(v) else v for k, v in inputs.items()}
                                
#                                 with torch.no_grad():
#                                     outputs = model.generate(**inputs, max_new_tokens=2048)
                                
#                                 audio_path = processor.save_audio(outputs.speech_outputs[0]) if hasattr(outputs, 'speech_outputs') else processor.decode_audio(outputs)[0]
                                
#                                 with open(audio_path if isinstance(audio_path, str) else tempfile.mktemp(suffix='.wav'), "rb") as rf:
#                                     result = rf.read()
                                
#                                 if os.path.exists(audio_path) and isinstance(audio_path, str):
#                                     os.unlink(audio_path)
                                
#                                 return result
                            
#                             data = await asyncio.get_event_loop().run_in_executor(None, run_vibevoice)
                            
#                         else:
#                             # gTTS - Not natively async, run in executor
#                             from gtts import gTTS
#                             def run_gtts():
#                                 import tempfile
#                                 tts = gTTS(text=chunk_text, lang=lang_code)
#                                 fd, path = tempfile.mkstemp(suffix='.mp3')
#                                 os.close(fd)
#                                 try:
#                                     tts.save(path)
#                                     with open(path, "rb") as rf:
#                                         return rf.read()
#                                 finally:
#                                     os.unlink(path)
                            
#                             data = await asyncio.get_event_loop().run_in_executor(None, run_gtts)
#                             await asyncio.sleep(0.5) # Rate limit safety

#                         audio_segments[index] = data
#                         completed[0] += 1
#                         notifications.put((0.1 + (completed[0] / total_chunks * 0.8), 
#                                          f"Downloaded {completed[0]} of {total_chunks} segments..."))
#                     except Exception as e:
#                         log(f"Error in chunk {index}: {str(e)}")

#             if engine == 'VibeVoice':
#                 try:
#                     import torch, transformers
#                 except ImportError:
#                     log("ERROR: VibeVoice requires 'torch' and 'transformers', which are not bundled with "
#                         "this plugin (they are multi-GB, platform-specific packages). Install them into "
#                         "Calibre's own Python environment, then retry. See the plugin README for install "
#                         "instructions.")
#                     return

#             # Create tasks
#             tasks = [fetch_chunk(i, chunk) for i, chunk in enumerate(text_chunks)]
#             await asyncio.gather(*tasks)
            
#             # Unify in order
#             log("Assembling audio file...")
#             with open(output_path, "wb") as f:
#                 for segment in audio_segments:
#                     if segment:
#                         f.write(segment)

#         # Run the async loop
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
#         try:
#             loop.run_until_complete(run_concurrent_tts())
#         finally:
#             loop.close()

#         if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
#             strip_audio_tags(output_path, vendor_path)
#             log("SUCCESS: Generation finished.")
#             return True, (book_id, output_format, output_path)
#         else:
#             return False, (book_id, output_format, "Audio generation failed or was aborted.")

#     except Exception as e:
#         log(f"CRITICAL ERROR: {traceback.format_exc()}")
#         return False, (book_id, output_format, str(e))
    
def main(epub_path, output_path, voice, engine, lang_code, vendor_path, book_id, output_format, audio_quality, ffmpeg_path, notifications, abort, log):
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)

    try:
        log(f"Starting conversion for book ID: {book_id} (Quality: {audio_quality})")

        notifications.put((0.05, "Extracting chapters..."))
        chapters = extract_chapters(epub_path, log)

        metadata = extract_epub_metadata(epub_path, log)
        log(f"Metadata: title='{metadata['title']}', author='{metadata['author']}', cover={'found' if metadata['cover_path'] else 'none'}")

        if not chapters:
            return False, (book_id, output_format, "Could not extract chapters.")

        for ch in chapters:
            ch['text'] = clean_text_for_tts(ch['text'])
        log(f"Found {len(chapters)} chapters")

        chunk_size = 5000
        for ch in chapters:
            local_chunks = [ch['text'][i:i+chunk_size] for i in range(0, len(ch['text']), chunk_size)] or ['']
            ch['chunks'] = local_chunks
            ch['audio_parts'] = [None] * len(local_chunks)

        total_chunks = sum(len(ch['chunks']) for ch in chapters)
        log(f"Total chunks: {total_chunks}")

        async def run_concurrent_tts():
            semaphore = asyncio.Semaphore(3)
            completed = [0]

            async def fetch_chunk(c_idx, local_idx, chunk_text):
                async with semaphore:
                    if abort.is_set(): return
                    try:
                        data = b""
                        if engine == 'Edge TTS':
                            import edge_tts
                            communicate = edge_tts.Communicate(chunk_text, voice)
                            async for message in communicate.stream():
                                if message["type"] == "audio":
                                    data += message["data"]
                        elif engine == 'VibeVoice':
                            # keep the existing VibeVoice run_vibevoice() block here, unchanged
                            #pass
                            raise NotImplementedError("VibeVoice support was not carried over in this build.")
                        else:
                            from gtts import gTTS
                            def run_gtts():
                                import tempfile
                                tts = gTTS(text=chunk_text, lang=lang_code)
                                fd, path = tempfile.mkstemp(suffix='.mp3')
                                os.close(fd)
                                try:
                                    tts.save(path)
                                    with open(path, "rb") as rf:
                                        return rf.read()
                                finally:
                                    os.unlink(path)
                            data = await asyncio.get_event_loop().run_in_executor(None, run_gtts)

                        await asyncio.sleep(0.5)
                        chapters[c_idx]['audio_parts'][local_idx] = data
                        completed[0] += 1
                        notifications.put((0.1 + (completed[0] / total_chunks * 0.7),
                                            f"Generating audio: chapter {c_idx + 1} of {len(chapters)} "
                                            f"({completed[0]} of {total_chunks} segments)"))
                    except Exception as e:
                        log(f"Error in chapter {c_idx} chunk {local_idx}: {str(e)}")

            tasks = [fetch_chunk(c_idx, l_idx, txt)
                     for c_idx, ch in enumerate(chapters)
                     for l_idx, txt in enumerate(ch['chunks'])]
            await asyncio.gather(*tasks)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_concurrent_tts())
        finally:
            loop.close()

        book_temp_dir = os.path.join(
            os.path.dirname(epub_path),
            f".audiobook_temp_{os.path.splitext(os.path.basename(epub_path))[0]}"
        )
        os.makedirs(book_temp_dir, exist_ok=True)
        log(f"Storing chapter audio in: {book_temp_dir}")

        chapter_files = []
        for i, ch in enumerate(chapters):
            audio = b"".join(p for p in ch['audio_parts'] if p)
            if not audio:
                continue
            path = os.path.join(book_temp_dir, f"chapter_{i:04d}.mp3")
            with open(path, 'wb') as f:
                f.write(audio)
            chapter_files.append({'path': path, 'title': ch['title']})

        if not chapter_files:
            return False, (book_id, output_format, "Audio generation failed or was aborted.")

        notifications.put((0.85, "Assembling audiobook..."))

        if output_format.upper() == 'M4B':
            ok = build_m4b(chapter_files, output_path, vendor_path, ffmpeg_path, metadata, notifications, log)
        else:
            with open(output_path, 'wb') as out:
                for cf in chapter_files:
                    with open(cf['path'], 'rb') as f:
                        out.write(f.read())
            ok = True

        if ok:
            try:
                shutil.rmtree(book_temp_dir)
            except Exception as e:
                log(f"Could not remove temp folder: {e}")
        else:
            log(f"Assembly failed — keeping {len(chapter_files)} chapter audio files so you don't have to redo TTS.")
            log(f"Location: {book_temp_dir}")

        if ok and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            if output_format.upper() != 'M4B':
                strip_audio_tags(output_path, vendor_path)
            log("SUCCESS: Generation finished.")
            return True, (book_id, output_format, output_path)
        else:
            return False, (book_id, output_format, "Audio generation failed or was aborted.")

    except Exception as e:
        log(f"CRITICAL ERROR: {traceback.format_exc()}")
        return False, (book_id, output_format, str(e))

    
def clean_text_for_tts(text):
    text = unicodedata.normalize('NFKC', text)
    replacements = {'\xad': '', '\u200b': '', '\ufeff': '', '“': '"', '”': '"', '‘': "'", '’': "'", '…': '...', '—': '-'}
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = "".join(c for c in text if unicodedata.category(c)[0] != 'C' or c in '\n\t')
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def strip_audio_tags(file_path, vendor_path):
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
    try:
        from mutagen.mp3 import MP3
        audio = MP3(file_path)
        audio.delete()
        audio.save()
    except: pass

# def extract_content_robust(epub_path, log):
    from calibre.ebooks.oeb.polish.container import get_container
    from bs4 import BeautifulSoup
    try:
        container = get_container(epub_path)
        all_text = []
        from calibre.ebooks.oeb.polish.cover import find_cover_page
        cover_page = None
        try: cover_page = find_cover_page(container)
        except: pass
        
        spine_names = [x[0] if isinstance(x, (list, tuple)) else x for x in container.spine_names]
        for name in spine_names:
            if cover_page and name == cover_page: continue
            mime = container.mime_map.get(name)
            if mime in {'text/html', 'application/xhtml+xml'}:
                try:
                    raw = container.raw_data(name)
                    soup = BeautifulSoup(raw, 'html.parser')
                    for tag in soup(["script", "style", "img", "image", "svg", "video", "audio", "iframe", "meta", "link"]):
                        tag.decompose()
                    title_tag = soup.find(['h1', 'h2', 'h3'])
                    title_text = title_tag.get_text().strip() if title_tag else ""
                    if title_tag: title_tag.decompose()
                    text = soup.get_text(separator=' ', strip=True)
                    if text or title_text:
                        if title_text: all_text.append(f"{title_text}. {text}. ")
                        else: all_text.append(f"{text}. ")
                except: continue
        return "".join(all_text)
    except: return None

def extract_chapters(epub_path, log):
    """Returns [{'title': str, 'text': str}, ...] — one entry per spine
    document, skipping the cover page and anything that looks like a TOC/nav page."""
    from calibre.ebooks.oeb.polish.container import get_container
    from bs4 import BeautifulSoup

    TOC_TITLE_HINTS = {'table of contents', 'contents', 'toc'}
    TOC_EXACT_NAME_HINTS = {'toc', 'nav', 'contents', 'tableofcontents', 'table_of_contents'}

    try:
        container = get_container(epub_path)
        chapters = []

        from calibre.ebooks.oeb.polish.cover import find_cover_page
        cover_page = None
        try: cover_page = find_cover_page(container)
        except: pass

        spine_names = [x[0] if isinstance(x, (list, tuple)) else x for x in container.spine_names]

        for name in spine_names:
            if cover_page and name == cover_page:
                continue
            name_stem = os.path.splitext(os.path.basename(name))[0].lower()
            if name_stem in TOC_EXACT_NAME_HINTS:
                log(f"Skipping likely TOC/nav page: {name}")
                continue

            mime = container.mime_map.get(name)
            if mime not in {'text/html', 'application/xhtml+xml'}:
                continue

            try:
                raw = container.raw_data(name)
                soup = BeautifulSoup(raw, 'html.parser')
                for tag in soup(["script", "style", "img", "image", "svg", "video", "audio", "iframe", "meta", "link"]):
                    tag.decompose()

                title_tag = soup.find(['h1', 'h2', 'h3'])
                title_text = title_tag.get_text().strip() if title_tag else ""
                if title_tag: title_tag.decompose()

                if title_text.lower() in TOC_TITLE_HINTS:
                    log(f"Skipping TOC page by heading: {name} ('{title_text}')")
                    continue

                text = soup.get_text(separator=' ', strip=True)
                if not text and not title_text:
                    continue

                chapters.append({
                    'title': title_text or f"Chapter {len(chapters) + 1}",
                    'text': f"{title_text}. {text}" if title_text else text
                })
            except Exception:
                continue

        return chapters
    except Exception:
        return None

def build_m4b(chapter_files, output_path, vendor_path, ffmpeg_path, metadata, notifications, log):
    import subprocess
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
    from mutagen.mp3 import MP3

    ffmpeg_exe = ffmpeg_path if ffmpeg_path and os.path.exists(ffmpeg_path) else 'ffmpeg'
    log(f"Using ffmpeg at: {ffmpeg_exe}")

    tmp_dir = os.path.dirname(output_path) or '.'
    concat_list_path = os.path.join(tmp_dir, 'concat_list.txt')
    chapters_meta_path = os.path.join(tmp_dir, 'chapters.txt')
    cover_path = metadata.get('cover_path')

    with open(concat_list_path, 'w', encoding='utf-8') as f:
        for cf in chapter_files:
            escaped = cf['path'].replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    # Track cumulative chapter boundaries (in ms) alongside writing the metadata file,
    # so we know both the total duration and which chapter any given timestamp falls in.
    chapter_boundaries = []  # [(end_ms, title), ...]
    with open(chapters_meta_path, 'w', encoding='utf-8') as f:
        f.write(";FFMETADATA1\n")
        if metadata.get('title'):
            f.write(f"title={metadata['title']}\n")
        if metadata.get('author'):
            f.write(f"artist={metadata['author']}\n")
            f.write(f"album_artist={metadata['author']}\n")
        f.write("\n")
        cursor_ms = 0
        for cf in chapter_files:
            try:
                length_s = MP3(cf['path']).info.length
            except Exception:
                length_s = 0
            start_ms = cursor_ms
            end_ms = cursor_ms + int(length_s * 1000)
            title = (cf['title'] or "Chapter").replace('\n', ' ').strip()
            f.write(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={start_ms}\nEND={end_ms}\ntitle={title}\n")
            chapter_boundaries.append((end_ms, title))
            cursor_ms = end_ms

    total_duration_ms = cursor_ms if chapter_boundaries else 1  # avoid div-by-zero
    log(f"Total audiobook duration: {total_duration_ms / 1000 / 60:.1f} minutes across {len(chapter_files)} chapters")

    cmd = [ffmpeg_exe, '-y', '-f', 'concat', '-safe', '0', '-i', concat_list_path]

    cover_index = None
    if cover_path and os.path.exists(cover_path):
        cmd += ['-i', cover_path]
        cover_index = 1

    chapters_input_index = 2 if cover_index is not None else 1
    cmd += ['-i', chapters_meta_path]
    cmd += ['-map_metadata', str(chapters_input_index)]
    cmd += ['-map', '0:a']
    if cover_index is not None:
        cmd += ['-map', f'{cover_index}:v', '-c:v', 'copy', '-disposition:v', 'attached_pic']
    cmd += ['-c:a', 'aac', '-b:a', '128k', '-f', 'mp4']
    cmd += ['-progress', 'pipe:1', '-nostats', output_path]

    def find_current_chapter(elapsed_ms):
        for end_ms, title in chapter_boundaries:
            if elapsed_ms <= end_ms:
                return title
        return chapter_boundaries[-1][1] if chapter_boundaries else ""

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in proc.stdout:
            line = line.strip()
            if line.startswith('out_time_ms='):
                try:
                    elapsed_ms = int(line.split('=')[1]) / 1000  # ffmpeg reports microseconds
                    pct = min(elapsed_ms / total_duration_ms, 1.0)
                    chapter_title = find_current_chapter(elapsed_ms)
                    notifications.put((0.85 + pct * 0.15,
                                        f"Encoding audiobook: {pct * 100:.0f}% (around \"{chapter_title}\")"))
                except (ValueError, IndexError, ZeroDivisionError):
                    pass

        proc.wait()
        stderr_output = proc.stderr.read()
        if proc.returncode != 0:
            log(f"ffmpeg error: {stderr_output[-2000:]}")
            return False
        return True
    except FileNotFoundError:
        log(f"ERROR: ffmpeg not found at '{ffmpeg_exe}' or on PATH.")
        return False
    finally:
        for p in (concat_list_path, chapters_meta_path, cover_path):
            if p:
                try: os.remove(p)
                except: pass

def extract_epub_metadata(epub_path, log):
    """Returns {'title': str|None, 'author': str|None, 'cover_path': str|None}."""
    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.ebooks.oeb.polish.cover import get_raster_cover_name
    from calibre.ebooks.metadata.opf2 import OPF
    import io, tempfile

    result = {'title': None, 'author': None, 'cover_path': None}
    try:
        container = get_container(epub_path)

        try:
            raw_opf = container.raw_data(container.opf_name, decode=False)
            opf = OPF(io.BytesIO(raw_opf), basedir=os.path.dirname(epub_path))
            result['title'] = opf.title
            authors = list(opf.authors) if opf.authors else []
            result['author'] = ' & '.join(authors) if authors else None
        except Exception as e:
            log(f"Could not read title/author: {e}")

        try:
            cover_name = get_raster_cover_name(container)
            if cover_name:
                cover_bytes = container.raw_data(cover_name, decode=False)
                ext = os.path.splitext(cover_name)[1] or '.jpg'
                fd, cover_path = tempfile.mkstemp(suffix=ext)
                os.close(fd)
                with open(cover_path, 'wb') as f:
                    f.write(cover_bytes)
                result['cover_path'] = cover_path
        except Exception as e:
            log(f"Could not extract cover image: {e}")

    except Exception as e:
        log(f"Could not open epub for metadata: {e}")

    return result
