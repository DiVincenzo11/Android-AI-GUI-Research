# Third-party material

- Android Debug Bridge, UIAutomator and screenrecord are external Android SDK/device tools. Not redistributed. Documentation: https://developer.android.com/tools/adb
- Pillow is an external Python dependency, under its own license.
- Optional RapidOCR uses the fixed `rapidocr-onnxruntime==1.4.4` API and ONNX Runtime: https://github.com/RapidAI/RapidOCR . Its source and model licenses remain with the dependency distribution; this repository does not bundle OCR engine/model files. Upstream development has moved to the newer `rapidocr` package.
- Optional pytesseract / Tesseract are external OCR components under their respective licenses: https://github.com/madmaze/pytesseract and https://github.com/tesseract-ocr/tesseract . Tesseract engine and model files are not included.
- ScenGen is credited as a separate research baseline: https://github.com/iGUITest/ScenGen . No ScenGen code is bundled or claimed as this repository's implementation.
- `examples/historical/` includes selected screenshots of Otter, Perplexity and Brave captured during research, and selected native UI fields. App UI, trademarks, and any artwork remain their owners' property and are excluded from the source-code MIT license. The Brave page displays an original photo credit to Dylan Malval, retained in the unchanged capture. These images document observed behavior; no ownership of app artwork or blanket redistribution license is claimed.
- Historical observations are not endorsements of the apps, compliance findings, or current-version guarantees.
