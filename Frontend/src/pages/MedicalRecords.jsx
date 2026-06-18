import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useLanguage } from '../context/LanguageContext';

export default function MedicalRecords() {
  const { t } = useLanguage();
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [error, setError] = useState('');
  const [fileToUpload, setFileToUpload] = useState(null);

  const [selectedRecord, setSelectedRecord] = useState(null);
  const [showInsightsModal, setShowInsightsModal] = useState(false);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisError, setAnalysisError] = useState('');

  const loadRecords = async () => {
    try {
      const data = await api.getRecords();
      setRecords(data);
    } catch (err) {
      console.error(err);
      setError("Failed to fetch medical documents.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRecords();
  }, []);

  const handleFileChange = (e) => {
    setFileToUpload(e.target.files[0]);
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!fileToUpload) {
      alert("Please choose a file to upload first.");
      return;
    }

    setUploadLoading(true);
    setError('');
    
    try {
      const formData = new FormData();
      formData.append('file', fileToUpload);
      const res = await api.uploadRecord(formData);
      setFileToUpload(null);
      
      // Reset input element
      const fileInput = document.getElementById('record-file-input');
      if (fileInput) fileInput.value = '';

      // Speech notification dispatch
      const scanStatus = res.fraud_status || 'VERIFIED (Authentic)';
      const speakText = scanStatus.includes('FLAGGED')
        ? `Alert. TARS scan complete. The uploaded report, ${fileToUpload.name}, has been flagged for potential document tampering.`
        : `TARS scan complete. The uploaded report, ${fileToUpload.name}, has been verified as authentic.`;
      
      window.dispatchEvent(new CustomEvent('tars_speak', { detail: { text: speakText } }));

      // Reload
      loadRecords();
    } catch (err) {
      console.error(err);
      setError("File upload failed: " + err.message);
    } finally {
      setUploadLoading(false);
    }
  };

  const handleAnalyzeRecord = async (record) => {
    setSelectedRecord(record);
    setShowInsightsModal(true);
    setInsightsLoading(true);
    setAnalysisResult(null);
    setAnalysisError('');
    
    try {
      const data = await api.analyzeRecord(record.id);
      setAnalysisResult(data);
    } catch (err) {
      console.error(err);
      setAnalysisError(err.message || "Failed to analyze document. Ensure your GROQ_API_KEY is configured.");
    } finally {
      setInsightsLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-xl animate-pulse">
        <div className="h-12 bg-surface-container rounded-xl w-1/3"></div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
          <div className="lg:col-span-2 space-y-md">
            <div className="h-96 bg-surface-container rounded-xl"></div>
          </div>
          <div className="h-48 bg-surface-container rounded-xl"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-xl animate-in fade-in duration-300">
      <header>
        <h2 className="text-on-surface font-headline-lg text-headline-lg">
          {t('records')}
        </h2>
        <p className="text-on-surface-variant font-body-md text-body-md">Store, organize, and view your diagnostic reports and medical files with secure backup.</p>
      </header>

      {error && (
        <div className="p-4 bg-error-container text-on-error-container rounded-xl flex items-center gap-sm">
          <span className="material-symbols-outlined">error</span>
          <p>{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        {/* Left: Files List */}
        <div className="lg:col-span-2 space-y-lg">
          <div className="bg-white border border-outline-variant/30 rounded-2xl p-lg shadow-sm interactive-card">
            <h3 className="text-title-md font-bold text-primary mb-md flex items-center gap-xs">
              <span className="material-symbols-outlined text-secondary">folder_open</span>
              Your Uploaded Records
            </h3>

            {records.length === 0 ? (
              <div className="p-xl border border-dashed border-outline-variant rounded-xl text-center text-outline bg-surface">
                <span className="material-symbols-outlined text-4xl mb-xs">cloud_off</span>
                <p className="text-sm font-semibold">No medical records uploaded yet.</p>
                <p className="text-xs">Select a file on the right side panel to upload your first report.</p>
              </div>
            ) : (
              <div className="divide-y divide-outline-variant/20">
                {records.map(record => (
                  <div key={record.id} className="py-md flex flex-col sm:flex-row justify-between items-start sm:items-center gap-md hover:bg-surface-container-low/20 transition-colors px-2 rounded-lg">
                    <div className="flex gap-md items-start">
                      <div className="w-10 h-10 rounded-lg bg-secondary-container text-on-secondary-container flex items-center justify-center shrink-0">
                        <span className="material-symbols-outlined text-[20px]">
                          {record.file_type.includes('pdf') ? 'picture_as_pdf' : 'image'}
                        </span>
                      </div>
                      <div>
                        <h4 className="font-bold text-on-surface text-sm max-w-sm truncate">{record.file_name}</h4>
                        <p className="text-xs text-outline">{record.file_type} | Uploaded: {new Date(record.uploaded_at).toLocaleDateString()}</p>
                        <div className="flex items-center gap-xs mt-1">
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            record.fraud_status?.includes('VERIFIED') ? 'bg-emerald-500' : 'bg-error animate-pulse'
                          }`}></span>
                          <span className={`text-[10px] font-bold ${
                            record.fraud_status?.includes('VERIFIED') ? 'text-emerald-600' : 'text-error'
                          }`}>
                            🛡️ Scan: {record.fraud_status || 'VERIFIED (Authentic)'}
                          </span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex flex-wrap items-center gap-xs">
                      {record.fraud_status?.includes('VERIFIED') && (
                        <button
                          onClick={() => handleAnalyzeRecord(record)}
                          className="px-3.5 py-1.5 bg-primary hover:bg-primary/95 text-on-primary font-bold text-xs rounded-lg transition-colors flex items-center gap-xs shadow-sm"
                        >
                          <span className="material-symbols-outlined text-[16px]">psychology</span>
                          AI Insights
                        </button>
                      )}

                      <a 
                        href={record.file_path} 
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-3.5 py-1.5 bg-secondary hover:bg-secondary/95 text-white font-bold text-xs rounded-lg transition-colors flex items-center gap-xs shadow-sm"
                      >
                        <span className="material-symbols-outlined text-[16px]">visibility</span>
                        View File
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Upload Panel */}
        <div className="space-y-lg">
          <div className="bg-white border border-outline-variant/30 rounded-2xl p-lg shadow-sm interactive-card">
            <h3 className="text-title-md font-bold text-primary mb-md flex items-center gap-xs">
              <span className="material-symbols-outlined text-secondary">cloud_upload</span>
              Upload Document
            </h3>

            <form onSubmit={handleUploadSubmit} className="space-y-md">
              <div className="border border-dashed border-outline-variant rounded-xl p-md bg-surface text-center flex flex-col items-center justify-center min-h-[140px] relative">
                <span className="material-symbols-outlined text-4xl text-outline mb-sm">file_upload</span>
                <span className="text-xs font-semibold text-primary mb-xs">Select PDF or Image file</span>
                <span className="text-[10px] text-outline">Max size: 10MB</span>
                <input 
                  id="record-file-input"
                  required
                  type="file" 
                  accept=".pdf,image/*"
                  onChange={handleFileChange}
                  className="absolute inset-0 opacity-0 cursor-pointer"
                />
              </div>

              {fileToUpload && (
                <div className="p-sm bg-secondary-container/45 text-on-secondary-container text-xs rounded-lg font-bold flex items-center gap-sm">
                  <span className="material-symbols-outlined text-[18px]">attachment</span>
                  <span className="truncate">{fileToUpload.name}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={uploadLoading}
                className="w-full py-3 bg-primary hover:bg-primary/95 text-white font-bold rounded-lg transition-colors flex items-center justify-center gap-xs focus:outline-none shadow-md"
              >
                {uploadLoading ? (
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  <>
                    <span className="material-symbols-outlined">upload</span>
                    Upload Report
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* AI Insights Modal */}
      {showInsightsModal && (
        <div className="fixed inset-0 bg-black/55 backdrop-blur-sm z-[100] flex justify-center items-center p-4">
          <div className="bg-white rounded-2xl border border-outline-variant shadow-2xl w-full max-w-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[85vh]">
            <div className="p-4 border-b border-outline-variant bg-surface flex justify-between items-center shrink-0">
              <div className="flex items-center gap-xs">
                <span className="material-symbols-outlined text-primary">psychology</span>
                <div>
                  <h3 className="font-bold text-primary text-sm">TARS Clinical AI Insights</h3>
                  <p className="text-[10px] text-outline">Analyzing: {selectedRecord?.file_name}</p>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => setShowInsightsModal(false)}
                className="p-1 hover:bg-surface-container-high rounded-full transition-colors text-outline focus:outline-none"
              >
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto space-y-lg flex-1">
              {insightsLoading ? (
                <div className="flex flex-col justify-center items-center py-xl space-y-md text-outline">
                  <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
                  <p className="text-xs font-semibold animate-pulse text-primary">TARS is reading your report and consulting medical models...</p>
                </div>
              ) : analysisError ? (
                <div className="p-4 bg-error-container text-on-error-container rounded-xl flex items-center gap-sm">
                  <span className="material-symbols-outlined">error</span>
                  <p className="text-xs">{analysisError}</p>
                </div>
              ) : analysisResult ? (
                <div className="space-y-lg text-left">
                  {/* Clinical Insights */}
                  <div className="space-y-xs">
                    <h4 className="text-xs font-bold text-primary flex items-center gap-2xs uppercase tracking-wider">
                      <span className="material-symbols-outlined text-md">analytics</span>
                      Clinical Findings & Conditions
                    </h4>
                    <div className="p-4 bg-surface-container-low border border-outline-variant/40 rounded-xl">
                      <p className="text-xs leading-relaxed text-on-surface whitespace-pre-wrap">{analysisResult.insights}</p>
                    </div>
                  </div>

                  {/* Suggested Medications */}
                  <div className="space-y-xs">
                    <h4 className="text-xs font-bold text-secondary flex items-center gap-2xs uppercase tracking-wider">
                      <span className="material-symbols-outlined text-md">medication</span>
                      Suggested Medications
                    </h4>
                    <div className="p-4 bg-surface-container-low border border-outline-variant/40 rounded-xl">
                      <p className="text-xs leading-relaxed text-on-surface whitespace-pre-wrap">{analysisResult.medications}</p>
                    </div>
                  </div>

                  {/* Disclaimer */}
                  <div className="p-4 bg-error-container/20 border border-error/20 rounded-xl flex gap-xs items-start">
                    <span className="material-symbols-outlined text-error text-md mt-[2px]">warning</span>
                    <p className="text-[10px] text-error font-semibold leading-normal">{analysisResult.disclaimer}</p>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-outline text-center">No analysis data available.</p>
              )}
            </div>
            
            <div className="p-4 border-t border-outline-variant/50 bg-surface flex justify-end shrink-0">
              <button 
                type="button"
                onClick={() => setShowInsightsModal(false)}
                className="px-5 py-2 bg-primary hover:bg-primary/95 text-on-primary font-bold text-xs rounded-xl hover:shadow-md active:scale-95 transition-all focus:outline-none"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
