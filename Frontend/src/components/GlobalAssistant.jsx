import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';

class PCMAudioPlayer {
  constructor(sampleRate = 16000, onEnded = null) {
    this.sampleRate = sampleRate;
    this.onEnded = onEnded;
    this.audioCtx = null;
    this.nextPlayTime = 0;
    this.activeSources = [];
  }

  playChunk(arrayBuffer) {
    if (!this.audioCtx) {
      this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      this.nextPlayTime = this.audioCtx.currentTime;
    }

    const int16Data = new Int16Array(arrayBuffer);
    const float32Data = new Float32Array(int16Data.length);
    for (let i = 0; i < int16Data.length; i++) {
      float32Data[i] = int16Data[i] / 32768.0;
    }

    const audioBuffer = this.audioCtx.createBuffer(1, float32Data.length, this.sampleRate);
    audioBuffer.getChannelData(0).set(float32Data);

    const source = this.audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioCtx.destination);

    const currentTime = this.audioCtx.currentTime;
    if (this.nextPlayTime < currentTime) {
      this.nextPlayTime = currentTime;
    }
    
    source.start(this.nextPlayTime);
    this.nextPlayTime += audioBuffer.duration;
    this.activeSources.push(source);

    source.onended = () => {
      this.activeSources = this.activeSources.filter(src => src !== source);
      if (this.activeSources.length === 0 && this.onEnded) {
        this.onEnded();
      }
    };
  }

  stop() {
    this.activeSources.forEach(source => {
      try { source.stop(); } catch (e) {}
    });
    this.activeSources = [];
    if (this.audioCtx) {
      try { this.audioCtx.close(); } catch (e) {}
      this.audioCtx = null;
      this.nextPlayTime = 0;
    }
  }
}

function floatTo16BitPCM(input) {
  let output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    let s = Math.max(-1, Math.min(1, input[i]));
    output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return output.buffer;
}

export default function GlobalAssistant() {
  const { user, logout } = useAuth();
  const { t, currentLanguage, setCurrentLanguage } = useLanguage();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const consecutiveSilencesRef = useRef(0);
  const mediaRecorderRef = useRef(null);
  const audioContextRef = useRef(null);
  const streamRef = useRef(null);
  const voiceChunksRef = useRef([]);
  const animationFrameRef = useRef(null);
  const speechQueueRef = useRef([]);
  const isProcessingQueueRef = useRef(false);
  const voiceSocketRef = useRef(null);
  const vadWorkerRef = useRef(null);
  const pcmPlayerRef = useRef(null);
  
  const [tarsVoiceEnabled, setTarsVoiceEnabled] = useState(() => {
    return localStorage.getItem('tars_voice_enabled') !== 'false';
  });

  const [isInCall, setIsInCall] = useState(() => localStorage.getItem('is_in_call') === 'true');

  // Track if we are currently in an active voice dialog session (hands-free back-and-forth)
  const [voiceSessionActive, setVoiceSessionActive] = useState(false);
  const hasGreetedRef = useRef(false);
  
  // TARS Custom API Keys State
  const geminiKey = localStorage.getItem('tars_gemini_key') || '';
  const groqKey = localStorage.getItem('tars_groq_key') || '';
  const hfKey = localStorage.getItem('tars_hf_key') || '';

  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [language, setLanguage] = useState('en-IN'); // en-IN, hi-IN, te-IN
  const [isListening, setIsListening] = useState(false);
  const [backgroundListening, setBackgroundListening] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const languageLocales = {
      en: 'en-IN',
      hi: 'hi-IN',
      te: 'te-IN'
    };
    setLanguage(languageLocales[currentLanguage] || 'en-IN');
  }, [currentLanguage]);

  useEffect(() => {
    setMessages(prev => {
      if (prev.length === 0) {
        return [{ role: 'assistant', content: t('tarsGreetingInitial') }];
      }
      const newMsgs = [...prev];
      if (newMsgs[0] && newMsgs[0].role === 'assistant') {
        const content = newMsgs[0].content;
        if (content.startsWith('Hello! I am TARS') || 
            content.startsWith('नमस्ते!') || 
            content.startsWith('నమస్తే!')) {
          newMsgs[0].content = t('tarsGreetingInitial');
        }
      }
      return newMsgs;
    });
  }, [currentLanguage, t]);

  const connectVoiceWebSocket = () => {
    if (voiceSocketRef.current && (voiceSocketRef.current.readyState === WebSocket.CONNECTING || voiceSocketRef.current.readyState === WebSocket.OPEN)) {
      voiceSocketRef.current.send(JSON.stringify({ type: 'speech_start' }));
      setIsListening(true);
      return;
    }

    const token = localStorage.getItem('access_token');
    const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${wsScheme}://${window.location.host}/ws/tars/voice?token=${token}`;

    const socket = new WebSocket(wsUrl);
    voiceSocketRef.current = socket;
    socket.binaryType = 'arraybuffer';

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: 'speech_start' }));
      setIsListening(true);
    };

    socket.onmessage = (event) => {
      if (typeof event.data === 'string') {
        if (event.data.startsWith('data: ')) {
          const line = event.data;
          if (line === 'data: [DONE]') return;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'chunk') {
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg && lastMsg.role === 'assistant') {
                  lastMsg.content += data.content;
                }
                return newMessages;
              });
            } else if (data.type === 'action') {
              if (data.action) {
                handleAction(data.action, data.reply);
              }
            }
          } catch (e) {
            console.error("Error parsing socket text data:", e);
          }
          return;
        }

        const control = JSON.parse(event.data);
        if (control.type === 'transcription') {
          setMessages(prev => [
            ...prev,
            { role: 'user', content: control.text },
            { role: 'assistant', content: '' }
          ]);
          setLoading(false);
        } else if (control.type === 'audio_start') {
          setIsSpeaking(true);
        } else if (control.type === 'audio_end') {
          // Completed chunk
        } else if (control.type === 'error') {
          console.error("Socket error:", control.message);
          setLoading(false);
        }
      } else {
        if (pcmPlayerRef.current) {
          pcmPlayerRef.current.playChunk(event.data);
        }
      }
    };

    socket.onerror = (err) => {
      console.error("Voice socket error:", err);
    };

    socket.onclose = () => {
      console.log("Voice socket closed");
    };
  };

  useEffect(() => {
    vadWorkerRef.current = new Worker('/vadWorker.js');
    
    vadWorkerRef.current.onmessage = (e) => {
      const { type, chunk } = e.data;
      if (type === 'speech_start') {
        connectVoiceWebSocket();
      } else if (type === 'speech_stop') {
        if (voiceSocketRef.current && voiceSocketRef.current.readyState === WebSocket.OPEN) {
          voiceSocketRef.current.send(JSON.stringify({ 
            type: 'speech_stop', 
            groq_key: localStorage.getItem('tars_groq_key') || '', 
            hf_key: localStorage.getItem('tars_hf_key') || '' 
          }));
          stopListening();
          setLoading(true);
        }
      } else if (type === 'audio_chunk') {
        if (voiceSocketRef.current && voiceSocketRef.current.readyState === WebSocket.OPEN) {
          const int16PCM = floatTo16BitPCM(new Float32Array(chunk));
          voiceSocketRef.current.send(int16PCM);
        }
      }
    };

    return () => {
      if (vadWorkerRef.current) {
        vadWorkerRef.current.terminate();
      }
      if (voiceSocketRef.current) {
        voiceSocketRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    pcmPlayerRef.current = new PCMAudioPlayer(16000, () => {
      setIsSpeaking(false);
      if (voiceSessionActive) {
        setTimeout(() => {
          startListening();
        }, 300);
      }
    });
    return () => {
      if (pcmPlayerRef.current) {
        pcmPlayerRef.current.stop();
      }
    };
  }, [voiceSessionActive]);

  useEffect(() => {
    const handleStorageChange = () => {
      setTarsVoiceEnabled(localStorage.getItem('tars_voice_enabled') !== 'false');
      setIsInCall(localStorage.getItem('is_in_call') === 'true');
    };
    const handleCallStateChange = () => {
      const callActive = localStorage.getItem('is_in_call') === 'true';
      setIsInCall(callActive);
      if (callActive) {
        cancelSpeech();
        if (bgRecognitionRef.current) {
          try { bgRecognitionRef.current.stop(); } catch (e) {}
        }
      }
    };
    window.addEventListener('tars_voice_toggle', handleStorageChange);
    window.addEventListener('call_state_change', handleCallStateChange);
    window.addEventListener('storage', handleStorageChange);
    return () => {
      window.removeEventListener('tars_voice_toggle', handleStorageChange);
      window.removeEventListener('call_state_change', handleCallStateChange);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  // Load voices for speechSynthesis
  useEffect(() => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.getVoices();
      const handleVoices = () => {
        window.speechSynthesis.getVoices();
      };
      window.speechSynthesis.addEventListener('voiceschanged', handleVoices);
      return () => {
        window.speechSynthesis.removeEventListener('voiceschanged', handleVoices);
      };
    }
  }, []);

  // Autoplay and run on login via first user interaction
  // Autoplay greeting removed - TARS is silent and in standby by default on load

  // Voice broadcast listener for actions from other pages (e.g. anti-fraud scans)
  useEffect(() => {
    const handleTarsSpeak = (e) => {
      if (tarsVoiceEnabled) {
        speakMessage(e.detail.text);
      }
    };
    window.addEventListener('tars_speak', handleTarsSpeak);
    return () => {
      window.removeEventListener('tars_speak', handleTarsSpeak);
    };
  }, [tarsVoiceEnabled]);
  
  const messagesEndRef = useRef(null);
  const bgRecognitionRef = useRef(null);
  const activeRecognitionRef = useRef(null);
  const utteranceRef = useRef(null);

  const handleSendRef = useRef(null);
  const startListeningRef = useRef(null);
  
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  useEffect(() => {
    handleSendRef.current = handleSend;
    startListeningRef.current = startListening;
  });

  // Custom API key sync removed

  // Rising chime on activation: C5 -> E5 -> G5 -> C6
  const playActivationSound = () => {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const now = audioCtx.currentTime;
      const notes = [523.25, 659.25, 783.99, 1046.50];
      notes.forEach((freq, idx) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, now + idx * 0.08);
        gain.gain.setValueAtTime(0, now + idx * 0.08);
        gain.gain.linearRampToValueAtTime(0.2, now + idx * 0.08 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.08 + 0.25);
        osc.start(now + idx * 0.08);
        osc.stop(now + idx * 0.08 + 0.3);
      });
    } catch (e) {
      console.warn("Activation sound failed", e);
    }
  };

  // Descending chime on deactivation: G5 -> E5 -> C5 -> C4
  const playDeactivationSound = () => {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const now = audioCtx.currentTime;
      const notes = [783.99, 659.25, 523.25, 261.63];
      notes.forEach((freq, idx) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, now + idx * 0.08);
        gain.gain.setValueAtTime(0, now + idx * 0.08);
        gain.gain.linearRampToValueAtTime(0.2, now + idx * 0.08 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.08 + 0.25);
        osc.start(now + idx * 0.08);
        osc.stop(now + idx * 0.08 + 0.3);
      });
    } catch (e) {
      console.warn("Deactivation sound failed", e);
    }
  };

  // Helper matching activation commands
  const isActivationCommand = (text) => {
    const t = text.toLowerCase().trim();
    if (t === "tars" || t === "tars wake up" || t === "wake up tars" || 
        t.includes("tars turn on") || t.includes("turn on tars") || 
        t.includes("tars activate") || t.includes("tars chalu") || 
        t.includes("tars kholo") || t.includes("tars on") || 
        t.includes("tars start") || t.includes("tars meluko")) {
      return true;
    }
    return false;
  };

  // Helper matching deactivation commands
  const isDeactivationCommand = (text) => {
    const textVal = text.toLowerCase().trim();
    const phrasesStr = t('tarsDeactivatePhrases');
    const phrases = phrasesStr.split(',').map(p => p.trim().toLowerCase());
    return phrases.some(phrase => textVal.includes(phrase) || phrase === textVal);
  };



  // Automatic response language script detector
  const detectLanguageOfText = (str) => {
    if (/[\u0C00-\u0C7F]/.test(str)) return 'te';
    if (/[\u0900-\u097F]/.test(str)) return 'hi';
    // If no native script is found, fallback to active settings/state to support Hinglish/Tinglish
    const activeLang = localStorage.getItem('app_lang') || 'en';
    if (language.startsWith('te') || activeLang === 'te') return 'te';
    if (language.startsWith('hi') || activeLang === 'hi') return 'hi';
    return 'en';
  };

  const processSpeechQueue = () => {
    if (isInCall) {
      speechQueueRef.current = [];
      isProcessingQueueRef.current = false;
      setIsSpeaking(false);
      return;
    }

    if (speechQueueRef.current.length === 0) {
      isProcessingQueueRef.current = false;
      setIsSpeaking(false);
      return;
    }

    isProcessingQueueRef.current = true;
    setIsSpeaking(true);

    const nextItem = speechQueueRef.current.shift();
    if (!nextItem) {
      isProcessingQueueRef.current = false;
      setIsSpeaking(false);
      return;
    }

    const { text, callback } = nextItem;

    if ('speechSynthesis' in window) {
      // Clean up text for speech to avoid speaking punctuation like "asterisk", "square bracket", etc.
      const cleanedText = text
        .replace(/\*/g, '')
        .replace(/[\[\]]/g, '')
        .replace(/[{}]/g, '')
        .replace(/[-_]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();

      if (!cleanedText) {
        if (callback) callback();
        setTimeout(() => {
          processSpeechQueue();
        }, 100);
        return;
      }

      const utterance = new SpeechSynthesisUtterance(cleanedText);
      utteranceRef.current = utterance; // Keep a reference to prevent garbage collection
      const voices = window.speechSynthesis.getVoices();
      
      const detectedLang = detectLanguageOfText(text);
      let voice = null;
      
      if (detectedLang === 'te') {
        // Telugu sweet female voice search
        voice = voices.find(v => (v.lang.startsWith('te') || v.name.toLowerCase().includes('telugu')) && 
                            (v.name.toLowerCase().includes('shruti') || v.name.toLowerCase().includes('chitra') || v.name.toLowerCase().includes('female')));
        if (!voice) voice = voices.find(v => v.lang.startsWith('te') || v.name.toLowerCase().includes('telugu'));
        utterance.lang = 'te-IN';
      } else if (detectedLang === 'hi') {
        // Hindi sweet female voice search
        voice = voices.find(v => (v.lang.startsWith('hi') || v.name.toLowerCase().includes('hindi')) && 
                            (v.name.toLowerCase().includes('kalpana') || v.name.toLowerCase().includes('heera') || v.name.toLowerCase().includes('female')));
        if (!voice) voice = voices.find(v => v.lang.startsWith('hi') || v.name.toLowerCase().includes('hindi'));
        utterance.lang = 'hi-IN';
      } else {
        // English sweet female voice priorities
        const sweetFemaleEnglishPriorities = ['google us english', 'microsoft zira', 'samantha', 'google uk english female', 'karen', 'eva'];
        for (const name of sweetFemaleEnglishPriorities) {
          const found = voices.find(v => v.name.toLowerCase().includes(name) && v.lang.startsWith('en'));
          if (found) {
            voice = found;
            break;
          }
        }
        if (!voice) voice = voices.find(v => v.lang.startsWith('en') && v.name.toLowerCase().includes('female'));
        if (!voice) voice = voices.find(v => v.lang.startsWith('en') || v.name.toLowerCase().includes('english'));
        utterance.lang = 'en-US';
      }
      
      if (voice) {
        utterance.voice = voice;
      }
      
      // Sweet friendly tone & natural human speaking pace
      utterance.pitch = 1.15; 
      utterance.rate = 0.82; 
      
      const handleEnd = () => {
        utteranceRef.current = null;
        if (callback) {
          try {
            callback();
          } catch (e) {
            console.error("Callback error in speech queue:", e);
          }
        }
        setTimeout(() => {
          processSpeechQueue();
        }, 100);
      };
      
      utterance.onend = handleEnd;
      utterance.onerror = (e) => {
        console.warn("SpeechSynthesisUtterance error:", e);
        handleEnd();
      };
      
      window.speechSynthesis.speak(utterance);
    } else {
      setIsSpeaking(false);
      if (callback) callback();
    }
  };

  // Speaks using exactly one sweet female voice per language, with human-paced rate
  const speakMessage = (text, callback = null) => {
    if (isInCall) {
      if (callback) callback();
      return;
    }

    if (!('speechSynthesis' in window)) {
      setIsSpeaking(false);
      if (callback) callback();
      return;
    }

    // Split text into sentences using lookbehind pattern (safe in all modern browsers)
    const sentences = text
      .split(/(?<=[.?!।])\s+/)
      .map(s => s.trim())
      .filter(s => s.length > 0);

    if (sentences.length === 0) {
      if (callback) {
        if (speechQueueRef.current.length === 0 && !isProcessingQueueRef.current) {
          callback();
        } else {
          // Attach callback to the last item in the queue so it executes after all queued speech is finished
          const lastItem = speechQueueRef.current[speechQueueRef.current.length - 1];
          if (lastItem) {
            const oldCb = lastItem.callback;
            lastItem.callback = () => {
              if (oldCb) oldCb();
              callback();
            };
          } else {
            callback();
          }
        }
      }
      return;
    }

    // Queue all sentences. The callback will be attached only to the last sentence of this group.
    sentences.forEach((sentence, idx) => {
      const isLast = idx === sentences.length - 1;
      speechQueueRef.current.push({
        text: sentence,
        callback: isLast ? callback : null
      });
    });

    if (!isProcessingQueueRef.current) {
      processSpeechQueue();
    }
  };

  const cancelSpeech = () => {
    speechQueueRef.current = [];
    isProcessingQueueRef.current = false;
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    if (pcmPlayerRef.current) {
      pcmPlayerRef.current.stop();
    }
    utteranceRef.current = null;
    setIsSpeaking(false);
  };

  // Cleanup speech and active listener when voice toggle is disabled manually
  useEffect(() => {
    if (!tarsVoiceEnabled) {
      cancelSpeech();
      setVoiceSessionActive(false);
      stopListening();
    }
  }, [tarsVoiceEnabled]);

  // Dispatch state changes for other components (like TopNavBar) to stay in sync
  useEffect(() => {
    window.dispatchEvent(new CustomEvent('tars_state_change', {
      detail: { isListening, isSpeaking, loading, tarsVoiceEnabled }
    }));
  }, [isListening, isSpeaking, loading, tarsVoiceEnabled]);

  // Listen to global mic clicks from other components (like TopNavBar)
  useEffect(() => {
    const handleGlobalMicClick = () => {
      if (localStorage.getItem('is_in_call') === 'true') {
        alert(t('tarsVoiceCallWarning'));
        return;
      }
      
      if (!user) {
        cancelSpeech();
        speakMessage(t('tarsLoginWarning'));
        return;
      }

      if (isListening || isSpeaking || voiceSessionActive) {
        cancelSpeech();
        setVoiceSessionActive(false);
        stopListening();
        playDeactivationSound();
        return;
      }

      // Ensure TARS voice is enabled
      if (!tarsVoiceEnabled) {
        setTarsVoiceEnabled(true);
        localStorage.setItem('tars_voice_enabled', 'true');
        window.dispatchEvent(new Event('tars_voice_toggle'));
      }
      
      setIsOpen(true);
      cancelSpeech();
      setVoiceSessionActive(true);
      
      // Delay slightly to allow panel opening transition
      setTimeout(() => {
        if (startListeningRef.current) {
          startListeningRef.current();
        }
      }, 300);
    };

    window.addEventListener('tars_global_mic_click', handleGlobalMicClick);
    return () => {
      window.removeEventListener('tars_global_mic_click', handleGlobalMicClick);
    };
  }, [user, tarsVoiceEnabled, isListening, isSpeaking, voiceSessionActive]);

  // Background Standby listener logic (runs globally, halts when speaking, active listening, or in session)
  useEffect(() => {
    if (!tarsVoiceEnabled || isListening || isSpeaking || voiceSessionActive || isInCall) {
      if (bgRecognitionRef.current) {
        try {
          bgRecognitionRef.current.stop();
        } catch (e) {}
        bgRecognitionRef.current = null;
        setBackgroundListening(false);
      }
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("Background SpeechRecognition not supported in this browser.");
      return;
    }

    const bgRec = new SpeechRecognition();
    bgRec.continuous = false;
    bgRec.interimResults = true;
    bgRec.lang = language;

    bgRec.onstart = () => {
      setBackgroundListening(true);
    };

    bgRec.onend = () => {
      setBackgroundListening(false);
      if (tarsVoiceEnabled && !isListening && !isSpeaking && !voiceSessionActive && bgRecognitionRef.current === bgRec) {
        setTimeout(() => {
          if (tarsVoiceEnabled && !isListening && !isSpeaking && !voiceSessionActive && bgRecognitionRef.current === bgRec) {
            try {
              bgRec.start();
            } catch (e) {
              console.error("Failed to restart background listener", e);
            }
          }
        }, 1500);
      }
    };

    bgRec.onerror = (e) => {
      console.warn("Background SpeechRecognition error:", e);
      if (e.error === 'not-allowed') {
        setTarsVoiceEnabled(false);
        localStorage.setItem('tars_voice_enabled', 'false');
        window.dispatchEvent(new Event('tars_voice_toggle'));
      }
    };

    bgRec.onresult = (event) => {
      const lastIndex = event.results.length - 1;
      const transcript = event.results[lastIndex][0].transcript.trim();
      console.log("Background heard:", transcript);

      const transcriptLower = transcript.toLowerCase();
      const wakeWordsStr = t('tarsWakeWords');
      const wakeWords = wakeWordsStr.split(',').map(w => w.trim().toLowerCase());
      const containsWakeWord = wakeWords.some(w => transcriptLower.includes(w) || w === transcriptLower);

      if (containsWakeWord) {
        try {
          bgRec.stop();
        } catch (e) {}

        if (!user) {
          playActivationSound();
          speakMessage(t('tarsLoginWarning'));
          return;
        }

        let processedText = transcript;
        const wakeWordsStr = t('tarsWakeWords');
        const wakeWords = wakeWordsStr.split(',').map(w => w.trim().toLowerCase());
        wakeWords.sort((a, b) => b.length - a.length);
        for (const word of wakeWords) {
          const regex = new RegExp(`\\b${word}\\b`, 'gi');
          processedText = processedText.replace(regex, '');
          processedText = processedText.replace(new RegExp(word, 'gi'), '');
        }
        processedText = processedText.trim();

        playActivationSound();
        setVoiceSessionActive(true);

        if (processedText.length > 1) {
          handleSend(processedText);
        } else {
          // Greet and start active listening
          const greeting = t('tarsListening');
          speakMessage(greeting, () => {
            startListening();
          });
        }
      }
    };

    bgRecognitionRef.current = bgRec;
    const startTimeout = setTimeout(() => {
      if (bgRecognitionRef.current === bgRec) {
        try {
          bgRec.start();
        } catch (e) {
          console.warn("Failed to start background SpeechRecognition:", e);
        }
      }
    }, 300);

    return () => {
      clearTimeout(startTimeout);
      bgRecognitionRef.current = null;
      try {
        bgRec.stop();
      } catch (e) {}
    };
  }, [user, tarsVoiceEnabled, isListening, isSpeaking, voiceSessionActive, language, isInCall]);

  function stopListening() {
    if (activeRecognitionRef.current) {
      try {
        activeRecognitionRef.current.stop();
      } catch (e) {}
      activeRecognitionRef.current = null;
    }
    setIsListening(false);
  }

  const startListening = () => {
    if (isInCall) {
      alert(t('tarsVoiceCallWarning'));
      return;
    }
    
    let stoppedBg = false;
    if (bgRecognitionRef.current) {
      try {
        bgRecognitionRef.current.stop();
        stoppedBg = true;
      } catch (e) {}
    }

    cancelSpeech();
    setIsListening(true);

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert(t('tarsUnsupported'));
      setIsListening(false);
      return;
    }

    const startActiveRec = () => {
      if (isInCall) return;
      const activeRec = new SpeechRecognition();
      activeRec.continuous = false;
      activeRec.interimResults = false;
      activeRec.lang = language;

      activeRec.onstart = () => {
        console.log("Active SpeechRecognition started...");
      };

      activeRec.onend = () => {
        console.log("Active SpeechRecognition ended.");
        setIsListening(false);
      };

      activeRec.onerror = (e) => {
        console.error("Active SpeechRecognition error:", e);
        setIsListening(false);
        if (e.error === 'not-allowed') {
          alert(t('tarsMicDenied'));
        } else if (e.error !== 'no-speech' && e.error !== 'aborted') {
          console.warn(`Speech recognition non-fatal error: ${e.error}`);
        }
      };

      activeRec.onresult = (event) => {
        const transcript = event.results[0][0].transcript.trim();
        console.log("Active SpeechRecognition heard:", transcript);
        if (transcript.length > 0) {
          handleSend(transcript);
        }
      };

      activeRecognitionRef.current = activeRec;
      try {
        activeRec.start();
      } catch (e) {
        console.error("Failed to start active SpeechRecognition:", e);
        setIsListening(false);
      }
    };

    if (stoppedBg) {
      setTimeout(startActiveRec, 350);
    } else {
      startActiveRec();
    }
  };

  const handleSend = async (textToSend = null) => {
    const text = (textToSend || inputValue).trim();
    if (!text) return;

    setInputValue('');

    if (isDeactivationCommand(text)) {
      playDeactivationSound();
      const goodbye = t('tarsGoodbye');
      setMessages(prev => [...prev, { role: 'user', content: text }, { role: 'assistant', content: goodbye }]);
      speakMessage(goodbye);
      setVoiceSessionActive(false);
      return;
    }

    setMessages(prev => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '' }]);
    setLoading(true);

    let spokenIndex = 0;

    try {
      const data = await api.sendAssistantMessage(text, geminiKey, groqKey, hfKey, language, (chunkText) => {
        setMessages(prev => {
          const newMessages = [...prev];
          newMessages[newMessages.length - 1].content = chunkText;
          return newMessages;
        });

        // Speak completed sentences during streaming
        if (voiceSessionActive) {
          const pendingText = chunkText.slice(spokenIndex);
          let match;
          const sentenceRegex = /[^.?!।\n]+[.?!।\n]+/g;
          while ((match = sentenceRegex.exec(pendingText)) !== null) {
            const sentence = match[0].trim();
            if (sentence) {
              speakMessage(sentence);
            }
            spokenIndex += match[0].length;
          }
        }
      });
      
      setMessages(prev => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1].content = data.reply;
        return newMessages;
      });
      
      if (data.action) {
        await handleAction(data.action, data.reply);
      } else {
        if (voiceSessionActive) {
          const remainingText = data.reply.slice(spokenIndex).trim();
          speakMessage(remainingText || "", () => {
            setTimeout(() => {
              startListening();
            }, 300);
          });
        }
      }
    } catch (err) {
      console.error(err);
      const errorMsg = `Error: ${err.message}`;
      setMessages(prev => [...prev, { role: 'assistant', content: errorMsg }]);
      
      const speechError = t('tarsError');
      if (voiceSessionActive) {
        speakMessage(speechError, () => {
          setTimeout(() => {
            startListening();
          }, 300);
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (action, assistantReply = '') => {
    const { type, parameters } = action;
    setMessages(prev => [...prev, { role: 'system', content: `Executing system action: ${type}...` }]);

    const resumeVoice = () => {
      if (voiceSessionActive) {
        setTimeout(() => {
          if (startListeningRef.current) {
            startListeningRef.current();
          }
        }, 300);
      }
    };

    const speakAndResume = (speakText) => {
      if (voiceSessionActive) {
        speakMessage(speakText, resumeVoice);
      } else {
        resumeVoice();
      }
    };

    try {
      if (type === 'openPage') {
        const page = parameters.page_name || 'dashboard';
        const spec = parameters.specialization || parameters.speciality || '';
        if (page === 'appointments' || page === 'doctors') {
          navigate(`/appointments?search=${spec}`);
        } else {
          navigate(`/${page}`);
        }
        speakAndResume(assistantReply || `Opening ${page} page.`);
      } else if (type === 'createAppointment') {
        if (user && (user.role === 'doctor' || user.role === 'admin')) {
          const errorMsg = user.role === 'doctor' 
            ? "You cannot book an appointment as a doctor. You manage consultations from your dashboard workspace." 
            : "You cannot book an appointment as an administrator.";
          setMessages(prev => [...prev, { role: 'assistant', content: errorMsg }]);
          speakAndResume(errorMsg);
          return;
        }
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 2);
        const yyyy = tomorrow.getFullYear();
        const mm = String(tomorrow.getMonth() + 1).padStart(2, '0');
        const dd = String(tomorrow.getDate()).padStart(2, '0');
        const tomorrowStr = `${yyyy}-${mm}-${dd}`;

        const docId = parameters.doctor_id || 1;
        const date = parameters.date || tomorrowStr;
        const time = parameters.time || '10:00';
        
        try {
          await api.bookAppointment(docId, date, time);
          const successMsg = `Appointment successfully booked for ${date} at ${time}!`;
          setMessages(prev => [...prev, { role: 'assistant', content: successMsg }]);
          speakAndResume(successMsg);
        } catch (err) {
          const errorMsg = err.response?.data?.detail || err.message || "Failed to book appointment.";
          setMessages(prev => [...prev, { role: 'assistant', content: errorMsg }]);
          speakAndResume(errorMsg);
        }
      } else if (type === 'fetchPrescription') {
        const list = parameters.prescriptions || [];
        if (list.length > 0) {
          setMessages(prev => [
            ...prev,
            {
              role: 'assistant',
              content: `Here are the prescriptions found:`,
              uiCard: 'prescriptions',
              data: list
            }
          ]);
        }
        speakAndResume(assistantReply || `Prescriptions fetched successfully.`);
      } else if (type === 'updatePatient') {
        const addr = parameters.address || '';
        let lat = parameters.latitude;
        let lng = parameters.longitude;

        const performUpdate = async (finalLat, finalLng) => {
          const payload = { address: addr };
          if (finalLat && finalLng) {
            payload.latitude = finalLat;
            payload.longitude = finalLng;
          }
          await api.updateProfile(payload);
          const successMsg = `Patient profile successfully updated with address "${addr || 'current position'}" and location (${finalLat || 'N/A'}, ${finalLng || 'N/A'}).`;
          setMessages(prev => [...prev, { role: 'assistant', content: successMsg }]);
          speakAndResume(successMsg);
        };

        if (!lat || !lng) {
          if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
              async (position) => {
                const browserLat = position.coords.latitude;
                const browserLng = position.coords.longitude;
                await performUpdate(browserLat, browserLng);
              },
              async (error) => {
                console.warn("Browser geolocation failed, updating address only", error);
                await performUpdate(null, null);
              },
              { enableHighAccuracy: true, timeout: 5000 }
            );
            return;
          }
        }
        await performUpdate(lat, lng);
      } else if (type === 'triggerSOS' || type === 'trigger_sos') {
        speakAndResume(assistantReply || "Triggering emergency SOS.");
        if (navigator.geolocation) {
          navigator.geolocation.getCurrentPosition(
            async (position) => {
              const lat = position.coords.latitude;
              const lng = position.coords.longitude;
              await api.triggerSOS(null, lat, lng);
            },
            async (error) => {
              console.warn("Geolocation failed or denied, sending SOS without coordinates.", error);
              await api.triggerSOS(null, null, null);
            },
            { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
          );
        } else {
          await api.triggerSOS(null, null, null);
        }
      } else if (type === 'logout') {
        speakAndResume(assistantReply || "Logging out.");
        logout();
      } else if (type === 'setReminder' || type === 'set_reminder') {
        const payload = {
          medicine_name: parameters.medicine_name || 'Medicine',
          dosage: parameters.dosage || '1 pill',
          time: parameters.time || '08:00',
          days: parameters.days || 'Daily',
          method: parameters.method || 'app',
          contact_info: parameters.contact_info || null
        };
        const data = await api.createReminder(payload);
        const successMsg = `Reminder successfully set for ${data.medicine_name} (${data.dosage}) at ${data.time} via ${data.method}!`;
        setMessages(prev => [...prev, { role: 'assistant', content: successMsg }]);
        window.dispatchEvent(new Event('reminders_updated'));
        speakAndResume(successMsg);
      } else if (type === 'createPrescription' || type === 'create_prescription') {
        speakAndResume(assistantReply || "Prescription successfully issued.");
        setTimeout(() => {
          navigate('/chat');
        }, 1500);
      }
    } catch (err) {
      console.error(err);
      const errorMsg = `Action failed: ${err.message}`;
      setMessages(prev => [...prev, { role: 'assistant', content: errorMsg }]);
      speakAndResume(errorMsg);
    }
  };

  const handleInputFocusOrChange = () => {
    cancelSpeech();
    setVoiceSessionActive(false);
    stopListening();
  };

  // Compute HUD state for TARS voice assistant
  let hudIcon = 'forum';
  let hudBg = 'bg-primary hover:bg-primary/95';
  let hudTitle = t('assistant');

  if (isOpen) {
    hudIcon = 'close';
    hudTitle = t('tarsClose');
  } else {
    if (loading) {
      hudIcon = 'progress_activity';
      hudBg = 'bg-indigo-600 hover:bg-indigo-700';
      hudTitle = t('tarsThinking');
    } else if (isListening) {
      hudIcon = 'graphic_eq';
      hudBg = 'bg-emerald-600 hover:bg-emerald-700';
      hudTitle = t('tarsListeningStatus');
    } else if (isSpeaking) {
      hudIcon = 'volume_up';
      hudBg = 'bg-cyan-600 hover:bg-cyan-700';
      hudTitle = t('tarsSpeakingStatus');
    } else {
      hudIcon = 'forum';
      hudBg = tarsVoiceEnabled ? 'bg-primary hover:bg-primary/95' : 'bg-outline/60 hover:bg-outline/70';
      hudTitle = tarsVoiceEnabled ? t('tarsActiveStatus') : t('tarsDisabledStatus');
    }
  }

  // Halos based on voice states
  let haloColor = '';
  if (loading) {
    haloColor = 'border-indigo-500';
  } else if (isListening) {
    haloColor = 'border-emerald-500';
  } else if (isSpeaking) {
    haloColor = 'border-cyan-500';
  } else if (tarsVoiceEnabled && !isOpen) {
    haloColor = 'border-emerald-500/50';
  }

  return (
    <div className="fixed bottom-6 right-6 z-[90] flex flex-col items-end">
      {isOpen && (
        <div className="w-96 h-[500px] bg-white rounded-2xl border border-outline-variant shadow-2xl overflow-hidden flex flex-col mb-4 animate-in slide-in-from-bottom-8 duration-200">
          
          {/* Header */}
          <div className="p-4 border-b border-outline-variant bg-surface flex flex-col gap-xs">
            <div className="flex justify-between items-center w-full">
              <div className="flex items-center gap-xs">
                <span className="material-symbols-outlined text-secondary animate-pulse">forum</span>
                <h3 className="font-bold text-primary text-label-md">{t('assistant')}</h3>
              </div>
              
              <div className="flex items-center gap-sm">
                {/* Close button removed as launcher button below toggles open/close */}
              </div>
            </div>
            
            {/* TARS Status Control Row */}
            <div className="flex justify-between items-center mt-1 pt-1 border-t border-outline-variant/40 text-[10px]">
              <div className="flex items-center gap-xs text-outline font-semibold">
                <span className={`w-2 h-2 rounded-full ${tarsVoiceEnabled ? 'bg-emerald-500 animate-pulse' : 'bg-outline/60'}`}></span>
                <span>{tarsVoiceEnabled ? t('tarsStandbyActive') : t('tarsStandbyDisabled')}</span>
              </div>
              <button 
                onClick={() => {
                  const newVal = !tarsVoiceEnabled;
                  if (!newVal) {
                    playDeactivationSound();
                    setVoiceSessionActive(false);
                  } else {
                    playActivationSound();
                  }
                  setTarsVoiceEnabled(newVal);
                  localStorage.setItem('tars_voice_enabled', newVal ? 'true' : 'false');
                  window.dispatchEvent(new Event('tars_voice_toggle'));
                }}
                className={`px-2 py-0.5 rounded-full font-bold text-[9px] transition-all focus:outline-none ${
                  tarsVoiceEnabled 
                    ? 'bg-outline-variant/40 text-outline hover:bg-error/10 hover:text-error' 
                    : 'bg-emerald-100 text-emerald-800 hover:bg-emerald-200'
                }`}
              >
                {tarsVoiceEnabled ? t('tarsTurnOff') : t('tarsTurnOn')}
              </button>
            </div>
          </div>

            {/* Messages List */}
            <>
              <div className="flex-1 p-4 overflow-y-auto space-y-md bg-surface-container-lowest">
                {messages.map((msg, index) => (
                  <div 
                    key={index} 
                    className={`flex flex-col ${
                      msg.role === 'user' ? 'items-end' : msg.role === 'system' ? 'items-center' : 'items-start'
                    }`}
                  >
                    <div 
                      className={`max-w-[85%] rounded-xl px-4 py-2 text-xs leading-relaxed ${
                        msg.role === 'user' 
                          ? 'bg-secondary text-white rounded-tr-none' 
                          : msg.role === 'system'
                          ? 'bg-surface-container text-outline text-[10px] font-semibold'
                          : 'bg-surface-container-high text-on-surface rounded-tl-none'
                      }`}
                    >
                      {msg.content.replace(/\[ACTION:[\s\S]*?\]/g, '')}
                      {msg.uiCard === 'prescriptions' && msg.data && (
                        <div className="mt-2 space-y-xs w-full">
                          {msg.data.map((p, idx) => (
                            <a
                              key={idx}
                              href={p.file_path}
                              target="_blank"
                              rel="noreferrer"
                              className="flex items-center gap-xs p-2 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg font-bold border border-primary/20 transition-all text-[11px] no-underline"
                            >
                              <span className="material-symbols-outlined text-[16px]">download</span>
                              <span className="truncate flex-1">{p.file_name}</span>
                              <span className="text-[9px] text-outline font-normal">{p.uploaded_at.split(' ')[0]}</span>
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                
                {loading && (
                  <div className="flex items-center gap-xs text-outline text-xs animate-pulse">
                    <span className="w-1.5 h-1.5 bg-outline rounded-full animate-bounce"></span>
                    <span className="w-1.5 h-1.5 bg-outline rounded-full animate-bounce delay-75"></span>
                    <span className="w-1.5 h-1.5 bg-outline rounded-full animate-bounce delay-150"></span>
                    <span>{t('tarsThinkingLabel')}</span>
                  </div>
                )}
                
                {isListening && (
                  /* Listening Indicator Waveform */
                  <div className="flex items-center justify-center gap-xs p-2 bg-emerald-500/10 text-emerald-500 rounded-xl text-xs font-semibold animate-pulse border border-emerald-500/20">
                    <span className="material-symbols-outlined text-[16px] animate-spin">graphic_eq</span>
                    <span>{t('tarsListeningStatus')}</span>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </div>

              {/* Quick Suggestions */}
              <div className="p-2 border-t border-outline-variant bg-surface flex gap-sm overflow-x-auto whitespace-nowrap scrollbar-none">
                <button 
                  onClick={() => handleSend(t('tarsSuggestionFindDoctorText'))}
                  className="text-[10px] bg-secondary-container text-on-secondary-container px-2.5 py-1 rounded-full font-bold hover:opacity-90 active:scale-95 duration-100"
                >
                  {t('tarsSuggestionFindDoctor')}
                </button>
                <button 
                  onClick={() => handleSend(t('tarsSuggestionBookVisitText'))}
                  className="text-[10px] bg-secondary-container text-on-secondary-container px-2.5 py-1 rounded-full font-bold hover:opacity-90 active:scale-95 duration-100"
                >
                  {t('tarsSuggestionBookVisit')}
                </button>
                <button 
                  onClick={() => handleSend(t('tarsSuggestionViewRecordsText'))}
                  className="text-[10px] bg-secondary-container text-on-secondary-container px-2.5 py-1 rounded-full font-bold hover:opacity-90 active:scale-95 duration-100"
                >
                  {t('tarsSuggestionViewRecords')}
                </button>
                <button 
                  onClick={() => handleSend(t('tarsSuggestionFileComplaintText'))}
                  className="text-[10px] bg-secondary-container text-on-secondary-container px-2.5 py-1 rounded-full font-bold hover:opacity-90 active:scale-95 duration-100"
                >
                  {t('tarsSuggestionFileComplaint')}
                </button>
              </div>

              {/* Input Panel */}
              <div className="p-3 border-t border-outline-variant bg-white flex gap-sm items-center">
                <input 
                  type="text" 
                  placeholder={t('tarsInputPlaceholder')}
                  value={inputValue}
                  onChange={(e) => {
                    setInputValue(e.target.value);
                    handleInputFocusOrChange();
                  }}
                  onFocus={handleInputFocusOrChange}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  className="flex-1 py-2 px-3 border border-outline-variant rounded-lg bg-surface text-xs text-on-surface focus:outline-none focus:border-secondary"
                />
                
                <button 
                  onClick={() => handleSend()}
                  className="p-2 bg-primary hover:bg-primary/95 text-white rounded-full transition-all focus:outline-none active:scale-95"
                >
                  <span className="material-symbols-outlined text-[18px]">send</span>
                </button>
              </div>
            </>
        </div>
      )}

      {/* Launcher Button with dynamic TARS HUD */}
      <button 
        onClick={() => {
          if (!user) {
            cancelSpeech();
            speakMessage(t('tarsLoginWarning'));
            return;
          }
          const nextOpen = !isOpen;
          setIsOpen(nextOpen);
          if (!nextOpen) {
            cancelSpeech();
            setVoiceSessionActive(false);
            stopListening();
          }
        }}
        className={`w-14 h-14 ${hudBg} text-white rounded-full flex items-center justify-center shadow-2xl active:scale-95 transition-all duration-300 focus:outline-none relative`}
        title={hudTitle}
      >
        {/* Glowing Halo Rings */}
        {haloColor && (
          <span className={`absolute -inset-1.5 rounded-full border-2 ${haloColor} ${
            isListening ? 'animate-ping duration-1000' : isSpeaking ? 'animate-pulse' : tarsVoiceEnabled && !isOpen ? 'animate-pulse opacity-50' : 'animate-pulse'
          } pointer-events-none`}></span>
        )}
        
        {/* Status Indicator Dot (Standby) */}
        {tarsVoiceEnabled && !isOpen && !isListening && !isSpeaking && !loading && (
          <span className="absolute top-0 right-0 w-3.5 h-3.5 bg-emerald-500 rounded-full border-2 border-white flex items-center justify-center shadow-md">
            <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse"></span>
          </span>
        )}
        
        {/* Icon */}
        <span className={`material-symbols-outlined text-[28px] ${hudIcon === 'progress_activity' ? 'animate-spin' : ''}`}>
          {hudIcon}
        </span>
      </button>
    </div>
  );
}
