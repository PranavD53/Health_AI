// vadWorker.js
// A Web Worker to handle Voice Activity Detection (VAD) on the client side.

let sampleRate = 16000;
let energyThreshold = 0.015; // Adjusted dynamically or set statically
let silenceTimeoutMs = 1500;  // Hangover time
let minSpeechDurationMs = 200; // Minimum duration to consider as speech

let isSpeaking = false;
let lastSpeechTime = 0;
let speechStartTime = 0;

self.onmessage = (event) => {
  const { type, data } = event.data;
  
  if (type === 'init') {
    sampleRate = data.sampleRate || 16000;
    energyThreshold = data.energyThreshold || 0.015;
    silenceTimeoutMs = data.silenceTimeoutMs || 1500;
    minSpeechDurationMs = data.minSpeechDurationMs || 200;
    
    isSpeaking = false;
    lastSpeechTime = 0;
    speechStartTime = 0;
    return;
  }
  
  if (type === 'process') {
    const pcmData = new Float32Array(data);
    const now = Date.now();
    
    // Compute Root Mean Square (RMS) energy
    let sum = 0;
    for (let i = 0; i < pcmData.length; i++) {
      sum += pcmData[i] * pcmData[i];
    }
    const rms = Math.sqrt(sum / pcmData.length);
    
    const isAboveThreshold = rms > energyThreshold;
    
    if (isAboveThreshold) {
      lastSpeechTime = now;
      if (!isSpeaking) {
        if (speechStartTime === 0) {
          speechStartTime = now;
        } else if (now - speechStartTime >= minSpeechDurationMs) {
          isSpeaking = true;
          self.postMessage({ type: 'speech_start' });
        }
      }
    } else {
      if (isSpeaking) {
        if (now - lastSpeechTime >= silenceTimeoutMs) {
          isSpeaking = false;
          speechStartTime = 0;
          self.postMessage({ type: 'speech_stop' });
        }
      } else {
        // Reset speech start timer if energy falls below threshold too quickly (glitch filter)
        if (speechStartTime > 0 && now - lastSpeechTime > 200) {
          speechStartTime = 0;
        }
      }
    }
    
    // Always stream back the processed audio chunk if speaking or preparing to speak
    if (isSpeaking || speechStartTime > 0) {
      self.postMessage({ type: 'audio_chunk', chunk: pcmData.buffer }, [pcmData.buffer]);
    }
  }
};
