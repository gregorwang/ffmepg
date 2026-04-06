#pragma once

#ifdef _WIN32
#define AMC_EXPORT __declspec(dllexport)
#else
#define AMC_EXPORT
#endif

extern "C"
{
    AMC_EXPORT int amc_probe_media_json(const wchar_t* input_path, wchar_t* output_json, int output_capacity);
    AMC_EXPORT int amc_validate_output_json(const wchar_t* input_path, const wchar_t* output_path, int tolerance_seconds, wchar_t* output_json, int output_capacity);
    AMC_EXPORT int amc_analyze_subtitles_json(const wchar_t* input_path, wchar_t* output_json, int output_capacity);
    AMC_EXPORT int amc_list_audio_tracks_json(const wchar_t* input_path, wchar_t* output_json, int output_capacity);
    AMC_EXPORT int amc_extract_audio_json(const wchar_t* input_path, const wchar_t* output_path, int track_index, const wchar_t* format, int bitrate_kbps, int normalize, wchar_t* output_json, int output_capacity);
    AMC_EXPORT int amc_detect_silence_json(const wchar_t* input_path, double noise_threshold_db, double min_duration, wchar_t* output_json, int output_capacity);
    AMC_EXPORT int amc_fast_clip_json(const wchar_t* input_path, const wchar_t* output_path, double start_seconds, double duration_seconds, wchar_t* output_json, int output_capacity);
    AMC_EXPORT int amc_detect_scenes_json(const wchar_t* input_path, double threshold, wchar_t* output_json, int output_capacity);
    AMC_EXPORT int amc_sample_frame_png_json(const wchar_t* input_path, const wchar_t* output_path, double time_seconds, wchar_t* output_json, int output_capacity);
    AMC_EXPORT int amc_sample_frames_batch_json(const wchar_t* input_path, const wchar_t* output_directory, const wchar_t* file_prefix, const wchar_t* times_csv, wchar_t* output_json, int output_capacity);
}
