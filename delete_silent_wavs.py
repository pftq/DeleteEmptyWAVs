"""
Delete Empty WAV Files
Scans the current directory for WAV files and deletes those containing only silence.
Silence is defined as audio with peak level at or below -115 dB.
Files are sent to the Recycle Bin, not permanently deleted.
"""

import os
import wave
import array
import math

try:
    from send2trash import send2trash
    HAS_SEND2TRASH = True
except ImportError:
    HAS_SEND2TRASH = False


DEBUG = False  # Set to True to show peak dB for each file
SILENCE_THRESHOLD_DB = -115  # Files at or below this level are considered silent

CHUNK_SIZE = 1024 * 1024  # 1MB chunks for fast reading


def get_peak_db(filepath):
    """
    Get the peak dB level of a WAV file.

    Returns:
        (peak_db, is_true_zero) tuple where:
        - peak_db is the peak level in dB (negative value, 0 = max)
        - is_true_zero is True if all samples are exactly zero
        Returns (None, None) if the file couldn't be read
    """
    try:
        with wave.open(filepath, 'rb') as wav:
            n_frames = wav.getnframes()

            # Empty file (no frames) is considered empty
            if n_frames == 0:
                return (float('-inf'), True)

            n_channels = wav.getnchannels()
            sample_width = wav.getsampwidth()

            # Determine array typecode and max value based on sample width
            if sample_width == 1:
                # 8-bit unsigned
                typecode = 'B'
                max_val = 127  # Centered at 128
                center = 128
            elif sample_width == 2:
                # 16-bit signed
                typecode = 'h'
                max_val = 32767
                center = 0
            elif sample_width == 4:
                # 32-bit signed
                typecode = 'i'
                max_val = 2147483647
                center = 0
            elif sample_width == 3:
                # 24-bit - handle specially (no native array type)
                typecode = None
                max_val = 8388607
                center = 0
            else:
                print(f"  Unsupported sample width: {sample_width}")
                return (None, None)

            peak_amplitude = 0
            is_all_zero = True

            # Read in chunks
            frames_per_chunk = CHUNK_SIZE // (n_channels * sample_width)
            frames_read = 0

            while frames_read < n_frames:
                chunk_frames = min(frames_per_chunk, n_frames - frames_read)
                raw_data = wav.readframes(chunk_frames)
                if not raw_data:
                    break

                if sample_width == 3:
                    # Handle 24-bit audio (slower path, no native array type)
                    for i in range(0, len(raw_data), 3):
                        if i + 3 <= len(raw_data):
                            b = raw_data[i:i+3]
                            val = b[0] | (b[1] << 8) | (b[2] << 16)
                            if val >= 0x800000:
                                val -= 0x1000000
                            if val != 0:
                                is_all_zero = False
                            peak_amplitude = max(peak_amplitude, abs(val))
                else:
                    # Fast path using array module (C implementation)
                    samples = array.array(typecode)
                    samples.frombytes(raw_data)

                    if center == 0:
                        # For signed formats, use min/max directly
                        chunk_min = min(samples)
                        chunk_max = max(samples)
                        if chunk_min != 0 or chunk_max != 0:
                            is_all_zero = False
                        peak_amplitude = max(peak_amplitude, abs(chunk_min), chunk_max)
                    else:
                        # For 8-bit unsigned, adjust for center
                        chunk_min = min(samples) - center
                        chunk_max = max(samples) - center
                        if chunk_min != 0 or chunk_max != 0:
                            is_all_zero = False
                        peak_amplitude = max(peak_amplitude, abs(chunk_min), abs(chunk_max))

                frames_read += chunk_frames

            # Convert to dB
            if peak_amplitude == 0:
                peak_db = float('-inf')
            else:
                peak_db = 20 * math.log10(peak_amplitude / max_val)

            return (peak_db, is_all_zero)

    except wave.Error as e:
        print(f"  Error reading {filepath}: {e}")
        return (None, None)
    except Exception as e:
        print(f"  Error processing {filepath}: {e}")
        return (None, None)


def is_silent_fast(filepath):
    """
    Fast check if a WAV file is silent (below threshold).
    Exits early on first sample exceeding the silence threshold.

    Returns:
        True if silent, False if not silent, None on error
    """
    try:
        with wave.open(filepath, 'rb') as wav:
            n_frames = wav.getnframes()

            if n_frames == 0:
                return True

            n_channels = wav.getnchannels()
            sample_width = wav.getsampwidth()

            # Determine array typecode and max value based on sample width
            if sample_width == 1:
                typecode = 'B'
                max_val = 127
                center = 128
            elif sample_width == 2:
                typecode = 'h'
                max_val = 32767
                center = 0
            elif sample_width == 4:
                typecode = 'i'
                max_val = 2147483647
                center = 0
            elif sample_width == 3:
                typecode = None
                max_val = 8388607
                center = 0
            else:
                print(f"  Unsupported sample width: {sample_width}")
                return None

            # Calculate amplitude threshold from dB threshold
            threshold_amplitude = int(max_val * (10 ** (SILENCE_THRESHOLD_DB / 20)))

            # Read in chunks with early exit
            frames_per_chunk = CHUNK_SIZE // (n_channels * sample_width)
            frames_read = 0

            while frames_read < n_frames:
                chunk_frames = min(frames_per_chunk, n_frames - frames_read)
                raw_data = wav.readframes(chunk_frames)
                if not raw_data:
                    break

                if sample_width == 3:
                    # 24-bit audio
                    for i in range(0, len(raw_data), 3):
                        if i + 3 <= len(raw_data):
                            b = raw_data[i:i+3]
                            val = b[0] | (b[1] << 8) | (b[2] << 16)
                            if val >= 0x800000:
                                val -= 0x1000000
                            if abs(val) > threshold_amplitude:
                                return False
                else:
                    samples = array.array(typecode)
                    samples.frombytes(raw_data)

                    if center == 0:
                        chunk_min = min(samples)
                        chunk_max = max(samples)
                    else:
                        chunk_min = min(samples) - center
                        chunk_max = max(samples) - center

                    # Early exit if any sample exceeds threshold
                    if abs(chunk_min) > threshold_amplitude or chunk_max > threshold_amplitude:
                        return False

                frames_read += chunk_frames

            return True

    except wave.Error as e:
        print(f"  Error reading {filepath}: {e}")
        return None
    except Exception as e:
        print(f"  Error processing {filepath}: {e}")
        return None


def is_empty_wav(filepath):
    """
    Check if a WAV file is silent.

    Returns:
        (is_silent, peak_db) tuple where:
        - is_silent is True if the file is silent, False otherwise, None on error
        - peak_db is the peak level in dB (only calculated when DEBUG is True)
    """
    if DEBUG:
        peak_db, _ = get_peak_db(filepath)
        if peak_db is None:
            return (None, None)
        is_silent = peak_db <= SILENCE_THRESHOLD_DB
        return (is_silent, peak_db)
    else:
        is_silent = is_silent_fast(filepath)
        return (is_silent, None)


def main():
    print("=" * 60)
    print("Delete Empty WAV Files")
    print("=" * 60)
    print()
    print("- Deletes WAV files with silence (peak <= -115 dB)")
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

        is_empty, peak_db = is_empty_wav(filename)

        if DEBUG:
            # Format peak dB for display
            if peak_db is None:
                db_str = "ERROR"
            elif peak_db == float('-inf'):
                db_str = "-inf dB"
            else:
                db_str = f"{peak_db:+.1f} dB"

            if is_empty is True:
                empty_files.append(filename)
                print(f"  [EMPTY]   {db_str:>12}  {filename}")
            elif is_empty is False:
                if name_without_ext.endswith('_Master'):
                    print(f"  [MASTER]  {db_str:>12}  {filename}")
                else:
                    print(f"  [OK]      {db_str:>12}  {filename}")
        else:
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
