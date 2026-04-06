#include "AnimeMediaCore.h"

#include <cstdio>
#include <algorithm>
#include <filesystem>
#include <iomanip>
#include <memory>
#include <regex>
#include <sstream>
#include <string>
#include <vector>
#include <windows.h>

namespace
{
    constexpr int kSuccess = 0;
    constexpr int kInvalidArgument = 1;
    constexpr int kBufferTooSmall = 2;

    std::wstring EscapeJson(const std::wstring& value)
    {
        std::wstring escaped;
        escaped.reserve(value.size() + 8);

        for (const wchar_t ch : value)
        {
            switch (ch)
            {
            case L'\\':
                escaped += L"\\\\";
                break;
            case L'"':
                escaped += L"\\\"";
                break;
            case L'\r':
                escaped += L"\\r";
                break;
            case L'\n':
                escaped += L"\\n";
                break;
            case L'\t':
                escaped += L"\\t";
                break;
            default:
                escaped += ch;
                break;
            }
        }

        return escaped;
    }

    int CopyToOutput(const std::wstring& payload, wchar_t* output_json, int output_capacity)
    {
        if (output_json == nullptr || output_capacity <= 0)
        {
            return kInvalidArgument;
        }

        const auto required = static_cast<int>(payload.size()) + 1;
        if (required > output_capacity)
        {
            return kBufferTooSmall;
        }

        wmemcpy(output_json, payload.c_str(), payload.size());
        output_json[payload.size()] = L'\0';
        return kSuccess;
    }

    std::filesystem::path GetExecutableDirectory()
    {
        std::wstring buffer(MAX_PATH, L'\0');
        const auto length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
        buffer.resize(length);
        return std::filesystem::path(buffer).parent_path();
    }

    std::wstring QuotePath(const std::filesystem::path& path)
    {
        return L"\"" + path.wstring() + L"\"";
    }

    std::wstring ResolveToolCommand(const wchar_t* executableName)
    {
        const auto appDirectory = GetExecutableDirectory();
        const auto packagedTool = appDirectory / L"tools" / L"ffmpeg" / executableName;
        if (std::filesystem::exists(packagedTool))
        {
            return QuotePath(packagedTool);
        }

        return executableName;
    }

    std::wstring ConvertBytesToWide(const std::string& bytes, UINT codePage)
    {
        if (bytes.empty())
        {
            return L"";
        }

        const auto required = MultiByteToWideChar(
            codePage,
            0,
            bytes.data(),
            static_cast<int>(bytes.size()),
            nullptr,
            0);

        if (required <= 0)
        {
            return L"";
        }

        std::wstring output(static_cast<size_t>(required), L'\0');
        MultiByteToWideChar(
            codePage,
            0,
            bytes.data(),
            static_cast<int>(bytes.size()),
            output.data(),
            required);

        return output;
    }

    std::wstring DecodeCommandOutput(const std::string& bytes)
    {
        for (const auto codePage : {CP_UTF8, CP_ACP, CP_OEMCP})
        {
            const auto decoded = ConvertBytesToWide(bytes, codePage);
            if (!decoded.empty())
            {
                return decoded;
            }
        }

        return L"";
    }

    std::wstring RunCommand(const std::wstring& command, DWORD& exitCode);

    std::wstring RunCommand(const std::wstring& command)
    {
        DWORD ignoredExitCode = 0;
        return RunCommand(command, ignoredExitCode);
    }

    std::wstring RunCommand(const std::wstring& command, DWORD& exitCode)
    {
        SECURITY_ATTRIBUTES securityAttributes{};
        securityAttributes.nLength = sizeof(SECURITY_ATTRIBUTES);
        securityAttributes.bInheritHandle = TRUE;

        HANDLE readPipe = nullptr;
        HANDLE writePipe = nullptr;

        if (!CreatePipe(&readPipe, &writePipe, &securityAttributes, 0))
        {
            return L"";
        }

        SetHandleInformation(readPipe, HANDLE_FLAG_INHERIT, 0);

        STARTUPINFOW startupInfo{};
        startupInfo.cb = sizeof(STARTUPINFOW);
        startupInfo.dwFlags = STARTF_USESTDHANDLES;
        startupInfo.hStdOutput = writePipe;
        startupInfo.hStdError = writePipe;

        PROCESS_INFORMATION processInfo{};
        auto fullCommand = L"cmd.exe /d /s /c \"" + command + L"\"";
        std::vector<wchar_t> commandBuffer(fullCommand.begin(), fullCommand.end());
        commandBuffer.push_back(L'\0');

        const auto created = CreateProcessW(
            nullptr,
            commandBuffer.data(),
            nullptr,
            nullptr,
            TRUE,
            CREATE_NO_WINDOW,
            nullptr,
            nullptr,
            &startupInfo,
            &processInfo);

        CloseHandle(writePipe);

        if (!created)
        {
            CloseHandle(readPipe);
            exitCode = static_cast<DWORD>(-1);
            return L"";
        }

        std::string outputBytes;
        char buffer[4096];
        DWORD bytesRead = 0;

        while (ReadFile(readPipe, buffer, static_cast<DWORD>(std::size(buffer)), &bytesRead, nullptr) && bytesRead > 0)
        {
            outputBytes.append(buffer, buffer + bytesRead);
        }

        WaitForSingleObject(processInfo.hProcess, INFINITE);
        GetExitCodeProcess(processInfo.hProcess, &exitCode);
        CloseHandle(processInfo.hThread);
        CloseHandle(processInfo.hProcess);
        CloseHandle(readPipe);

        return DecodeCommandOutput(outputBytes);
    }

    std::vector<std::wstring> SplitCsvLine(const std::wstring& line)
    {
        std::vector<std::wstring> parts;
        std::wstring current;
        bool inQuotes = false;

        for (const wchar_t ch : line)
        {
            if (ch == L'"')
            {
                inQuotes = !inQuotes;
                continue;
            }

            if (ch == L',' && !inQuotes)
            {
                parts.push_back(current);
                current.clear();
                continue;
            }

            if (ch != L'\r' && ch != L'\n')
            {
                current += ch;
            }
        }

        parts.push_back(current);
        return parts;
    }

    bool IsImageBasedCodec(const std::wstring& codecName)
    {
        return codecName.find(L"pgs") != std::wstring::npos ||
               codecName.find(L"dvd") != std::wstring::npos ||
               codecName.find(L"dvb") != std::wstring::npos ||
               codecName.find(L"xsub") != std::wstring::npos ||
               codecName.find(L"vobsub") != std::wstring::npos;
    }

    std::wstring Trim(const std::wstring& value)
    {
        const auto start = value.find_first_not_of(L" \t\r\n");
        if (start == std::wstring::npos)
        {
            return L"";
        }

        const auto end = value.find_last_not_of(L" \t\r\n");
        return value.substr(start, end - start + 1);
    }

    std::wstring ExtractSubtitleTextSample(const std::wstring& mediaPath, const std::wstring& streamIndex, const std::wstring& codecName)
    {
        if (IsImageBasedCodec(codecName))
        {
            return L"";
        }

        const auto ffmpeg = ResolveToolCommand(L"ffmpeg.exe");
        const std::wstring command =
            ffmpeg +
            L" -v error -i " + QuotePath(mediaPath) +
            L" -map 0:" + streamIndex +
            L" -f srt - 2>NUL";

        const auto output = RunCommand(command);
        if (output.empty())
        {
            return L"";
        }

        std::wistringstream stream(output);
        std::wstring line;
        std::wstring collected;
        int linesCollected = 0;

        const std::wregex numberLine(LR"(^\d+$)");
        const std::wregex timeLine(LR"(^\d{2}:\d{2}:\d{2})");

        while (std::getline(stream, line))
        {
            const auto trimmed = Trim(line);
            if (trimmed.empty())
            {
                continue;
            }

            if (std::regex_match(trimmed, numberLine) || std::regex_search(trimmed, timeLine))
            {
                continue;
            }

            if (!collected.empty())
            {
                collected += L" / ";
            }

            collected += trimmed;
            linesCollected++;

            if (linesCollected >= 2)
            {
                break;
            }
        }

        return collected;
    }

    std::wstring BuildSubtitleTracksJson(const std::wstring& mediaPath, const std::wstring& ffprobeOutput)
    {
        std::wstringstream json;
        json << L"[";

        std::wistringstream stream(ffprobeOutput);
        std::wstring line;
        bool first = true;

        while (std::getline(stream, line))
        {
            if (line.empty())
            {
                continue;
            }

            const auto parts = SplitCsvLine(line);
            if (parts.size() < 4)
            {
                continue;
            }

            const std::wstring index = parts[0];
            const std::wstring codec_name = parts.size() > 1 ? parts[1] : L"";
            const std::wstring is_default = parts.size() > 2 ? parts[2] : L"0";
            const std::wstring language = parts.size() > 3 ? parts[3] : L"";
            const std::wstring title = parts.size() > 4 ? parts[4] : L"";
            const std::wstring textSample = ExtractSubtitleTextSample(mediaPath, index, codec_name);

            if (!first)
            {
                json << L",";
            }

            first = false;
            json << L"{"
                 << L"\"index\":" << index << L","
                 << L"\"title\":\"" << EscapeJson(title) << L"\","
                 << L"\"language\":\"" << EscapeJson(language) << L"\","
                 << L"\"is_default\":" << (is_default == L"1" ? L"true" : L"false") << L","
                 << L"\"codec_name\":\"" << EscapeJson(codec_name) << L"\","
                 << L"\"text_sample\":\"" << EscapeJson(textSample) << L"\""
                 << L"}";
        }

        json << L"]";
        return json.str();
    }

    int ParseIntOrDefault(const std::wstring& value, int defaultValue = 0)
    {
        try
        {
            return value.empty() ? defaultValue : std::stoi(value);
        }
        catch (...)
        {
            return defaultValue;
        }
    }

    long long ParseLongLongOrDefault(const std::wstring& value, long long defaultValue = 0)
    {
        try
        {
            return value.empty() ? defaultValue : std::stoll(value);
        }
        catch (...)
        {
            return defaultValue;
        }
    }

    std::wstring FormatSeconds(double timeSeconds)
    {
        std::wostringstream stream;
        stream << std::fixed << std::setprecision(3) << (timeSeconds < 0.0 ? 0.0 : timeSeconds);
        return stream.str();
    }

    std::wstring FormatDecimal(double value)
    {
        std::wostringstream stream;
        stream << std::fixed << std::setprecision(3) << value;
        return stream.str();
    }

    std::wstring ProbeDurationSeconds(const std::wstring& mediaPath)
    {
        const auto ffprobe = ResolveToolCommand(L"ffprobe.exe");
        const std::wstring command =
            ffprobe +
            L" -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 " +
            QuotePath(mediaPath) +
            L" 2>NUL";

        return Trim(RunCommand(command));
    }

    double ParseDurationSeconds(const std::wstring& value)
    {
        try
        {
            return value.empty() ? 0.0 : std::stod(value);
        }
        catch (...)
        {
            return 0.0;
        }
    }

    std::wstring ProbeSubtitleTracksCsv(const std::wstring& mediaPath)
    {
        const auto ffprobe = ResolveToolCommand(L"ffprobe.exe");
        return RunCommand(
            ffprobe + L" -v error -select_streams s "
            L"-show_entries stream=index,codec_name:stream_tags=title,language:stream_disposition=default "
            L"-of csv=p=0 " + QuotePath(mediaPath) + L" 2>NUL");
    }

    std::wstring ProbeAudioTracksCsv(const std::wstring& mediaPath)
    {
        const auto ffprobe = ResolveToolCommand(L"ffprobe.exe");
        return RunCommand(
            ffprobe + L" -v error -select_streams a "
            L"-show_entries stream=index,codec_name,channels,sample_rate,bit_rate:stream_tags=title,language:stream_disposition=default "
            L"-of csv=p=0 " + QuotePath(mediaPath) + L" 2>NUL");
    }

    std::wstring BuildAudioTracksJson(const std::wstring& ffprobeOutput)
    {
        std::wstringstream json;
        json << L"[";

        std::wistringstream stream(ffprobeOutput);
        std::wstring line;
        bool first = true;
        int audioOrdinal = 0;

        while (std::getline(stream, line))
        {
            if (line.empty())
            {
                continue;
            }

            const auto parts = SplitCsvLine(line);
            if (parts.size() < 6)
            {
                continue;
            }

            const auto streamIndex = ParseIntOrDefault(parts[0], -1);
            const auto codecName = parts.size() > 1 ? parts[1] : L"";
            const auto sampleRate = ParseIntOrDefault(parts.size() > 2 ? parts[2] : L"0");
            const auto channels = ParseIntOrDefault(parts.size() > 3 ? parts[3] : L"0");
            const auto bitRate = ParseLongLongOrDefault(parts.size() > 4 ? parts[4] : L"0");
            const auto isDefault = parts.size() > 5 ? parts[5] : L"0";
            const auto language = parts.size() > 6 ? parts[6] : L"";
            const auto title = parts.size() > 7 ? parts[7] : L"";

            if (!first)
            {
                json << L",";
            }

            first = false;
            json << L"{"
                 << L"\"index\":" << audioOrdinal << L","
                 << L"\"stream_index\":" << streamIndex << L","
                 << L"\"codec_name\":\"" << EscapeJson(codecName) << L"\","
                 << L"\"language\":\"" << EscapeJson(language) << L"\","
                 << L"\"title\":\"" << EscapeJson(title) << L"\","
                 << L"\"channels\":" << channels << L","
                 << L"\"sample_rate\":" << sampleRate << L","
                 << L"\"bit_rate\":" << bitRate << L","
                 << L"\"is_default\":" << (isDefault == L"1" ? L"true" : L"false")
                 << L"}";
            audioOrdinal++;
        }

        json << L"]";
        return json.str();
    }

    std::vector<double> ParseTimesCsv(const std::wstring& timesCsv)
    {
        std::vector<double> values;
        std::wstringstream stream(timesCsv);
        std::wstring token;

        while (std::getline(stream, token, L','))
        {
            const auto trimmed = Trim(token);
            if (trimmed.empty())
            {
                continue;
            }

            values.push_back(ParseDurationSeconds(trimmed));
        }

        return values;
    }

    bool ExecuteFrameSample(const std::wstring& inputPath, const std::wstring& outputPath, double timeSeconds)
    {
        if (!std::filesystem::exists(inputPath))
        {
            return false;
        }

        const auto parentPath = std::filesystem::path(outputPath).parent_path();
        if (!parentPath.empty())
        {
            std::error_code errorCode;
            std::filesystem::create_directories(parentPath, errorCode);
        }

        const auto ffmpeg = ResolveToolCommand(L"ffmpeg.exe");
        const std::wstring command =
            ffmpeg +
            L" -v error -y -ss " + FormatSeconds(timeSeconds) +
            L" -i " + QuotePath(inputPath) +
            L" -frames:v 1 -an -sn " +
            QuotePath(outputPath);

        RunCommand(command);
        return std::filesystem::exists(outputPath);
    }

    bool ExecuteGeneratedOutputCommand(const std::wstring& command, const std::wstring& outputPath, std::wstring& commandOutput, DWORD& exitCode)
    {
        const auto parentPath = std::filesystem::path(outputPath).parent_path();
        if (!parentPath.empty())
        {
            std::error_code errorCode;
            std::filesystem::create_directories(parentPath, errorCode);
        }

        commandOutput = RunCommand(command, exitCode);
        return exitCode == 0 && std::filesystem::exists(outputPath);
    }

    std::wstring BuildResultSnippet(const std::wstring& output)
    {
        auto trimmed = Trim(output);
        if (trimmed.size() <= 240)
        {
            return trimmed;
        }

        return trimmed.substr(0, 240) + L"...";
    }

    std::wstring BuildAudioFormatExtension(const std::wstring& format)
    {
        if (_wcsicmp(format.c_str(), L"copy") == 0)
        {
            return L".mka";
        }

        if (_wcsicmp(format.c_str(), L"mp3") == 0)
        {
            return L".mp3";
        }

        if (_wcsicmp(format.c_str(), L"wav") == 0)
        {
            return L".wav";
        }

        if (_wcsicmp(format.c_str(), L"flac") == 0)
        {
            return L".flac";
        }

        return L".m4a";
    }

    std::wstring BuildAudioCodecArguments(const std::wstring& format, int bitrateKbps, bool normalize)
    {
        const auto normalizedBitrate = bitrateKbps > 0 ? bitrateKbps : 192;
        std::wstring arguments;

        if (_wcsicmp(format.c_str(), L"copy") == 0 && !normalize)
        {
            arguments = L" -c:a copy";
        }
        else if (_wcsicmp(format.c_str(), L"mp3") == 0)
        {
            arguments = L" -c:a libmp3lame -q:a 2";
        }
        else if (_wcsicmp(format.c_str(), L"wav") == 0)
        {
            arguments = L" -c:a pcm_s16le -ar 44100";
        }
        else if (_wcsicmp(format.c_str(), L"flac") == 0)
        {
            arguments = L" -c:a flac";
        }
        else
        {
            arguments = L" -c:a aac -profile:a aac_low -b:a " + std::to_wstring(normalizedBitrate) + L"k";
        }

        if (normalize && _wcsicmp(format.c_str(), L"copy") != 0)
        {
            arguments += L" -af loudnorm=I=-14:TP=-2:LRA=11";
        }
        else if (normalize && _wcsicmp(format.c_str(), L"copy") == 0)
        {
            arguments = L" -c:a aac -profile:a aac_low -b:a " + std::to_wstring(normalizedBitrate) + L"k -af loudnorm=I=-14:TP=-2:LRA=11";
        }

        return arguments;
    }

    std::wstring BuildAudioExtractCommand(
        const std::wstring& inputPath,
        const std::wstring& outputPath,
        int trackIndex,
        const std::wstring& format,
        int bitrateKbps,
        bool normalize)
    {
        const auto ffmpeg = ResolveToolCommand(L"ffmpeg.exe");
        std::wstring command =
            ffmpeg +
            L" -v error -y -i " + QuotePath(inputPath) +
            L" -vn -sn";

        if (trackIndex >= 0)
        {
            command += L" -map 0:a:" + std::to_wstring(trackIndex);
        }

        command += BuildAudioCodecArguments(format, bitrateKbps, normalize);
        command += L" " + QuotePath(outputPath);
        return command;
    }

    std::wstring BuildFastClipCommand(
        const std::wstring& inputPath,
        const std::wstring& outputPath,
        double startSeconds,
        double durationSeconds)
    {
        const auto ffmpeg = ResolveToolCommand(L"ffmpeg.exe");
        return
            ffmpeg +
            L" -v error -y -ss " + FormatSeconds(startSeconds) +
            L" -i " + QuotePath(inputPath) +
            L" -t " + FormatSeconds(durationSeconds) +
            L" -map 0 -c copy -avoid_negative_ts 1 " +
            QuotePath(outputPath);
    }

    std::wstring BuildSilenceSegmentsJson(const std::wstring& ffmpegOutput)
    {
        const std::wregex silenceStartRegex(LR"(silence_start:\s*(-?\d+(?:\.\d+)?))");
        const std::wregex silenceEndRegex(LR"(silence_end:\s*(-?\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(-?\d+(?:\.\d+)?))");

        std::wistringstream stream(ffmpegOutput);
        std::wstring line;
        std::wstringstream json;
        json << L"[";
        bool first = true;
        double currentStart = -1.0;

        while (std::getline(stream, line))
        {
            std::wsmatch match;
            if (std::regex_search(line, match, silenceStartRegex))
            {
                currentStart = ParseDurationSeconds(match[1].str());
                continue;
            }

            if (!std::regex_search(line, match, silenceEndRegex))
            {
                continue;
            }

            const auto endSeconds = ParseDurationSeconds(match[1].str());
            const auto durationSeconds = ParseDurationSeconds(match[2].str());
            const auto startSeconds = currentStart >= 0.0 ? currentStart : std::max(0.0, endSeconds - durationSeconds);
            currentStart = -1.0;

            if (!first)
            {
                json << L",";
            }

            first = false;
            json << L"{"
                 << L"\"start_seconds\":" << FormatSeconds(startSeconds) << L","
                 << L"\"end_seconds\":" << FormatSeconds(endSeconds) << L","
                 << L"\"duration_seconds\":" << FormatSeconds(durationSeconds)
                 << L"}";
        }

        json << L"]";
        return json.str();
    }

    std::wstring BuildSceneCutsJson(const std::wstring& ffmpegOutput)
    {
        const std::wregex sceneRegex(LR"(pts_time:(-?\d+(?:\.\d+)?))");
        std::wistringstream stream(ffmpegOutput);
        std::wstring line;
        std::vector<double> sceneTimes;

        while (std::getline(stream, line))
        {
            std::wsmatch match;
            if (std::regex_search(line, match, sceneRegex))
            {
                sceneTimes.push_back(ParseDurationSeconds(match[1].str()));
            }
        }

        std::sort(sceneTimes.begin(), sceneTimes.end());
        sceneTimes.erase(std::unique(sceneTimes.begin(), sceneTimes.end()), sceneTimes.end());

        std::wstringstream json;
        json << L"[";
        for (size_t index = 0; index < sceneTimes.size(); ++index)
        {
            if (index > 0)
            {
                json << L",";
            }

            json << L"{"
                 << L"\"sequence\":" << (index + 1) << L","
                 << L"\"time_seconds\":" << FormatSeconds(sceneTimes[index])
                 << L"}";
        }

        json << L"]";
        return json.str();
    }
}

int amc_probe_media_json(const wchar_t* input_path, wchar_t* output_json, int output_capacity)
{
    if (input_path == nullptr)
    {
        return kInvalidArgument;
    }

    const std::wstring path(input_path);
    const bool exists = std::filesystem::exists(path);
    const auto durationSeconds = exists ? ProbeDurationSeconds(path) : L"0";
    const auto audioTracksCsv = exists ? ProbeAudioTracksCsv(path) : L"";
    const auto audioTracksJson = BuildAudioTracksJson(audioTracksCsv);
    const auto subtitleTracksCsv = exists ? ProbeSubtitleTracksCsv(path) : L"";
    const auto subtitleTracksJson = BuildSubtitleTracksJson(path, subtitleTracksCsv);

    const std::wstring payload =
        L"{"
        L"\"message\":\"AnimeMediaCore 原生媒体探测已执行。\","
        L"\"input_path\":\"" + EscapeJson(path) + L"\","
        L"\"file_exists\":" + std::wstring(exists ? L"true" : L"false") + L","
        L"\"duration_seconds\":" + (durationSeconds.empty() ? L"0" : durationSeconds) + L","
        L"\"audio_tracks\":" + audioTracksJson + L","
        L"\"subtitle_tracks\":" + subtitleTracksJson +
        L"}";

    return CopyToOutput(payload, output_json, output_capacity);
}

int amc_validate_output_json(const wchar_t* input_path, const wchar_t* output_path, int tolerance_seconds, wchar_t* output_json, int output_capacity)
{
    if (input_path == nullptr || output_path == nullptr)
    {
        return kInvalidArgument;
    }

    const std::wstring inputPath(input_path);
    const std::wstring outputPath(output_path);
    const bool inputExists = std::filesystem::exists(inputPath);
    const bool outputExists = std::filesystem::exists(outputPath);
    const auto inputDurationText = inputExists ? ProbeDurationSeconds(inputPath) : L"0";
    const auto outputDurationText = outputExists ? ProbeDurationSeconds(outputPath) : L"0";
    const auto inputDuration = ParseDurationSeconds(inputDurationText);
    const auto outputDuration = ParseDurationSeconds(outputDurationText);
    const auto difference = std::abs(inputDuration - outputDuration);
    const bool isMatch = inputExists && outputExists && difference <= static_cast<double>(tolerance_seconds);

    std::wostringstream payload;
    payload << L"{"
            << L"\"message\":\"AnimeMediaCore 原生输出校验已执行。\","
            << L"\"input_path\":\"" << EscapeJson(inputPath) << L"\","
            << L"\"output_path\":\"" << EscapeJson(outputPath) << L"\","
            << L"\"input_exists\":" << (inputExists ? L"true" : L"false") << L","
            << L"\"output_exists\":" << (outputExists ? L"true" : L"false") << L","
            << L"\"tolerance_seconds\":" << tolerance_seconds << L","
            << L"\"input_duration_seconds\":" << FormatSeconds(inputDuration) << L","
            << L"\"output_duration_seconds\":" << FormatSeconds(outputDuration) << L","
            << L"\"difference_seconds\":" << FormatSeconds(difference) << L","
            << L"\"is_match\":" << (isMatch ? L"true" : L"false")
            << L"}";

    return CopyToOutput(payload.str(), output_json, output_capacity);
}

int amc_analyze_subtitles_json(const wchar_t* input_path, wchar_t* output_json, int output_capacity)
{
    if (input_path == nullptr)
    {
        return kInvalidArgument;
    }

    const std::wstring path(input_path);
    const bool exists = std::filesystem::exists(path);
    const std::wstring escaped_path = EscapeJson(path);
    const std::wstring ffprobeOutput = exists ? ProbeSubtitleTracksCsv(path) : L"";
    const std::wstring subtitleTracksJson = BuildSubtitleTracksJson(path, ffprobeOutput);

    std::wstring payload =
        L"{"
        L"\"message\":\"AnimeMediaCore 原生字幕分析已执行。\","
        L"\"input_path\":\"" + escaped_path + L"\","
        L"\"file_exists\":" + std::wstring(exists ? L"true" : L"false") + L","
        L"\"subtitle_tracks\":" + subtitleTracksJson +
        L"}";

    return CopyToOutput(payload, output_json, output_capacity);
}

int amc_list_audio_tracks_json(const wchar_t* input_path, wchar_t* output_json, int output_capacity)
{
    if (input_path == nullptr)
    {
        return kInvalidArgument;
    }

    const std::wstring path(input_path);
    const bool exists = std::filesystem::exists(path);
    const auto audioTracksCsv = exists ? ProbeAudioTracksCsv(path) : L"";
    const auto audioTracksJson = BuildAudioTracksJson(audioTracksCsv);

    const std::wstring payload =
        L"{"
        L"\"message\":\"AnimeMediaCore 原生音轨探测已执行。\"," 
        L"\"input_path\":\"" + EscapeJson(path) + L"\","
        L"\"file_exists\":" + std::wstring(exists ? L"true" : L"false") + L","
        L"\"audio_tracks\":" + audioTracksJson +
        L"}";

    return CopyToOutput(payload, output_json, output_capacity);
}

int amc_extract_audio_json(const wchar_t* input_path, const wchar_t* output_path, int track_index, const wchar_t* format, int bitrate_kbps, int normalize, wchar_t* output_json, int output_capacity)
{
    if (input_path == nullptr || output_path == nullptr || format == nullptr)
    {
        return kInvalidArgument;
    }

    const std::wstring inputPath(input_path);
    const std::wstring outputPath(output_path);
    const std::wstring formatName(format);
    const bool inputExists = std::filesystem::exists(inputPath);
    DWORD exitCode = static_cast<DWORD>(-1);
    std::wstring commandOutput;
    bool success = false;

    if (inputExists)
    {
        const auto command = BuildAudioExtractCommand(inputPath, outputPath, track_index, formatName, bitrate_kbps, normalize != 0);
        success = ExecuteGeneratedOutputCommand(command, outputPath, commandOutput, exitCode);
    }

    const auto outputExists = std::filesystem::exists(outputPath);
    const std::wstring payload =
        L"{"
        L"\"message\":\"AnimeMediaCore 原生音频提取已执行。\"," 
        L"\"input_path\":\"" + EscapeJson(inputPath) + L"\","
        L"\"output_path\":\"" + EscapeJson(outputPath) + L"\","
        L"\"file_exists\":" + std::wstring(inputExists ? L"true" : L"false") + L","
        L"\"output_exists\":" + std::wstring(outputExists ? L"true" : L"false") + L","
        L"\"success\":" + std::wstring(success ? L"true" : L"false") + L","
        L"\"track_index\":" + std::to_wstring(track_index) + L","
        L"\"format\":\"" + EscapeJson(formatName) + L"\","
        L"\"bitrate_kbps\":" + std::to_wstring(bitrate_kbps > 0 ? bitrate_kbps : 192) + L","
        L"\"normalize\":" + std::wstring(normalize != 0 ? L"true" : L"false") + L","
        L"\"exit_code\":" + std::to_wstring(static_cast<unsigned long long>(exitCode)) + L","
        L"\"details\":\"" + EscapeJson(BuildResultSnippet(commandOutput)) + L"\""
        L"}";

    return CopyToOutput(payload, output_json, output_capacity);
}

int amc_detect_silence_json(const wchar_t* input_path, double noise_threshold_db, double min_duration, wchar_t* output_json, int output_capacity)
{
    if (input_path == nullptr)
    {
        return kInvalidArgument;
    }

    const std::wstring inputPath(input_path);
    const bool inputExists = std::filesystem::exists(inputPath);
    DWORD exitCode = static_cast<DWORD>(-1);
    std::wstring commandOutput;
    std::wstring segmentsJson = L"[]";

    if (inputExists)
    {
        const auto ffmpeg = ResolveToolCommand(L"ffmpeg.exe");
        const std::wstring command =
            ffmpeg +
            L" -hide_banner -nostats -i " + QuotePath(inputPath) +
            L" -vn -sn -af silencedetect=n=" + FormatDecimal(noise_threshold_db) + L"dB:d=" + FormatSeconds(min_duration) +
            L" -f null -";
        commandOutput = RunCommand(command, exitCode);
        segmentsJson = BuildSilenceSegmentsJson(commandOutput);
    }

    const std::wstring payload =
        L"{"
        L"\"message\":\"AnimeMediaCore 原生静音检测已执行。\"," 
        L"\"input_path\":\"" + EscapeJson(inputPath) + L"\","
        L"\"file_exists\":" + std::wstring(inputExists ? L"true" : L"false") + L","
        L"\"noise_threshold_db\":" + FormatDecimal(noise_threshold_db) + L","
        L"\"min_duration\":" + FormatSeconds(min_duration) + L","
        L"\"exit_code\":" + std::to_wstring(static_cast<unsigned long long>(exitCode)) + L","
        L"\"segments\":" + segmentsJson + L","
        L"\"details\":\"" + EscapeJson(BuildResultSnippet(commandOutput)) + L"\""
        L"}";

    return CopyToOutput(payload, output_json, output_capacity);
}

int amc_fast_clip_json(const wchar_t* input_path, const wchar_t* output_path, double start_seconds, double duration_seconds, wchar_t* output_json, int output_capacity)
{
    if (input_path == nullptr || output_path == nullptr)
    {
        return kInvalidArgument;
    }

    const std::wstring inputPath(input_path);
    const std::wstring outputPath(output_path);
    const bool inputExists = std::filesystem::exists(inputPath);
    DWORD exitCode = static_cast<DWORD>(-1);
    std::wstring commandOutput;
    bool success = false;

    if (inputExists)
    {
        const auto command = BuildFastClipCommand(inputPath, outputPath, start_seconds, duration_seconds);
        success = ExecuteGeneratedOutputCommand(command, outputPath, commandOutput, exitCode);
    }

    const auto outputExists = std::filesystem::exists(outputPath);
    const std::wstring payload =
        L"{"
        L"\"message\":\"AnimeMediaCore 原生无损快切已执行。\"," 
        L"\"input_path\":\"" + EscapeJson(inputPath) + L"\","
        L"\"output_path\":\"" + EscapeJson(outputPath) + L"\","
        L"\"file_exists\":" + std::wstring(inputExists ? L"true" : L"false") + L","
        L"\"output_exists\":" + std::wstring(outputExists ? L"true" : L"false") + L","
        L"\"success\":" + std::wstring(success ? L"true" : L"false") + L","
        L"\"start_seconds\":" + FormatSeconds(start_seconds) + L","
        L"\"duration_seconds\":" + FormatSeconds(duration_seconds) + L","
        L"\"exit_code\":" + std::to_wstring(static_cast<unsigned long long>(exitCode)) + L","
        L"\"details\":\"" + EscapeJson(BuildResultSnippet(commandOutput)) + L"\""
        L"}";

    return CopyToOutput(payload, output_json, output_capacity);
}

int amc_detect_scenes_json(const wchar_t* input_path, double threshold, wchar_t* output_json, int output_capacity)
{
    if (input_path == nullptr)
    {
        return kInvalidArgument;
    }

    const std::wstring inputPath(input_path);
    const bool inputExists = std::filesystem::exists(inputPath);
    DWORD exitCode = static_cast<DWORD>(-1);
    std::wstring commandOutput;
    std::wstring scenesJson = L"[]";

    if (inputExists)
    {
        const auto ffmpeg = ResolveToolCommand(L"ffmpeg.exe");
        const std::wstring command =
            ffmpeg +
            L" -hide_banner -i " + QuotePath(inputPath) +
            L" -map 0:v:0 -vf \"select='gt(scene," + FormatSeconds(threshold) + L")',showinfo\" -an -sn -f null -";
        commandOutput = RunCommand(command, exitCode);
        scenesJson = BuildSceneCutsJson(commandOutput);
    }

    const std::wstring payload =
        L"{"
        L"\"message\":\"AnimeMediaCore 原生场景检测已执行。\"," 
        L"\"input_path\":\"" + EscapeJson(inputPath) + L"\","
        L"\"file_exists\":" + std::wstring(inputExists ? L"true" : L"false") + L","
        L"\"threshold\":" + FormatSeconds(threshold) + L","
        L"\"exit_code\":" + std::to_wstring(static_cast<unsigned long long>(exitCode)) + L","
        L"\"scenes\":" + scenesJson + L","
        L"\"details\":\"" + EscapeJson(BuildResultSnippet(commandOutput)) + L"\""
        L"}";

    return CopyToOutput(payload, output_json, output_capacity);
}

int amc_sample_frame_png_json(const wchar_t* input_path, const wchar_t* output_path, double time_seconds, wchar_t* output_json, int output_capacity)
{
    if (input_path == nullptr || output_path == nullptr)
    {
        return kInvalidArgument;
    }

    const std::wstring inputPath(input_path);
    const std::wstring outputPath(output_path);
    const bool inputExists = std::filesystem::exists(inputPath);
    if (inputExists)
    {
        ExecuteFrameSample(inputPath, outputPath, time_seconds);
    }

    const bool outputExists = std::filesystem::exists(outputPath);
    const std::wstring payload =
        L"{"
        L"\"message\":\"AnimeMediaCore 原生抽帧已执行。\","
        L"\"input_path\":\"" + EscapeJson(inputPath) + L"\","
        L"\"output_path\":\"" + EscapeJson(outputPath) + L"\","
        L"\"input_exists\":" + std::wstring(inputExists ? L"true" : L"false") + L","
        L"\"output_exists\":" + std::wstring(outputExists ? L"true" : L"false") + L","
        L"\"time_seconds\":" + FormatSeconds(time_seconds) +
        L"}";

    return CopyToOutput(payload, output_json, output_capacity);
}

int amc_sample_frames_batch_json(const wchar_t* input_path, const wchar_t* output_directory, const wchar_t* file_prefix, const wchar_t* times_csv, wchar_t* output_json, int output_capacity)
{
    if (input_path == nullptr || output_directory == nullptr || file_prefix == nullptr || times_csv == nullptr)
    {
        return kInvalidArgument;
    }

    const std::wstring inputPath(input_path);
    const std::wstring outputDirectory(output_directory);
    const std::wstring filePrefix(file_prefix);
    const std::wstring timesCsv(times_csv);
    const auto sampleTimes = ParseTimesCsv(timesCsv);

    std::wostringstream samplesJson;
    samplesJson << L"[";

    bool first = true;
    int index = 1;
    for (const auto sampleTime : sampleTimes)
    {
        const auto fileName = filePrefix + L"-" + std::to_wstring(index) + L"-" + FormatSeconds(sampleTime) + L"s.png";
        const auto outputPath = (std::filesystem::path(outputDirectory) / fileName).wstring();
        const auto outputExists = ExecuteFrameSample(inputPath, outputPath, sampleTime);

        if (!first)
        {
            samplesJson << L",";
        }

        first = false;
        samplesJson << L"{"
                    << L"\"time_seconds\":" << FormatSeconds(sampleTime) << L","
                    << L"\"output_path\":\"" << EscapeJson(outputPath) << L"\","
                    << L"\"output_exists\":" << (outputExists ? L"true" : L"false")
                    << L"}";
        index++;
    }

    samplesJson << L"]";

    const std::wstring payload =
        L"{"
        L"\"message\":\"AnimeMediaCore 原生批量抽帧已执行。\","
        L"\"input_path\":\"" + EscapeJson(inputPath) + L"\","
        L"\"output_directory\":\"" + EscapeJson(outputDirectory) + L"\","
        L"\"samples\":" + samplesJson.str() +
        L"}";

    return CopyToOutput(payload, output_json, output_capacity);
}
