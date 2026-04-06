# AnimeMediaCore

`AnimeMediaCore` 是 `AnimeTranscoder` 的未来原生媒体核心目录。

当前它的定位不是马上替代 `ffmpeg CLI`，而是作为后续 `C/C++` 能力下沉的正式边界。

## 目标

- 为媒体探测、校验、抽帧、字幕分析等能力提供原生实现空间
- 对外提供稳定的 `C ABI`
- 对内允许使用 `C++` 封装复杂逻辑
- 与 `C#` 桌面层通过 `DLL` 集成

## 目录约定

```text
AnimeMediaCore/
  include/   # 对外头文件
  src/       # .c / .cpp 实现
  tests/     # 原生模块测试
```

## 设计原则

- 对外接口尽量小
- 优先下沉探测与校验，不急于重写全链路转码
- 公开接口使用 `C`
- 内部实现允许使用 `C++`

## 建议的第一批接口

- `amc_probe_media`
- `amc_validate_output`
- `amc_sample_frame`
- `amc_analyze_subtitle_tracks`

## 当前状态

当前目录已具备可编译的 `Visual Studio + CMake` 原生模块骨架，并且已经实现第一批接口：

- `amc_probe_media_json`
- `amc_validate_output_json`
- `amc_analyze_subtitles_json`
- `amc_sample_frame_png_json`
- `amc_sample_frames_batch_json`

当前实现仍然以调用打包后的 `ffmpeg/ffprobe` 为主，但已经完成了：

- 稳定的 `C ABI`
- `C++` 内部实现
- 本机构建脚本
- 与 `WPF` 应用侧的直接集成

下一阶段继续下沉的重点：

- `amc_probe_media`
- `amc_validate_output`
- 更细的帧采样与截图分析
- 再评估是否值得进入 `libav*` 级别下沉
