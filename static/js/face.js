/**
 * Thin wrapper around face-api.js used by both the face-enrollment page
 * and the mark-attendance page. Models are loaded once from /static/models
 * (bundled locally so the whole system works without an internet
 * connection once the page has loaded).
 */
const FaceEngine = (function () {
  let modelsLoaded = false;
  const MODEL_URL = "/static/models";

  async function loadModels() {
    if (modelsLoaded) return;
    await Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
      faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
      faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
    ]);
    modelsLoaded = true;
  }

  async function startCamera(videoEl) {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 480, height: 480, facingMode: "user" },
      audio: false,
    });
    videoEl.srcObject = stream;
    await videoEl.play();
    return stream;
  }

  function stopCamera(stream) {
    if (stream) stream.getTracks().forEach((t) => t.stop());
  }

  /** Detect a single face in the given <video> element and return its
   * 128-d descriptor (a plain array of floats), or null if no face found. */
  async function captureDescriptor(videoEl) {
    const options = new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.5 });
    const result = await faceapi
      .detectSingleFace(videoEl, options)
      .withFaceLandmarks()
      .withFaceDescriptor();
    if (!result) return null;
    return Array.from(result.descriptor);
  }

  return { loadModels, startCamera, stopCamera, captureDescriptor };
})();
