import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { applyTheme } from '../utils/theme';
import { resolveMediaUrl } from '../utils/apiConfig';
import { useAuth } from '../context/AuthContext';

export default function Settings() {
  const { user, checkAuth } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saveLoading, setSaveLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  // Editable fields for patient
  const [name, setName] = useState('');
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState('Male');
  const [height, setHeight] = useState('');
  const [weight, setWeight] = useState('');
  const [allergies, setAllergies] = useState('');
  const [conditions, setConditions] = useState('');
  const [address, setAddress] = useState('');
  
  // Editable fields for doctor
  const [specialization, setSpecialization] = useState('General Medicine');
  const [customSpecialization, setCustomSpecialization] = useState('');
  const [experience, setExperience] = useState('');
  const [location, setLocation] = useState('');
  const [contact, setContact] = useState('');
  const [licenseNumber, setLicenseNumber] = useState('');
  const [licenseDocument, setLicenseDocument] = useState(null);
  const [profilePicture, setProfilePicture] = useState(null);
  const [existingLicensePath, setExistingLicensePath] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [gpsLoading, setGpsLoading] = useState(false);

  const [mapLoaded, setMapLoaded] = useState(false);
  const mapRef = React.useRef(null);
  const markerRef = React.useRef(null);

  useEffect(() => {
    if (window.L) {
      setMapLoaded(true);
      return;
    }
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(link);

    const script = document.createElement('script');
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.async = true;
    script.onload = () => {
      setMapLoaded(true);
    };
    document.body.appendChild(script);
  }, []);

  useEffect(() => {
    if (!mapLoaded || !window.L) return;

    const defaultLat = parseFloat(latitude) || 12.9716;
    const defaultLng = parseFloat(longitude) || 77.5946;

    const container = document.getElementById('doctor-map');
    if (!container) return;

    if (!mapRef.current) {
      const map = window.L.map('doctor-map').setView([defaultLat, defaultLng], 13);
      window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map);

      const marker = window.L.marker([defaultLat, defaultLng], { draggable: true }).addTo(map);

      marker.on('dragend', () => {
        const position = marker.getLatLng();
        setLatitude(position.lat.toFixed(6));
        setLongitude(position.lng.toFixed(6));
      });

      mapRef.current = map;
      markerRef.current = marker;
    } else {
      const latNum = parseFloat(latitude);
      const lngNum = parseFloat(longitude);
      if (!isNaN(latNum) && !isNaN(lngNum)) {
        const currentLatLng = markerRef.current.getLatLng();
        if (Math.abs(currentLatLng.lat - latNum) > 0.0001 || Math.abs(currentLatLng.lng - lngNum) > 0.0001) {
          mapRef.current.setView([latNum, lngNum], 13);
          markerRef.current.setLatLng([latNum, lngNum]);
        }
      }
    }
  }, [mapLoaded, latitude, longitude]);

  useEffect(() => {
    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        markerRef.current = null;
      }
    };
  }, []);

  // Admin Request States
  const [adminRequestLoading, setAdminRequestLoading] = useState(false);
  const [adminRequestSuccess, setAdminRequestSuccess] = useState(false);
  const [adminRequestError, setAdminRequestError] = useState('');

  // Theme Swatch States
  const [currentTheme, setCurrentTheme] = useState(() => {
    return localStorage.getItem('theme') || 'light';
  });

  const [customColors, setCustomColors] = useState(() => {
    try {
      const saved = localStorage.getItem('custom_theme_colors');
      return saved ? JSON.parse(saved) : {
        primary: '#5c60f5',
        secondary: '#0ea5e9',
        background: '#f8fafc',
        surface: '#ffffff'
      };
    } catch (e) {
      return {
        primary: '#5c60f5',
        secondary: '#0ea5e9',
        background: '#f8fafc',
        surface: '#ffffff'
      };
    }
  });

  // Curated color swatches for Theme Design Studio
  const primarySwatches = ['#5c60f5', '#0d9488', '#8b5cf6', '#f43f5e', '#ec4899', '#10b981', '#06b6d4', '#f97316', '#6366f1', '#15803d'];
  const secondarySwatches = ['#0ea5e9', '#d946ef', '#14b8a6', '#f59e0b', '#fda4af', '#22c55e', '#4f46e5', '#dc2626', '#a855f7', '#eab308'];
  const backgroundSwatches = ['#f8fafc', '#f0fdfa', '#faf5ff', '#fff5f5', '#f0f9ff', '#f0fdf4', '#090916', '#121212', '#fdf6e2', '#0f172a'];
  const surfaceSwatches = ['#ffffff', '#f1f5f9', '#fafaf9', '#e6fffa', '#ffeef0', '#111024', '#1a1a2e', '#1e1e1e', '#eefdf6', '#1e293b'];

  useEffect(() => {
    const handleThemeChange = () => {
      setCurrentTheme(localStorage.getItem('theme') || 'light');
      try {
        const saved = localStorage.getItem('custom_theme_colors');
        if (saved) setCustomColors(JSON.parse(saved));
      } catch (e) {
        console.error(e);
      }
    };
    window.addEventListener('theme_change', handleThemeChange);
    return () => {
      window.removeEventListener('theme_change', handleThemeChange);
    };
  }, []);

  const handleThemeSelect = (themeName) => {
    setCurrentTheme(themeName);
    localStorage.setItem('theme', themeName);
    applyTheme(themeName);
    window.dispatchEvent(new Event('theme_change'));
  };

  const handleCustomColorChange = (key, value) => {
    const updated = { ...customColors, [key]: value };
    setCustomColors(updated);
    if (localStorage.getItem('theme') === 'custom') {
      localStorage.setItem('custom_theme_colors', JSON.stringify(updated));
      applyTheme('custom');
      window.dispatchEvent(new Event('theme_change'));
    }
  };

  const handleApplyCustomTheme = () => {
    localStorage.setItem('custom_theme_colors', JSON.stringify(customColors));
    handleThemeSelect('custom');
  };


  const handleRequestAdmin = async () => {
    setAdminRequestLoading(true);
    setAdminRequestError('');
    setAdminRequestSuccess(false);
    try {
      await api.requestAdmin();
      setAdminRequestSuccess(true);
      await checkAuth();
    } catch (err) {
      console.error(err);
      setAdminRequestError(err.message || 'Failed to submit promotion request.');
    } finally {
      setAdminRequestLoading(false);
    }
  };

  const loadProfile = async () => {
    if (!user) return;
    setLoading(true);
    try {
      if (user.role === 'patient') {
        const data = await api.getProfile();
        setName(data.name || '');
        setDob(data.date_of_birth || '');
        setGender(data.gender || 'Male');
        setHeight(data.height || '');
        setWeight(data.weight || '');
        setAllergies(data.allergies || '');
        setConditions(data.existing_conditions || '');
        setAddress(data.address || '');
      } else if (user.role === 'doctor') {
        const docs = await api.getDoctors();
        const doc = docs.find(d => d.user_id === user.id);
        if (doc) {
          setName(doc.name || '');
          const knownSpecs = ["Cardiology", "Dermatology", "General Medicine", "Neurology", "Pediatrics"];
          if (doc.specialization && knownSpecs.includes(doc.specialization)) {
            setSpecialization(doc.specialization);
            setCustomSpecialization('');
          } else {
            setSpecialization('Other');
            setCustomSpecialization(doc.specialization || '');
          }
          setExperience(doc.experience_years || '');
          setLocation(doc.location || '');
          setAddress(doc.address || '');
          setContact(doc.contact || '');
          setLicenseNumber(doc.license_number || '');
          setExistingLicensePath(doc.license_document_path || '');
          setLatitude(doc.latitude !== undefined && doc.latitude !== null ? doc.latitude.toString() : '');
          setLongitude(doc.longitude !== undefined && doc.longitude !== null ? doc.longitude.toString() : '');
        }
      } else if (user.role === 'admin') {
        try {
          const data = await api.getProfile();
          setName(data.name || '');
          setAddress(data.address || '');
        } catch (err) {
          setName('');
          setAddress('');
        }
      }
    } catch (err) {
      console.error(err);
      setError("Failed to load profile settings.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, [user]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess(false);
    setSaveLoading(true);

    try {
      if (user.role === 'patient') {
        // Patient Profile Create / Update
        try {
          await api.getProfile();
          // Exists -> Update
          await api.updateProfile({
            name,
            date_of_birth: dob,
            gender,
            height: height ? parseFloat(height) : null,
            weight: weight ? parseFloat(weight) : null,
            allergies,
            existing_conditions: conditions,
            address
          });
        } catch (err) {
          // Doesn't exist -> Create
          await api.createProfile({
            name,
            date_of_birth: dob,
            gender,
            height: height ? parseFloat(height) : null,
            weight: weight ? parseFloat(weight) : null,
            allergies,
            existing_conditions: conditions,
            address
          });
        }
      } else if (user.role === 'doctor') {
        const formData = new FormData();
        formData.append('name', name);
        formData.append('specialization', specialization === 'Other' ? customSpecialization : specialization);
        formData.append('location', location);
        formData.append('experience_years', experience);
        formData.append('contact', contact || user.email);
        formData.append('address', address);
        formData.append('license_number', licenseNumber);
        if (licenseDocument) {
          formData.append('license_document', licenseDocument);
        }
        if (profilePicture) {
          formData.append('profile_picture', profilePicture);
        }
        if (latitude) {
          formData.append('latitude', latitude);
        }
        if (longitude) {
          formData.append('longitude', longitude);
        }
        
        await api.updateDoctorProfile(formData);
        
        // Reset file inputs
        setLicenseDocument(null);
        setProfilePicture(null);
        const licenseInput = document.getElementById('settings-license-input');
        const picInput = document.getElementById('settings-pic-input');
        if (licenseInput) licenseInput.value = '';
        if (picInput) picInput.value = '';
      } else if (user.role === 'admin') {
        try {
          await api.getProfile();
          await api.updateProfile({
            name,
            address
          });
        } catch (err) {
          await api.createProfile({
            name,
            address
          });
        }
      }
      
      setSuccess(true);
      await loadProfile();
      await checkAuth();
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error(err);
      setError("Failed to save settings: " + err.message);
    } finally {
      setSaveLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-xl animate-pulse">
        <div className="h-12 bg-surface-container rounded-xl w-1/3"></div>
        <div className="h-96 bg-surface-container rounded-xl"></div>
      </div>
    );
  }

  return (
    <div className="space-y-xl animate-in fade-in duration-300">
      <header>
        <h2 className="text-on-surface font-headline-lg text-headline-lg">
          Profile Settings
        </h2>
        <p className="text-on-surface-variant font-body-md text-body-md">Modify your personal settings, health attributes, and contact address details.</p>
      </header>

      {error && (
        <div className="p-4 bg-error-container text-on-error-container rounded-xl flex items-center gap-sm">
          <span className="material-symbols-outlined">error</span>
          <p>{error}</p>
        </div>
      )}

      {success && (
        <div className="p-4 bg-success/10 text-success rounded-xl flex items-center gap-sm font-bold text-sm">
          <span className="material-symbols-outlined">check_circle</span>
          <p>Profile details saved successfully!</p>
        </div>
      )}

      <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm overflow-hidden p-lg">
        <form onSubmit={handleSubmit} className="space-y-lg max-w-2xl">
          {user?.role === 'patient' && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Full Name</label>
                  <input 
                    required
                    type="text" 
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  />
                </div>
                
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Date of Birth</label>
                  <input 
                    type="date" 
                    value={dob}
                    onChange={(e) => setDob(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-md">
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Gender</label>
                  <select 
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm font-semibold"
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Height (cm)</label>
                  <input 
                    type="number" 
                    value={height}
                    onChange={(e) => setHeight(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                    placeholder="e.g. 172"
                  />
                </div>

                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Weight (kg)</label>
                  <input 
                    type="number" 
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                    placeholder="e.g. 65"
                  />
                </div>
              </div>

              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Allergies</label>
                <input 
                  type="text" 
                  value={allergies}
                  onChange={(e) => setAllergies(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  placeholder="e.g. Pollen, Penicillin"
                />
              </div>

              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Existing Medical Conditions</label>
                <textarea 
                  rows="2"
                  value={conditions}
                  onChange={(e) => setConditions(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  placeholder="e.g. Hypertension, Diabetes Type 2"
                />
              </div>

              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Home Address (Required for Emergency SOS Broadcasting)</label>
                <textarea 
                  required
                  rows="2"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  placeholder="e.g. 12 Park Avenue, Apartment 3B, New York"
                />
              </div>
            </>
          )}

          {user?.role === 'doctor' && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Full Name</label>
                  <input 
                    required
                    type="text" 
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  />
                </div>

                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Doctor ID / License Number *</label>
                  <input 
                    required
                    type="text" 
                    value={licenseNumber}
                    onChange={(e) => setLicenseNumber(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm font-semibold"
                  />
                </div>
              </div>
              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Clinic Location Room</label>
                <input 
                  required
                  type="text" 
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Specialization</label>
                  <select 
                    value={specialization}
                    onChange={(e) => setSpecialization(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm font-semibold"
                  >
                    <option value="Cardiology">Cardiology</option>
                    <option value="Dermatology">Dermatology</option>
                    <option value="General Medicine">General Medicine</option>
                    <option value="Neurology">Neurology</option>
                    <option value="Pediatrics">Pediatrics</option>
                    <option value="Other">Other (Specify below)</option>
                  </select>
                </div>
                
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Experience (Years)</label>
                  <input 
                    required
                    type="number" 
                    value={experience}
                    onChange={(e) => setExperience(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  />
                </div>
              </div>

              {specialization === 'Other' && (
                <div className="space-y-xs animate-in slide-in-from-top-4 duration-150">
                  <label className="text-xs font-bold text-primary ml-unit">Specify Specialization *</label>
                  <input 
                    required
                    type="text" 
                    value={customSpecialization}
                    onChange={(e) => setCustomSpecialization(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                    placeholder="e.g. Oncology, Psychiatry"
                  />
                </div>
              )}

              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Clinic Full Address</label>
                <textarea 
                  required
                  rows="3"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                />
              </div>

              {/* Clinic Coordinates selector */}
              <div className="space-y-xs border border-outline-variant/60 p-3 rounded-lg bg-surface-container-low">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold text-primary flex items-center gap-xs">
                    <span className="material-symbols-outlined text-[16px] text-secondary">pin_drop</span>
                    Clinic GPS Location (For emergency SOS routing)
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      if (!navigator.geolocation) {
                        alert("Geolocation not supported by browser.");
                        return;
                      }
                      setGpsLoading(true);
                      navigator.geolocation.getCurrentPosition(
                        (position) => {
                          setLatitude(position.coords.latitude.toFixed(6));
                          setLongitude(position.coords.longitude.toFixed(6));
                          setGpsLoading(false);
                        },
                        (err) => {
                          console.error(err);
                          alert("Could not detect GPS location automatically. Please enter coordinates manually.");
                          setGpsLoading(false);
                        }
                      );
                    }}
                    disabled={gpsLoading}
                    className="text-[10px] bg-secondary-container text-on-secondary-container px-2 py-1 rounded hover:bg-secondary-container/80 transition flex items-center gap-xs font-bold focus:outline-none"
                  >
                    {gpsLoading ? (
                      <span className="w-3.5 h-3.5 border border-primary border-t-transparent rounded-full animate-spin"></span>
                    ) : (
                      <>
                        <span className="material-symbols-outlined text-[12px]">my_location</span>
                        Get GPS Location
                      </>
                    )}
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-md pt-2">
                  <div className="space-y-xs">
                    <label className="text-[10px] font-bold text-outline uppercase">Latitude</label>
                    <input 
                      type="number"
                      step="any"
                      placeholder="e.g. 12.9716"
                      value={latitude}
                      onChange={(e) => setLatitude(e.target.value)}
                      className="w-full px-3 py-1.5 rounded border border-outline-variant bg-surface text-xs outline-none focus:border-secondary"
                    />
                  </div>
                  <div className="space-y-xs">
                    <label className="text-[10px] font-bold text-outline uppercase">Longitude</label>
                    <input 
                      type="number"
                      step="any"
                      placeholder="e.g. 77.5946"
                      value={longitude}
                      onChange={(e) => setLongitude(e.target.value)}
                      className="w-full px-3 py-1.5 rounded border border-outline-variant bg-surface text-xs outline-none focus:border-secondary"
                    />
                  </div>
                </div>
                <div id="doctor-map" className="border border-outline-variant/50 shadow-sm" style={{ height: '220px', width: '100%', borderRadius: '12px', marginTop: '12px', zIndex: 1 }} />
              </div>

              {/* Upload Documents and Photos */}
              <div className="space-y-md border border-dashed border-outline-variant p-4 rounded-xl bg-surface">
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary block">
                    Upload New Medical License Document (PDF/Image) *
                  </label>
                  <p className="text-[10px] text-outline mb-xs">
                    Uploading a new license resets your credentials verification back to pending.
                  </p>
                  <label className="flex items-center justify-between border border-outline-variant rounded-lg px-4 py-2.5 bg-surface hover:bg-surface-container-low cursor-pointer transition-colors text-xs text-on-surface-variant font-medium">
                    <span className="flex items-center gap-xs truncate max-w-[80%]">
                      <span className="material-symbols-outlined text-[18px] text-secondary">cloud_upload</span>
                      <span className="truncate">{licenseDocument ? licenseDocument.name : "Choose medical license..."}</span>
                    </span>
                    <span className="px-2.5 py-1 bg-secondary-container text-on-secondary-container rounded font-bold text-[10px] shrink-0">Browse</span>
                    <input 
                      id="settings-license-input"
                      type="file" 
                      accept=".pdf,image/*"
                      onChange={(e) => setLicenseDocument(e.target.files[0])}
                      className="hidden"
                    />
                  </label>
                  {existingLicensePath && (
                    <p className="text-[10px] text-secondary font-bold mt-1">
                      Current: <a href={resolveMediaUrl(existingLicensePath)} target="_blank" rel="noopener noreferrer" className="hover:underline">View Active License Document</a>
                    </p>
                  )}
                </div>

                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary block">Upload New Profile Photo</label>
                  <label className="flex items-center justify-between border border-outline-variant rounded-lg px-4 py-2.5 bg-surface hover:bg-surface-container-low cursor-pointer transition-colors text-xs text-on-surface-variant font-medium">
                    <span className="flex items-center gap-xs truncate max-w-[80%]">
                      <span className="material-symbols-outlined text-[18px] text-secondary">photo_camera</span>
                      <span className="truncate">{profilePicture ? profilePicture.name : "Choose profile photo..."}</span>
                    </span>
                    <span className="px-2.5 py-1 bg-secondary-container text-on-secondary-container rounded font-bold text-[10px] shrink-0">Browse</span>
                    <input 
                      id="settings-pic-input"
                      type="file" 
                      accept="image/*"
                      onChange={(e) => setProfilePicture(e.target.files[0])}
                      className="hidden"
                    />
                  </label>
                </div>
              </div>
            </>
          )}

          {user?.role === 'admin' && (
            <>
              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Admin Full Name</label>
                <input 
                  required
                  type="text" 
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  placeholder="e.g. System Administrator"
                />
              </div>

              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Work / Office Address</label>
                <textarea 
                  required
                  rows="3"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  placeholder="e.g. Platform HQ Office, 5th Floor, Medical Center"
                />
              </div>
            </>
          )}

          <button
            type="submit"
            disabled={saveLoading}
            className="px-6 py-3 bg-primary hover:bg-primary/95 text-white font-bold rounded-lg transition-colors flex items-center gap-xs focus:outline-none shadow-md"
          >
            {saveLoading ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <>
                <span className="material-symbols-outlined">save</span>
                Save Profile
              </>
            )}
          </button>
        </form>
      </div>

      {user?.role !== 'admin' && user?.role !== 'patient' && !user?.has_admin_permission && (
        <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm overflow-hidden p-lg mt-xl">
          <h3 className="text-on-surface font-title-lg text-title-lg mb-xs">Elevate Account Privileges</h3>
          <p className="text-on-surface-variant font-body-md text-body-md mb-lg">
            Request promotion to an Administrator role. Administrators can manage users, check verification statuses, and review clinical logs. Requests must be approved by the system superadmin.
          </p>
          {user?.admin_requested ? (
            <div className="inline-flex items-center gap-sm px-4 py-2 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm font-semibold">
              <span className="material-symbols-outlined animate-pulse text-amber-600">pending</span>
              Promotion Request Pending Approval
            </div>
          ) : (
            <button
              type="button"
              onClick={handleRequestAdmin}
              disabled={adminRequestLoading}
              className="px-6 py-2.5 bg-secondary hover:bg-secondary/95 disabled:bg-outline-variant text-white font-bold rounded-lg transition-colors flex items-center gap-xs focus:outline-none shadow-md"
            >
              {adminRequestLoading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              ) : (
                <>
                  <span className="material-symbols-outlined">admin_panel_settings</span>
                  Request Admin Role Promotion
                </>
              )}
            </button>
          )}
          {adminRequestSuccess && (
            <p className="text-success text-xs font-bold mt-sm flex items-center gap-xs">
              <span className="material-symbols-outlined text-sm">check_circle</span>
              Promotion request sent successfully!
            </p>
          )}
          {adminRequestError && (
            <p className="text-error text-xs font-bold mt-sm flex items-center gap-xs">
              <span className="material-symbols-outlined text-sm">error</span>
              {adminRequestError}
            </p>
          )}
        </div>
      )}

      {/* Theme & Personalization Panel */}
      <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm overflow-hidden p-lg mt-xl interactive-card">
        <h3 className="text-on-surface font-title-lg text-title-lg mb-xs flex items-center gap-xs">
          <span className="material-symbols-outlined text-secondary">palette</span>
          Theme & Personalization
        </h3>
        <p className="text-on-surface-variant font-body-md text-body-md mb-lg">
          Select your preferred interface color palette. The settings will apply globally across all doctor, patient, and administration spaces.
        </p>

        <div className="grid grid-cols-2 sm:grid-cols-6 gap-md">
          {[
            { id: 'light', name: 'Classic Blue', primary: '#5c60f5', bg: '#f8fafc', desc: 'Soothing professional blue' },
            { id: 'dark', name: 'Midnight Navy', primary: '#818cf8', bg: '#090916', desc: 'Low-light dark mode' },
            { id: 'teal', name: 'Forest Teal', primary: '#0d9488', bg: '#f0fdfa', desc: 'Fresh clinical mint' },
            { id: 'purple', name: 'Royal Violet', primary: '#8b5cf6', bg: '#faf5ff', desc: 'Creative accent purple' },
            { id: 'rose', name: 'Warm Rose', primary: '#f43f5e', bg: '#fff5f5', desc: 'Warm comforting rose' },
            { id: 'custom', name: 'Custom Studio', primary: 'linear-gradient(to tr, #ec4899, #8b5cf6)', bg: '#f8fafc', desc: 'Design your own theme palette' }
          ].map((themeOpt) => {
            const isSelected = currentTheme === themeOpt.id;
            return (
              <button
                key={themeOpt.id}
                type="button"
                onClick={() => handleThemeSelect(themeOpt.id)}
                className={`p-md rounded-xl border text-left flex flex-col justify-between h-32 transition-all active:scale-[0.98] ${
                  isSelected 
                    ? 'border-primary bg-primary-container/20 ring-2 ring-primary/40' 
                    : 'border-outline-variant hover:border-secondary hover:bg-surface-container-low dark:hover:bg-white/5'
                }`}
              >
                <div className="flex justify-between items-start w-full">
                  <span className="w-6 h-6 rounded-full border border-white flex items-center justify-center" style={{ background: themeOpt.primary }}>
                    {isSelected && <span className="material-symbols-outlined text-[14px] text-white font-bold">check</span>}
                  </span>
                  <span className="w-8 h-4 rounded border border-outline-variant/30" style={{ backgroundColor: themeOpt.id === 'custom' ? customColors.background : themeOpt.bg }}></span>
                </div>
                <div>
                  <h4 className="font-bold text-xs text-on-surface dark:text-white">{themeOpt.name}</h4>
                  <p className="text-[9px] text-outline mt-0.5 leading-tight">{themeOpt.desc}</p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Custom Theme Design Studio */}
        {currentTheme === 'custom' && (
          <div className="mt-xl border-t border-outline-variant/20 pt-xl space-y-lg animate-in slide-in-from-top duration-300">
            <div className="flex items-center gap-xs mb-xs">
              <span className="material-symbols-outlined text-primary">design_services</span>
              <h4 className="text-on-surface font-bold text-sm">Theme Design Studio</h4>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-xl">
              {/* Left Side: Swatch grids */}
              <div className="md:col-span-2 space-y-md">
                {/* 1. Primary Color */}
                <div className="space-y-xs">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-outline font-bold uppercase tracking-wider">1. Brand Primary Color</span>
                    <input 
                      type="color" 
                      value={customColors.primary} 
                      onChange={(e) => handleCustomColorChange('primary', e.target.value)}
                      className="w-8 h-8 rounded-lg cursor-pointer border border-outline-variant bg-transparent focus:outline-none"
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {primarySwatches.map(color => (
                      <button 
                        key={color}
                        type="button"
                        onClick={() => handleCustomColorChange('primary', color)}
                        className={`w-6 h-6 rounded-full border transition-all hover:scale-110 active:scale-95 ${customColors.primary === color ? 'border-on-surface ring-2 ring-primary/40' : 'border-transparent'}`}
                        style={{ backgroundColor: color }}
                        title={color}
                      />
                    ))}
                  </div>
                </div>

                {/* 2. Secondary Color */}
                <div className="space-y-xs">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-outline font-bold uppercase tracking-wider">2. Secondary Accent Color</span>
                    <input 
                      type="color" 
                      value={customColors.secondary} 
                      onChange={(e) => handleCustomColorChange('secondary', e.target.value)}
                      className="w-8 h-8 rounded-lg cursor-pointer border border-outline-variant bg-transparent focus:outline-none"
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {secondarySwatches.map(color => (
                      <button 
                        key={color}
                        type="button"
                        onClick={() => handleCustomColorChange('secondary', color)}
                        className={`w-6 h-6 rounded-full border transition-all hover:scale-110 active:scale-95 ${customColors.secondary === color ? 'border-on-surface ring-2 ring-primary/40' : 'border-transparent'}`}
                        style={{ backgroundColor: color }}
                        title={color}
                      />
                    ))}
                  </div>
                </div>

                {/* 3. Background Color */}
                <div className="space-y-xs">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-outline font-bold uppercase tracking-wider">3. Portal Background Color</span>
                    <input 
                      type="color" 
                      value={customColors.background} 
                      onChange={(e) => handleCustomColorChange('background', e.target.value)}
                      className="w-8 h-8 rounded-lg cursor-pointer border border-outline-variant bg-transparent focus:outline-none"
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {backgroundSwatches.map(color => (
                      <button 
                        key={color}
                        type="button"
                        onClick={() => handleCustomColorChange('background', color)}
                        className={`w-6 h-6 rounded-full border transition-all hover:scale-110 active:scale-95 ${customColors.background === color ? 'border-on-surface ring-2 ring-primary/40' : 'border-transparent'}`}
                        style={{ backgroundColor: color }}
                        title={color}
                      />
                    ))}
                  </div>
                </div>

                {/* 4. Surface Color */}
                <div className="space-y-xs">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-outline font-bold uppercase tracking-wider">4. Dashboard Surface Color</span>
                    <input 
                      type="color" 
                      value={customColors.surface} 
                      onChange={(e) => handleCustomColorChange('surface', e.target.value)}
                      className="w-8 h-8 rounded-lg cursor-pointer border border-outline-variant bg-transparent focus:outline-none"
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {surfaceSwatches.map(color => (
                      <button 
                        key={color}
                        type="button"
                        onClick={() => handleCustomColorChange('surface', color)}
                        className={`w-6 h-6 rounded-full border transition-all hover:scale-110 active:scale-95 ${customColors.surface === color ? 'border-on-surface ring-2 ring-primary/40' : 'border-transparent'}`}
                        style={{ backgroundColor: color }}
                        title={color}
                      />
                    ))}
                  </div>
                </div>
              </div>

              {/* Right Side: Live preview block */}
              <div className="bg-surface-container-low border border-outline-variant/35 rounded-2xl p-lg flex flex-col justify-between h-full">
                <div className="space-y-md">
                  <span className="text-xs text-outline font-bold uppercase tracking-wider block">Live Palette Preview</span>
                  <div className="grid grid-cols-2 gap-sm">
                    <div className="p-sm rounded-lg border border-outline-variant/20 flex flex-col justify-between h-20" style={{ backgroundColor: customColors.surface }}>
                      <span className="text-[10px] text-outline font-bold">Surface Color</span>
                      <span className="text-xs font-bold font-mono" style={{ color: customColors.primary }}>{customColors.surface}</span>
                    </div>
                    <div className="p-sm rounded-lg border border-outline-variant/20 flex flex-col justify-between h-20" style={{ backgroundColor: customColors.background }}>
                      <span className="text-[10px] text-outline font-bold">Background Color</span>
                      <span className="text-xs font-bold font-mono" style={{ color: customColors.secondary }}>{customColors.background}</span>
                    </div>
                    <div className="p-sm rounded-lg border border-outline-variant/20 flex flex-col justify-between h-20" style={{ backgroundColor: customColors.primary }}>
                      <span className="text-[10px] text-white font-bold opacity-80">Primary Color</span>
                      <span className="text-xs font-bold font-mono text-white">{customColors.primary}</span>
                    </div>
                    <div className="p-sm rounded-lg border border-outline-variant/20 flex flex-col justify-between h-20" style={{ backgroundColor: customColors.secondary }}>
                      <span className="text-[10px] text-white font-bold opacity-80">Secondary Color</span>
                      <span className="text-xs font-bold font-mono text-white">{customColors.secondary}</span>
                    </div>
                  </div>
                  
                  <div className="p-md rounded-xl border border-outline-variant/20 bg-white dark:bg-[#111024]/40 mt-md space-y-xs">
                    <h5 className="font-bold text-xs" style={{ color: customColors.primary }}>Sample Dashboard Element</h5>
                    <p className="text-[10px] text-outline">Derived container styling and readable text overlays will dynamically adjust to your choice.</p>
                    <button 
                      type="button" 
                      className="mt-xs w-full py-1.5 rounded-lg font-bold text-[10px] text-white shadow-sm transition-transform active:scale-[0.97]"
                      style={{ backgroundColor: customColors.secondary }}
                    >
                      Sample Button
                    </button>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleApplyCustomTheme}
                  className="mt-lg w-full py-3 bg-primary hover:bg-primary/95 text-white font-bold text-xs rounded-xl shadow-md transition-transform active:scale-[0.98] focus:outline-none flex items-center justify-center gap-xs"
                >
                  <span className="material-symbols-outlined text-[18px]">palette</span>
                  Apply Custom Theme Settings
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
