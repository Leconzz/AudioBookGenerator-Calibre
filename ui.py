import sys
import os
import time

# Add vendor directory to sys.path
plugin_path = os.path.dirname(__file__)
vendor_path = os.path.join(plugin_path, 'vendor')
if vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

from calibre.gui2.actions import InterfaceAction
from calibre.gui2 import error_dialog, question_dialog, info_dialog, Dispatcher
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre_plugins.audiobook_generator.config import prefs

from qt.core import QImage, QPainter, QBuffer, QIODevice, Qt, QMenu

# Global reference to the plugin instance for the config dialog
_plugin_instance = None

def get_plugin_instance():
    return _plugin_instance

class InterfacePlugin(InterfaceAction):
    name = 'Audiobook Generator'
    
    # List of formats that this plugin can "process". 
    # Adding MP3 here helps Calibre understand that this plugin 
    # is interested in these formats for actions like "Send to device".
    supported_formats = ['mp3', 'm4b']
    
    action_spec = ('Audiobook Generator', None, 
                   'Generate audiobooks from ebooks using TTS', None)
    
    def genesis(self):
        global _plugin_instance
        _plugin_instance = self
        
        if hasattr(self, 'interface_action_base_plugin'):
            self.interface_action_base_plugin.actual_plugin_object = self
        
        icon = get_icons('images/icon.png')
        if icon:
            self.qaction.setIcon(icon)
        self.qaction.triggered.connect(self.show_dialog)
        
        # 1. Configure Action in toolbar menu
        self.config_action = self.create_action(
            spec=('Configure Plugin', 'config.png', 'Change plugin settings', None),
            attr='configure_plugin'
        )
        self.config_action.triggered.connect(self.do_config)
        
        self.menu = QMenu(self.gui)
        self.menu.addAction(self.config_action)
        self.qaction.setMenu(self.menu)

    def do_config(self):
        if hasattr(self, 'interface_action_base_plugin'):
            self.interface_action_base_plugin.do_user_config(self.gui)
        else:
            self.gui.iactions['Preferences'].do_config('plugins', self.name)

    def show_dialog(self):
        ids = self.gui.library_view.get_selected_ids()
        if not ids:
            return error_dialog(self.gui, 'No book selected', 
                                'Please select a book first.', show=True)
        
        if len(ids) > 1:
            return error_dialog(self.gui, 'Multiple books selected', 
                                'Please select only one book at a time.', show=True)

        db = self.gui.current_db
        book_id = ids[0]
        mi = db.get_metadata(book_id, index_is_id=True)
        title = mi.title
        
        language = prefs['language']
        if prefs['detect_language'] and mi.languages:
            l = mi.languages[0].lower()
            if l.startswith('en') or l == 'eng':
                language = 'English'
            elif l.startswith('es') or l == 'spa':
                # Map to Spain if specifically es-es or spa-es, else Latam
                if l == 'es-es' or l == 'spa-es':
                    language = 'Spanish (Spain)'
                else:
                    language = 'Spanish (Latam)'
            elif l.startswith('pt') or l == 'por':
                language = 'Portuguese'
            elif l.startswith('fr') or l == 'fra' or l == 'fre':
                language = 'French'
            elif l.startswith('it') or l == 'ita':
                language = 'Italian'

        engine = prefs['tts_engine']
        gender = prefs['voice_gender']
        output_format = prefs['output_format']

        epub_path = db.new_api.format_abspath(book_id, 'EPUB')
        est_message = ""
        
        if epub_path and os.path.exists(epub_path):
            try:
                from calibre.ebooks.oeb.polish.container import get_container
                from bs4 import BeautifulSoup
                container = get_container(epub_path)
                spine_names = [x[0] if isinstance(x, (list, tuple)) else x for x in container.spine_names]
                total_text_len = 0
                for name in spine_names:
                    mime = container.mime_map.get(name)
                    if mime in {'text/html', 'application/xhtml+xml'}:
                        raw = container.raw_data(name)
                        soup = BeautifulSoup(raw, 'html.parser')
                        for tag in soup(["script", "style", "img", "image", "svg", "video", "audio", "iframe"]):
                            tag.decompose()
                        text = soup.get_text(separator=' ', strip=True)
                        if text:
                            title_tag = soup.find(['h1', 'h2', 'h3'])
                            title_text = title_tag.get_text().strip() if title_tag else ""
                            total_text_len += len(f"{title_text}\n\n{text}\n\n")
                
                chunk_size = 5000
                num_chunks = (total_text_len // chunk_size) + (1 if total_text_len % chunk_size > 0 else 0)
                total_seconds = num_chunks * 7
                est_minutes = int(total_seconds / 60)
                est_message = f"Estimated time: ~{total_seconds if total_seconds < 60 else est_minutes} {'seconds' if total_seconds < 60 else 'minutes'} ({num_chunks} chunks)."
            except:
                est_message = "Estimation unavailable."

        msg = (f'\nDo you want to generate an {output_format} version of "{title}"?\n\n'
               f'Engine: {engine} ({language}, {gender})\n'
               f'{est_message}\n\n'
               'The process runs in the background. You can monitor progress in the "Jobs" spinner.'
               '\n' + '\n' * 6)

        if question_dialog(self.gui, 'Generate Audiobook', msg):
            self.start_background_job(book_id, title, language, engine, gender, output_format)

    def start_background_job(self, book_id, title, language, engine, gender, output_format):
        from calibre_plugins.audiobook_generator.worker import main as worker_main
        db = self.gui.current_db.new_api
        epub_path = db.format_abspath(book_id, 'EPUB')
        if not epub_path:
            return error_dialog(self.gui, 'No EPUB found', 'This book does not have an EPUB format.', show=True)

        import tempfile
        temp_dir = tempfile.mkdtemp(prefix='calibre_audiobook_out_')
        temp_output = os.path.join(temp_dir, f'output.{output_format.lower()}')

        ffmpeg_path = self.get_ffmpeg_path()
        split_by_volume = prefs.get('split_by_volume', False)

        VOICE_MAPPING = {
            'English': {'Male': 'en-US-EricNeural', 'Female': 'en-US-AriaNeural', 'lang': 'en'},
            'Spanish (Latam)': {'Male': 'es-MX-JorgeNeural', 'Female': 'es-MX-DaliaNeural', 'lang': 'es'},
            'Spanish (Spain)': {'Male': 'es-ES-AlvaroNeural', 'Female': 'es-ES-ElviraNeural', 'lang': 'es'},
            'Portuguese': {'Male': 'pt-PT-DuarteNeural', 'Female': 'pt-PT-RaquelNeural', 'lang': 'pt'},
            'French': {'Male': 'fr-FR-HenriNeural', 'Female': 'fr-FR-DeniseNeural', 'lang': 'fr'},
            'Italian': {'Male': 'it-IT-DiegoNeural', 'Female': 'it-IT-ElsaNeural', 'lang': 'it'}
        }
        
        mapping = VOICE_MAPPING.get(language, VOICE_MAPPING['English'])
        voice = mapping[gender] if engine == 'Edge TTS' else None
        lang_code = mapping['lang'] if engine != 'VibeVoice' else None
        audio_quality = prefs.get('audio_quality', 'Low')

        callback = Dispatcher(self.on_job_finished)

        job = ThreadedJob('audiobook_gen', f'Generating audiobook for "{title}"', worker_main, 
                          [epub_path, temp_output, voice, engine, lang_code, vendor_path, book_id, output_format, audio_quality,
                           ffmpeg_path, split_by_volume], {}, 
                          callback)
        self.gui.job_manager.run_threaded_job(job)
        self.gui.status_bar.show_message(f'Audiobook Generator: Background job started for "{title}"', 3000)

    def on_job_finished(self, job):
        if job.failed:
            self.gui.status_bar.show_message('Audiobook Generator: Job failed!', 10000)
            return

        try:
            success, result_data = job.result
            book_id, output_format, result_val = result_data
        except: return

        if not success:
            if isinstance(result_val, str) and result_val.startswith("VOLUME_PLAN_GENERATED:"):
                msg = result_val[len("VOLUME_PLAN_GENERATED:"):].strip()
                info_dialog(self.gui, 'Volume Plan Created', msg, show=True)
                self.gui.status_bar.show_message('Audiobook Generator: Volume plan created — edit and run again.', 10000)
            else:
                self.gui.status_bar.show_message(f"Audiobook Generator: FAILED - {result_val}", 10000)
            return

        import shutil
        output_paths = result_val if isinstance(result_val, list) else [result_val]
        multi_volume = len(output_paths) > 1
        temp_dir = os.path.dirname(output_paths[0])

        try:
            db = self.gui.current_db.new_api
            storage_mode = prefs.get('storage_mode', 'Internal')
            unified_path = prefs.get('unified_folder_path', '')
            mi = db.get_metadata(book_id)
            safe_title = "".join([c for c in mi.title if c.isalnum() or c in (' ', '-', '_')]).strip()
            safe_author = "".join([c for c in mi.authors[0] if c.isalnum() or c in (' ', '-', '_')]).strip()

            for i, path in enumerate(output_paths):
                vol_suffix = f" - Vol {i + 1}" if multi_volume else ""

                if storage_mode == 'External' and unified_path and os.path.exists(unified_path):
                    filename = f"{safe_title}{vol_suffix} - {safe_author}.{output_format.lower()}"
                    shutil.move(path, os.path.join(unified_path, filename))
                elif i == 0:
                    # First (or only) file is registered as the book's actual Calibre format.
                    with open(path, 'rb') as f:
                        db.add_format(book_id, output_format, f, replace=True)
                    os.remove(path)
                else:
                    # Calibre only tracks one file per format per book, so additional
                    # volumes are placed directly in the book's own folder as extra files.
                    book_dir = os.path.dirname(db.format_abspath(book_id, output_format))
                    filename = f"{safe_title}{vol_suffix}.{output_format.lower()}"
                    shutil.move(path, os.path.join(book_dir, filename))

            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

            self.apply_emblem_to_book(book_id)
            msg = (f'Audiobook Generator: SUCCESS - {len(output_paths)} volumes saved.'
                   if multi_volume else 'Audiobook Generator: SUCCESS - Finished and saved.')
            self.gui.status_bar.show_message(msg, 10000)
        except Exception as e:
            self.gui.status_bar.show_message(f"Audiobook Generator: Error - {str(e)}", 10000)

    def has_audio_format(self, book_id):
        db = self.gui.current_db.new_api
        formats = db.formats(book_id)
        if 'MP3' in formats or 'M4B' in formats:
            return True
        
        # Check external folder if configured
        storage_mode = prefs.get('storage_mode', 'Internal')
        unified_path = prefs.get('unified_folder_path', '')
        if storage_mode == 'External' and unified_path and os.path.exists(unified_path):
            mi = db.get_metadata(book_id)
            safe_title = "".join([c for c in mi.title if c.isalnum() or c in (' ', '-', '_')]).strip()
            safe_author = "".join([c for c in mi.authors[0] if c.isalnum() or c in (' ', '-', '_')]).strip()
            for ext in ('mp3', 'm4b'):
                filename = f"{safe_title} - {safe_author}.{ext}"
                if os.path.exists(os.path.join(unified_path, filename)):
                    return True
        return False

    def remove_emblem_from_book(self, book_id):
        """Attempts to restore original cover from ebook file if audio is missing."""
        if self.has_audio_format(book_id):
            return

        db = self.gui.current_db.new_api
        formats = db.formats(book_id)
        
        from calibre.ebooks.metadata.meta import get_metadata
        for fmt in formats:
            path = db.format_abspath(book_id, fmt)
            if path and os.path.exists(path):
                try:
                    with open(path, 'rb') as f:
                        mi = get_metadata(f, stream_type=fmt.lower())
                    cover_data = None
                    if mi.cover_data and mi.cover_data[1]:
                        cover_data = mi.cover_data[1]
                    elif mi.cover and os.path.exists(mi.cover):
                        with open(mi.cover, 'rb') as cf:
                            cover_data = cf.read()
                    if cover_data:
                        db.set_cover({book_id: cover_data})
                        self.gui.library_view.model().refresh_ids([book_id])
                        return
                except: continue

    def sync_all_icons(self):
        """Runs library sync in a background thread to prevent UI freeze."""
        # Using a ThreadedJob for the sync as well
        def sync_worker(db, book_ids, notifications, abort, log, has_audio_func):
            add_count = 0
            rem_count = 0
            total = len(book_ids)
            for i, bid in enumerate(book_ids):
                if abort.is_set(): break
                if has_audio_func(bid):
                    add_count += 1
                else:
                    rem_count += 1
                if i % 10 == 0:
                    notifications.put((i/total, f"Scanning book {i} of {total}..."))
            return add_count, rem_count, book_ids

        db = self.gui.current_db.new_api
        ids = list(db.all_book_ids())
        
        # We'll do the actual drawing back in the GUI thread via the callback
        job = ThreadedJob('audiobook_sync', 'Syncing Audiobook Icons', sync_worker, 
                          [db, ids, self.has_audio_format], {}, Dispatcher(self.on_sync_finished))
        self.gui.job_manager.run_threaded_job(job)
        self.gui.status_bar.show_message('Audiobook Generator: Started library-wide sync...', 3000)

    def on_sync_finished(self, job):
        if job.failed:
            self.gui.status_bar.show_message('Audiobook Generator: Sync failed!', 5000)
            return
        
        add_count, rem_count, ids = job.result
        
        # Drawing must happen in GUI thread
        for bid in ids:
            if self.has_audio_format(bid):
                self.apply_emblem_to_book(bid)
            else:
                self.remove_emblem_from_book(bid)
                
        self.gui.status_bar.show_message(f'Audiobook Generator: Sync complete ({add_count} icons, {rem_count} cleared).', 10000)

    def apply_settings(self):
        pass

    def apply_emblem_to_book(self, book_id):
        """Adds a cassette emblem to the book cover."""
        db = self.gui.current_db.new_api
        cover_data = db.cover(book_id)
        if not cover_data:
            return
            
        try:
            img = QImage.fromData(cover_data)
            if img.isNull():
                return
                
            # Load cassette emblem
            emblem_path = os.path.join(plugin_path, 'images', 'cassette.png')
            if not os.path.exists(emblem_path):
                return
                
            emblem = QImage(emblem_path)
            if emblem.isNull():
                return
                
            # Scale emblem to a fraction of the cover size (e.g., 1/4 width)
            w = img.width() // 4
            h = (emblem.height() * w) // emblem.width()
            emblem = emblem.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            # Draw emblem on bottom right
            painter = QPainter(img)
            painter.drawImage(img.width() - w - 10, img.height() - h - 10, emblem)
            painter.end()
            
            # Save back to DB
            ba = QBuffer()
            ba.open(QIODevice.OpenModeFlag.WriteOnly)
            img.save(ba, "JPG")
            db.set_cover({book_id: ba.data()})
            self.gui.library_view.model().refresh_ids([book_id])
        except:
            pass

    def get_ffmpeg_path(self):
    # """ffmpeg.exe lives inside the plugin zip and can't be executed from there,
    # so extract it once to a real folder on disk and reuse it after that."""
        import tempfile
        cache_dir = os.path.join(tempfile.gettempdir(), 'calibre_audiobook_gen_bin')
        os.makedirs(cache_dir, exist_ok=True)
        exe_name = 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg'
        cached_path = os.path.join(cache_dir, exe_name)

        if not os.path.exists(cached_path):
            try:
                base_plugin = self.interface_action_base_plugin
                resource_name = f'vendor/bin/{exe_name}'
                resources = base_plugin.load_resources([resource_name])
                raw = resources.get(resource_name)
                if not raw:
                    return None
                with open(cached_path, 'wb') as f:
                    f.write(raw)
                if sys.platform != 'win32':
                    os.chmod(cached_path, 0o755)
            except Exception:
                return None

        return cached_path if os.path.exists(cached_path) else None
