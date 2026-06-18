import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';

export default function GlobalAssistant() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  
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
  
  // TARS Custom API Keys State
  const [groqKey, setGroqKey] = useState(() => localStorage.getItem('tars_groq_key') || '');
  const [hfKey, setHfKey] = useState(() => localStorage.getItem('tars_hf_key') || '');
  const [showSettings, setShowSettings] = useState(false);

  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I am TARS, your multilingual AI assistant. I can speak and listen in English, Hindi (हिन्दी), Telugu (తెలుగు), Hinglish, and Tinglish. Say "TARS wake up" or click the mic to begin, or type a request to navigate through the application.' }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [language, setLanguage] = useState('en-US'); // en-US, hi-IN, te-IN
  const [isListening, setIsListening] = useState(false);
  const [backgroundListening, setBackgroundListening] = useState(false);
  const [loading, setLoading] = useState(false);
  
  const messagesEndRef = useRef(null);
  const bgRecognitionRef = useRef(null);
  const activeRecognitionRef = useRef(null);

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
    return 'en';
  };

  // Speaks using exactly one sweet female voice per language, with human-paced rate
  const speakMessage = (text, callback = null) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
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
      
      if (callback) {
        utterance.onend = callback;
        utterance.onerror = callback; // fallback to continue even on error
      }
      
      window.speechSynthesis.speak(utterance);
    } else if (callback) {
      callback();
    }
  };

  // Unified Toggle Open / Hello Greeting & Exit Goodbye sequence
  const toggleOpen = (shouldOpen) => {
    if (shouldOpen) {
      playActivationSound();
      setIsOpen(true);
      
      // Determine greeting based on current UI language
      const uiLang = localStorage.getItem('app_lang') || 'en';
      let greeting = "Hello, how can I assist you today?";
      if (uiLang === 'hi') {
        greeting = "नमस्ते, आज मैं आपकी क्या सहायता कर सकता हूँ?";
      } else if (uiLang === 'te') {
        greeting = "నమస్కారం, ఈ రోజు నేను మీకు ఎలా సహాయపడగలను?";
      }

      setMessages(prev => [...prev, { role: 'assistant', content: greeting }]);
      
      setTimeout(() => {
        speakMessage(greeting, () => {
          if (tarsVoiceEnabled) {
            setVoiceSessionActive(true);
            startListening();
          }
        });
      }, 350);
    } else {
      playDeactivationSound();
      
      const uiLang = localStorage.getItem('app_lang') || 'en';
      let goodbye = "It's been a pleasure working with you.";
      if (uiLang === 'hi') {
        goodbye = "आपके साथ काम करके बेहद खुशी हुई।";
      } else if (uiLang === 'te') {
        goodbye = "మీతో కలిసి పనిచేయడం సంతోషంగా ఉంది.";
      }
      
      setMessages(prev => [...prev, { role: 'assistant', content: goodbye }]);
      speakMessage(goodbye);
      
      setVoiceSessionActive(false);
      if (activeRecognitionRef.current) {
        try { activeRecognitionRef.current.stop(); } catch(e){}
      }
      setIsOpen(false);
      setShowSettings(false);
    }
  };

  // Background Standby listener logic
  useEffect(() => {
    if (!user || !tarsVoiceEnabled || isOpen || isListening) {
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
    bgRec.interimResults = false;
    bgRec.lang = language;

    bgRec.onstart = () => {
      setBackgroundListening(true);
    };

    bgRec.onend = () => {
      setBackgroundListening(false);
      if (user && tarsVoiceEnabled && !isOpen && !isListening && bgRecognitionRef.current === bgRec) {
        setTimeout(() => {
          if (user && tarsVoiceEnabled && !isOpen && !isListening && bgRecognitionRef.current === bgRec) {
            try {
              bgRec.start();
            } catch (e) {
              console.error("Failed to restart background listener", e);
            }
          }
        }, 3000);
      }
    };

    bgRec.onerror = (e) => {
      console.warn("Background SpeechRecognition error:", e);
    };

    bgRec.onresult = (event) => {
      const lastIndex = event.results.length - 1;
      const transcript = event.results[lastIndex][0].transcript.trim();
      console.log("Background heard:", transcript);

      if (isActivationCommand(transcript)) {
        try {
          bgRec.stop();
        } catch (e) {}
        toggleOpen(true);
      }
    };

    bgRecognitionRef.current = bgRec;
    try {
      bgRec.start();
    } catch (e) {
      console.warn("Failed to start background SpeechRecognition:", e);
    }

    return () => {
      bgRecognitionRef.current = null;
      try {
        bgRec.stop();
      } catch (e) {}
    };
  }, [user, tarsVoiceEnabled, isOpen, isListening, language]);

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

    const recognition = new SpeechRecognition();
    recognition.lang = language;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
    };
    
    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.onerror = (e) => {
      console.error("Active recognition error:", e);
      setIsListening(false);
      setVoiceSessionActive(false);
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript.trim();
      setInputValue(transcript);

      // Check for voice deactivation command
      if (isDeactivationCommand(transcript)) {
        toggleOpen(false);
        return;
      }

      handleSend(transcript);
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
      const data = await api.sendAssistantMessage(text, groqKey, hfKey);
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      
      // Speak back response
      speakMessage(data.reply, () => {
        // Automatically restart listening if we are in an active voice session
        if (voiceSessionActive) {
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
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (action) => {
    const { type, parameters } = action;
    setMessages(prev => [...prev, { role: 'system', content: `Executing system action: ${type.replace('_', ' ')}...` }]);

    try {
      if (type === 'find_doctors') {
        const spec = parameters.specialization || '';
        navigate(`/appointments?search=${spec}`);
      } else if (type === 'view_records') {
        navigate('/records');
      } else if (type === 'view_dashboard') {
        navigate('/dashboard');
      } else if (type === 'view_settings') {
        navigate('/settings');
      } else if (type === 'view_chat') {
        navigate('/chat');
      } else if (type === 'book_appointment') {
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
        setMessages(prev => [...prev, { role: 'assistant', content: `Appointment successfully booked for ${date} at ${time}!` }]);
        speakMessage("Appointment successfully booked!");
      } else if (type === 'lodge_complaint') {
        const msg = parameters.message || 'General Complaint';
        await api.submitComplaint(msg);
        setMessages(prev => [...prev, { role: 'assistant', content: `I have lodged your complaint in our admin panel. Our support team will resolve this shortly.` }]);
        speakMessage("Your complaint has been successfully filed with the admin panel.");
      } else if (type === 'analyze_symptom') {
        const sym = parameters.symptoms || '';
        const dur = parameters.duration || '1 day';
        const sev = parameters.severity || 'mild';
        
        const data = await api.analyzeSymptom(sym, dur, sev);
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
        speakMessage(data.reply);
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'assistant', content: `Action failed: ${err.message}` }]);
    }
  };

  if (!user) return null;

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
                  onChange={(e) => setLanguage(e.target.value)}
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

                <button 
                  onClick={() => toggleOpen(false)}
                  className="p-1 hover:bg-surface-container-high rounded-full transition-colors text-outline focus:outline-none"
                >
                  <span className="material-symbols-outlined text-[18px]">close</span>
                </button>
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
                      setVoiceSessionActive(true);
                      startListening();
                    }
                  }}
                  className={`p-2 rounded-full transition-all focus:outline-none ${
                    isListening ? 'bg-error text-white animate-pulse' : 'bg-surface-container-high text-outline hover:text-secondary'
                  }`}
                  title={isListening ? "Listening... Click to stop" : "Click to speak"}
                >
                  <span className="material-symbols-outlined">{isListening ? 'mic' : 'mic_off'}</span>
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

      {/* Launcher Button with TARS background listening indicator */}
      <button 
        onClick={() => toggleOpen(!isOpen)}
        className="w-14 h-14 bg-primary hover:bg-primary/95 text-white rounded-full flex items-center justify-center shadow-2xl active:scale-95 transition-all focus:outline-none relative"
        title={tarsVoiceEnabled ? "TARS Voice Standby is Active" : "TARS Voice Standby is Disabled"}
      >
        {tarsVoiceEnabled && !isOpen && (
          <span className="absolute -inset-1.5 rounded-full border-2 border-emerald-500 animate-ping opacity-45 pointer-events-none"></span>
        )}
        {tarsVoiceEnabled && !isOpen && (
          <span className="absolute top-0 right-0 w-3.5 h-3.5 bg-emerald-500 rounded-full border-2 border-white flex items-center justify-center shadow-md">
            <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse"></span>
          </span>
        )}
        <span className="material-symbols-outlined text-[28px]">{isOpen ? 'close' : 'forum'}</span>
      </button>
    </div>
  );
}
