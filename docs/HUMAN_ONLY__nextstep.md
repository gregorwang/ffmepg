下面是一份完整的、可以直接交给 Codex 执行的任务文档。你复制整块丢给 Codex 就行：

---

```markdown
# Codex Task: Round N — Stabilize, Test, Whisper Adapter, Transcode CLI

## 0. Role & Rules

You are working on a C# / WPF desktop application for video post-processing.
The solution uses .NET 8, CommunityToolkit.Mvvm, and ffmpeg / ffprobe as external CLI tools.

**Hard rules for this entire task:**

- Every new or modified public method MUST have corresponding unit tests.
- Never swallow exceptions (catch without log or rethrow).
- All file-protocol models (transcript.json, selection.json, project.json) MUST have round-trip serialization tests (serialize → deserialize → assert equality).
- After finishing ALL tasks, run `dotnet build` and `dotnet test`. Fix any failure before committing.
- At the end of your work, list in the commit message: (a) number of new tests added, (b) total test count, (c) one-line summary per task completed.
- If during execution you change your plan, encounter unexpected issues, or abandon an approach, you MUST record it in `docs/decisions-log.md` (see Task A for format).

---

## 1. Current Architecture Summary (Read-Only Context)

```
Solution
├── Core/                          # No UI dependencies
│   ├── Models/                    # Domain models, enums
│   ├── Workflows/                 # TranscodeQueueWorkflow, AudioProjectWorkflow
│   ├── Services/                  # FfmpegService, FfprobeService, etc.
│   └── Interfaces/                # ITranscodeQueueCallbacks, etc.
├── CLI/                           # System.CommandLine console app
│   └── Commands/                  # probe, project, audio, transcript, selection
├── WPF GUI/                       # Views, ViewModels — calls Core workflows
├── Tests/                         # xUnit test project
└── docs/
```

**Key design principle:** Core contains all business logic. GUI and CLI are both thin shells that call Core. Any feature accessible via GUI must also be accessible via CLI, so that an external AI agent can drive the software through CLI commands.

**CLI I/O protocol:**
- stdout: final result as JSON
- stderr: JSONL progress lines `{"percent":0.5,"message":"..."}`
- Exit code 0 = success, non-zero = failure

**Audio Project file-based workflow (already implemented in CLI):**
```
probe → project init → audio export-work → [Whisper: NOT YET] → transcript import → selection import → audio render-selection
```

**Main Transcode Queue workflow (Core done, CLI NOT yet):**
- TranscodeQueueWorkflow in Core handles: pre-check → optional overlay prep → ffmpeg transcode → verify → optional delete source
- GUI already calls this workflow
- CLI entry does NOT exist yet

---

## 2. Tasks (Execute in Order)

### Task A: Create `docs/decisions-log.md`

Create the file `docs/decisions-log.md` with the following template content:

```markdown
# Decisions Log

This file records plan changes, abandoned approaches, unexpected issues,
and technical debt discovered during development. It is an engineering
journal for project maintainers, not for end users.

Each entry uses this format:

## [YYYY-MM-DD] Short Title

**Context**: What was being worked on
**Original Plan**: What was originally intended
**What Happened**: What actually occurred
**Decision Made**: What was done instead
**Future Impact**: How this affects subsequent work

---

(Entries below, newest first)
```

From this point onward in this task session, every time you change your approach or encounter something unexpected, append an entry here.

---

### Task B: Comprehensive Test Coverage for Existing Code

**Goal:** Bring test coverage for Core workflows and file-protocol models to a solid baseline.

**B1 — Round-trip serialization tests for all file-protocol models:**

For every JSON model used as a file protocol between CLI steps (TranscriptDocument, SelectionDocument, AudioProjectFile, and any others), write a test that:
1. Creates an instance with representative data (not empty, include edge-case values like unicode characters, zero-duration segments, negative timestamps)
2. Serializes to JSON string
3. Deserializes back
4. Asserts all properties are equal to the original

**B2 — AudioProjectWorkflow tests (minimum 15 tests total):**

Must include at least these scenarios:
- Happy path for each workflow step
- Input file does not exist → expect clear error, no crash
- Input file has no audio track → expect clear error
- transcript.json is malformed JSON → expect error with message indicating parse failure
- transcript.json is valid JSON but wrong schema → expect error
- selection.json references segment IDs that don't exist in transcript → expect error or warning
- selection.json is empty (no segments selected) → test what render does (should it produce silence? produce error? — decide and document)
- CancellationToken is triggered mid-operation → verify cancellation is respected
- Output path directory does not exist → expect it to be created, or clear error
- Work audio file is zero bytes → expect error

**B3 — TranscodeQueueWorkflow tests (minimum 10 tests total):**

Must include at least these scenarios:
- Single item, happy path, no overlay
- Queue of 3 items, second fails, third still executes (verify queue continues)
- Queue of 3 items, cancellation during second → third does NOT execute
- Input file missing → individual task fails with clear error
- Output disk path does not exist → clear error or auto-create
- ffmpeg process returns non-zero exit code → task marked as failed
- Delete-source is configured true, but source file is locked → task completes but logs warning
- Progress callback fires with increasing percentages

**B4 — CLI command parsing tests (minimum 5 tests):**

Test that CLI commands parse arguments correctly:
- `probe <path>` produces correct options object
- `audio export-work` with all flags parses correctly
- Missing required argument → exit code non-zero
- Unknown flag → exit code non-zero
- `--help` → exit code zero (does not crash)

After completing all tests, run `dotnet test` and ensure 100% pass.

---

### Task C: Whisper CLI Adapter (External Process, Zero Coupling)

**Goal:** Enable the audio project workflow to generate transcript.json by invoking a locally installed whisper.cpp binary as an external process.

**Key principle:** The adapter treats whisper.cpp the same way FfmpegService treats ffmpeg — as an external CLI tool. No ML libraries, no model loading in-process, no NuGet packages for whisper.

**C1 — Interface & Configuration**

In Core, define:

```csharp
public class WhisperOptions
{
    /// <summary>Path to whisper main.exe (or just "main" if on PATH)</summary>
    public string ExecutablePath { get; set; } = "main";
    
    /// <summary>Path to the .bin model file</summary>
    public string ModelPath { get; set; } = "";
    
    /// <summary>Language code: "ja", "zh", "en", "auto", etc.</summary>
    public string Language { get; set; } = "auto";
    
    /// <summary>Number of threads (0 = let whisper decide)</summary>
    public int Threads { get; set; } = 0;
    
    /// <summary>Additional raw CLI arguments to pass through</summary>
    public string ExtraArgs { get; set; } = "";
}

public interface ITranscriptionService
{
    /// <summary>
    /// Run speech-to-text on the given audio file and return a TranscriptDocument.
    /// </summary>
    Task<TranscriptDocument> TranscribeAsync(
        string audioFilePath,
        WhisperOptions options,
        IProgress<double>? progress,
        CancellationToken ct);
}
```

**C2 — WhisperCliAdapter implementation**

Create `Core/Services/WhisperCliAdapter.cs` implementing `ITranscriptionService`.

Logic:
1. Validate that `options.ExecutablePath` exists (or is on PATH) and `options.ModelPath` file exists. Throw clear exception if not.
2. Whisper.cpp requires 16kHz mono WAV input. Check if the input file is WAV. If not, use FfmpegService to convert it to a temp 16kHz mono WAV first. (The existing `audio export-work` step already produces a WAV, so in normal flow this conversion should be skippable — but handle it defensively.)
3. Build the whisper.cpp command line:
   ```
   {ExecutablePath} -m {ModelPath} -f {inputWav} -oj -l {Language} -t {Threads} {ExtraArgs}
   ```
   `-oj` tells whisper.cpp to output a JSON file alongside the input (e.g., `input.wav.json`).
4. Start the process, capture stderr for progress (whisper.cpp prints progress to stderr).
5. Wait for exit. If non-zero exit code, throw with stderr content.
6. Read the output JSON file (whisper.cpp format), parse it, and convert to the project's `TranscriptDocument` model.
7. Clean up any temp files.

**Whisper.cpp JSON output format** (for your reference when parsing):
```json
{
  "transcription": [
    {
      "timestamps": { "from": "00:00:00,000", "to": "00:00:03,500" },
      "offsets": { "from": 0, "to": 3500 },
      "text": " こんにちは"
    },
    ...
  ]
}
```

Convert this to your project's `TranscriptDocument` format. Map `offsets.from` → start ms, `offsets.to` → end ms, `text` → text. Generate sequential segment IDs (e.g., "seg_001", "seg_002", ...).

**C3 — CLI command: `transcript generate`**

Add a new CLI command:
```
transcript generate --project <project-dir> [--whisper-exe <path>] [--model <path>] [--language ja] [--threads 4]
```

Logic:
1. Load the AudioProject from the project directory
2. Locate the work audio file (should already exist from `audio export-work` step)
3. Call `ITranscriptionService.TranscribeAsync()`
4. Save the resulting TranscriptDocument as `transcript.json` in the project directory
5. Output result JSON to stdout

Default paths for `--whisper-exe` and `--model` can come from a config file or environment variable, but must be overridable via CLI flags.

**C4 — Whisper adapter tests (minimum 8 tests):**

Since we can't actually run whisper.cpp in unit tests, use a mock/stub approach:
- Test command-line argument building with various WhisperOptions combinations
- Test parsing of whisper.cpp JSON output format → TranscriptDocument conversion (use embedded sample JSON strings)
- Test handling of empty transcription result (no segments)
- Test handling of segments with zero duration
- Test handling of segments with unicode/CJK text
- Test error when executable path doesn't exist
- Test error when model path doesn't exist
- Test cleanup of temp files after successful transcription

---

### Task D: Main Transcode CLI Entry

**Goal:** Add CLI commands for the main transcode queue so external AI can drive transcoding without GUI.

**D1 — Single transcode command:**
```
transcode run --input <path> --output <path> --preset <preset-name> [--no-overlay]
```

- Calls TranscodeQueueWorkflow for a single item
- `--preset` selects encoding parameters (define at least "default" preset)
- `--no-overlay` is currently always implied since overlay prep hasn't been moved to Core yet. But include the flag so the interface is future-proof. If `--no-overlay` is absent and no overlay is available, just proceed without overlay (don't error).
- Progress reported via stderr JSONL, final result via stdout JSON.

**D2 — Batch transcode command:**
```
transcode queue --spec <spec.json>
```

Where `spec.json` is:
```json
{
  "tasks": [
    {
      "input": "C:/videos/raw1.mp4",
      "output": "C:/videos/out1.mp4",
      "preset": "default",
      "deleteSource": false
    },
    ...
  ]
}
```

- Calls TranscodeQueueWorkflow with the full queue
- Reports per-item progress and completion via stderr JSONL
- Final summary (how many succeeded, how many failed) via stdout JSON

**D3 — Transcode CLI tests (minimum 5 tests):**
- `transcode run` argument parsing with all flags
- `transcode queue` spec.json deserialization (valid file)
- `transcode queue` spec.json missing → clear error
- `transcode queue` spec.json malformed → clear error
- `transcode run` with input file not found → error exit code

---

## 3. Definition of Done

Before committing, verify ALL of the following:

- [ ] `dotnet build` succeeds with zero warnings (treat warnings as errors)
- [ ] `dotnet test` succeeds with ALL tests passing
- [ ] Total test count has increased by at least 40 from the starting count
- [ ] `docs/decisions-log.md` exists and contains at least the template (plus any entries from this session)
- [ ] New CLI commands are registered and appear in `--help` output
- [ ] No `// TODO` or `// HACK` comments added without a corresponding entry in decisions-log.md explaining why
- [ ] Commit message includes: new test count, total test count, one-line summary per task

---

## 4. Out of Scope (Do NOT Do These)

- Do NOT integrate Demucs or any audio source separation
- Do NOT embed whisper model files into the application
- Do NOT add any NuGet packages for ML/AI inference
- Do NOT move overlay/danmaku preparation to Core (that is a future task)
- Do NOT modify the GUI layer in this round
- Do NOT add any cloud API calls

---

## 5. Reference: Whisper.cpp Installation on This Machine

The user already has whisper.cpp installed:
- Binary directory: `C:\Users\汪家俊\Downloads\whisper-bin-x64\Release\`
- Main executable: `main.exe` (in that directory)
- Model file: approximately 1.6 GB, likely `ggml-medium.bin` (in the same directory or a `models` subfolder — adapter should accept explicit path)

These paths should NOT be hardcoded. They should be configurable via:
1. CLI flags (`--whisper-exe`, `--model`)
2. A config file (e.g., `appsettings.json` or a dedicated `whisper-config.json` in the project)
3. Fallback to environment variables `WHISPER_EXE_PATH` and `WHISPER_MODEL_PATH`

Priority: CLI flag > config file > environment variable > error "whisper not configured".
```

---

这份文档的设计思路：

**为什么按 A → B → C → D 的顺序？** 因为 A 是建日志文件（10 秒钟），B 是给现有代码补测试网（不改功能、只加测试，最安全），C 是新增 Whisper 适配层（新功能但解耦），D 是主转码 CLI（依赖现有 workflow）。先稳后推。

**为什么测试要求写得这么具体？** 因为如果你只说"请写测试"，Codex 会写 3 个 happy path 就交差。把具体场景列出来是在告诉它"这些是验收标准，少一个都不行"。

**Whisper 适配层为什么单独定义了接口？** 这样未来你如果想换成 faster-whisper、SenseVoice 或者云端 API，只需要实现同一个 `ITranscriptionService` 接口，不用动 workflow 和 CLI 的代码。

你拿这份文档直接丢给 Codex 就行。执行完之后回来我们一起看结果。