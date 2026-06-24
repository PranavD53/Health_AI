import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../services/api';
import { useLanguage } from '../context/LanguageContext';
import { resolveMediaUrl } from '../utils/apiConfig';

// Custom Localized Dictionary for Imaging Diagnostic Screen
const pageTranslations = {
  en: {
    title: "AI Medical Imaging & Skin Diagnostics",
    subtitle: "Upload clinical photos for automated preliminary assessment and instant specialist routing.",
    dropzonePlaceholder: "Drag & drop clinical scan, or click to browse",
    selectScanType: "Select Diagnostic Category",
    skin: "Skin Condition",
    throat: "Throat Redness",
    xray: "X-Ray / Scan",
    analyzeBtn: "Perform Clinical Scan",
    analyzing: "Processing Multimodal Image Analysis...",
    resultsTitle: "Clinical Diagnosis Report",
    severity: "Severity Level",
    findings: "Clinical Observations & Findings",
    specialist: "Recommended Specialist",
    bookBtn: "Schedule Specialist Appointment",
    historyTitle: "Diagnostic History",
    noHistory: "No diagnostics history found. Upload a scan above to begin.",
    deleteBtn: "Delete Report",
    viewReportBtn: "View Report",
    closeBtn: "Close",
    date: "Date Analyzed",
    category: "Scan Category",
    normal: "Normal",
    low: "Low Severity",
    moderate: "Moderate Severity",
    high: "High Severity",
    critical: "Critical",
    dermatology: "Dermatologist",
    otolaryngology: "ENT Specialist",
    radiology: "Radiologist",
    general: "General Physician",
    uploadSuccess: "Diagnostic report processed successfully!",
    uploadFailed: "Analysis failed: ",
    deleteConfirm: "Are you sure you want to delete this diagnostic report?",
    uploadLabel: "Upload Target Image",
    fileTypesDesc: "Supports JPG, PNG, WEBP up to 10MB",
    aiAssessment: "AI Smart Assessment",
    aiAssessmentDesc: "This automated diagnostics system runs visual scans through deep learning architectures to isolate focal points, check dermatological asymmetry, detect posterior inflammation, or evaluate airspace lucency.",
    safeAnon: "Safe and Anonymous",
    safeAnonDesc: "Your uploaded images are secured and cataloged for routing under HIPAA compliant guidelines.",
    instantBooking: "Instant Specialist Booking",
    instantBookingDesc: "If visual signals indicate moderate to critical pathology, the system pre-fills routing details to let you book the correct specialist instantly.",
    tarsAudio: "TARS Audio Output",
    tarsAudioDesc: "TARS reads clinical outputs aloud and suggests routing actions using our real-time voice pipeline.",
    modelActive: "AI Core Diagnostics Model Active"
  },
  es: {
    title: "Imágenes Médicas y Diagnóstico de Piel con IA",
    subtitle: "Suba fotos clínicas para una evaluación preliminar automatizada y direccionamiento a especialistas.",
    dropzonePlaceholder: "Arrastre y suelte la imagen, o haga clic para buscar",
    selectScanType: "Seleccione Categoría de Diagnóstico",
    skin: "Condición de la Piel",
    throat: "Enrojecimiento de Garganta",
    xray: "Radiografía / Escaneo",
    analyzeBtn: "Realizar Análisis Clínico",
    analyzing: "Procesando Análisis de Imagen Multimodal...",
    resultsTitle: "Informe de Diagnóstico Clínico",
    severity: "Nivel de Gravedad",
    findings: "Observaciones Clínicas y Resultados",
    specialist: "Especialista Recomendado",
    bookBtn: "Programar Cita con Especialista",
    historyTitle: "Historial de Diagnóstico",
    noHistory: "No se encontró historial. Suba un escaneo arriba para comenzar.",
    deleteBtn: "Eliminar Informe",
    viewReportBtn: "Ver Informe",
    closeBtn: "Cerrar",
    date: "Fecha de Análisis",
    category: "Categoría de Escaneo",
    normal: "Normal",
    low: "Bajo",
    moderate: "Moderado",
    high: "Alto",
    critical: "Crítico",
    dermatology: "Dermatólogo",
    otolaryngology: "Especialista ORL",
    radiology: "Radiólogo",
    general: "Médico General",
    uploadSuccess: "Informe de diagnóstico procesado con éxito!",
    uploadFailed: "Análisis fallido: ",
    deleteConfirm: "¿Está seguro de que desea eliminar este informe?",
    uploadLabel: "Subir imagen de destino",
    fileTypesDesc: "Soporta JPG, PNG, WEBP hasta 10MB",
    aiAssessment: "Evaluación inteligente de IA",
    aiAssessmentDesc: "Este sistema de diagnóstico automatizado realiza escaneos visuales a través de arquitecturas de aprendizaje profundo para aislar puntos focales, verificar la asimetría dermatológica o evaluar la lucidez del espacio aéreo.",
    safeAnon: "Seguro y Anónimo",
    safeAnonDesc: "Sus imágenes cargadas están protegidas y catalogadas para su direccionamiento según las pautas de cumplimiento de HIPAA.",
    instantBooking: "Reserva inmediata de especialista",
    instantBookingDesc: "Si las señales visuales indican una patología moderada a crítica, el sistema preselecciona los detalles para reservar al especialista adecuado.",
    tarsAudio: "Salida de audio de TARS",
    tarsAudioDesc: "TARS lee los resultados clínicos en voz alta y sugiere acciones utilizando nuestra canalización de voz en tiempo real.",
    modelActive: "Modelo de diagnóstico central de IA activo"
  },
  hi: {
    title: "एआई मेडिकल इमेजिंग और त्वचा निदान",
    subtitle: "स्वचालित प्रारंभिक मूल्यांकन और तत्काल विशेषज्ञ रेफरल के लिए नैदानिक फ़ोटो अपलोड करें।",
    dropzonePlaceholder: "यहाँ फोटो खींच कर लाएँ या ब्राउज़ करने के लिए क्लिक करें",
    selectScanType: "नैदानिक श्रेणी का चयन करें",
    skin: "त्वचा की स्थिति",
    throat: "गले की लालिमा",
    xray: "एक्स-रे / स्कैन",
    analyzeBtn: "नैदानिक स्कैन शुरू करें",
    analyzing: "छवि विश्लेषण संसाधित किया जा रहा है...",
    resultsTitle: "नैदानिक निदान रिपोर्ट",
    severity: "गंभीरता का स्तर",
    findings: "नैदानिक टिप्पणियां और निष्कर्ष",
    specialist: "अनुशंसित विशेषज्ञ",
    bookBtn: "विशेषज्ञ के साथ अपॉइंटमेंट बुक करें",
    historyTitle: "निदान इतिहास",
    noHistory: "कोई निदान इतिहास नहीं मिला। शुरू करने के लिए ऊपर एक स्कैन अपलोड करें।",
    deleteBtn: "रिपोर्ट हटाएं",
    viewReportBtn: "रिपोर्ट देखें",
    closeBtn: "बंद करें",
    date: "विश्लेषण की तिथि",
    category: "स्कैन श्रेणी",
    normal: "सामान्य",
    low: "कम गंभीरता",
    moderate: "मध्यम गंभीरता",
    high: "उच्च गंभीरता",
    critical: "गंभीर (क्रिटिकल)",
    dermatology: "त्वचा विशेषज्ञ",
    otolaryngology: "कान, नाक, गला विशेषज्ञ",
    radiology: "रेडियोलॉजिस्ट",
    general: "सामान्य चिकित्सक",
    uploadSuccess: "नैदानिक रिपोर्ट सफलतापूर्वक संसाधित की गई!",
    uploadFailed: "विश्लेषण विफल रहा: ",
    deleteConfirm: "क्या आप वाकई इस नैदानिक रिपोर्ट को हटाना चाहते हैं?",
    uploadLabel: "लक्ष्य छवि अपलोड करें",
    fileTypesDesc: "JPG, PNG, WEBP का समर्थन 10MB तक",
    aiAssessment: "एआई स्मार्ट मूल्यांकन",
    aiAssessmentDesc: "यह स्वचालित निदान प्रणाली फोकल पॉइंट को अलग करने, त्वचा की विषमता की जांच करने, पीछे की सूजन का पता लगाने या वायुक्षेत्र ल्यूसी का मूल्यांकन करने के लिए गहन शिक्षण आर्किटेक्चर के माध्यम से दृश्य स्कैन चलाती है।",
    safeAnon: "सुरक्षित और गुमनाम",
    safeAnonDesc: "आपके अपलोड किए गए चित्र हिपा (HIPAA) अनुपालन दिशानिर्देशों के तहत सुरक्षित और कैटलॉग किए गए हैं।",
    instantBooking: "तत्काल विशेषज्ञ बुकिंग",
    instantBookingDesc: "यदि दृश्य संकेत मध्यम से गंभीर विकृति का संकेत देते हैं, तो सिस्टम रूटिंग विवरणों को पहले से भर देता है ताकि आप तुरंत सही विशेषज्ञ को बुक कर सकें।",
    tarsAudio: "टार्स ऑडियो आउटपुट",
    tarsAudioDesc: "टार्स नैदानिक परिणामों को जोर से पढ़ता है और हमारी रीयल-टाइम वॉयस पाइपलाइन का उपयोग करके रूटिंग क्रियाओं का सुझाव देता है।",
    modelActive: "एआई कोर निदान मॉडल सक्रिय"
  },
  te: {
    title: "AI మెడికల్ ఇమేజింగ్ & స్కిన్ డయాగ్నోస్టిక్స్",
    subtitle: "ఆటోమేటెడ్ ప్రాథమిక అంచనా మరియు తక్షణ నిపుణుల సలహా కోసం క్లినికల్ ఫోటోలను అప్‌లోడ్ చేయండి.",
    dropzonePlaceholder: "క్లినికల్ స్కాన్‌ను ఇక్కడ లాగి వదలండి, లేదా వెతకడానికి క్లిక్ చేయండి",
    selectScanType: "డయాగ్నోస్టిక్ వర్గాన్ని ఎంచుకోండి",
    skin: "చర్మ వ్యాధి",
    throat: "గొంతు ఎరుపు",
    xray: "ఎక్స్-రే / స్కాన్",
    analyzeBtn: "క్లినికల్ స్కాన్ చేయి",
    analyzing: "మల్టీమోడల్ ఇమేజ్ విశ్లేషణను ప్రాసెస్ చేస్తోంది...",
    resultsTitle: "క్లినికల్ డయాగ్నోసిస్ నివేదిక",
    severity: "తీవ్రత స్థాయి",
    findings: "క్లినికల్ పరిశీలనలు & ఫలితాలు",
    specialist: "సిఫార్సు చేయబడిన నిపుణుడు",
    bookBtn: "నిపుణుడి అపాయింట్‌మెంట్ షెడ్యూల్ చేయి",
    historyTitle: "డయాగ్నోస్టిక్ చరిత్ర",
    noHistory: "డయాగ్నోస్టిక్స్ చరిత్ర కనుగొనబడలేదు. ప్రారంభించడానికి పైన ఒక స్కాన్‌ను అప్‌లోడ్ చేయండి.",
    deleteBtn: "నివేదికను తొలగించు",
    viewReportBtn: "నివేదిక చూడండి",
    closeBtn: "మూసివేయి",
    date: "విశ్లేషించిన తేదీ",
    category: "స్కాన్ వర్గం",
    normal: "సాధారణం",
    low: "తక్కువ తీవ్రత",
    moderate: "మధ్యస్థ తీవ్రత",
    high: "ఎక్కువ తీవ్రత",
    critical: "తీవ్రమైనది (క్రిటికల్)",
    dermatology: "చర్మ నిపుణుడు (డెర్మటాలజిస్ట్)",
    otolaryngology: "ENT నిపుణుడు",
    radiology: "రేడియాలజిస్ట్",
    general: "జనరల్ ఫిజీషియన్",
    uploadSuccess: "డయాగ్నోస్టిక్ నివేదిక విజయవంతంగా ప్రాసెస్ చేయబడింది!",
    uploadFailed: "విశ్లేషణ విఫలమైంది: ",
    deleteConfirm: "మీరు ఖచ్చితంగా ఈ డయాగ్నోస్టిక్ నివేదికను తొలగించాలనుకుంటున్నారా?",
    uploadLabel: "లక్ష్య చిత్రాన్ని అప్‌లోడ్ చేయండి",
    fileTypesDesc: "10MB వరకు JPG, PNG, WEBP ఫైళ్లకు సపోర్ట్ చేస్తుంది",
    aiAssessment: "AI స్మార్ట్ అంచనా",
    aiAssessmentDesc: "ఈ ఆటోమేటెడ్ డయాగ్నోస్టిక్స్ సిస్టమ్ ఫోకల్ పాయింట్లను వేరు చేయడానికి, చర్మ అసమానతలను తనిఖీ చేయడానికి, గొంతు వెనుక భాగంలో మంటను గుర్తించడానికి లేదా ఎయిర్‌స్పేస్ లూసెన్సీని అంచనా వేయడానికి డీప్ లెర్నింగ్ ఆర్కిటెక్చర్ల ద్వారా విజువల్ స్కాన్‌లను నడుపుతుంది.",
    safeAnon: "సురక్షితమైనది మరియు అనామకమైనది",
    safeAnonDesc: "మీరు అప్‌లోడ్ చేసిన చిత్రాలు HIPAA నిబంధనల ప్రకారం సురక్షితంగా ఉంచబడతాయి.",
    instantBooking: "తక్షణ నిపుణుల బుకింగ్",
    instantBookingDesc: "విజువల్ సిగ్నల్స్ ఒక మోస్తరు లేదా తీవ్రమైన వ్యాధిని సూచిస్తే, తగిన నిపుణుడిని వెంటనే బుక్ చేసుకోవడానికి సిస్టమ్ రూటింగ్ వివరాలను స్వయంచాలకంగా పూరిస్తుంది.",
    tarsAudio: "TARS ఆడియో అవుట్‌పుట్",
    tarsAudioDesc: "TARS క్లినికల్ ఫలితాలను బిగ్గరగా చదువుతుంది మరియు మా రియల్ టైమ్ వాయిస్ పైప్‌లైన్ ఉపయోగించి తగిన చర్యలను సూచిస్తుంది.",
    modelActive: "AI కోర్ డయాగ్నోస్టిక్స్ మోడల్ సక్రియంగా ఉంది"
  }
};

export default function ImagingDiagnostics() {
  const { currentLanguage, t } = useLanguage();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  
  // Detect current language code
  const localT = pageTranslations[currentLanguage] || pageTranslations['en'];

  const translateScanType = (type) => {
    if (!type) return '';
    const lower = type.toLowerCase();
    if (lower.includes('skin')) return localT.skin;
    if (lower.includes('throat')) return localT.throat;
    if (lower.includes('x-ray') || lower.includes('xray')) return localT.xray;
    return type;
  };

  const translateSeverity = (sev) => {
    if (!sev) return '';
    const lower = sev.toLowerCase();
    if (lower.includes('normal')) return localT.normal;
    if (lower.includes('low')) return localT.low;
    if (lower.includes('moderate')) return localT.moderate;
    if (lower.includes('high')) return localT.high;
    if (lower.includes('critical')) return localT.critical;
    return sev;
  };

  const translateSpecialist = (spec) => {
    if (!spec) return '';
    const lower = spec.toLowerCase();
    if (lower.includes('dermatology') || lower.includes('dermatologist')) return localT.dermatology;
    if (lower.includes('otolaryngology') || lower.includes('ent')) return localT.otolaryngology;
    if (lower.includes('radiology') || lower.includes('radiologist')) return localT.radiology;
    if (lower.includes('general')) return localT.general;
    return spec;
  };

  const [diagnostics, setDiagnostics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  
  // Form states
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [scanType, setScanType] = useState('Skin Condition');

  // Report details state
  const [activeReport, setActiveReport] = useState(null);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    loadDiagnostics();
  }, []);

  // Listen for open_report search parameter to auto-open modal
  useEffect(() => {
    const reportId = searchParams.get('open_report');
    if (reportId && diagnostics.length > 0) {
      const match = diagnostics.find(d => d.id === parseInt(reportId));
      if (match) {
        setActiveReport(match);
        setShowModal(true);
      }
    }
  }, [searchParams, diagnostics]);

  const loadDiagnostics = async () => {
    try {
      const data = await api.getMyDiagnostics();
      setDiagnostics(data);
    } catch (err) {
      console.error(err);
      setError("Failed to load diagnostics history.");
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      alert("File is too large. Maximum allowed size is 10MB.");
      return;
    }

    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setError('');
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      alert("Please upload a valid image file.");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      alert("File is too large. Maximum allowed size is 10MB.");
      return;
    }

    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setError('');
  };

  const handleAnalyzeSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      setError("Please upload an image file first.");
      return;
    }

    setAnalyzing(true);
    setError('');
    setSuccessMsg('');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('scan_type', scanType);

      const result = await api.analyzeImaging(formData);
      setSuccessMsg(localT.uploadSuccess);
      
      // Open report detail automatically
      setActiveReport(result);
      setShowModal(true);

      // Trigger TARS response speak event
      const cleanFindings = result.findings.split('[Diagnostic')[0].trim();
      const speakText = `Analysis complete for your ${scanType} scan. The severity is marked as ${result.severity}. Findings show: ${cleanFindings.slice(0, 150)}... The recommended specialist is ${result.recommended_specialist}.`;
      window.dispatchEvent(new CustomEvent('tars_speak', { detail: { text: speakText } }));

      // Clean form state
      setSelectedFile(null);
      setPreviewUrl(null);
      
      // Reload history
      loadDiagnostics();
    } catch (err) {
      console.error(err);
      setError(localT.uploadFailed + (err.message || err));
    } finally {
      setAnalyzing(false);
    }
  };

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm(localT.deleteConfirm)) return;

    try {
      await api.deleteDiagnostic(id);
      loadDiagnostics();
      if (activeReport && activeReport.id === id) {
        setShowModal(false);
        setActiveReport(null);
      }
    } catch (err) {
      alert("Failed to delete diagnostic report: " + err.message);
    }
  };

  const handleBookRedirect = (specialist) => {
    // Redirects to appointments search page passing state for pre-filling specialization
    navigate('/appointments', { state: { specialization: specialist } });
  };

  const getSeverityColor = (sev) => {
    const s = sev ? sev.toLowerCase() : '';
    if (s.includes('normal')) return 'bg-success/20 text-success border-success/30';
    if (s.includes('low')) return 'bg-info/20 text-info border-info/30';
    if (s.includes('moderate')) return 'bg-warning/20 text-warning border-warning/30';
    if (s.includes('high')) return 'bg-orange-500/20 text-orange-500 border-orange-500/30';
    if (s.includes('critical')) return 'bg-error/20 text-error border-error/30 animate-pulse';
    return 'bg-surface-container-high text-on-surface border-outline/30';
  };

  return (
    <div className="space-y-xl pb-10">
      {/* Header */}
      <div className="bg-surface-container-low border border-outline-variant/30 rounded-3xl p-lg md:p-xl shadow-sm relative overflow-hidden backdrop-blur-md">
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl pointer-events-none"></div>
        <h1 className="text-display-sm md:text-display-md font-black tracking-tight text-primary">
          {localT.title}
        </h1>
        <p className="text-body-lg text-outline mt-xs max-w-2xl">
          {localT.subtitle}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter">
        {/* Left Side: Upload & Control Panel */}
        <div className="lg:col-span-7 bg-surface border border-outline-variant/20 rounded-3xl p-md md:p-lg shadow-sm flex flex-col justify-between relative overflow-hidden">
          <form onSubmit={handleAnalyzeSubmit} className="space-y-md flex-1 flex flex-col">
            
            {/* Category Selector */}
            <div>
              <label className="text-title-sm font-bold text-on-surface mb-xs block">
                {localT.selectScanType}
              </label>
              <div className="grid grid-cols-3 gap-sm">
                {[
                  { id: 'Skin Condition', label: localT.skin, icon: 'texture' },
                  { id: 'Throat Redness', label: localT.throat, icon: 'face' },
                  { id: 'X-Ray', label: localT.xray, icon: 'photo_size_select_actual' }
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setScanType(item.id)}
                    className={`flex flex-col items-center justify-center p-md rounded-2xl border text-center transition-all ${
                      scanType === item.id
                        ? 'border-primary bg-primary/5 text-primary scale-[0.98]'
                        : 'border-outline-variant/30 bg-surface-container-lowest text-outline hover:bg-surface-container-low'
                    }`}
                  >
                    <span className="material-symbols-outlined text-[28px] mb-xs">{item.icon}</span>
                    <span className="text-label-sm font-bold leading-tight">{item.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Drag & Drop Upload Area */}
            <div className="flex-1 flex flex-col">
              <label className="text-title-sm font-bold text-on-surface mb-xs block">
                {localT.uploadLabel}
              </label>
              
              <div
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                className={`flex-1 border-2 border-dashed rounded-3xl p-lg flex flex-col items-center justify-center transition-all cursor-pointer min-h-[220px] relative overflow-hidden ${
                  previewUrl ? 'border-primary/50' : 'border-outline-variant hover:border-primary/50'
                }`}
                onClick={() => document.getElementById('imaging-file-input').click()}
              >
                {previewUrl ? (
                  <div className="relative w-full h-full max-h-[300px] flex items-center justify-center overflow-hidden rounded-xl">
                    <img 
                      src={previewUrl} 
                      alt="Scan Preview" 
                      className="max-w-full max-h-[280px] object-contain rounded-lg shadow-sm"
                    />
                    
                    {/* Glowing Laser Scan Effect */}
                    {analyzing && (
                      <div className="absolute inset-0 pointer-events-none">
                        <div 
                          className="w-full h-1 bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_8px_cyan] absolute left-0 right-0 animate-[scan_2s_ease-in-out_infinite]"
                          style={{
                            animationName: 'scanLaserAnimation',
                            animationDuration: '2s',
                            animationIterationCount: 'infinite',
                            animationTimingFunction: 'ease-in-out'
                          }}
                        ></div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center space-y-sm">
                    <div className="w-14 h-14 rounded-full bg-surface-container-high flex items-center justify-center mx-auto text-outline">
                      <span className="material-symbols-outlined text-[32px]">cloud_upload</span>
                    </div>
                    <div>
                      <p className="text-body-md font-bold text-on-surface">{localT.dropzonePlaceholder}</p>
                      <p className="text-label-sm text-outline mt-2">{localT.fileTypesDesc}</p>
                    </div>
                  </div>
                )}
                
                <input
                  type="file"
                  id="imaging-file-input"
                  accept="image/*"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </div>
            </div>

            {/* Error & Success Messages */}
            {error && (
              <div className="p-md rounded-2xl bg-error/10 text-error text-xs font-semibold flex items-center gap-xs border border-error/25">
                <span className="material-symbols-outlined text-[18px]">error</span>
                <span>{error}</span>
              </div>
            )}

            {successMsg && (
              <div className="p-md rounded-2xl bg-success/10 text-success text-xs font-semibold flex items-center gap-xs border border-success/25">
                <span className="material-symbols-outlined text-[18px]">check_circle</span>
                <span>{successMsg}</span>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={analyzing || !selectedFile}
              className={`w-full py-4 rounded-2xl font-bold flex items-center justify-center gap-sm active:scale-[0.98] transition-all shadow-md ${
                !selectedFile || analyzing
                  ? 'bg-surface-container-high text-outline cursor-not-allowed'
                  : 'bg-primary text-on-primary hover:bg-primary/95'
              }`}
            >
              {analyzing ? (
                <>
                  <div className="w-5 h-5 border-2 border-on-primary border-t-transparent rounded-full animate-spin"></div>
                  <span>{localT.analyzing}</span>
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined">analytics</span>
                  <span>{localT.analyzeBtn}</span>
                </>
              )}
            </button>

          </form>
        </div>

        {/* Right Side: Information / Quick Guideline */}
        <div className="lg:col-span-5 bg-surface-container-low border border-outline-variant/30 rounded-3xl p-lg flex flex-col justify-between shadow-sm relative overflow-hidden">
          <div className="space-y-md">
            <div className="flex items-center gap-sm">
              <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
                <span className="material-symbols-outlined">biotech</span>
              </div>
              <h3 className="text-title-md font-black text-on-surface">{localT.aiAssessment}</h3>
            </div>
            
            <p className="text-body-sm text-outline leading-relaxed">
              {localT.aiAssessmentDesc}
            </p>

            <div className="space-y-sm pt-xs">
              <div className="flex gap-sm p-sm rounded-xl hover:bg-surface-container-high transition-colors">
                <span className="material-symbols-outlined text-primary mt-0.5">verified_user</span>
                <div>
                  <h4 className="text-label-md font-bold text-on-surface">{localT.safeAnon}</h4>
                  <p className="text-label-sm text-outline">{localT.safeAnonDesc}</p>
                </div>
              </div>
              
              <div className="flex gap-sm p-sm rounded-xl hover:bg-surface-container-high transition-colors">
                <span className="material-symbols-outlined text-primary mt-0.5">swap_calls</span>
                <div>
                  <h4 className="text-label-md font-bold text-on-surface">{localT.instantBooking}</h4>
                  <p className="text-label-sm text-outline">{localT.instantBookingDesc}</p>
                </div>
              </div>

              <div className="flex gap-sm p-sm rounded-xl hover:bg-surface-container-high transition-colors">
                <span className="material-symbols-outlined text-primary mt-0.5">quick_reference_all</span>
                <div>
                  <h4 className="text-label-md font-bold text-on-surface">{localT.tarsAudio}</h4>
                  <p className="text-label-sm text-outline">{localT.tarsAudioDesc}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-lg border-t border-outline-variant/30 pt-md flex items-center gap-sm">
            <span className="w-2.5 h-2.5 rounded-full bg-success"></span>
            <span className="text-label-sm font-bold text-outline">{localT.modelActive}</span>
          </div>
        </div>
      </div>

      {/* History Grid */}
      <div className="space-y-md">
        <h2 className="text-title-lg font-black tracking-tight text-on-surface flex items-center gap-sm">
          <span className="material-symbols-outlined">history</span>
          {localT.historyTitle}
        </h2>
        
        {loading ? (
          <div className="flex justify-center items-center py-xl">
            <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : diagnostics.length === 0 ? (
          <div className="bg-surface-container-lowest border border-outline-variant/30 rounded-3xl p-lg text-center text-outline">
            <span className="material-symbols-outlined text-[48px] mb-xs">folder_open</span>
            <p className="text-body-md font-bold">{localT.noHistory}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-gutter">
            {diagnostics.map((report) => {
              const cleanFindings = report.findings.split('[Diagnostic')[0].trim();
              return (
                <div 
                  key={report.id}
                  onClick={() => {
                    setActiveReport(report);
                    setShowModal(true);
                  }}
                  className="bg-surface border border-outline-variant/20 rounded-3xl p-md hover:border-primary/30 hover:shadow-lg transition-all duration-300 cursor-pointer flex flex-col justify-between space-y-md group relative overflow-hidden"
                >
                  <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-xl pointer-events-none group-hover:scale-150 transition-all duration-300"></div>
                  
                  <div className="space-y-sm">
                    {/* Header: Date and Category */}
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-bold text-outline tracking-wider uppercase">
                        {new Date(report.created_at).toLocaleDateString(undefined, { 
                          month: 'short', 
                          day: 'numeric', 
                          year: 'numeric' 
                        })}
                      </span>
                      <span className={`text-[10px] font-black uppercase px-2.5 py-1 rounded-full border ${getSeverityColor(report.severity)}`}>
                        {translateSeverity(report.severity)}
                      </span>
                    </div>

                    {/* Scan image thumbnail & Category */}
                    <div className="flex items-center gap-sm">
                      <div className="w-12 h-12 rounded-xl bg-surface-container-high overflow-hidden flex items-center justify-center border border-outline-variant/20 relative">
                        <img 
                          src={resolveMediaUrl(report.file_path)} 
                          alt="Thumbnail" 
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            // If base64 exists, display it, else fallback icon
                            if (report.file_data) {
                              e.target.src = `data:${report.file_type};base64,${report.file_data}`;
                            } else {
                              e.target.style.display = 'none';
                            }
                          }}
                        />
                      </div>
                      <div>
                        <h3 className="font-bold text-on-surface text-body-md group-hover:text-primary transition-colors leading-tight">
                          {translateScanType(report.scan_type)}
                        </h3>
                        <p className="text-xs text-outline capitalize leading-none mt-1">
                          {translateSpecialist(report.recommended_specialist)}
                        </p>
                      </div>
                    </div>

                    {/* Findings Snippet */}
                    <p className="text-xs text-outline line-clamp-3 leading-relaxed">
                      {cleanFindings}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="border-t border-outline-variant/30 pt-sm flex items-center justify-between">
                    <span className="text-[11px] font-bold text-primary flex items-center gap-0.5 hover:translate-x-0.5 transition-transform">
                      {localT.viewReportBtn}
                      <span className="material-symbols-outlined text-[12px]">arrow_forward</span>
                    </span>
                    
                    <button
                      onClick={(e) => handleDelete(e, report.id)}
                      className="p-1 rounded-lg text-outline hover:text-error hover:bg-error/5 transition-all"
                      title={localT.deleteBtn}
                    >
                      <span className="material-symbols-outlined text-[18px]">delete</span>
                    </button>
                  </div>

                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modal Dialog for Diagnostic Detail */}
      {showModal && activeReport && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] animate-in fade-in duration-200">
          <div className="bg-surface-container-lowest border border-outline-variant/30 rounded-3xl p-lg w-full max-w-2xl max-h-[85vh] overflow-y-auto shadow-2xl flex flex-col space-y-md scale-in">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-outline-variant/30 pb-sm">
              <div>
                <span className="text-[10px] bg-primary/10 text-primary border border-primary/20 px-2.5 py-0.5 rounded-full font-black uppercase tracking-wider">
                  {translateScanType(activeReport.scan_type)}
                </span>
                <h3 className="text-title-lg font-black text-on-surface mt-1">
                  {localT.resultsTitle}
                </h3>
              </div>
              <button 
                onClick={() => setShowModal(false)}
                className="w-10 h-10 rounded-full bg-surface-container-high hover:bg-surface-container-highest text-on-surface flex items-center justify-center transition-colors"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            {/* Modal Content */}
            <div className="space-y-md">
              {/* Image Preview & Severity */}
              <div className="grid grid-cols-1 md:grid-cols-12 gap-md">
                <div className="md:col-span-5 bg-surface-container-high rounded-2xl overflow-hidden flex items-center justify-center border border-outline-variant/20 max-h-[200px]">
                  <img 
                    src={resolveMediaUrl(activeReport.file_path)} 
                    alt="Diagnostic Scan" 
                    className="w-full h-full object-contain"
                    onError={(e) => {
                      if (activeReport.file_data) {
                        e.target.src = `data:${activeReport.file_type};base64,${activeReport.file_data}`;
                      }
                    }}
                  />
                </div>
                
                <div className="md:col-span-7 flex flex-col justify-center space-y-sm">
                  <div>
                    <span className="text-label-sm font-bold text-outline uppercase tracking-wider">{localT.severity}</span>
                    <div className="mt-1">
                      <span className={`text-xs font-black uppercase px-3 py-1.5 rounded-full border ${getSeverityColor(activeReport.severity)}`}>
                        {translateSeverity(activeReport.severity)}
                      </span>
                    </div>
                  </div>

                  <div>
                    <span className="text-label-sm font-bold text-outline uppercase tracking-wider">{localT.specialist}</span>
                    <div className="flex items-center gap-xs text-primary font-extrabold capitalize text-body-md mt-1">
                      <span className="material-symbols-outlined text-[18px]">medical_services</span>
                      <span>{translateSpecialist(activeReport.recommended_specialist)}</span>
                    </div>
                  </div>

                  <p className="text-[10px] text-outline italic">
                    {localT.date}: {new Date(activeReport.created_at).toLocaleString()}
                  </p>
                </div>
              </div>

              {/* Findings text */}
              <div className="space-y-xs bg-surface-container-low border border-outline-variant/30 rounded-2xl p-md">
                <h4 className="text-label-md font-extrabold text-on-surface uppercase tracking-wide">
                  {localT.findings}
                </h4>
                <div className="text-body-sm text-on-surface-variant leading-relaxed whitespace-pre-wrap">
                  {activeReport.findings ? activeReport.findings.split('[Diagnostic')[0].trim() : ''}
                </div>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="border-t border-outline-variant/30 pt-md flex flex-col sm:flex-row items-center gap-sm justify-between">
              <button
                type="button"
                onClick={(e) => handleDelete(e, activeReport.id)}
                className="w-full sm:w-auto text-error font-bold text-label-md py-2.5 px-4 rounded-xl hover:bg-error/5 transition-colors flex items-center justify-center gap-xs"
              >
                <span className="material-symbols-outlined text-[18px]">delete</span>
                <span>{localT.deleteBtn}</span>
              </button>

              <div className="flex items-center gap-sm w-full sm:w-auto">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="w-full sm:w-auto text-outline font-bold text-label-md py-2.5 px-5 rounded-xl border border-outline-variant/40 hover:bg-surface-container-high transition-colors"
                >
                  {localT.closeBtn}
                </button>
                <button
                  type="button"
                  onClick={() => handleBookRedirect(activeReport.recommended_specialist)}
                  className="w-full sm:w-auto bg-primary text-on-primary font-bold text-label-md py-2.5 px-5 rounded-xl hover:bg-primary/95 transition-all flex items-center justify-center gap-xs shadow-md active:scale-95"
                >
                  <span className="material-symbols-outlined text-[18px]">event</span>
                  <span>{localT.bookBtn}</span>
                </button>
              </div>
            </div>

          </div>
        </div>
      )}

      {/* Global CSS for laser scanning line animation */}
      <style>{`
        @keyframes scanLaserAnimation {
          0% { top: 0%; opacity: 0.8; }
          50% { top: 98%; opacity: 1; }
          100% { top: 0%; opacity: 0.8; }
        }
      `}</style>
    </div>
  );
}
