# Provider contract

The core editor must not depend on one transcription vendor. A provider adapter returns a canonical transcript and a processing receipt.

```json
{
  "format": "cvc-transcript-v1",
  "language": "ru",
  "cues": [
    {"start": 1.2, "end": 3.4, "text": "...", "speaker": "speaker-01", "confidence": 0.91}
  ],
  "processing": {
    "provider": "provider-id",
    "mode": "cloud",
    "uploaded": true,
    "retention": "confirmed by provider",
    "user_consent": true
  }
}
```

Supported entry paths:

1. Imported SRT, VTT, or provider JSON. This is the default and makes no network request.
2. An explicit cloud provider adapter. Ask for consent before upload and keep its credentials outside the project.
3. An optional local adapter. It may use CPU/GPU when available, but it must never be required for installation or onboarding.

The adapter must not assign a real person's name from a diarization label. Identity confirmation belongs to the review layer.
