import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../services/api';

export default function Register() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('patient'); // patient, doctor

  // Input refs for container-click focus shifting
  const emailRef = useRef(null);
  const passwordRef = useRef(null);
  const confirmPasswordRef = useRef(null);
  
  const docEmailRef = useRef(null);
  const docNameRef = useRef(null);
  const docPasswordRef = useRef(null);
  const docConfirmPasswordRef = useRef(null);
  const docLicenseRef = useRef(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  // Doctor profile fields
  const [doctorName, setDoctorName] = useState('');
  const [specialization, setSpecialization] = useState('General Medicine');
  const [customSpecialization, setCustomSpecialization] = useState('');
  const [location, setLocation] = useState('');
  const [experience, setExperience] = useState('');
  const [contact, setContact] = useState('');
  const [address, setAddress] = useState('');
  const [licenseNumber, setLicenseNumber] = useState('');
  const [licenseDocument, setLicenseDocument] = useState(null);
  const [profilePicture, setProfilePicture] = useState(null);
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

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handlePatientSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      await api.register(email, password, 'patient');
      // Redirect to OTP Verify
      navigate('/otp-verify', { state: { email } });
    } catch (err) {
      console.error(err);
      setError(err.message || "Registration failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleDoctorSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (!licenseDocument) {
      setError("Medical license board verification document is required.");
      return;
    }

    setLoading(true);
    try {
      // 1. Create user account
      await api.register(email, password, 'doctor');

      // 2. Temporarily log in to get access token to upload profile
      const loginData = await api.login(email, password);

      // 3. Prepare Multipart Form Data
      const formData = new FormData();
      formData.append('name', doctorName);
      formData.append('specialization', specialization === 'Other' ? customSpecialization : specialization);
      formData.append('location', location);
      formData.append('experience_years', experience);
      formData.append('contact', contact || email);
      formData.append('address', address);
      formData.append('license_number', licenseNumber);
      formData.append('license_document', licenseDocument);
      if (profilePicture) {
        formData.append('profile_picture', profilePicture);
      }
      if (latitude) {
        formData.append('latitude', latitude);
      }
      if (longitude) {
        formData.append('longitude', longitude);
      }

      // 4. Register doctor profile
      await api.registerDoctor(formData);

      // 5. Remove token from localStorage (they are registered, but must verify OTP first to use dashboard)
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user_role');
      localStorage.setItem('is_verified', 'false');

      // 6. Redirect to OTP Verify
      navigate('/otp-verify', { state: { email } });
    } catch (err) {
      console.error(err);
      setError(err.message || "Registration or file upload failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-background text-on-surface min-h-screen flex overflow-hidden">
      {/* Left Branding Section */}
      <section className="hidden lg:flex flex-col justify-between w-[45%] bg-primary relative overflow-hidden p-3xl">
        <div className="relative z-10">
          <div className="flex items-center gap-sm mb-xl">
            <span className="material-symbols-outlined text-primary-fixed-dim text-4xl" style={{ fontVariationSettings: "'FILL' 1" }}>health_and_safety</span>
            <h1 className="text-white font-headline-lg text-headline-lg tracking-tight">HealthAI</h1>
          </div>
          <div className="max-w-md">
            <h2 className="text-white font-display-lg text-4xl mb-md leading-tight">Join HealthAI.</h2>
            <p className="text-primary-fixed font-body-lg text-body-lg opacity-80 font-normal">Create an account to manage appointments, access clinical results, and collaborate with health professionals.</p>
          </div>
        </div>
        <div className="absolute bottom-0 right-0 w-full h-full -z-10 mix-blend-overlay">
          <div 
            className="w-full h-full bg-cover bg-center" 
            style={{ backgroundImage: "url('https://lh3.googleusercontent.com/aida-public/AB6AXuAneSzkINXhT4E7YNKfuaeuVDeXneIxWoDNJIyi1bvDS4EByUp5lDkaZgbYQBeqgfSApPp9bd13IGFMjlE0KPbWUJv8hRna3Nu_O-GwR3c4jQzi9Da9schzqvXixy7-Xcf3Flb7-UMSUsj9xanTMsh3kIULdy3MfnC8-_3Y-A43HAY81zeq64N5tVg7mQFXR9EWNoaE2qEX38_uT9vuhsenTzn-uSO1oGz9xsl5LHaDV2jHTpplKzsQGt2sW_0PICfkhnXJ1oOIUL0')" }}
          />
        </div>
      </section>

      {/* Right Registration Section */}
      <main className="w-full lg:w-[55%] h-screen overflow-y-auto p-margin-mobile md:p-2xl bg-surface-container-lowest flex flex-col items-center animate-in fade-in duration-300">
        <div className="w-full max-w-lg my-auto py-xl">
          <header className="mb-xl text-center lg:text-left">
            <h3 className="text-on-surface font-headline-lg text-headline-lg mb-xs">Create Account</h3>
            <p className="text-on-surface-variant font-body-md text-body-md">Get started by choosing your profile role.</p>
          </header>

          {/* Tabs */}
          <div className="flex p-unit bg-surface-container-high rounded-xl mb-xl">
            <button 
              onClick={() => { setActiveTab('patient'); setError(''); }}
              className={`flex-1 flex items-center justify-center gap-xs py-md rounded-lg transition-all duration-200 text-label-md font-label-md ${
                activeTab === 'patient' 
                  ? 'bg-secondary-container text-on-secondary-container shadow-sm' 
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[20px]">person</span>
              Patient Registration
            </button>
            <button 
              onClick={() => { setActiveTab('doctor'); setError(''); }}
              className={`flex-1 flex items-center justify-center gap-xs py-md rounded-lg transition-all duration-200 text-label-md font-label-md ${
                activeTab === 'doctor' 
                  ? 'bg-secondary-container text-on-secondary-container shadow-sm' 
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[20px]">medical_services</span>
              Doctor Onboarding
            </button>
          </div>

          {error && (
            <div className="p-4 bg-error-container text-on-error-container rounded-xl mb-xl flex items-center gap-sm">
              <span className="material-symbols-outlined">error</span>
              <p className="text-sm">{error}</p>
            </div>
          )}

          {activeTab === 'patient' ? (
            <form onSubmit={handlePatientSubmit} className="space-y-lg">
              <div className="space-y-xs">
                <label className="text-label-md font-label-md text-on-surface ml-unit">Email Address</label>
                <div className="relative cursor-text" onClick={() => emailRef.current?.focus()}>
                  <input 
                    ref={emailRef}
                    autoFocus
                    required
                    type="email" 
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none transition-all text-sm"
                    placeholder="patient@example.com"
                  />
                </div>
              </div>

              <div className="space-y-xs">
                <label className="text-label-md font-label-md text-on-surface ml-unit">Password</label>
                <div className="relative cursor-text" onClick={(e) => {
                  if (!e.target.closest('button')) {
                    passwordRef.current?.focus();
                  }
                }}>
                  <input 
                    ref={passwordRef}
                    required
                    type={showPassword ? "text" : "password"} 
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-4 pr-[44px] py-3 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none transition-all text-sm"
                    placeholder="Choose a strong password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-md top-1/2 -translate-y-1/2 text-outline hover:text-on-surface focus:outline-none flex items-center"
                  >
                    <span className="material-symbols-outlined text-lg select-none">
                      {showPassword ? "visibility_off" : "visibility"}
                    </span>
                  </button>
                </div>
              </div>

              <div className="space-y-xs">
                <label className="text-label-md font-label-md text-on-surface ml-unit">Confirm Password</label>
                <div className="relative cursor-text" onClick={(e) => {
                  if (!e.target.closest('button')) {
                    confirmPasswordRef.current?.focus();
                  }
                }}>
                  <input 
                    ref={confirmPasswordRef}
                    required
                    type={showConfirmPassword ? "text" : "password"} 
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full pl-4 pr-[44px] py-3 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none transition-all text-sm"
                    placeholder="Re-enter password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-md top-1/2 -translate-y-1/2 text-outline hover:text-on-surface focus:outline-none flex items-center"
                  >
                    <span className="material-symbols-outlined text-lg select-none">
                      {showConfirmPassword ? "visibility_off" : "visibility"}
                    </span>
                  </button>
                </div>
              </div>

              <button 
                type="submit" 
                disabled={loading}
                className="w-full py-3 bg-primary hover:bg-primary/95 text-white font-bold rounded-lg transition-colors flex items-center justify-center gap-xs focus:outline-none shadow-sm"
              >
                {loading ? (
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  <>
                    <span className="material-symbols-outlined">how_to_reg</span>
                    Register Account
                  </>
                )}
              </button>
            </form>
          ) : (
            <form onSubmit={handleDoctorSubmit} className="space-y-lg">
              {/* Auth Credentials */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div className="space-y-xs">
                  <label className="text-label-md font-label-md text-on-surface ml-unit">Email</label>
                  <div className="relative cursor-text" onClick={() => docEmailRef.current?.focus()}>
                    <input 
                      ref={docEmailRef}
                      autoFocus
                      required
                      type="email" 
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none text-xs"
                      placeholder="doctor@example.com"
                    />
                  </div>
                </div>
                <div className="space-y-xs">
                  <label className="text-label-md font-label-md text-on-surface ml-unit">Full Name (including Dr.)</label>
                  <div className="relative cursor-text" onClick={() => docNameRef.current?.focus()}>
                    <input 
                      ref={docNameRef}
                      required
                      type="text" 
                      value={doctorName}
                      onChange={(e) => setDoctorName(e.target.value)}
                      className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none text-xs"
                      placeholder="Dr. Elizabeth Blackwell"
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div className="space-y-xs">
                  <label className="text-label-md font-label-md text-on-surface ml-unit">Password</label>
                  <div className="relative cursor-text" onClick={(e) => {
                    if (!e.target.closest('button')) {
                      docPasswordRef.current?.focus();
                    }
                  }}>
                    <input 
                      ref={docPasswordRef}
                      required
                      type={showPassword ? "text" : "password"} 
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full pl-4 pr-[44px] py-2.5 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none text-xs"
                      placeholder="Password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-md top-1/2 -translate-y-1/2 text-outline hover:text-on-surface focus:outline-none flex items-center"
                    >
                      <span className="material-symbols-outlined text-lg select-none">
                        {showPassword ? "visibility_off" : "visibility"}
                      </span>
                    </button>
                  </div>
                </div>
                <div className="space-y-xs">
                  <label className="text-label-md font-label-md text-on-surface ml-unit">Confirm Password</label>
                  <div className="relative cursor-text" onClick={(e) => {
                    if (!e.target.closest('button')) {
                      docConfirmPasswordRef.current?.focus();
                    }
                  }}>
                    <input 
                      ref={docConfirmPasswordRef}
                      required
                      type={showConfirmPassword ? "text" : "password"} 
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="w-full pl-4 pr-[44px] py-2.5 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none text-xs"
                      placeholder="Confirm Password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-md top-1/2 -translate-y-1/2 text-outline hover:text-on-surface focus:outline-none flex items-center"
                    >
                      <span className="material-symbols-outlined text-lg select-none">
                        {showConfirmPassword ? "visibility_off" : "visibility"}
                      </span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Specialization & Experience */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div className="space-y-xs">
                  <label className="text-label-md font-label-md text-on-surface ml-unit">Specialization</label>
                  <select 
                    value={specialization}
                    onChange={(e) => setSpecialization(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none text-xs"
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
                  <label className="text-label-md font-label-md text-on-surface ml-unit">Experience (Years)</label>
                  <input 
                    required
                    type="number" 
                    value={experience}
                    onChange={(e) => setExperience(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none text-xs"
                    placeholder="e.g. 12"
                  />
                </div>
              </div>

              {specialization === 'Other' && (
                <div className="space-y-xs animate-in slide-in-from-top-4 duration-150">
                  <label className="text-label-md font-label-md text-on-surface ml-unit">Specify Specialization *</label>
                  <input 
                    required
                    type="text" 
                    value={customSpecialization}
                    onChange={(e) => setCustomSpecialization(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none text-xs"
                    placeholder="e.g. Oncology, Psychiatry"
                  />
                </div>
              )}

              <div className="space-y-xs">
                <label className="text-label-md font-label-md text-on-surface ml-unit">Clinic Location Room/Building</label>
                <input 
                  required
                  type="text" 
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none text-xs"
                  placeholder="e.g. Suite 402, Medical Arts Building"
                />
              </div>

              <div className="space-y-xs">
                <label className="text-label-md font-label-md text-on-surface ml-unit">Clinic Full Address</label>
                <textarea 
                  required
                  rows="2"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full px-4 py-2 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none text-xs"
                  placeholder="e.g. 123 Health Blvd, Metro City"
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

              <div className="space-y-xs">
                <label className="text-label-md font-label-md text-on-surface ml-unit">Medical License Number / Unique Doctor ID *</label>
                <div className="relative cursor-text" onClick={() => docLicenseRef.current?.focus()}>
                  <input 
                    ref={docLicenseRef}
                    required
                    type="text" 
                    value={licenseNumber}
                    onChange={(e) => setLicenseNumber(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none text-xs"
                    placeholder="e.g. MD-12345-AI"
                  />
                </div>
              </div>

              {/* Upload Documents */}
              <div className="space-y-md border border-dashed border-outline-variant p-4 rounded-xl bg-surface">
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary block">Upload Medical License (PDF/Image) *</label>
                  <label className="flex items-center justify-between border border-outline-variant rounded-lg px-4 py-2.5 bg-surface hover:bg-surface-container-low cursor-pointer transition-colors text-xs text-on-surface-variant font-medium">
                    <span className="flex items-center gap-xs truncate max-w-[80%]">
                      <span className="material-symbols-outlined text-[18px] text-secondary">cloud_upload</span>
                      <span className="truncate">{licenseDocument ? licenseDocument.name : "Choose medical license..."}</span>
                    </span>
                    <span className="px-2.5 py-1 bg-secondary-container text-on-secondary-container rounded font-bold text-[10px] shrink-0">Browse</span>
                    <input 
                      required
                      type="file" 
                      accept=".pdf,image/*"
                      onChange={(e) => setLicenseDocument(e.target.files[0])}
                      className="hidden"
                    />
                  </label>
                </div>

                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary block">Upload Profile Photo (Optional)</label>
                  <label className="flex items-center justify-between border border-outline-variant rounded-lg px-4 py-2.5 bg-surface hover:bg-surface-container-low cursor-pointer transition-colors text-xs text-on-surface-variant font-medium">
                    <span className="flex items-center gap-xs truncate max-w-[80%]">
                      <span className="material-symbols-outlined text-[18px] text-secondary">photo_camera</span>
                      <span className="truncate">{profilePicture ? profilePicture.name : "Choose profile photo..."}</span>
                    </span>
                    <span className="px-2.5 py-1 bg-secondary-container text-on-secondary-container rounded font-bold text-[10px] shrink-0">Browse</span>
                    <input 
                      type="file" 
                      accept="image/*"
                      onChange={(e) => setProfilePicture(e.target.files[0])}
                      className="hidden"
                    />
                  </label>
                </div>
              </div>

              <button 
                type="submit" 
                disabled={loading}
                className="w-full py-3 bg-secondary hover:bg-secondary/95 text-white font-bold rounded-lg transition-colors flex items-center justify-center gap-xs focus:outline-none shadow-sm"
              >
                {loading ? (
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  <>
                    <span className="material-symbols-outlined">verified_user</span>
                    Submit Doctor Application
                  </>
                )}
              </button>
            </form>
          )}

          <footer className="mt-xl text-center">
            <p className="text-body-md text-on-surface-variant">
              Already have an account?{' '}
              <Link to="/login" className="text-primary font-bold hover:underline">
                Sign In
              </Link>
            </p>
          </footer>
        </div>
      </main>
    </div>
  );
}
