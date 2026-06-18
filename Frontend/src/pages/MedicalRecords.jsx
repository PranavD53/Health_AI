import React, { useState, useEffect } from 'react';
import { api } from '../services/api';

export default function MedicalRecords() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [error, setError] = useState('');
  const [fileToUpload, setFileToUpload] = useState(null);

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
      await api.uploadRecord(formData);
      setFileToUpload(null);
      
      // Reset input element
      const fileInput = document.getElementById('record-file-input');
      if (fileInput) fileInput.value = '';

      // Reload
      loadRecords();
    } catch (err) {
      console.error(err);
      setError("File upload failed: " + err.message);
    } finally {
      setUploadLoading(false);
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
          Medical Records Management
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
                      </div>
                    </div>
                    
                    <a 
                      href={`http://127.0.0.1:8000${record.file_path}`} 
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3.5 py-1.5 bg-secondary hover:bg-secondary/95 text-white font-bold text-xs rounded-lg transition-colors flex items-center gap-xs shadow-sm"
                    >
                      <span className="material-symbols-outlined text-[16px]">visibility</span>
                      View File
                    </a>
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
    </div>
  );
}
