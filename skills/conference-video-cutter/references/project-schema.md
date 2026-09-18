# Review project model

Use a human-readable JSON project as the interchange format. Paths are relative to the project file unless explicitly documented otherwise.

```json
{
  "language": "ru",
  "source": "recording.mp4",
  "transcript": "transcript.cvc.json",
  "transcription": {"mode": "import", "provider": null},
  "output_dir": "output",
  "copy_streams": false,
  "speakers": {
    "speaker-01": {"name": "Alex Example", "name_ru": "Алексей Пример", "topic": "..."}
  },
  "segments": [
    {
      "id": "01",
      "speaker_id": "speaker-01",
      "title": "Тема выступления",
      "kind": "main_talk",
      "start": "00:05:00.000",
      "end": "00:25:00.000",
      "role": "speaker"
    }
  ]
}
```

Use half-open ranges `[start, end)`. `role: speaker` requires a confirmed speaker; `role: extra` is for host-only material, preparation, technical delays, opening, and closing. Keep intentionally excluded ranges in review notes rather than silently deleting evidence.
