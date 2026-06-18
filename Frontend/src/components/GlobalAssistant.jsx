import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function GlobalAssistant() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  
  // Track if standby background wake-word/command detection is enabled by the user
  const [tarsVoiceEnabled, setTarsVoiceEnabled] = useState(true);
  // Track if we are currently in an active voice dialog session (hands-free back-and-forth)
  const [voiceSessionActive, setVoiceSessionActive] = useState(false);
  
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I am TARS, your multilingual AI assistant. I can speak and listen in English, Hindi (हिन्दी), Telugu (తెలుగు), Hinglish, and Tinglish. Say "TARS wake up" or click the mic to begin, or type a request to navigate through the application.' }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [language, setLanguage] = useState('en-US'); // en-US, hi-IN, te-IN
  const [isListening, setIsListening] = useState(false);
  const [backgroundListening, setBackgroundListening] = useState(false);
  const [loading, setLoading] = useState(false);
  const [apiSettingsOpen, setApiSettingsOpen] = useState(false);
  const [groqKey, setGroqKey] = useState('');
  const [hfKey, setHfKey] = useState('');
  
  const messagesEndRef = useRef(null);
  const bgRecognitionRef = useRef(null);
  const activeRecognitionRef = useRef(null);

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

  // Load API keys from localStorage on mount
  useEffect(() => {
    const savedGroqKey = localStorage.getItem('tars_groq_key') || '';
    const savedHfKey = localStorage.getItem('tars_hf_key') || '';
    setGroqKey(savedGroqKey);
    setHfKey(savedHfKey);
  }, []);

  // Save API keys to localStorage when they change
  useEffect(() => {
    localStorage.setItem('tars_groq_key', groqKey);
    localStorage.setItem('tars_hf_key', hfKey);
  }, [groqKey, hfKey]);

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

  // Background Standby listener logic
  useEffect(() => {
    // Only run if user logged in, standby voice is enabled, UI is closed, and we're not actively listening
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
        playActivationSound();
        setIsOpen(true);
        setVoiceSessionActive(true);

        let greeting = "Hello, how can I assist you today?";
        if (language.startsWith('hi')) {
          greeting = "टार্স सक्रिय है। मैं आपकी क्या सहायता कर सकता हूँ?";
        } else if (language.startsWith('te')) {
          greeting = "టార్స్ యాక్టివేట్ చేయబడింది. నేను మీకు ఎలా సహాయపడగలను?";
        }

        setMessages(prev => [...prev, { role: 'assistant', content: greeting }]);
        
        try {
          bgRec.stop();
        } catch (e) {}

        setTimeout(() => {
          speakMessage(greeting, () => {
            startListening();
          });
        }, 300);
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

  const speakMessage = (text, callback = null) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      const voices = window.speechSynthesis.getVoices();
      
      let voice = null;
      if (language.startsWith('hi')) {
        voice = voices.find(v => v.lang.startsWith('hi') || v.name.toLowerCase().includes('hindi'));
        utterance.lang = 'hi-IN';
      } else if (language.startsWith('te')) {
        voice = voices.find(v => v.lang.startsWith('te') || v.name.toLowerCase().includes('telugu'));
        utterance.lang = 'te-IN';
      } else {
        // Prefer sweeter, more natural voices for English
        const preferredVoices = [
          'Google US English',
          'Google UK English Female',
          'Microsoft Zira',
          'Microsoft Eva',
          'Microsoft Aria',
          'Samantha'
        ];
        for (const preferred of preferredVoices) {
          voice = voices.find(v => v.name === preferred || v.name.toLowerCase().includes(preferred.toLowerCase()));
          if (voice) break;
        }
        if (!voice) {
          voice = voices.find(v => v.lang.startsWith('en') || v.name.toLowerCase().includes('english'));
        }
        utterance.lang = 'en-US';
      }
      
      if (voice) utterance.voice = voice;
      
      // Raise pitch to 1.1 for sweeter, less robotic tone
      utterance.pitch = 1.1;
      utterance.rate = 1.0;
      
      if (callback) {
        utterance.onend = callback;
        utterance.onerror = callback; // fallback to continue even on error
      }
      
      window.speechSynthesis.speak(utterance);
    } else if (callback) {
      callback();
    }
  };

  const startListening = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge.");
      return;
    }
    
    // Stop standby listener first
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

      // Check for local deactivation command
      if (isDeactivationCommand(transcript)) {
        setVoiceSessionActive(false);
        playDeactivationSound();

        let goodbye = "It's been a pleasure working with you.";
        if (language.startsWith('hi')) {
          goodbye = "टार्स बंद हो रहा है। शुभ रात्रि।";
        } else if (language.startsWith('te')) {
          goodbye = "టార్స్ ఆఫ్ చేయబడింది. సెలవు.";
        }

        setMessages(prev => [...prev, { role: 'assistant', content: goodbye }]);
        speakMessage(goodbye);
        setIsOpen(false);
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
                <h3 className="font-bold text-primary text-label-md">TARS Voice Assistant</h3>
              </div>
              
              <div className="flex items-center gap-sm">
                {/* API Settings Button */}
                <button 
                  onClick={() => setApiSettingsOpen(!apiSettingsOpen)}
                  className="p-1 hover:bg-surface-container-high rounded-full transition-colors text-outline hover:text-primary focus:outline-none"
                  title="API Settings"
                >
                  <span className="material-symbols-outlined text-sm">settings</span>
                </button>
                {/* Language Selection */}
                <select 
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="text-xs border border-outline-variant rounded p-1 bg-surface focus:outline-none font-semibold text-on-surface"
                >
                  <option value="en-US">English</option>
                  <option value="hi-IN">Hindi (हिन्दी)</option>
                  <option value="te-IN">Telugu (తెలుగు)</option>
                </select>
                <button 
                  onClick={() => setIsOpen(false)}
                  className="p-1 hover:bg-surface-container-high rounded-full transition-colors text-outline focus:outline-none"
                >
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>
            </div>
            
            {/* API Settings Panel */}
            {apiSettingsOpen && (
              <div className="mt-2 p-3 bg-surface-container-low rounded-xl border border-outline-variant/30 animate-in slide-in-from-top-2 duration-200">
                <h4 className="font-bold text-primary text-xs mb-2">Custom API Keys (Optional)</h4>
                <div className="space-y-2">
                  <div>
                    <label className="text-[10px] text-outline font-semibold block mb-1">Groq API Key</label>
                    <input 
                      type="password"
                      value={groqKey}
                      onChange={(e) => setGroqKey(e.target.value)}
                      placeholder="Enter your free Groq API key..."
                      className="w-full px-2 py-1.5 bg-white border border-outline-variant/30 rounded-lg text-[11px] focus:outline-none focus:border-secondary text-on-surface"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-outline font-semibold block mb-1">Hugging Face Token</label>
                    <input 
                      type="password"
                      value={hfKey}
                      onChange={(e) => setHfKey(e.target.value)}
                      placeholder="Enter your Hugging Face token..."
                      className="w-full px-2 py-1.5 bg-white border border-outline-variant/30 rounded-lg text-[11px] focus:outline-none focus:border-secondary text-on-surface"
                    />
                  </div>
                  <p className="text-[9px] text-outline italic">Leave empty to use backend default keys</p>
                </div>
              </div>
            )}
            
            {/* TARS Status Control Row */}
            <div className="flex justify-between items-center mt-1 pt-1 border-t border-outline-variant/40 text-[11px]">
              <div className="flex items-center gap-xs text-outline font-semibold">
                <span className={`w-2.5 h-2.5 rounded-full ${tarsVoiceEnabled ? 'bg-emerald-500 animate-pulse' : 'bg-outline/60'}`}></span>
                <span>Voice Standby: {tarsVoiceEnabled ? 'Active' : 'Disabled'}</span>
              </div>
              <button 
                onClick={() => {
                  if (tarsVoiceEnabled) {
                    playDeactivationSound();
                    setTarsVoiceEnabled(false);
                    setVoiceSessionActive(false);
                  } else {
                    playActivationSound();
                    setTarsVoiceEnabled(true);
                  }
                }}
                className={`px-2 py-0.5 rounded-full font-bold text-[10px] transition-all focus:outline-none ${
                  tarsVoiceEnabled 
                    ? 'bg-outline-variant/40 text-outline hover:bg-error/10 hover:text-error' 
                    : 'bg-emerald-100 text-emerald-800 hover:bg-emerald-200'
                }`}
              >
                {tarsVoiceEnabled ? 'Turn OFF' : 'Turn ON'}
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 p-4 overflow-y-auto space-y-md bg-surface-container-lowest">
            {messages.map((msg, index) => (
              <div 
                key={index} 
                className={`flex flex-col ${
                  msg.role === 'user' ? 'items-end' : msg.role === 'system' ? 'items-center' : 'items-start'
                }`}
              >
                <div 
                  className={`max-w-[85%] rounded-xl px-4 py-2 text-sm ${
                    msg.role === 'user' 
                      ? 'bg-secondary text-white rounded-tr-none' 
                      : msg.role === 'system'
                      ? 'bg-surface-container text-outline text-[11px] font-semibold'
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
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Suggestions */}
          <div className="p-2 border-t border-outline-variant bg-surface flex gap-sm overflow-x-auto whitespace-nowrap scrollbar-none">
            <button 
              onClick={() => handleSend("Find general doctors")}
              className="text-[11px] bg-secondary-container text-on-secondary-container px-2 py-1 rounded-full font-semibold hover:opacity-90"
            >
              🔍 Find Doctor
            </button>
            <button 
              onClick={() => handleSend("Book appointment with Dr. Alice Smith tomorrow at 10:00 AM")}
              className="text-[11px] bg-secondary-container text-on-secondary-container px-2 py-1 rounded-full font-semibold hover:opacity-90"
            >
              📅 Book Visit
            </button>
            <button 
              onClick={() => handleSend("View my medical records")}
              className="text-[11px] bg-secondary-container text-on-secondary-container px-2 py-1 rounded-full font-semibold hover:opacity-90"
            >
              📂 View Records
            </button>
            <button 
              onClick={() => handleSend("I want to submit a complaint about the clinic's check-in waiting time")}
              className="text-[11px] bg-secondary-container text-on-secondary-container px-2 py-1 rounded-full font-semibold hover:opacity-90"
            >
              ⚠️ File Complaint
            </button>
          </div>

          {/* Input Panel */}
          <div className="p-3 border-t border-outline-variant bg-white flex gap-sm items-center">
            <button 
              onClick={() => {
                if (isListening) {
                  // Stop active voice session
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
                isListening ? 'bg-error text-on-error animate-pulse' : 'bg-surface-container-high text-outline hover:text-secondary'
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
              className="flex-1 py-2 px-3 border border-outline-variant rounded-lg bg-surface text-on-surface text-sm focus:outline-none focus:border-secondary"
            />
            
            <button 
              onClick={() => handleSend()}
              className="p-2 bg-primary hover:bg-primary/95 text-white rounded-full transition-all focus:outline-none"
            >
              <span className="material-symbols-outlined text-[20px]">send</span>
            </button>
          </div>
        </div>
      )}

      {/* Launcher Button with TARS background listening indicator */}
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-14 h-14 bg-primary hover:bg-primary/95 text-white rounded-full flex items-center justify-center shadow-2xl active:scale-95 transition-all focus:outline-none relative"
        title={tarsVoiceEnabled ? "TARS Voice Standby is Active" : "TARS Voice Standby is Disabled"}
      >
        {tarsVoiceEnabled && !isOpen && (
          <span className="absolute -inset-1 rounded-full border-2 border-emerald-500 animate-ping opacity-45 pointer-events-none"></span>
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
