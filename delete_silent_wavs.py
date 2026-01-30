"""
Delete Empty WAV Files
Scans the current directory for WAV files and deletes those containing only silence (true zero audio).
Files are sent to the Recycle Bin, not permanently deleted.
"""

import os
import sys
import wave
import struct

try:
    from send2trash import send2trash
    HAS_SEND2TRASH = True
except ImportError:
    HAS_SEND2TRASH = False


def get_peak_amplitude(audio_data, sample_width):
    """Get the peak (maximum absolute) amplitude of audio data."""
    if len(audio_data) == 0:
        return 0

    # Determine format based on sample width
    if sample_width == 1:
        fmt = f"{len(audio_data)}B"  # unsigned 8-bit
        samples = struct.unpack(fmt, audio_data)
        samples = [abs(s - 128) for s in samples]  # convert to signed, take abs
    elif sample_width == 2:
        fmt = f"{len(audio_data) // 2}h"  # signed 16-bit
        samples = [abs(s) for s in struct.unpack(fmt, audio_data)]
    elif sample_width == 4:
        fmt = f"{len(audio_data) // 4}i"  # signed 32-bit
        samples = [abs(s) for s in struct.unpack(fmt, audio_data)]
    else:
        return -1  # unsupported format

    if len(samples) == 0:
        return 0

    return max(samples)


def is_empty_wav(filepath):
    """
    Check if a WAV file contains only true silence (all zeros).

    Only returns True if the file has no audio frames OR all samples are exactly zero.

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

            sample_width = wav.getsampwidth()
            audio_data = wav.readframes(n_frames)

            peak = get_peak_amplitude(audio_data, sample_width)

            if peak < 0:
                print(f"  Warning: Unsupported sample width ({sample_width} bytes) in {filepath}")
                return None

            # Only consider empty if peak amplitude is exactly 0
            return peak == 0

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
    print("- Renames files ending in '_Master' to remove the suffix")
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
            new_name = f[:-11] + ".wav"  # Remove _Master.wav, add .wav
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
                new_name = filename[:-11] + ".wav"  # Remove _Master.wav, add .wav
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
