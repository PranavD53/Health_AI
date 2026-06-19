import React, { useState, useEffect, useRef } from 'react';
import { api } from '../services/api';
import { resolveMediaUrl } from '../utils/apiConfig';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { useWebSocket } from '../context/WebSocketContext';

export default function Chat() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const [contacts, setContacts] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [activeConv, setActiveConv] = useState(null);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [messageText, setMessageText] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(Date.now());
  
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [loadingConvs, setLoadingConvs] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [previousMessageCount, setPreviousMessageCount] = useState(0);
  
  const [showPrescriptionModal, setShowPrescriptionModal] = useState(false);
  const [prescriptionForm, setPrescriptionForm] = useState({
    patient_name: '',
    diagnosis: '',
    medicines: [{ name: '', dosage: '', frequency: '', duration: '' }],
    instructions: ''
  });

  const handleAddMedicine = () => {
    setPrescriptionForm(prev => ({
      ...prev,
      medicines: [...prev.medicines, { name: '', dosage: '', frequency: '', duration: '' }]
    }));
  };

  const handleUpdateMedicine = (index, field, value) => {
    const updated = [...prescriptionForm.medicines];
    updated[index][field] = value;
    setPrescriptionForm(prev => ({
      ...prev,
      medicines: updated
    }));
  };

  const handleRemoveMedicine = (index) => {
    if (prescriptionForm.medicines.length === 1) return;
    setPrescriptionForm(prev => ({
      ...prev,
      medicines: prev.medicines.filter((_, i) => i !== index)
    }));
  };

  const handleSendPrescription = async (e) => {
    e.preventDefault();
    if (!prescriptionForm.patient_name.trim() || !prescriptionForm.diagnosis.trim()) {
      alert("Please fill in patient name and diagnosis.");
      return;
    }
    const validMeds = prescriptionForm.medicines.filter(m => m.name.trim() !== '');
    if (validMeds.length === 0) {
      alert("Please add at least one medication.");
      return;
    }

    try {
      setSending(true);
      const payload = {
        ...prescriptionForm,
        medicines: validMeds
      };
      await api.sendPrescription(activeConv.id, payload);
      setPrescriptionForm({
        patient_name: activeConv.other_user?.name || '',
        diagnosis: '',
        medicines: [{ name: '', dosage: '', frequency: '', duration: '' }],
        instructions: ''
      });
      setShowPrescriptionModal(false);
      await fetchMessages(activeConv.id, true);
      fetchConversations();
    } catch (err) {
      console.error(err);
      alert(`Failed to send prescription: ${err.message}`);
    } finally {
      setSending(false);
    }
  };

  useEffect(() => {
    if (activeConv) {
      setPrescriptionForm(prev => ({
        ...prev,
        patient_name: activeConv.other_user?.name || ''
      }));
    }
  }, [activeConv]);

  const messagesEndRef = useRef(null);
  const { subscribe } = useWebSocket() || {};

  // Load contacts and active conversations on mount
  useEffect(() => {
    fetchContacts();
    fetchConversations();
  }, []);

  // Use WebSocket for real-time messages
  useEffect(() => {
    if (!subscribe) return;
    
    const unsubscribe = subscribe((data) => {
      if (data.event === 'new_message') {
        // If it's for the currently active conversation, fetch new messages
        if (activeConv && data.conversation_id === activeConv.id) {
          fetchMessages(activeConv.id, true);
        } else {
          // Otherwise just update the conversations list so the preview updates
          fetchConversations();
        }
      }
    });
    
    return unsubscribe;
  }, [subscribe, activeConv]);

  useEffect(() => {
    setPreviousMessageCount(0); // Reset message count when switching conversations

    if (activeConv) {
      fetchMessages(activeConv.id, false);
    } else {
      setMessages([]);
    }
  }, [activeConv]);

  // Scroll to bottom when messages list updates
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const playNotificationSound = () => {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const now = audioCtx.currentTime;
      
      // First chime (higher pitch)
      const osc1 = audioCtx.createOscillator();
      const gain1 = audioCtx.createGain();
      osc1.connect(gain1);
      gain1.connect(audioCtx.destination);
      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(880, now); // A5
      gain1.gain.setValueAtTime(0, now);
      gain1.gain.linearRampToValueAtTime(0.15, now + 0.02);
      gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
      osc1.start(now);
      osc1.stop(now + 0.2);
      
      // Second chime (slightly lower, creating a pleasant double-chime effect)
      const osc2 = audioCtx.createOscillator();
      const gain2 = audioCtx.createGain();
      osc2.connect(gain2);
      gain2.connect(audioCtx.destination);
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(784, now + 0.15); // G5
      gain2.gain.setValueAtTime(0, now + 0.15);
      gain2.gain.linearRampToValueAtTime(0.15, now + 0.17);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc2.start(now + 0.15);
      osc2.stop(now + 0.35);
    } catch (e) {
      console.warn("Notification sound failed:", e);
    }
  };

  const fetchContacts = async () => {
    setLoadingContacts(true);
    try {
      const data = await api.getContacts();
      setContacts(data);
    } catch (err) {
      console.error("Failed to load contacts:", err);
    } finally {
      setLoadingContacts(false);
    }
  };

  const fetchConversations = async () => {
    setLoadingConvs(true);
    try {
      const data = await api.getConversations();
      setConversations(data);
    } catch (err) {
      console.error("Failed to load conversations:", err);
    } finally {
      setLoadingConvs(false);
    }
  };

  const fetchMessages = async (convId, isSilent = false) => {
    if (!isSilent) setLoadingMessages(true);
    try {
      const data = await api.getChatMessages(convId);
      // Only set messages state if length differs or messages updated to prevent layout flash
      setMessages(prev => {
        if (JSON.stringify(prev) !== JSON.stringify(data)) {
          // Play notification sound if new message arrived from other participant
          if (data.length > previousMessageCount && previousMessageCount !== 0) {
            const lastMessage = data[data.length - 1];
            if (lastMessage.sender_id !== user.id) {
              playNotificationSound();
            }
          }
          setPreviousMessageCount(data.length);
          return data;
        }
        return prev;
      });
    } catch (err) {
      console.error("Failed to load messages:", err);
    } finally {
      if (!isSilent) setLoadingMessages(false);
    }
  };

  const handleStartConversation = async (targetUserId) => {
    try {
      const res = await api.startConversation(targetUserId);
      await fetchConversations();
      
      // Find the started conversation
      const allConvs = await api.getConversations();
      const match = allConvs.find(c => c.id === res.id);
      if (match) {
        setActiveConv(match);
      }
      setSearchQuery('');
    } catch (err) {
      alert("Could not start conversation: " + err.message);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!activeConv || (!messageText.trim() && !selectedFile)) return;

    setSending(true);
    try {
      const formData = new FormData();
      if (messageText.trim()) {
        formData.append('content', messageText);
      }
      if (selectedFile) {
        formData.append('file', selectedFile);
      }

      await api.sendChatMessage(activeConv.id, formData);
      setMessageText('');
      setSelectedFile(null);
      setFileInputKey(Date.now());
      
      // Instantly load new messages and refresh conversation last previews
      await fetchMessages(activeConv.id, true);
      fetchConversations();
    } catch (err) {
      alert("Failed to send message: " + err.message);
    } finally {
      setSending(false);
    }
  };

  const handleDeleteConversation = async (convId) => {
    if (!window.confirm("Are you sure you want to delete this chat conversation? This will delete all messages permanently.")) {
      return;
    }
    try {
      await api.deleteConversation(convId);
      setActiveConv(null);
      fetchConversations();
    } catch (err) {
      alert("Failed to delete conversation: " + err.message);
    }
  };

  const handleDeleteMessage = async (msgId) => {
    if (!activeConv) return;
    if (!window.confirm("Are you sure you want to delete this message?")) {
      return;
    }
    try {
      await api.deleteMessage(activeConv.id, msgId);
      await fetchMessages(activeConv.id, true);
      fetchConversations();
    } catch (err) {
      alert("Failed to delete message: " + err.message);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  // Filter contacts based on search query
  const filteredContacts = contacts.filter(c => 
    c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getInitials = (name) => {
    if (!name) return "?";
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  const getAttachmentPreview = (path, name) => {
    if (!path) return null;
    const label = name || path;
    const isImage = /\.(jpg|jpeg|png|gif|webp)$/i.test(label);
    const isPdf = /\.pdf$/i.test(label);
    const fullUrl = resolveMediaUrl(path);

    if (isImage) {
      return (
        <div className="mt-2 rounded-lg overflow-hidden max-w-xs border border-outline-variant/30 shadow-sm bg-white">
          <img src={fullUrl} alt={name || "Uploaded image"} className="max-h-48 w-auto object-contain cursor-pointer hover:opacity-95" onClick={() => window.open(fullUrl, '_blank', 'noopener,noreferrer')} />
        </div>
      );
    }

    return (
      <div className="mt-2 flex items-center gap-xs p-2 bg-surface-container-high/60 rounded-lg max-w-xs border border-outline-variant/20 hover:bg-surface-container-high transition-colors">
        <span className="material-symbols-outlined text-secondary text-lg">
          {isPdf ? 'picture_as_pdf' : 'description'}
        </span>
        <a href={fullUrl} target="_blank" rel="noopener noreferrer" download={isPdf ? label : undefined} className="text-xs text-primary font-semibold hover:underline truncate flex-1">
          {isPdf ? `Download Prescription (${label})` : (name || "Download File")}
        </a>
      </div>
    );
  };

  return (
    <div className="flex bg-surface rounded-2xl border border-outline-variant/30 shadow-md h-[calc(100vh-120px)] overflow-hidden animate-in fade-in duration-300">
      
      {/* Left Pane: Contacts & Conversations list */}
      <div className="w-80 border-r border-outline-variant/30 flex flex-col bg-surface-container-low shrink-0">
        
        {/* Search Input */}
        <div className="p-4 border-b border-outline-variant/30 bg-surface">
          <div className="relative">
            <span className="material-symbols-outlined absolute left-3 top-2.5 text-outline text-md">search</span>
            <input 
              type="text"
              placeholder={t('searchContacts')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-surface-container-high border border-outline-variant/30 rounded-xl text-xs focus:outline-none focus:border-secondary transition-colors"
            />
          </div>
        </div>

        {/* Content List Area */}
        <div className="flex-1 overflow-y-auto">
          {searchQuery.trim() !== '' ? (
            // Search Mode: Contacts
            <div className="p-2 space-y-xs">
              <p className="text-[10px] text-outline font-bold px-2 uppercase tracking-wider mb-2">{t('availableContacts')}</p>
              {loadingContacts ? (
                <div className="text-center py-4 text-xs text-outline">Searching contacts...</div>
              ) : filteredContacts.length === 0 ? (
                <div className="text-center py-4 text-xs text-outline">No contacts found</div>
              ) : (
                filteredContacts.map(c => (
                  <div 
                    key={c.id}
                    onClick={() => handleStartConversation(c.id)}
                    className="p-2 hover:bg-primary/5 rounded-xl cursor-pointer flex items-center gap-sm transition-colors animate-in slide-in-from-bottom-2 duration-150"
                  >
                    <div className="w-9 h-9 rounded-full bg-secondary-container text-on-secondary-container font-bold flex items-center justify-center text-xs shrink-0 shadow-sm">
                      {getInitials(c.name)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h4 className="font-bold text-xs text-on-surface truncate">{c.name}</h4>
                      <p className="text-[10px] text-outline capitalize font-semibold">{c.role} • {c.email}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          ) : (
            // Default Mode: Active Conversations
            <div className="p-2 space-y-xs">
              <p className="text-[10px] text-outline font-bold px-2 uppercase tracking-wider mb-2">{t('activeConvs')}</p>
              {loadingConvs ? (
                <div className="text-center py-8">
                  <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
                </div>
              ) : conversations.length === 0 ? (
                <div className="text-center py-8 text-xs text-outline font-semibold">
                  <span className="material-symbols-outlined text-2xl block mb-xs text-outline/60">chat_bubble</span>
                  {t('noConvs')}
                </div>
              ) : (
                conversations.map(conv => {
                  const isSelected = activeConv?.id === conv.id;
                  return (
                    <div 
                      key={conv.id}
                      onClick={() => setActiveConv(conv)}
                      className={`p-3 rounded-xl cursor-pointer flex items-center justify-between gap-sm transition-all duration-150 group ${
                        isSelected 
                          ? 'bg-secondary-container/80 text-on-secondary-container shadow-sm border border-secondary-container' 
                          : 'hover:bg-surface-container-high border border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-sm min-w-0 flex-1">
                        <div className="w-10 h-10 rounded-full bg-primary-fixed text-primary font-bold flex items-center justify-center text-xs shrink-0 shadow-sm">
                          {getInitials(conv.other_user.name)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex justify-between items-baseline mb-0.5">
                            <h4 className="font-bold text-xs text-on-surface truncate">{conv.other_user.name}</h4>
                            {conv.last_message && (
                              <span className="text-[9px] text-outline shrink-0">
                                {new Date(conv.last_message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </span>
                            )}
                          </div>
                          <p className="text-[10px] text-outline font-semibold uppercase mb-unit capitalize">{conv.other_user.role}</p>
                          <p className="text-[11px] text-on-surface-variant truncate">
                            {conv.last_message ? (
                              conv.last_message.sender_id === user.id ? `You: ${conv.last_message.content || '[Attachment]'}` : conv.last_message.content || '[Attachment]'
                            ) : (
                              "No messages yet"
                            )}
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteConversation(conv.id);
                        }}
                        className="p-1.5 text-outline hover:text-error hover:bg-error/10 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity focus:outline-none shrink-0"
                        title={t('deleteConversation') || 'Delete Conversation'}
                      >
                        <span className="material-symbols-outlined text-sm">delete</span>
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right Pane: Message Area */}
      <div className="flex-1 flex flex-col bg-white">
        {activeConv ? (
          <>
            {/* Header info */}
            <div className="px-6 py-4 border-b border-outline-variant/30 flex items-center justify-between bg-surface shadow-sm z-10 shrink-0">
              <div className="flex items-center gap-md">
                <div className="w-10 h-10 rounded-full bg-primary-fixed text-primary font-bold flex items-center justify-center text-sm shadow-sm">
                  {getInitials(activeConv.other_user.name)}
                </div>
                <div>
                  <h3 className="font-bold text-on-surface text-sm">{activeConv.other_user.name}</h3>
                  <div className="flex items-center gap-xs">
                    <span className="w-2 h-2 bg-success rounded-full"></span>
                    <span className="text-[10px] text-outline capitalize font-bold">{activeConv.other_user.role} Workspace</span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => handleDeleteConversation(activeConv.id)}
                className="p-2 text-error hover:bg-error/10 rounded-xl transition-all focus:outline-none flex items-center justify-center"
                title={t('deleteConversation') || 'Delete Conversation'}
              >
                <span className="material-symbols-outlined text-md">delete</span>
              </button>
            </div>

            {/* Messages feed */}
            <div className="flex-1 overflow-y-auto p-6 space-y-md bg-surface-container-lowest">
              {loadingMessages && messages.length === 0 ? (
                <div className="flex justify-center items-center h-full">
                  <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
                </div>
              ) : (
                messages.map(msg => {
                  const isMe = msg.sender_id === user.id;
                  return (
                    <div 
                      key={msg.id} 
                      className={`flex ${isMe ? 'justify-end' : 'justify-start'} animate-in fade-in duration-200`}
                    >
                      <div className={`max-w-[70%] rounded-2xl px-4 py-2.5 shadow-sm relative group ${
                        isMe 
                          ? 'bg-primary text-on-primary rounded-tr-none' 
                          : 'bg-surface-container-high text-on-surface rounded-tl-none border border-outline-variant/20'
                      }`}>
                        {isMe && (
                          <button
                            type="button"
                            onClick={() => handleDeleteMessage(msg.id)}
                            className="absolute -left-7 top-1/2 -translate-y-1/2 p-1 text-outline hover:text-error hover:bg-error/10 rounded-lg opacity-60 hover:opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity focus:outline-none"
                            title="Delete Message"
                          >
                            <span className="material-symbols-outlined text-[14px]">delete</span>
                          </button>
                        )}
                        {msg.content && (
                          <p className="text-xs leading-relaxed whitespace-pre-wrap break-words">{msg.content}</p>
                        )}
                        {getAttachmentPreview(msg.attachment_path, msg.attachment_name)}
                        <span className={`text-[8px] block mt-1 text-right ${isMe ? 'text-on-primary/70' : 'text-outline'}`}>
                          {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div className="p-4 border-t border-outline-variant/30 bg-surface">
              <form onSubmit={handleSendMessage} className="space-y-sm">
                
                {/* File Previews */}
                {selectedFile && (
                  <div className="flex items-center justify-between bg-secondary-container/40 p-2.5 rounded-xl border border-secondary-container max-w-sm animate-in slide-in-from-bottom-2 duration-150">
                    <div className="flex items-center gap-xs text-xs truncate font-bold text-secondary">
                      <span className="material-symbols-outlined text-md">attachment</span>
                      <span className="truncate">{selectedFile.name}</span>
                    </div>
                    <button 
                      type="button" 
                      onClick={() => {
                        setSelectedFile(null);
                        setFileInputKey(Date.now());
                      }}
                      className="p-1 hover:bg-secondary-container rounded-full text-secondary transition-colors focus:outline-none"
                    >
                      <span className="material-symbols-outlined text-sm">close</span>
                    </button>
                  </div>
                )}

                <div className="flex items-center gap-sm">
                  {/* File attach button */}
                  <label className="p-2.5 hover:bg-surface-container-high rounded-xl text-outline hover:text-secondary cursor-pointer transition-colors focus:outline-none shrink-0 border border-outline-variant/30 bg-surface shadow-sm">
                    <span className="material-symbols-outlined text-md">attach_file</span>
                    <input 
                      key={fileInputKey}
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg,.tiff,.doc,.docx,.txt,image/*"
                      className="hidden"
                      onChange={handleFileChange}
                    />
                  </label>

                  {/* Doctor Prescription Button */}
                  {user?.role === 'doctor' && (
                    <button
                      type="button"
                      onClick={() => setShowPrescriptionModal(true)}
                      className="p-2.5 bg-secondary text-on-secondary hover:bg-secondary/90 rounded-xl transition-all shadow-md active:scale-95 shrink-0 flex items-center justify-center gap-xs font-bold text-xs"
                      title="Issue Prescription Document"
                    >
                      <span className="material-symbols-outlined text-[18px]">medical_services</span>
                      <span className="hidden sm:inline">Prescribe</span>
                    </button>
                  )}

                  {/* Input field */}
                  <input 
                    type="text"
                    placeholder={t('typeMessage')}
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    className="flex-1 px-4 py-2.5 bg-surface-container-low border border-outline-variant/30 rounded-xl text-xs focus:outline-none focus:border-secondary transition-colors shadow-inner"
                  />

                  {/* Send button */}
                  <button 
                    type="submit"
                    disabled={sending || (!messageText.trim() && !selectedFile)}
                    className="p-2.5 bg-primary hover:bg-primary/95 disabled:bg-outline-variant text-on-primary rounded-xl transition-all shadow-md active:scale-95 shrink-0 flex items-center justify-center"
                  >
                    {sending ? (
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    ) : (
                      <span className="material-symbols-outlined text-md">send</span>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col justify-center items-center text-outline font-semibold select-none bg-surface-container-lowest">
            <span className="material-symbols-outlined text-6xl mb-sm text-outline/40">forum</span>
            <h3 className="text-on-surface text-sm font-bold">{t('selectChat')}</h3>
            <p className="text-[11px] text-outline font-normal max-w-xs text-center mt-xs">
              Search for doctor or patient contacts in the left pane to initialize a private consultation workspace.
            </p>
          </div>
        )}
      </div>

      {/* Prescription Modal */}
      {showPrescriptionModal && (
        <div className="fixed inset-0 bg-black/55 backdrop-blur-sm z-[100] flex justify-center items-center p-4">
          <div className="bg-white rounded-2xl border border-outline-variant shadow-2xl w-full max-w-xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-4 border-b border-outline-variant bg-surface flex justify-between items-center">
              <div className="flex items-center gap-xs">
                <span className="material-symbols-outlined text-secondary">medical_services</span>
                <h3 className="font-bold text-primary text-sm">Write Online Prescription</h3>
              </div>
              <button 
                type="button"
                onClick={() => setShowPrescriptionModal(false)}
                className="p-1 hover:bg-surface-container-high rounded-full transition-colors text-outline focus:outline-none"
              >
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            </div>
            
            <form onSubmit={handleSendPrescription} className="p-4 space-y-md">
              <div className="grid grid-cols-2 gap-sm">
                <div>
                  <label className="block text-[10px] font-bold text-outline uppercase mb-xs">Patient Name</label>
                  <input 
                    type="text"
                    required
                    value={prescriptionForm.patient_name}
                    onChange={(e) => setPrescriptionForm({...prescriptionForm, patient_name: e.target.value})}
                    className="w-full px-3 py-2 border border-outline-variant rounded-lg text-xs bg-surface text-on-surface focus:outline-none focus:border-secondary"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-outline uppercase mb-xs">Diagnosis</label>
                  <input 
                    type="text"
                    required
                    placeholder="e.g. Acute Bronchitis"
                    value={prescriptionForm.diagnosis}
                    onChange={(e) => setPrescriptionForm({...prescriptionForm, diagnosis: e.target.value})}
                    className="w-full px-3 py-2 border border-outline-variant rounded-lg text-xs bg-surface text-on-surface focus:outline-none focus:border-secondary"
                  />
                </div>
              </div>
              
              <div>
                <div className="flex justify-between items-center mb-xs">
                  <label className="block text-[10px] font-bold text-outline uppercase">Prescribed Medications</label>
                  <button 
                    type="button"
                    onClick={handleAddMedicine}
                    className="text-[10px] text-secondary font-bold hover:underline flex items-center gap-2xs focus:outline-none"
                  >
                    <span className="material-symbols-outlined text-xs">add</span> Add Row
                  </button>
                </div>
                
                <div className="max-h-48 overflow-y-auto border border-outline-variant rounded-xl overflow-hidden bg-surface">
                  <table className="w-full text-left border-collapse text-[11px]">
                    <thead>
                      <tr className="bg-surface-container border-b border-outline-variant text-outline font-bold">
                        <th className="p-2">Medication Name</th>
                        <th className="p-2">Dosage</th>
                        <th className="p-2">Frequency</th>
                        <th className="p-2">Duration</th>
                        <th className="p-2 w-10"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {prescriptionForm.medicines.map((med, idx) => (
                        <tr key={idx} className="border-b border-outline-variant last:border-0 hover:bg-surface-container/30">
                          <td className="p-1.5">
                            <input 
                              type="text"
                              required
                              placeholder="e.g. Paracetamol"
                              value={med.name}
                              onChange={(e) => handleUpdateMedicine(idx, 'name', e.target.value)}
                              className="w-full px-2 py-1 border border-outline-variant/50 rounded bg-white text-[11px] focus:outline-none focus:border-secondary"
                            />
                          </td>
                          <td className="p-1.5">
                            <input 
                              type="text"
                              required
                              placeholder="e.g. 500 mg"
                              value={med.dosage}
                              onChange={(e) => handleUpdateMedicine(idx, 'dosage', e.target.value)}
                              className="w-full px-2 py-1 border border-outline-variant/50 rounded bg-white text-[11px] focus:outline-none focus:border-secondary"
                            />
                          </td>
                          <td className="p-1.5">
                            <input 
                              type="text"
                              required
                              placeholder="e.g. 1-0-1"
                              value={med.frequency}
                              onChange={(e) => handleUpdateMedicine(idx, 'frequency', e.target.value)}
                              className="w-full px-2 py-1 border border-outline-variant/50 rounded bg-white text-[11px] focus:outline-none focus:border-secondary"
                            />
                          </td>
                          <td className="p-1.5">
                            <input 
                              type="text"
                              required
                              placeholder="e.g. 5 days"
                              value={med.duration}
                              onChange={(e) => handleUpdateMedicine(idx, 'duration', e.target.value)}
                              className="w-full px-2 py-1 border border-outline-variant/50 rounded bg-white text-[11px] focus:outline-none focus:border-secondary"
                            />
                          </td>
                          <td className="p-1.5 text-center">
                            <button
                              type="button"
                              disabled={prescriptionForm.medicines.length === 1}
                              onClick={() => handleRemoveMedicine(idx)}
                              className="p-1 hover:bg-error/10 text-outline hover:text-error disabled:opacity-40 rounded transition-colors focus:outline-none"
                            >
                              <span className="material-symbols-outlined text-xs">delete</span>
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              
              <div>
                <label className="block text-[10px] font-bold text-outline uppercase mb-xs">Special Instructions (Optional)</label>
                <textarea 
                  placeholder="e.g. Take after meals, drink warm water..."
                  rows={2}
                  value={prescriptionForm.instructions}
                  onChange={(e) => setPrescriptionForm({...prescriptionForm, instructions: e.target.value})}
                  className="w-full px-3 py-2 border border-outline-variant rounded-lg text-xs bg-surface text-on-surface focus:outline-none focus:border-secondary resize-none"
                />
              </div>
              
              <div className="flex justify-end gap-sm border-t border-outline-variant/50 pt-3">
                <button 
                  type="button"
                  onClick={() => setShowPrescriptionModal(false)}
                  className="px-4 py-2 border border-outline text-outline font-bold text-xs rounded-xl hover:bg-surface-container active:scale-95 transition-all focus:outline-none"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={sending}
                  className="px-4 py-2 bg-primary hover:bg-primary/95 text-on-primary font-bold text-xs rounded-xl hover:shadow-md active:scale-95 transition-all focus:outline-none flex items-center gap-xs"
                >
                  {sending && <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>}
                  <span>Issue & Send</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
