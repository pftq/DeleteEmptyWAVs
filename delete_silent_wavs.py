"""
Delete Empty WAV Files
Scans the current directory for WAV files and deletes those containing only silence (true zero audio).
Files are sent to the Recycle Bin, not permanently deleted.
"""

import os
import wave

try:
    from send2trash import send2trash
    HAS_SEND2TRASH = True
except ImportError:
    HAS_SEND2TRASH = False


CHUNK_SIZE = 1024 * 1024  # 1MB chunks for fast reading

# Pre-compute zero bytes for comparison
ZERO_CHUNK = bytes(CHUNK_SIZE)


def is_empty_wav(filepath):
    """
    Check if a WAV file contains only true silence (all zeros).

    Optimized: reads in chunks and exits early on first non-zero byte.

    Returns:
        True if the file is empty/silent, False otherwise
        None if the file couldn't be read
    """
    try:
        with wave.open(filepath, 'rb') as wav:
            n_frames = wav.getnframes()

            # Empty file (no frames) is considered empty
            if n_frames == 0:
                return True

            n_channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            total_bytes = n_frames * n_channels * sample_width

            # For 8-bit audio, silence is 128 (0x80), not 0
            is_8bit = (sample_width == 1)

            # Read in chunks for speed and memory efficiency
            bytes_read = 0
            while bytes_read < total_bytes:
                chunk_frames = min(CHUNK_SIZE // (n_channels * sample_width), n_frames - (bytes_read // (n_channels * sample_width)))
                if chunk_frames <= 0:
                    break

                chunk = wav.readframes(chunk_frames)
                if not chunk:
                    break

                if is_8bit:
                    # For 8-bit, check if all bytes are 128 (silence)
                    if any(b != 128 for b in chunk):
                        return False
                else:
                    # For 16-bit and higher, check if all bytes are zero
                    # Fast check: compare against zero bytes
                    if len(chunk) == CHUNK_SIZE:
                        if chunk != ZERO_CHUNK:
                            return False
                    else:
                        if any(b != 0 for b in chunk):
                            return False

                bytes_read += len(chunk)

            return True

    except wave.Error as e:
        print(f"  Error reading {filepath}: {e}")
        return None
    except Exception as e:
        print(f"  Error processing {filepath}: {e}")
        return None


def main():
    print("=" * 60)
    print("Delete Empty WAV Files")
    print("=" * 60)
    print()
    print("- Deletes WAV files with TRUE silence (all samples = 0)")
    print("- Renames files ending in '_Master' to '__FULLMIX'")
    print()

    # Get current directory
    current_dir = os.getcwd()
    print(f"Scanning: {current_dir}")
    print()

    # Find all WAV files
    wav_files = [f for f in os.listdir(current_dir)
                 if f.lower().endswith('.wav') and os.path.isfile(f)]

    if not wav_files:
        print("No WAV files found in the current directory.")
        input("\nPress Enter to exit...")
        return

    print(f"Found {len(wav_files)} WAV file(s)")
    print()

    # Analyze files
    empty_files = []
    master_files = []  # Files ending in _Master.wav

    print("Analyzing files...")
    print("-" * 40)

    for filename in wav_files:
        # Check for _Master suffix
        name_without_ext = filename[:-4]  # Remove .wav
        if name_without_ext.endswith('_Master'):
            master_files.append(filename)

        is_empty = is_empty_wav(filename)

        if is_empty is True:
            empty_files.append(filename)
            print(f"  [EMPTY]   {filename}")
        elif is_empty is False:
            if name_without_ext.endswith('_Master'):
                print(f"  [MASTER]  {filename}")
            else:
                print(f"  [OK]      {filename}")
        # If None, error was already printed

    print("-" * 40)
    print()

    # Remove empty files from master_files list (they'll be deleted anyway)
    master_files = [f for f in master_files if f not in empty_files]

    if not empty_files and not master_files:
        print("No empty WAV files or _Master files found.")
        input("\nPress Enter to exit...")
        return

    # Show what will be done
    if empty_files:
        print(f"Found {len(empty_files)} empty file(s) to delete:")
        for f in empty_files:
            print(f"  - {f}")
        print()

    if master_files:
        print(f"Found {len(master_files)} file(s) with '_Master' suffix to rename:")
        for f in master_files:
            new_name = f[:-11] + "__FULLMIX.wav"  # Replace _Master with __FULLMIX
            print(f"  - {f} -> {new_name}")
        print()

    response = input("Proceed? (y/n): ").strip().lower()

    if response != 'y':
        print("Cancelled. No changes made.")
        input("\nPress Enter to exit...")
        return

    # Send empty files to recycle bin
    print()
    deleted = 0
    if empty_files:
        for filename in empty_files:
            try:
                filepath = os.path.join(current_dir, filename)
                if HAS_SEND2TRASH:
                    send2trash(filepath)
                    print(f"  Recycled: {filename}")
                else:
                    os.remove(filename)
                    print(f"  Deleted (permanently): {filename}")
                deleted += 1
            except Exception as e:
                print(f"  Failed to delete {filename}: {e}")

    # Rename _Master files
    renamed = 0
    if master_files:
        for filename in master_files:
            try:
                new_name = filename[:-11] + "__FULLMIX.wav"  # Replace _Master with __FULLMIX
                old_path = os.path.join(current_dir, filename)
                new_path = os.path.join(current_dir, new_name)

                # Check if target already exists
                if os.path.exists(new_path):
                    print(f"  Skipped (target exists): {filename}")
                    continue

                os.rename(old_path, new_path)
                print(f"  Renamed: {filename} -> {new_name}")
                renamed += 1
            except Exception as e:
                print(f"  Failed to rename {filename}: {e}")

    print()
    if deleted > 0:
        if HAS_SEND2TRASH:
            print(f"Sent {deleted} file(s) to Recycle Bin.")
        else:
            print(f"Deleted {deleted} file(s) permanently.")
    if renamed > 0:
        print(f"Renamed {renamed} file(s).")
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
