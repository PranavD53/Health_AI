import React, { createContext, useContext, useState, useEffect } from 'react';

const LanguageContext = createContext();

export const useLanguage = () => useContext(LanguageContext);

export const translations = {
  en: {
    // Nav / Sidebar
    dashboard: "Dashboard",
    workspace: "Workspace",
    adminPortal: "Admin Portal",
    appointments: "Appointments",
    records: "Medical Records",
    chat: "Chat Workspace",
    settings: "Settings",
    logout: "Logout",
    assistant: "HealthAI Assistant",
    role: "Role",
    sosTrigger: "Trigger Clinical SOS",
    sosActive: "SOS Broadcast Active!",
    sosSending: "Activating Emergency...",
    switchToAdmin: "Switch to Admin Mode",
    switchToUser: "Switch to User Mode",
    switchToDoctor: "Switch to Doctor Mode",
    switchToCaregiver: "Switch to Caregiver Mode",
    
    // Patient Dashboard
    welcomeBack: "Welcome back,",
    syncRecords: "Your clinical health records and appointments are fully synchronized.",
    bookVisit: "Book Visit",
    uploadRecords: "Upload Records",
    upcomingAppts: "Upcoming Appointments",
    noAppts: "No upcoming appointments booked.",
    findDocToBook: "Find a Doctor to Book Now",
    cancel: "Cancel",
    aiIntel: "AI Clinical Intelligence",
    aiTip: "AI Tip",
    recordsFolder: "Medical Records Folder",
    recordCount: "files uploaded",
    noRecords: "No medical records found.",
    dateLabel: "Date",
    timeLabel: "Time",
    doctorLabel: "Doctor",
    specializationLabel: "Specialization",
    symptomsLabel: "Symptoms",
    symptomAnalyzer: "Quick Symptom Checker",
    analyzeBtn: "Analyze Symptoms",
    severityLabel: "Severity",
    durationLabel: "Duration",
    
    // Chat Page
    searchContacts: "Search contacts to chat...",
    availableContacts: "Available Contacts",
    activeConvs: "Active Conversations",
    noConvs: "No conversations yet. Type in search above to start one!",
    selectChat: "Select a Chat Conversation",
    consultationWorkspace: "Workspace",
    typeMessage: "Type a message or describe attached documents...",
    send: "Send",
    attachment: "Attachment",
    
    // Doctor Dashboard
    clinicSchedule: "Clinic Schedule",
    patientQueue: "Patient Queue",
    activeAlerts: "Active Emergency Alerts",
    noAlerts: "No emergency alerts reported.",
    resolveAlert: "Resolve Alert",
    patientName: "Patient Name",
    reason: "Reason",
    actions: "Actions",
    
    // Admin Dashboard
    complaintsRegistry: "Complaints & Support Registry",
    resolved: "Resolved",
    pending: "Pending",
    systemUsers: "Registered System Users",
    toggleStatus: "Toggle Status",
    active: "Active",
    inactive: "Inactive",
    grantAdmin: "Grant Admin Switch Permission",
    revokeAdmin: "Revoke Admin Switch Permission",
    adminAllowed: "Admin Mode Switch Granted",
    adminNotAllowed: "Admin Mode Switch Denied",

    // General Layout
    loadingText: "HealthAI is loading...",
    searchDocPlaceholder: "Search doctors by name or specialization...",
    uploadBtn: "Upload Medical PDF/Image",
    allRecords: "All Uploaded Records",

    // Feedback System
    feedbackTitle: "Consultation Feedback & Review",
    editFeedback: "Edit Feedback",
    submitFeedback: "Submit Feedback",
    overallRating: "Overall Consultation Rating",
    doctorRating: "Doctor Professional Rating",
    commentsLabel: "Written Comments & Experience Details",
    commentsPlaceholder: "Write about your experience with the doctor and consultation...",
    ratingCommunication: "Communication Style",
    ratingProfessionalism: "Professional Ethics & Skill",
    ratingWaitTime: "Waiting Time & Schedule Adherence",
    ratingSatisfaction: "Overall Service Satisfaction",
    optionalCategories: "Detailed Ratings (Optional)",
    privacyDisclaimer: "Your comments and detailed ratings are shared with the doctor and public profiles anonymously to protect your privacy.",
    feedbackSubmitted: "Feedback submitted successfully! Thank you for your review.",
    noPendingFeedback: "No consultations pending feedback.",
    feedbackFormError: "Please ensure overall and doctor ratings are selected.",
    completeVisit: "Complete Visit",
    feedbackAnalytics: "Feedback Analytics & Reviews",
    reviewsCount: "reviews",
    anonymousReview: "Verified Patient",
    averageRatingLabel: "Average Rating",
    viewReviewsBtn: "View Reviews",
    moderateReviewsTab: "Review Moderation",
    approveBtn: "Approve",
    rejectBtn: "Reject / Hide",
    noReviewsMsg: "No reviews submitted yet."
  },
  hi: {
    // Nav / Sidebar
    dashboard: "डैशबोर्ड",
    workspace: "कार्यस्थल",
    adminPortal: "एडमिन पोर्टल",
    appointments: "अपॉइंटमेंट",
    records: "चिकित्सा रिकॉर्ड",
    chat: "चैट वर्कस्पेस",
    settings: "सेटिंग्स",
    logout: "लॉगआउट",
    assistant: "हेल्थएआई सहायक",
    role: "भूमिका",
    sosTrigger: "आपातकालीन एसओएस भेजें",
    sosActive: "एसओएस सक्रिय है!",
    sosSending: "एसओएस सक्रिय किया जा रहा है...",
    switchToAdmin: "एडमिन मोड में जाएं",
    switchToUser: "यूज़र मोड में जाएं",
    switchToDoctor: "डॉक्टर मोड में जाएं",
    switchToCaregiver: "केयरगिवर मोड में जाएं",
    
    // Patient Dashboard
    welcomeBack: "आपका स्वागत है,",
    syncRecords: "आपके चिकित्सा रिकॉर्ड और अपॉइंटमेंट पूरी तरह से सिंक हैं।",
    bookVisit: "अपॉइंटमेंट बुक करें",
    uploadRecords: "रिकॉर्ड अपलोड करें",
    upcomingAppts: "आगामी अपॉइंटमेंट",
    noAppts: "कोई आगामी अपॉइंटमेंट बुक नहीं है।",
    findDocToBook: "बुक करने के लिए डॉक्टर खोजें",
    cancel: "रद्द करें",
    aiIntel: "एआई नैदानिक खुफिया",
    aiTip: "एआई टिप",
    recordsFolder: "चिकित्सा रिकॉर्ड फ़ोल्डर",
    recordCount: "फ़ाइलें अपलोड की गईं",
    noRecords: "कोई चिकित्सा रिकॉर्ड नहीं मिला।",
    dateLabel: "तारीख",
    timeLabel: "समय",
    doctorLabel: "चिकित्सक",
    specializationLabel: "विशेषज्ञता",
    symptomsLabel: "लक्षण",
    symptomAnalyzer: "त्वरित लक्षण परीक्षक",
    analyzeBtn: "लक्षणों का विश्लेषण करें",
    severityLabel: "तीव्रता",
    durationLabel: "अवधि",

    // Chat Page
    searchContacts: "चैट करने के लिए संपर्क खोजें...",
    availableContacts: "उपलब्ध संपर्क",
    activeConvs: "सक्रिय बातचीत",
    noConvs: "अभी तक कोई बातचीत नहीं हुई है। संपर्क खोजें!",
    selectChat: "एक चैट बातचीत चुनें",
    consultationWorkspace: "कार्यस्थान",
    typeMessage: "संदेश लिखें या दस्तावेज़ विवरण लिखें...",
    send: "भेजें",
    attachment: "अटैचमेंट",
    
    // Doctor Dashboard
    clinicSchedule: "क्लीनिक अनुसूची",
    patientQueue: "मरीजों की कतार",
    activeAlerts: "सक्रिय आपातकालीन अलर्ट",
    noAlerts: "कोई आपातकालीन अलर्ट नहीं मिला।",
    resolveAlert: "अलर्ट हल करें",
    patientName: "मरीज का नाम",
    reason: "कारण",
    actions: "कार्रवाई",
    
    // Admin Dashboard
    complaintsRegistry: "शिकायत एवं सहायता रजिस्ट्री",
    resolved: "समाधान किया गया",
    pending: "लंबित",
    systemUsers: "पंजीकृत सिस्टम उपयोगकर्ता",
    toggleStatus: "स्थिति बदलें",
    active: "सक्रिय",
    inactive: "निष्क्रिय",
    grantAdmin: "एडमिन स्विच अनुमति दें",
    revokeAdmin: "एडमिन स्विच अनुमति वापस लें",
    adminAllowed: "एडमिन मोड अनुमति स्वीकृत",
    adminNotAllowed: "एडमिन मोड अनुमति अस्वीकृत",

    // General Layout
    loadingText: "हेल्थएआई लोड हो रहा है...",
    searchDocPlaceholder: "नाम या विशेषज्ञता के आधार पर डॉक्टरों को खोजें...",
    uploadBtn: "चिकित्सा पीडीएफ/छवि अपलोड करें",
    allRecords: "सभी अपलोड किए गए रिकॉर्ड",

    // Feedback System
    feedbackTitle: "परामर्श प्रतिक्रिया और समीक्षा",
    editFeedback: "प्रतिक्रिया संपादित करें",
    submitFeedback: "प्रतिक्रिया भेजें",
    overallRating: "समग्र परामर्श रेटिंग",
    doctorRating: "डॉक्टर व्यावसायिक रेटिंग",
    commentsLabel: "लिखित टिप्पणियाँ और अनुभव विवरण",
    commentsPlaceholder: "डॉक्टर और परामर्श के अपने अनुभव के बारे में लिखें...",
    ratingCommunication: "संचार शैली",
    ratingProfessionalism: "व्यावसायिक नैतिकता और कौशल",
    ratingWaitTime: "प्रतीक्षा समय और कार्यक्रम का पालन",
    ratingSatisfaction: "समग्र सेवा संतुष्टि",
    optionalCategories: "विस्तृत रेटिंग (वैकल्पिक)",
    privacyDisclaimer: "आपकी गोपनीयता की रक्षा के लिए आपकी टिप्पणियाँ और विस्तृत रेटिंग डॉक्टर और सार्वजनिक प्रोफाइल के साथ गुमनाम रूप से साझा की जाती हैं।",
    feedbackSubmitted: "प्रतिक्रिया सफलतापूर्वक सबमिट की गई! आपकी समीक्षा के लिए धन्यवाद।",
    noPendingFeedback: "कोई परामर्श प्रतिक्रिया के लिए लंबित नहीं है।",
    feedbackFormError: "कृपया सुनिश्चित करें कि समग्र और डॉक्टर रेटिंग चुनी गई हैं।",
    completeVisit: "यात्रा पूरी करें",
    feedbackAnalytics: "प्रतिक्रिया विश्लेषण और समीक्षाएं",
    reviewsCount: "समीक्षाएं",
    anonymousReview: "सत्यापित रोगी",
    averageRatingLabel: "औसत रेटिंग",
    viewReviewsBtn: "समीक्षाएं देखें",
    moderateReviewsTab: "समीक्षा मॉडरेशन",
    approveBtn: "स्वीकार करें",
    rejectBtn: "अस्वीकार / छिपाएं",
    noReviewsMsg: "अभी तक कोई समीक्षा सबमिट नहीं की गई है।"
  },
  te: {
    // Nav / Sidebar
    dashboard: "డాష్‌బోర్డ్",
    workspace: "పని ప్రదేశం",
    adminPortal: "అడ్మిన్ పోర్టల్",
    appointments: "అపాయింట్‌మెంట్‌లు",
    records: "వైద్య రికార్డులు",
    chat: "చాట్ వర్క్‌స్పేస్",
    settings: "సెట్టింగ్‌లు",
    logout: "లాగ్అవుట్",
    assistant: "హెల్త్AI అసిస్టెంట్",
    role: "పాత్ర",
    sosTrigger: "SOS అత్యవసర ప్రకటన",
    sosActive: "SOS అత్యవసర సక్రియం చేయబడింది!",
    sosSending: "SOS పంపుతోంది...",
    switchToAdmin: "అడ్మిన్ మోడ్‌కు మారండి",
    switchToUser: "యూజర్ మోడ్‌కు మారండి",
    switchToDoctor: "డాక్టర్ మోడ్‌కు మారండి",
    switchToCaregiver: "కేర్‌గివర్ మోడ్‌కు మారండి",
    
    // Patient Dashboard
    welcomeBack: "స్వాగతం,",
    syncRecords: "మీ వైద్య రికార్డులు మరియు అపాయింట్‌మెంట్‌లు పూర్తిగా సమకాలీకరించబడ్డాయి.",
    bookVisit: "అపాయింట్‌మెంట్ బుక్ చేయి",
    uploadRecords: "రికార్డులు అప్‌లోడ్ చేయి",
    upcomingAppts: "రాబోయే అపాయింట్‌మెంట్‌లు",
    noAppts: "రాబోయే అపాయింట్‌మెంట్‌లు ఏవీ బుక్ చేయబడలేదు.",
    findDocToBook: "బుక్ చేయడానికి వైద్యుడిని కనుగొనండి",
    cancel: "రద్దు చేయి",
    aiIntel: "AI క్లినికల్ ఇంటెలిజెన్స్",
    aiTip: "AI చిట్కా",
    recordsFolder: "వైద్య రికార్డుల ఫోల్డర్",
    recordCount: "ఫైళ్లు అప్‌లోడ్ చేయబడ్డాయి",
    noRecords: "వైద్య రికార్డులు కనుగొనబడలేదు.",
    dateLabel: "తేదీ",
    timeLabel: "సమయం",
    doctorLabel: "వైద్యుడు",
    specializationLabel: "ప్రత్యేకత",
    symptomsLabel: "లక్షణాలు",
    symptomAnalyzer: "త్వరిత లక్షణాల తనిఖీ",
    analyzeBtn: "లక్షణాలను విశ్లేషించు",
    severityLabel: "తీవ్రత",
    durationLabel: "వ్యవధి",

    // Chat Page
    searchContacts: "చాట్ చేయడానికి పరిచయాలను వెతకండి...",
    availableContacts: "అందుబాటులో ఉన్న పరిచయాలు",
    activeConvs: "సక్రియ సంభాషణలు",
    noConvs: "ఇంకా సంభాషణలు లేవు. పరిచయాలను వెతకండి!",
    selectChat: "చాట్ సంభాషణను ఎంచుకోండి",
    consultationWorkspace: "వర్క్‌స్పేస్",
    typeMessage: "సందేశాన్ని టైప్ చేయండి లేదా ఫైల్ వివరాలు రాయండి...",
    send: "పంపు",
    attachment: "అటాచ్‌మెంట్",
    
    // Doctor Dashboard
    clinicSchedule: "క్లినిక్ షెడ్యూల్",
    patientQueue: "రోగుల క్యూ",
    activeAlerts: "సక్రియ అత్యవసర హెచ్చరికలు",
    noAlerts: "ఎటువంటి అత్యవసర హెచ్చరికలు లేవు.",
    resolveAlert: "హెచ్చరిక పరిష్కరించు",
    patientName: "రోగి పేరు",
    reason: "కారణం",
    actions: "చర్యలు",
    
    // Admin Dashboard
    complaintsRegistry: "ఫిర్యాదులు & సహాయ రిజిస్ట్రీ",
    resolved: "పరిష్కరించబడింది",
    pending: "పెండింగ్",
    systemUsers: "నమోదిత సిస్టమ్ వినియోగదారులు",
    toggleStatus: "స్థితిని మార్చండి",
    active: "సక్రియం",
    inactive: "నిష్క్రియం",
    grantAdmin: "అడ్మిన్ స్విచ్ అనుమతి ఇవ్వండి",
    revokeAdmin: "అడ్మిన్ స్విచ్ అనుమతి రద్దు చేయి",
    adminAllowed: "అడ్మిన్ మోడ్ అనుమతి లభించింది",
    adminNotAllowed: "అడ్మిన్ మోడ్ అనుమతి రద్దు చేయబడింది",

    // General Layout
    loadingText: "హెల్త్AI లోడ్ అవుతోంది...",
    searchDocPlaceholder: "వైద్యుడిని పేరు లేదా ప్రత్యేకత ఆధారంగా వెతకండి...",
    uploadBtn: "మెడికల్ పిడిఎఫ్/చిత్రాన్ని అప్‌లోడ్ చేయండి",
    allRecords: "అన్ని అప్‌లోడ్ చేయబడిన వైద్య రికార్డులు",

    // Feedback System
    feedbackTitle: "సంప్రదింపుల అభిప్రాయం & సమీక్ష",
    editFeedback: "అభిప్రాయాన్ని సవరించండి",
    submitFeedback: "అభిప్రాయాన్ని సమర్పించండి",
    overallRating: "మొత్తం సంప్రదింపుల రేటింగ్",
    doctorRating: "వైద్యుడి వృత్తిపరమైన రేటింగ్",
    commentsLabel: "లిఖితపూర్వక వ్యాఖ్యలు & అనుభవ వివరాలు",
    commentsPlaceholder: "వైద్యుడు మరియు సంప్రదింపులతో మీ అనుభవం గురించి రాయండి...",
    ratingCommunication: "కమ్యూనికేషన్ శైలి",
    ratingProfessionalism: "వృత్తిపరమైన నీతి & నైపుణ్యం",
    ratingWaitTime: "వేచి ఉండే సమయం & షెడ్యూల్ కట్టుబడి ఉండడం",
    ratingSatisfaction: "మొత్తం సేవా సంప్త్యప్తి",
    optionalCategories: "వివరణాత్మక రేటింగ్‌లు (ఐచ్ఛికం)",
    privacyDisclaimer: "మీ గోప్యతను రక్షించడానికి మీ వ్యాఖ్యలు మరియు వివరణాత్మక రేటింగ్‌లు వైద్యుడు మరియు పబ్లిక్ ప్రొఫైల్‌లతో అనామకంగా భాగస్వామ్యం చేయబడతాయి.",
    feedbackSubmitted: "అభిప్రాయం విజయవంతంగా సమర్పించబడింది! మీ సమీక్షకు ధన్యవాదాలు.",
    noPendingFeedback: "అభిప్రాయం పెండింగ్‌లో ఉన్న సంప్రదింపులు ఏవీ లేవు.",
    feedbackFormError: "దయచేసి మొత్తం మరియు వైద్యుడి రేటింగ్‌లు ఎంచుకున్నారని నిర్ధారించుకోండి.",
    completeVisit: "సందర్శన పూర్తి చేయి",
    feedbackAnalytics: "అభిప్రాయ విశ్లేషణ & సమీక్షలు",
    reviewsCount: "సమీక్షలు",
    anonymousReview: "ధృవీకరించబడిన రోగి",
    averageRatingLabel: "సగటు రేటింగ్",
    viewReviewsBtn: "సమీక్షలను వీక్షించండి",
    moderateReviewsTab: "సమీక్షల నియంత్రణ",
    approveBtn: "ఆమోదించు",
    rejectBtn: "తిరస్కరించు / దాచు",
    noReviewsMsg: "ఇంకా సమీక్షలు సమర్పించబడలేదు."
  }
};

export const LanguageProvider = ({ children }) => {
  const [currentLanguage, setCurrentLanguage] = useState(() => {
    return localStorage.getItem('app_lang') || 'en';
  });

  useEffect(() => {
    localStorage.setItem('app_lang', currentLanguage);
  }, [currentLanguage]);

  const t = (key) => {
    const langDict = translations[currentLanguage] || translations['en'];
    return langDict[key] || translations['en'][key] || key;
  };

  return (
    <LanguageContext.Provider value={{ currentLanguage, setCurrentLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
};
