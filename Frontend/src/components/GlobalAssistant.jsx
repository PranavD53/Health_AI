import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';

export default function GlobalAssistant() {
  const { user } = useAuth();
  const { t, currentLanguage, setCurrentLanguage } = useLanguage();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  
  const [tarsVoiceEnabled, setTarsVoiceEnabled] = useState(() => {
    return localStorage.getItem('tars_voice_enabled') !== 'false';
  });

  useEffect(() => {
    const handleStorageChange = () => {
      setTarsVoiceEnabled(localStorage.getItem('tars_voice_enabled') !== 'false');
    };
    window.addEventListener('tars_voice_toggle', handleStorageChange);
    window.addEventListener('storage', handleStorageChange);
    return () => {
      window.removeEventListener('tars_voice_toggle', handleStorageChange);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);
  // Track if we are currently in an active voice dialog session (hands-free back-and-forth)
  const [voiceSessionActive, setVoiceSessionActive] = useState(false);
  const hasGreetedRef = useRef(false);
  
  // TARS Custom API Keys State
  const [groqKey, setGroqKey] = useState(() => localStorage.getItem('tars_groq_key') || '');
  const [hfKey, setHfKey] = useState(() => localStorage.getItem('tars_hf_key') || '');
  const [showSettings, setShowSettings] = useState(false);

  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I am TARS, your multilingual AI assistant. I can speak and listen in English, Hindi (हिन्दी), Telugu (తెలుగు), Hinglish, and Tinglish. Say "TARS wake up" or click the mic to begin, or type a request to navigate through the application.' }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [language, setLanguage] = useState('en-US'); // en-US, hi-IN, te-IN

  useEffect(() => {
    if (currentLanguage === 'hi') {
      setLanguage('hi-IN');
    } else if (currentLanguage === 'te') {
      setLanguage('te-IN');
    } else {
      setLanguage('en-US');
    }
  }, [currentLanguage]);
  const [isListening, setIsListening] = useState(false);
  const [backgroundListening, setBackgroundListening] = useState(false);
  const [loading, setLoading] = useState(false);

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
  useEffect(() => {
    if (!user || !tarsVoiceEnabled) return;

    const initVoiceOnInteraction = () => {
      if (!hasGreetedRef.current) {
        hasGreetedRef.current = true;
        
        try {
          const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
          if (audioCtx.state === 'suspended') {
            audioCtx.resume();
          }
        } catch (e) {}

        playActivationSound();
        const uiLang = localStorage.getItem('app_lang') || 'en';
        let greeting = "TARS is active and ready. How can I help you today?";
        if (uiLang === 'hi') {
          greeting = "नमस्कार, मैं टार्स हूँ। मैं आज आपकी क्या सहायता कर सकती हूँ?";
        } else if (uiLang === 'te') {
          greeting = "నమస్కారం, నేను టార్స్. ఈ రోజు నేను మీకు ఎలా సహాయపడగలను?";
        }
        
        setVoiceSessionActive(true);
        speakMessage(greeting, () => {
          startListening();
        });
      }
    };

    window.addEventListener('click', initVoiceOnInteraction, { once: true });
    window.addEventListener('keydown', initVoiceOnInteraction, { once: true });

    return () => {
      window.removeEventListener('click', initVoiceOnInteraction);
      window.removeEventListener('keydown', initVoiceOnInteraction);
    };
  }, [user, tarsVoiceEnabled]);

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
  }, [messages, showSettings]);

  useEffect(() => {
    handleSendRef.current = handleSend;
    startListeningRef.current = startListening;
  });

  useEffect(() => {
    localStorage.setItem('tars_groq_key', groqKey);
  }, [groqKey]);

  useEffect(() => {
    localStorage.setItem('tars_hf_key', hfKey);
  }, [hfKey]);

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
    const t = text.toLowerCase().trim();
    const sleepPhrases = [
      "tars go to sleep", "tars sleep", "tars turn off", "turn off tars", 
      "tars stop", "stop tars", "tars deactivate", "tars bye", "bye tars",
      "tars sojao", "tars band karo", "tars off karo", "tars bandh karo", 
      "tars paduko", "tars off cheyyi", "tars stop cheyyi", "tars bandh cheyyi",
      "go to sleep tars", "sleep tars", "sojao tars", "band karo tars"
    ];
    return sleepPhrases.some(phrase => t.includes(phrase));
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

  // Speaks using exactly one sweet female voice per language, with human-paced rate
  const speakMessage = (text, callback = null) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      setIsSpeaking(true);
      const utterance = new SpeechSynthesisUtterance(text);
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
        setIsSpeaking(false);
        if (callback) callback();
      };
      
      utterance.onend = handleEnd;
      utterance.onerror = handleEnd; // fallback to continue even on error
      
      window.speechSynthesis.speak(utterance);
    } else {
      setIsSpeaking(false);
      if (callback) callback();
    }
  };

  const cancelSpeech = () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    utteranceRef.current = null;
    setIsSpeaking(false);
  };

  // Cleanup speech and active listener when voice toggle is disabled manually
  useEffect(() => {
    if (!tarsVoiceEnabled) {
      cancelSpeech();
      setVoiceSessionActive(false);
      if (activeRecognitionRef.current) {
        try { activeRecognitionRef.current.stop(); } catch(e){}
      }
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
  }, [tarsVoiceEnabled]);

  // Background Standby listener logic (runs globally, halts when speaking, active listening, or in session)
  useEffect(() => {
    if (!user || !tarsVoiceEnabled || isListening || isSpeaking || voiceSessionActive) {
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
    bgRec.continuous = true;
    bgRec.interimResults = true;
    bgRec.lang = language;

    bgRec.onstart = () => {
      setBackgroundListening(true);
    };

    bgRec.onend = () => {
      setBackgroundListening(false);
      if (user && tarsVoiceEnabled && !isListening && !isSpeaking && !voiceSessionActive && bgRecognitionRef.current === bgRec) {
        setTimeout(() => {
          if (user && tarsVoiceEnabled && !isListening && !isSpeaking && !voiceSessionActive && bgRecognitionRef.current === bgRec) {
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
    };

    bgRec.onresult = (event) => {
      const lastIndex = event.results.length - 1;
      const transcript = event.results[lastIndex][0].transcript.trim();
      console.log("Background heard:", transcript);

      const transcriptLower = transcript.toLowerCase();
      // Expanded wake word triggers (tars, tarz, stars, star, tar, task, torch, tour, cars, bars)
      const containsWakeWord = /\b(tars|tarz|stars|star|tar|task|torch|tour|cars|bars)\b/i.test(transcriptLower) ||
                               transcriptLower.includes("टार्स") || 
                               transcriptLower.includes("టార్స్");

      if (containsWakeWord) {
        try {
          bgRec.stop();
        } catch (e) {}

        let processedText = transcript
          .replace(/\b(tars|tarz|stars|star|torch|task|tour|tar|cars|bars)\b/gi, '')
          .replace(/टार्स/gi, '')
          .replace(/టార్స్/gi, '')
          .trim();

        // Clean up leading/trailing punctuation/spaces
        processedText = processedText.replace(/^[,.\s]+|[,.\s]+$/g, '');

        playActivationSound();
        setVoiceSessionActive(true);

        if (processedText.length > 1) {
          handleSend(processedText);
        } else {
          // Greet and start active listening
          const uiLang = localStorage.getItem('app_lang') || 'en';
          let greeting = "Yes, I am listening.";
          if (uiLang === 'hi') {
            greeting = "जी, मैं सुन रहा हूँ।";
          } else if (uiLang === 'te') {
            greeting = "అవును, నేను వింటున్నాను.";
          }
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
  }, [user, tarsVoiceEnabled, isListening, isSpeaking, voiceSessionActive, language]);

  const startListening = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge.");
      return;
    }
    
    if (bgRecognitionRef.current) {
      try {
        bgRecognitionRef.current.stop();
      } catch (e) {}
    }

    cancelSpeech();

    const recognition = new SpeechRecognition();
    recognition.lang = language;
    recognition.interimResults = true;
    recognition.continuous = true;
    recognition.maxAlternatives = 1;

    let resultReceived = false;
    let silenceTimer = null;
    let finalTranscript = "";

    recognition.onstart = () => {
      setIsListening(true);
    };
    
    recognition.onend = () => {
      setIsListening(false);
      if (silenceTimer) clearTimeout(silenceTimer);
      
      const textToSend = finalTranscript.trim();
      if (textToSend.length > 0) {
        // Check for voice deactivation command
        if (isDeactivationCommand(textToSend)) {
          playDeactivationSound();
          const uiLang = localStorage.getItem('app_lang') || 'en';
          let goodbye = "Goodbye.";
          if (uiLang === 'hi') goodbye = "अलविदा।";
          else if (uiLang === 'te') goodbye = "సెలవు.";
          speakMessage(goodbye);
          setVoiceSessionActive(false);
          setInputValue('');
          return;
        }
        handleSend(textToSend);
      } else {
        if (voiceSessionActive) {
          // Continuous listening: restart recognition if no speech was transcribed
          try {
            recognition.start();
          } catch (err) {
            console.error("Failed to auto-restart recognition on end:", err);
            setVoiceSessionActive(false);
            playDeactivationSound();
          }
        }
      }
    };

    recognition.onerror = (e) => {
      console.error("Active recognition error:", e);
      if (e.error === 'no-speech') {
        // Don't stop the session for no-speech, let onend handle restarting
        return;
      }
      setIsListening(false);
      if (silenceTimer) clearTimeout(silenceTimer);
      
      const textToSend = finalTranscript.trim();
      if (textToSend.length > 0) {
        handleSend(textToSend);
      } else {
        if (e.error !== 'aborted' && voiceSessionActive) {
          playDeactivationSound();
          setVoiceSessionActive(false);
        }
      }
    };

    recognition.onresult = (event) => {
      let localFinal = "";
      let localInterim = "";
      for (let i = 0; i < event.results.length; ++i) {
        const segment = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          localFinal += segment;
        } else {
          localInterim += segment;
        }
      }
      finalTranscript = localFinal;
      const currentText = (localFinal + localInterim).trim();
      if (currentText) {
        setInputValue(currentText);
        resultReceived = true;
      }

      // Reset silence timer: stop listening after 3.0 seconds of silence
      if (silenceTimer) clearTimeout(silenceTimer);
      silenceTimer = setTimeout(() => {
        try {
          recognition.stop();
        } catch (err) {}
      }, 3000);
    };

    activeRecognitionRef.current = recognition;
    recognition.start();
  };

  const handleSend = async (textToSend = null) => {
    const text = (textToSend || inputValue).trim();
    if (!text) return;

    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setInputValue('');
    setLoading(true);

    try {
      const data = await api.sendAssistantMessage(text, groqKey, hfKey, language);
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      
      // Speak back response
      speakMessage(data.reply, () => {
        // Automatically restart listening if we are in an active voice session AND no action is executing next
        if (!data.action && voiceSessionActive) {
          setTimeout(() => {
            startListening();
          }, 300);
        }
      });

      // Execute Action if present
      if (data.action) {
        handleAction(data.action);
      }
    } catch (err) {
      console.error(err);
      const errorMsg = `Error: ${err.message}`;
      setMessages(prev => [...prev, { role: 'assistant', content: errorMsg }]);
      
      const uiLang = localStorage.getItem('app_lang') || 'en';
      let speechError = "Sorry, I encountered an error. Please try again.";
      if (uiLang === 'hi') speechError = "क्षमा करें, मुझे कोई त्रुटि मिली। कृपया पुनः प्रयास करें।";
      else if (uiLang === 'te') speechError = "క్షమించండి, ఒక లోపం సంభవించింది. దయచేసి మళ్ళీ ప్రయత్నించండి.";
      
      speakMessage(speechError, () => {
        if (voiceSessionActive) {
          setTimeout(() => {
            startListening();
          }, 300);
        }
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (action) => {
    const { type, parameters } = action;
    setMessages(prev => [...prev, { role: 'system', content: `Executing system action: ${type.replace('_', ' ')}...` }]);

    const resumeVoice = () => {
      if (voiceSessionActive) {
        setTimeout(() => {
          startListening();
        }, 300);
      }
    };

    try {
      if (type === 'find_doctors') {
        if (user.role === 'doctor' || user.role === 'admin') {
          const errorMsg = user.role === 'doctor' 
            ? "You cannot book or browse appointments as a doctor. You manage consultations from your dashboard workspace." 
            : "You cannot book or browse appointments as an administrator.";
          setMessages(prev => [...prev, { role: 'assistant', content: errorMsg }]);
          speakMessage(errorMsg, resumeVoice);
          return;
        } else {
          const spec = parameters.specialization || '';
          navigate(`/appointments?search=${spec}`);
        }
        resumeVoice();
      } else if (type === 'view_records') {
        navigate('/records');
        resumeVoice();
      } else if (type === 'view_dashboard') {
        navigate('/dashboard');
        resumeVoice();
      } else if (type === 'view_settings') {
        navigate('/settings');
        resumeVoice();
      } else if (type === 'view_chat') {
        navigate('/chat');
        resumeVoice();
      } else if (type === 'book_appointment') {
        if (user.role === 'doctor' || user.role === 'admin') {
          const errorMsg = user.role === 'doctor' 
            ? "You cannot book an appointment as a doctor. You manage consultations from your dashboard workspace." 
            : "You cannot book an appointment as an administrator.";
          setMessages(prev => [...prev, { role: 'assistant', content: errorMsg }]);
          speakMessage(errorMsg, resumeVoice);
          return;
        }
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);
        const yyyy = tomorrow.getFullYear();
        const mm = String(tomorrow.getMonth() + 1).padStart(2, '0');
        const dd = String(tomorrow.getDate()).padStart(2, '0');
        const tomorrowStr = `${yyyy}-${mm}-${dd}`;

        const docId = parameters.doctor_id || 1;
        const date = parameters.date || tomorrowStr;
        const time = parameters.time || '10:00';
        
        await api.bookAppointment(docId, date, time);
        const successMsg = `Appointment successfully booked for ${date} at ${time}!`;
        setMessages(prev => [...prev, { role: 'assistant', content: successMsg }]);
        speakMessage(successMsg, resumeVoice);
      } else if (type === 'lodge_complaint') {
        const msg = parameters.message || 'General Complaint';
        await api.submitComplaint(msg);
        const successMsg = "Your complaint has been successfully filed with the admin panel.";
        setMessages(prev => [...prev, { role: 'assistant', content: `I have lodged your complaint in our admin panel. Our support team will resolve this shortly.` }]);
        speakMessage(successMsg, resumeVoice);
      } else if (type === 'analyze_symptom') {
        const sym = parameters.symptoms || '';
        const dur = parameters.duration || '1 day';
        const sev = parameters.severity || 'mild';
        
        const data = await api.analyzeSymptom(sym, dur, sev);
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
        speakMessage(data.reply, resumeVoice);
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'assistant', content: `Action failed: ${err.message}` }]);
    }
  };

  if (!user) return null;

  // Compute HUD state for TARS voice assistant
  let hudIcon = 'forum';
  let hudBg = 'bg-primary hover:bg-primary/95';
  let hudTitle = t('assistant');

  if (isOpen) {
    hudIcon = 'close';
    hudTitle = 'Close TARS';
  } else {
    if (loading) {
      hudIcon = 'progress_activity';
      hudBg = 'bg-indigo-600 hover:bg-indigo-700';
      hudTitle = 'TARS is thinking...';
    } else if (isListening) {
      hudIcon = 'graphic_eq';
      hudBg = 'bg-emerald-600 hover:bg-emerald-700';
      hudTitle = 'TARS is listening... Speak now';
    } else if (isSpeaking) {
      hudIcon = 'volume_up';
      hudBg = 'bg-cyan-600 hover:bg-cyan-700';
      hudTitle = 'TARS is speaking...';
    } else {
      hudIcon = 'forum';
      hudBg = tarsVoiceEnabled ? 'bg-primary hover:bg-primary/95' : 'bg-outline/60 hover:bg-outline/70';
      hudTitle = tarsVoiceEnabled ? 'TARS Voice Standby is Active' : 'TARS Voice Standby is Disabled';
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
                {/* Language Selection */}
                <select 
                  value={language}
                  onChange={(e) => {
                    const newLang = e.target.value;
                    setLanguage(newLang);
                    if (newLang === 'hi-IN') {
                      setCurrentLanguage('hi');
                    } else if (newLang === 'te-IN') {
                      setCurrentLanguage('te');
                    } else {
                      setCurrentLanguage('en');
                    }
                  }}
                  className="text-[10px] border border-outline-variant rounded-xl p-1 bg-white focus:outline-none font-semibold text-primary"
                >
                  <option value="en-US">English</option>
                  <option value="hi-IN">Hindi (हिन्दी)</option>
                  <option value="te-IN">Telugu (తెలుగు)</option>
                </select>
                
                {/* Tars Settings Toggle */}
                <button
                  onClick={() => setShowSettings(!showSettings)}
                  className={`p-1 rounded-full transition-colors focus:outline-none ${showSettings ? 'text-primary bg-primary/10' : 'text-outline hover:bg-surface-container-high'}`}
                  title="Configure TARS API Keys"
                >
                  <span className="material-symbols-outlined text-[18px]">settings</span>
                </button>

                {/* Close button removed as launcher button below toggles open/close */}
              </div>
            </div>
            
            {/* TARS Status Control Row */}
            <div className="flex justify-between items-center mt-1 pt-1 border-t border-outline-variant/40 text-[10px]">
              <div className="flex items-center gap-xs text-outline font-semibold">
                <span className={`w-2 h-2 rounded-full ${tarsVoiceEnabled ? 'bg-emerald-500 animate-pulse' : 'bg-outline/60'}`}></span>
                <span>Standby: {tarsVoiceEnabled ? 'Active' : 'Disabled'}</span>
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
                {tarsVoiceEnabled ? 'Turn OFF' : 'Turn ON'}
              </button>
            </div>
          </div>

          {showSettings ? (
            /* Configure Keys Panel */
            <div className="flex-1 p-4 overflow-y-auto bg-surface-container-lowest flex flex-col justify-between animate-in fade-in duration-200">
              <div className="space-y-md">
                <h4 className="font-bold text-sm text-primary flex items-center gap-xs">
                  <span className="material-symbols-outlined text-secondary text-md">key</span>
                  TARS Custom Keys Configuration
                </h4>
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  Want to use your own API keys? Paste a free Groq API Key or Hugging Face Token to get lightning-fast, highly intelligent responses.
                </p>
                <div className="space-y-sm">
                  <div className="flex flex-col gap-xs">
                    <label className="text-[10px] font-bold text-outline uppercase tracking-wider">Groq API Key</label>
                    <input 
                      type="password"
                      placeholder="Paste Groq Key (gsk_...)"
                      value={groqKey}
                      onChange={(e) => setGroqKey(e.target.value)}
                      className="py-1.5 px-3 border border-outline-variant rounded-lg bg-surface text-xs text-on-surface focus:outline-none focus:border-secondary"
                    />
                  </div>
                  <div className="flex flex-col gap-xs">
                    <label className="text-[10px] font-bold text-outline uppercase tracking-wider">Hugging Face Token</label>
                    <input 
                      type="password"
                      placeholder="Paste Hugging Face Token (hf_...)"
                      value={hfKey}
                      onChange={(e) => setHfKey(e.target.value)}
                      className="py-1.5 px-3 border border-outline-variant rounded-lg bg-surface text-xs text-on-surface focus:outline-none focus:border-secondary"
                    />
                  </div>
                </div>
              </div>
              
              <button 
                onClick={() => setShowSettings(false)}
                className="w-full py-2 bg-primary text-white font-bold rounded-lg text-xs hover:bg-primary/95 transition-all shadow-md focus:outline-none active:scale-[0.98]"
              >
                Save & Close
              </button>
            </div>
          ) : (
            /* Messages List */
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
                      {msg.content}
                    </div>
                  </div>
                ))}
                
                {loading && (
                  <div className="flex items-center gap-xs text-outline text-xs animate-pulse">
                    <span className="w-1.5 h-1.5 bg-outline rounded-full animate-bounce"></span>
                    <span className="w-1.5 h-1.5 bg-outline rounded-full animate-bounce delay-75"></span>
                    <span className="w-1.5 h-1.5 bg-outline rounded-full animate-bounce delay-150"></span>
                    <span>Thinking...</span>
                  </div>
                )}
                
                {isListening && (
                  /* Listening Indicator Waveform */
                  <div className="flex items-center justify-center gap-xs p-2 bg-emerald-500/10 text-emerald-500 rounded-xl text-xs font-semibold animate-pulse border border-emerald-500/20">
                    <span className="material-symbols-outlined text-[16px] animate-spin">graphic_eq</span>
                    <span>TARS is listening... Speak now</span>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </div>

              {/* Quick Suggestions */}
              <div className="p-2 border-t border-outline-variant bg-surface flex gap-sm overflow-x-auto whitespace-nowrap scrollbar-none">
                <button 
                  onClick={() => handleSend("Find general doctors")}
                  className="text-[10px] bg-secondary-container text-on-secondary-container px-2.5 py-1 rounded-full font-bold hover:opacity-90 active:scale-95 duration-100"
                >
                  🔍 Find Doctor
                </button>
                <button 
                  onClick={() => handleSend("Book appointment")}
                  className="text-[10px] bg-secondary-container text-on-secondary-container px-2.5 py-1 rounded-full font-bold hover:opacity-90 active:scale-95 duration-100"
                >
                  📅 Book Visit
                </button>
                <button 
                  onClick={() => handleSend("View my medical records")}
                  className="text-[10px] bg-secondary-container text-on-secondary-container px-2.5 py-1 rounded-full font-bold hover:opacity-90 active:scale-95 duration-100"
                >
                  📂 View Records
                </button>
                <button 
                  onClick={() => handleSend("I want to submit a complaint")}
                  className="text-[10px] bg-secondary-container text-on-secondary-container px-2.5 py-1 rounded-full font-bold hover:opacity-90 active:scale-95 duration-100"
                >
                  ⚠️ File Complaint
                </button>
              </div>

              {/* Input Panel */}
              <div className="p-3 border-t border-outline-variant bg-white flex gap-sm items-center">
                <button 
                  onClick={() => {
                    if (isListening) {
                      setVoiceSessionActive(false);
                      if (activeRecognitionRef.current) {
                        try {
                          activeRecognitionRef.current.stop();
                        } catch (e) {}
                      }
                    } else {
                      if (isSpeaking) {
                        cancelSpeech();
                      }
                      setVoiceSessionActive(true);
                      startListening();
                    }
                  }}
                  className={`p-2 rounded-full transition-all focus:outline-none ${
                    (isListening || isSpeaking) ? 'bg-error text-white animate-pulse' : 'bg-surface-container-high text-outline hover:text-secondary'
                  }`}
                  title={(isListening || isSpeaking) ? "Stop Assistant" : "Click to speak"}
                >
                  <span className="material-symbols-outlined">{(isListening || isSpeaking) ? 'mic' : 'mic_off'}</span>
                </button>
                
                <input 
                  type="text" 
                  placeholder="Ask TARS anything..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
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
          )}
        </div>
      )}

      {/* Launcher Button with dynamic TARS HUD */}
      <button 
        onClick={() => setIsOpen(!isOpen)}
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
