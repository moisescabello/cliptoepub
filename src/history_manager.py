#!/usr/bin/env python3
"""
History Manager for Clipboard to ePub
Manages conversion history and multi-clip combining functionality
"""

import json
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from collections import deque
import threading
try:
    from src import paths as paths  # type: ignore
except Exception:
    import paths  # type: ignore

logger = logging.getLogger('HistoryManager')


class ConversionHistory:
    """Manages history of ePub conversions"""

    def __init__(self, history_file: Optional[Path] = None, max_entries: int = 100):
        """
        Initialize conversion history

        Args:
            history_file: Path to history JSON file
            max_entries: Maximum number of history entries to keep
        """
        if history_file is None:
            history_file = paths.get_history_path()

        self.history_file = history_file
        self.max_entries = max_entries
        self.history = deque(maxlen=max_entries)
        self.lock = threading.Lock()

        self.ensure_history_dir()
        self.load_history()

    def ensure_history_dir(self):
        """Create history directory if it doesn't exist"""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

    def load_history(self):
        """Load history from file"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = deque(data, maxlen=self.max_entries)
                logger.info(f"Loaded {len(self.history)} history entries")
        except Exception as e:
            logger.error(f"Error loading history: {e}")
            self.history = deque(maxlen=self.max_entries)

    def save_history(self):
        """Save history to file"""
        try:
            with self.lock:
                with open(self.history_file, 'w', encoding='utf-8') as f:
                    json.dump(list(self.history), f, indent=2, ensure_ascii=False)
            logger.debug("History saved")
        except Exception as e:
            logger.error(f"Error saving history: {e}")

    def add_entry(self, filepath: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a conversion entry to history

        Args:
            filepath: Path to created ePub file
            metadata: Metadata about the conversion

        Returns:
            The created history entry
        """
        entry = {
            'id': self.generate_id(),
            'timestamp': datetime.now().isoformat(),
            'filepath': str(filepath),
            'filename': Path(filepath).name,
            'title': metadata.get('title', 'Untitled'),
            'format': metadata.get('format', 'unknown'),
            'chapters': metadata.get('chapters', 1),
            'size': metadata.get('size', 0),
            'author': metadata.get('author', 'Unknown Author'),
            'source_hash': metadata.get('source_hash', ''),
            'tags': metadata.get('tags', [])
        }

        with self.lock:
            self.history.appendleft(entry)
        self.save_history()

        logger.info(f"Added to history: {entry['title']}")
        return entry

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent conversion entries

        Args:
            limit: Number of entries to return

        Returns:
            List of recent history entries
        """
        with self.lock:
            return list(self.history)[:limit]

    def get_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        Get history entry by ID

        Args:
            entry_id: Entry ID

        Returns:
            History entry or None if not found
        """
        with self.lock:
            for entry in self.history:
                if entry['id'] == entry_id:
                    return entry
        return None

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search history entries

        Args:
            query: Search query

        Returns:
            Matching history entries
        """
        query = query.lower()
        results = []

        with self.lock:
            for entry in self.history:
                if (query in entry.get('title', '').lower() or
                    query in entry.get('filename', '').lower() or
                    query in entry.get('author', '').lower() or
                    any(query in tag.lower() for tag in entry.get('tags', []))):
                    results.append(entry)

        return results

    def clear_old_entries(self, days: int = 30):
        """
        Clear entries older than specified days

        Args:
            days: Number of days to keep
        """
        cutoff = datetime.now() - timedelta(days=days)
        new_history = deque(maxlen=self.max_entries)

        with self.lock:
            for entry in self.history:
                try:
                    entry_date = datetime.fromisoformat(entry['timestamp'])
                    if entry_date > cutoff:
                        new_history.append(entry)
                except (ValueError, KeyError) as e:
                    # Keep entries with invalid timestamps
                    logger.warning(f"Invalid timestamp in entry, keeping it: {e}")
                    new_history.append(entry)

            self.history = new_history
        self.save_history()

        logger.info(f"Cleared entries older than {days} days")

    @staticmethod
    def generate_id() -> str:
        """Generate unique ID for history entry"""
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]


class ClipboardAccumulator:
    """Accumulates multiple clipboard contents for combining into one ePub"""

    def __init__(self, max_clips: int = 50):
        """
        Initialize clipboard accumulator

        Args:
            max_clips: Maximum number of clips to accumulate
        """
        self.clips = []
        self.max_clips = max_clips
        self.lock = threading.Lock()

    def add_clip(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Add a clipboard content to accumulator

        Args:
            content: Clipboard content
            metadata: Optional metadata for the clip

        Returns:
            The clip entry
        """
        clip = {
            'id': self.generate_clip_id(),
            'timestamp': datetime.now().isoformat(),
            'content': content,
            'content_hash': hashlib.md5(content.encode()).hexdigest(),
            'length': len(content),
            'metadata': metadata or {},
            'preview': content[:200] + '...' if len(content) > 200 else content
        }

        with self.lock:
            # Check for duplicates
            for existing in self.clips:
                if existing['content_hash'] == clip['content_hash']:
                    logger.info("Duplicate clip ignored")
                    return existing

            self.clips.append(clip)

            # Limit number of clips
            if len(self.clips) > self.max_clips:
                self.clips = self.clips[-self.max_clips:]

        logger.info(f"Added clip to accumulator ({len(self.clips)} total)")
        return clip

    def get_clips(self) -> List[Dict[str, Any]]:
        """
        Get all accumulated clips

        Returns:
            List of clip entries
        """
        with self.lock:
            return self.clips.copy()

    def clear(self):
        """Clear all accumulated clips"""
        with self.lock:
            self.clips.clear()
        logger.info("Accumulator cleared")

    def remove_clip(self, clip_id: str) -> bool:
        """
        Remove a specific clip

        Args:
            clip_id: ID of clip to remove

        Returns:
            True if removed, False if not found
        """
        with self.lock:
            for i, clip in enumerate(self.clips):
                if clip['id'] == clip_id:
                    del self.clips[i]
                    logger.info(f"Removed clip {clip_id}")
                    return True
        return False

    def combine_clips(self, separator: str = "\n\n---\n\n") -> str:
        """
        Combine all clips into one content

        Args:
            separator: Separator between clips

        Returns:
            Combined content
        """
        with self.lock:
            if not self.clips:
                return ""

            contents = []
            for clip in self.clips:
                # Add timestamp header
                timestamp = datetime.fromisoformat(clip['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
                header = f"[Clipped at {timestamp}]"
                contents.append(header + "\n\n" + clip['content'])

            return separator.join(contents)

    def get_combined_metadata(self) -> Dict[str, Any]:
        """
        Get metadata for combined clips

        Returns:
            Combined metadata
        """
        with self.lock:
            if not self.clips:
                return {}

            total_length = sum(clip['length'] for clip in self.clips)
            first_timestamp = self.clips[0]['timestamp']
            last_timestamp = self.clips[-1]['timestamp']

            return {
                'title': f'Combined Clips ({len(self.clips)} items)',
                'description': f'Combined {len(self.clips)} clipboard clips',
                'total_length': total_length,
                'clip_count': len(self.clips),
                'first_clip': first_timestamp,
                'last_clip': last_timestamp,
                'format': 'combined'
            }

    @staticmethod
    def generate_clip_id() -> str:
        """Generate unique ID for clip"""
        import uuid
        return str(uuid.uuid4())[:8]


class ConversionCache:
    """Caches frequently converted content to avoid reprocessing"""

    def __init__(self, cache_dir: Optional[Path] = None, max_size_mb: int = 100):
        """
        Initialize conversion cache

        Args:
            cache_dir: Directory for cache files
            max_size_mb: Maximum cache size in MB
        """
        if cache_dir is None:
            cache_dir = paths.get_cache_dir()

        self.cache_dir = cache_dir
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache_index = {}
        self.lock = threading.Lock()

        self.ensure_cache_dir()
        self.load_index()

    def ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load_index(self):
        """Load cache index"""
        index_file = self.cache_dir / 'index.json'
        try:
            if index_file.exists():
                with open(index_file, 'r') as f:
                    self.cache_index = json.load(f)
                logger.info(f"Loaded cache index with {len(self.cache_index)} entries")
        except Exception as e:
            logger.error(f"Error loading cache index: {e}")
            self.cache_index = {}

    def save_index(self):
        """Save cache index"""
        index_file = self.cache_dir / 'index.json'
        try:
            with open(index_file, 'w') as f:
                json.dump(self.cache_index, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache index: {e}")

    def get_cache_key(self, content: str, options: Dict[str, Any]) -> str:
        """
        Generate cache key for content and options

        Args:
            content: Content to convert
            options: Conversion options

        Returns:
            Cache key
        """
        # Create a hash of content and options
        cache_data = {
            'content_hash': hashlib.md5(content.encode()).hexdigest(),
            'options': json.dumps(options, sort_keys=True)
        }
        return hashlib.md5(json.dumps(cache_data).encode()).hexdigest()

    def get(self, content: str, options: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached conversion result

        Args:
            content: Content to convert
            options: Conversion options

        Returns:
            Cached result or None
        """
        cache_key = self.get_cache_key(content, options)

        with self.lock:
            if cache_key in self.cache_index:
                cache_file = self.cache_dir / f"{cache_key}.json"
                if cache_file.exists():
                    try:
                        with open(cache_file, 'r') as f:
                            data = json.load(f)
                        logger.info("Cache hit")
                        # Update last accessed time
                        self.cache_index[cache_key]['last_accessed'] = datetime.now().isoformat()
                        self.save_index()
                        return data
                    except (json.JSONDecodeError, OSError, IOError) as e:
                        logger.error(f"Error reading cache file {cache_file}: {e}")
                        # Remove corrupted cache entry
                        self.cache_index.pop(cache_key, None)

        return None

    def put(self, content: str, options: Dict[str, Any], result: Dict[str, Any]):
        """
        Cache conversion result

        Args:
            content: Original content
            options: Conversion options
            result: Conversion result
        """
        cache_key = self.get_cache_key(content, options)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            with self.lock:
                # Save result to file
                with open(cache_file, 'w') as f:
                    json.dump(result, f, indent=2)

                # Update index
                self.cache_index[cache_key] = {
                    'created': datetime.now().isoformat(),
                    'last_accessed': datetime.now().isoformat(),
                    'size': cache_file.stat().st_size
                }

                self.save_index()
                self.cleanup_if_needed()

            logger.info(f"Cached result ({cache_file.stat().st_size / 1024:.1f} KB)")

        except Exception as e:
            logger.error(f"Error caching result: {e}")

    def cleanup_if_needed(self):
        """Clean up old cache entries if size limit exceeded"""
        total_size = sum(entry['size'] for entry in self.cache_index.values())

        if total_size > self.max_size_bytes:
            logger.info("Cache size limit exceeded, cleaning up")

            # Sort by last accessed time
            sorted_entries = sorted(
                self.cache_index.items(),
                key=lambda x: x[1].get('last_accessed', ''),
                reverse=False
            )

            # Remove oldest entries until under limit
            while total_size > self.max_size_bytes * 0.8 and sorted_entries:
                cache_key, entry = sorted_entries.pop(0)
                cache_file = self.cache_dir / f"{cache_key}.json"

                try:
                    cache_file.unlink()
                    total_size -= entry['size']
                    del self.cache_index[cache_key]
                    logger.debug(f"Removed cache entry {cache_key}")
                except (OSError, IOError) as e:
                    logger.warning(f"Could not remove cache file {cache_key}: {e}")

            self.save_index()

    def clear(self):
        """Clear all cache"""
        with self.lock:
            for cache_key in list(self.cache_index.keys()):
                cache_file = self.cache_dir / f"{cache_key}.json"
                try:
                    cache_file.unlink()
                except (OSError, IOError) as e:
                    logger.warning(f"Could not remove cache file {cache_key}: {e}")

            self.cache_index.clear()
            self.save_index()

        logger.info("Cache cleared")


# Test functions
def test_history_manager():
    """Test history manager functionality"""
    history = ConversionHistory()

    # Add test entry
    metadata = {
        'title': 'Test ePub',
        'format': 'markdown',
        'chapters': 3,
        'size': 1024 * 50,
        'author': 'Test Author'
    }
    entry = history.add_entry('/path/to/test.epub', metadata)
    print(f"Added entry: {entry['id']}")

    # Get recent
    recent = history.get_recent(5)
    print(f"Recent entries: {len(recent)}")

    # Search
    results = history.search('test')
    print(f"Search results: {len(results)}")


def test_accumulator():
    """Test clipboard accumulator"""
    acc = ClipboardAccumulator()

    # Add clips
    acc.add_clip("First clip content")
    acc.add_clip("Second clip content")
    acc.add_clip("Third clip content")

    # Get combined
    combined = acc.combine_clips()
    print(f"Combined content ({len(combined)} chars)")

    # Get metadata
    metadata = acc.get_combined_metadata()
    print(f"Combined metadata: {metadata}")


if __name__ == '__main__':
    test_history_manager()
    print("\n" + "="*50 + "\n")
    test_accumulator()
